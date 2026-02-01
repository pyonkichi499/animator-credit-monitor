import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from animator_credit_monitor.history import HistoryManager
from animator_credit_monitor.notifier import ConsoleNotifier
from animator_credit_monitor.scraper import BangumiScraper, SakugaWikiScraper

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


@cli.command()
@click.option("--dry-run", is_flag=True, help="Check for changes without saving state.")
@click.option("--bangumi-only", is_flag=True, help="Only check Bangumi.")
@click.option("--wiki-only", is_flag=True, help="Only check Sakuga@wiki.")
def check(dry_run: bool, bangumi_only: bool, wiki_only: bool) -> None:
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

    if wiki_only and not target_name:
        click.echo("Error: TARGET_NAME must be set for --wiki-only")
        sys.exit(1)

    history = HistoryManager(data_dir=Path(data_dir))
    notifier = ConsoleNotifier()
    found_new = False

    # Bangumi check
    if not wiki_only and bangumi_id:
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

    # Sakuga@wiki check
    if not bangumi_only and target_name:
        click.echo(f"Checking Sakuga@wiki (name: {target_name})...")
        scraper_wiki = SakugaWikiScraper()
        results = scraper_wiki.search(target_name)

        if results:
            diff = history.detect_diff(f"sakugawiki_{target_name}", results)
            if diff:
                found_new = True
                notifier.notify(
                    "新しいクレジット (作画@wiki)",
                    _format_wiki_diff(diff),
                )
            if not dry_run:
                history.save(f"sakugawiki_{target_name}", results)
        else:
            click.echo("  No data retrieved from Sakuga@wiki.")

    if not found_new:
        click.echo("No new credits found.")


def _format_bangumi_diff(diff: list[dict]) -> str:
    lines = []
    for item in diff:
        title = item.get("title", "Unknown")
        role = item.get("role", "")
        info = item.get("info", "")
        line = f"  - {title}"
        if role:
            line += f" [{role}]"
        if info:
            line += f" ({info})"
        lines.append(line)
    return "\n".join(lines)


def _format_wiki_diff(diff: list[dict]) -> str:
    lines = []
    for item in diff:
        title = item.get("title", "Unknown")
        url = item.get("url", "")
        line = f"  - {title}"
        if url:
            line += f" ({url})"
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    cli()
