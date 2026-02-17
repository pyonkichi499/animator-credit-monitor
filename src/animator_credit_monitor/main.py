import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from animator_credit_monitor.history import HistoryManager
from animator_credit_monitor.notifier import ConsoleNotifier, EmailNotifier, LineNotifier, MultiNotifier, Notifier
from animator_credit_monitor.scraper import AniListScraper, BangumiScraper

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


def _parse_notifier_types() -> list[str]:
    raw_multi = os.environ.get("NOTIFIERS", "").strip()
    if raw_multi:
        return [v.strip().lower() for v in raw_multi.split(",") if v.strip()]

    raw_single = os.environ.get("NOTIFIER", "console").strip().lower()
    return [raw_single]


def _build_email_notifier_from_env() -> EmailNotifier:
    host = os.environ.get("SMTP_HOST", "").strip()
    port = os.environ.get("SMTP_PORT", "587").strip()
    from_addr = os.environ.get("SMTP_FROM", "").strip()
    to_addr = os.environ.get("SMTP_TO", "").strip()
    username = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    subject_template = os.environ.get("EMAIL_SUBJECT_TEMPLATE", "{title}")
    body_template = os.environ.get("EMAIL_BODY_TEMPLATE", "{message}")

    if not host or not from_addr or not to_addr:
        raise ValueError("SMTP_HOST, SMTP_FROM, SMTP_TO are required when using email notifier")

    try:
        port_num = int(port)
    except ValueError as e:
        raise ValueError("SMTP_PORT must be an integer") from e

    return EmailNotifier(
        host=host,
        port=port_num,
        from_addr=from_addr,
        to_addr=to_addr,
        username=username,
        password=password,
        use_tls=use_tls,
        subject_template=subject_template,
        body_template=body_template,
    )


def _build_line_notifier_from_env() -> LineNotifier:
    token = os.environ.get("LINE_NOTIFY_TOKEN", "").strip()
    api_url = os.environ.get("LINE_NOTIFY_API_URL", "https://notify-api.line.me/api/notify").strip()
    message_template = os.environ.get("LINE_MESSAGE_TEMPLATE", "{title}\n{message}")
    if not token:
        raise ValueError("LINE_NOTIFY_TOKEN is required when using line notifier")
    return LineNotifier(token=token, api_url=api_url, message_template=message_template)


def _build_notifier_from_env() -> Notifier:
    notifier_types = _parse_notifier_types()
    if not notifier_types:
        raise ValueError("NOTIFIERS is empty")

    notifiers: list[Notifier] = []
    for notifier_type in notifier_types:
        if notifier_type == "console":
            notifiers.append(ConsoleNotifier())
        elif notifier_type == "email":
            notifiers.append(_build_email_notifier_from_env())
        elif notifier_type == "line":
            notifiers.append(_build_line_notifier_from_env())
        else:
            raise ValueError("Notifier type must be one of: console, email, line")

    if len(notifiers) == 1:
        return notifiers[0]
    return MultiNotifier(notifiers)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Check for changes without saving state.")
@click.option("--bangumi-only", is_flag=True, help="Only check Bangumi.")
@click.option("--anilist-only", is_flag=True, help="Only check AniList.")
def check(dry_run: bool, bangumi_only: bool, anilist_only: bool) -> None:
    """Check for new animation credits."""
    setup_logging()

    bangumi_id = os.environ.get("TARGET_BANGUMI_ID", "")
    target_name = os.environ.get("TARGET_NAME", "")
    data_dir = os.environ.get("DATA_DIR", "data")

    if not bangumi_id and not target_name:
        click.echo("Error: TARGET_BANGUMI_ID or TARGET_NAME must be set in .env")
        sys.exit(1)

    if bangumi_only and not bangumi_id:
        click.echo("Error: TARGET_BANGUMI_ID must be set for --bangumi-only")
        sys.exit(1)

    if anilist_only and not target_name:
        click.echo("Error: TARGET_NAME must be set for --anilist-only")
        sys.exit(1)

    try:
        notifier = _build_notifier_from_env()
    except ValueError as e:
        click.echo(f"Error: {e}")
        sys.exit(1)

    history = HistoryManager(data_dir=Path(data_dir))
    found_new = False

    # Bangumi check
    if not anilist_only and bangumi_id:
        click.echo(f"Checking Bangumi (person ID: {bangumi_id})...")
        scraper = BangumiScraper()
        works = scraper.fetch_works(bangumi_id)

        if works:
            diff = history.detect_diff(f"bangumi_{bangumi_id}", works)
            if diff:
                found_new = True
                notifier.notify(
                    "新しいクレジット (Bangumi)",
                    _format_bangumi_diff(diff),
                )
            if not dry_run:
                history.save(f"bangumi_{bangumi_id}", works)
        else:
            click.echo("  No data retrieved from Bangumi.")

    # Name-based check (AniList direct)
    if not bangumi_only and target_name:
        click.echo(f"Checking AniList (name: {target_name})...")
        scraper_anilist = AniListScraper()
        results = scraper_anilist.fetch_works(target_name)

        if results:
            source_key = f"anilist_{target_name}"
            diff = history.detect_diff(source_key, results)
            if diff:
                found_new = True
                notifier.notify(
                    "新しいクレジット (AniList)",
                    _format_anilist_diff(diff),
                )
            if not dry_run:
                history.save(source_key, results)
        else:
            click.echo("  No data retrieved from AniList.")

    if not found_new:
        click.echo("No new credits found.")


def _format_bangumi_diff(diff: list[dict]) -> str:
    lines = [f"検知件数: {len(diff)}"]
    for i, item in enumerate(diff, start=1):
        title = item.get("title", "Unknown")
        role = item.get("role", "")
        info = item.get("info", "")
        line = f"{i}. {title}"
        if role:
            line += f" [{role}]"
        if info:
            line += f" ({info})"
        lines.append(line)
    return "\n".join(lines)


def _format_anilist_diff(diff: list[dict]) -> str:
    lines = [f"検知件数: {len(diff)}"]
    for i, item in enumerate(diff, start=1):
        title = item.get("title", "Unknown")
        role = item.get("role", "")
        date = item.get("date", "")
        line = f"{i}. {title}"
        if role:
            line += f" [{role}]"
        if date:
            line += f" ({date})"
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    cli()
