import logging
import os
import sys

import click
from dotenv import load_dotenv

from animator_credit_monitor.config import AppConfig, ConfigValidationError, load_app_config_from_env
from animator_credit_monitor.delivery import DeliveryDispatcher, DeliveryTarget, RetryPolicy
from animator_credit_monitor.firestore_store import (
    FirestoreDependencyError,
    FirestoreOutboxRepository,
    FirestoreRunRepository,
    FirestoreSnapshotRepository,
    build_collections,
    create_firestore_client,
)
from animator_credit_monitor.firestore_usecase import FirestoreOutboxMonitorUseCase, FirestoreRuntimeContext
from animator_credit_monitor.formatters import format_anilist_diff, format_bangumi_diff
from animator_credit_monitor.history import HistoryManager
from animator_credit_monitor.models import RunReport, SourcePlan
from animator_credit_monitor.notifier import ConsoleNotifier, EmailNotifier, MultiNotifier, Notifier
from animator_credit_monitor.scraper import AniListScraper, BangumiScraper
from animator_credit_monitor.usecase import MonitorUseCase

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@click.group()
def cli() -> None:
    """Animator Credit Monitor - detect new animation credits."""
    load_dotenv()


def _build_notifier(config: AppConfig) -> Notifier:
    notifiers = [target.notifier for target in _build_delivery_targets(config)]
    return notifiers[0] if len(notifiers) == 1 else MultiNotifier(notifiers)


def _build_delivery_targets(config: AppConfig) -> list[DeliveryTarget]:
    targets: list[DeliveryTarget] = []
    for notifier_type in config.notifier_types:
        if notifier_type == "console":
            targets.append(
                DeliveryTarget(
                    channel="console",
                    destination_key="stdout",
                    notifier=ConsoleNotifier(),
                )
            )
        elif notifier_type == "email":
            targets.append(
                DeliveryTarget(
                    channel="email",
                    destination_key=config.email.to_addr,
                    notifier=EmailNotifier(
                        host=config.email.host,
                        port=config.email.port,
                        from_addr=config.email.from_addr,
                        to_addr=config.email.to_addr,
                        username=config.email.username,
                        password=config.email.password,
                        use_tls=config.email.use_tls,
                        subject_template=config.email.subject_template,
                        body_template=config.email.body_template,
                    ),
                )
            )
        else:
            raise ValueError("Notifier type must be one of: console, email")
    return targets


def _build_source_plans(config: AppConfig, *, bangumi_only: bool, anilist_only: bool) -> list[SourcePlan]:
    plans: list[SourcePlan] = []

    if not anilist_only and config.bangumi_id:
        bangumi_id = config.bangumi_id
        bangumi = BangumiScraper()
        plans.append(
            SourcePlan(
                short_name="Bangumi",
                label=f"Bangumi (person ID: {bangumi_id})",
                source_key=f"bangumi_{bangumi_id}",
                notification_title="新しいクレジット (Bangumi)",
                fetch_credits=lambda: bangumi.fetch_works(bangumi_id),
                format_diff=format_bangumi_diff,
                source_type="bangumi",
                target_label=bangumi_id,
            )
        )

    if not bangumi_only and config.target_name:
        target_name = config.target_name
        anilist = AniListScraper()
        plans.append(
            SourcePlan(
                short_name="AniList",
                label=f"AniList (name: {target_name})",
                source_key=f"anilist_{target_name}",
                notification_title="新しいクレジット (AniList)",
                fetch_credits=lambda: anilist.fetch_works(target_name),
                format_diff=format_anilist_diff,
                source_type="anilist",
                target_label=target_name,
            )
        )

    return plans


def _validate_cli_inputs(config: AppConfig, bangumi_only: bool, anilist_only: bool) -> None:
    if bangumi_only and anilist_only:
        raise click.ClickException("--bangumi-only and --anilist-only cannot be used together")
    if not config.bangumi_id and not config.target_name:
        raise click.ClickException("TARGET_BANGUMI_ID or TARGET_NAME must be set in .env")
    if bangumi_only and not config.bangumi_id:
        raise click.ClickException("TARGET_BANGUMI_ID must be set for --bangumi-only")
    if anilist_only and not config.target_name:
        raise click.ClickException("TARGET_NAME must be set for --anilist-only")


def _render_run_report(report: RunReport) -> None:
    for result in report.source_results:
        if not result.had_data:
            click.echo(f"  No data retrieved from {result.plan.short_name}.")
        if result.notification_error:
            click.echo(f"  Notification failed ({result.plan.short_name}): {result.notification_error}")

    if not report.found_new:
        click.echo("No new credits found.")

    if getattr(report, "redelivery_processed", 0):
        click.echo(
            f"Redelivery summary: processed={report.redelivery_processed}, failed={report.redelivery_failed}"
        )

    click.echo(
        f"Run summary: checks={report.checks_run}, "
        f"sources_with_new_credits={report.sources_with_new_credits}, "
        f"status={'error' if report.had_errors else 'ok'}"
    )


def _run_monitor_local(config: AppConfig, *, dry_run: bool, bangumi_only: bool, anilist_only: bool) -> int:
    notifier = _build_notifier(config)
    history = HistoryManager(data_dir=config.data_dir)
    usecase = MonitorUseCase(history=history, notifier=notifier)
    plans = _build_source_plans(config, bangumi_only=bangumi_only, anilist_only=anilist_only)

    for plan in plans:
        click.echo(f"Checking {plan.label}...")

    report = usecase.run(plans, dry_run=dry_run)
    _render_run_report(report)
    return 1 if report.had_errors else 0


def _infer_trigger_type() -> str:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip().lower()
    if event_name in {"workflow_dispatch", "repository_dispatch"}:
        return "manual"
    if event_name:
        return "schedule"
    return "manual"


def _run_monitor_firestore(config: AppConfig, *, dry_run: bool, bangumi_only: bool, anilist_only: bool) -> int:
    client = create_firestore_client(config.gcp_project_id, config.firestore_database)
    collections = build_collections(config.firestore_collection_prefix)
    snapshots = FirestoreSnapshotRepository(client, collections)
    runs = FirestoreRunRepository(client, collections, ttl_days=30)
    outbox = FirestoreOutboxRepository(client, collections, ttl_days=30)
    dispatcher = DeliveryDispatcher(
        targets=_build_delivery_targets(config),
        retry_policy=RetryPolicy(
            max_retries=config.notify_retry_max_retries,
            initial_delay_seconds=config.notify_retry_initial_delay_seconds,
        ),
    )
    usecase = FirestoreOutboxMonitorUseCase(
        snapshots=snapshots,
        runs=runs,
        outbox=outbox,
        dispatcher=dispatcher,
        retry_policy=RetryPolicy(
            max_retries=config.notify_retry_max_retries,
            initial_delay_seconds=config.notify_retry_initial_delay_seconds,
        ),
    )
    plans = _build_source_plans(config, bangumi_only=bangumi_only, anilist_only=anilist_only)
    for plan in plans:
        click.echo(f"Checking {plan.label}...")

    report = usecase.run(
        plans,
        dry_run=dry_run,
        context=FirestoreRuntimeContext(runtime="github_actions", trigger_type=_infer_trigger_type()),
    )
    _render_run_report(report)
    return 1 if report.had_errors else 0


@cli.command()
@click.option("--dry-run", is_flag=True, help="Check for changes without saving state.")
@click.option("--bangumi-only", is_flag=True, help="Only check Bangumi.")
@click.option("--anilist-only", is_flag=True, help="Only check AniList.")
def check(dry_run: bool, bangumi_only: bool, anilist_only: bool) -> None:
    """Check for new animation credits."""
    setup_logging()

    try:
        config = load_app_config_from_env(dict(os.environ))
        _validate_cli_inputs(config, bangumi_only=bangumi_only, anilist_only=anilist_only)
    except (ConfigValidationError, ValueError) as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
    except click.ClickException as e:
        click.echo(f"Error: {e.message}")
        sys.exit(1)

    try:
        if config.state_backend == "firestore":
            code = _run_monitor_firestore(
                config,
                dry_run=dry_run,
                bangumi_only=bangumi_only,
                anilist_only=anilist_only,
            )
        else:
            code = _run_monitor_local(
                config,
                dry_run=dry_run,
                bangumi_only=bangumi_only,
                anilist_only=anilist_only,
            )
    except FirestoreDependencyError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)

    sys.exit(code)


if __name__ == "__main__":
    cli()
