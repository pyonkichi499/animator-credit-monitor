from collections.abc import Callable
from dataclasses import dataclass

FetchCredits = Callable[[], list[dict]]
FormatDiff = Callable[[list[dict]], str]


@dataclass(frozen=True)
class SourcePlan:
    short_name: str
    label: str
    source_key: str
    notification_title: str
    fetch_credits: FetchCredits
    format_diff: FormatDiff
    source_type: str = ""
    target_label: str = ""


@dataclass(frozen=True)
class SourceRunResult:
    plan: SourcePlan
    had_data: bool
    diff_count: int
    notification_error: str | None
    saved_history: bool


@dataclass(frozen=True)
class RunReport:
    source_results: list[SourceRunResult]
    redelivery_processed: int = 0
    redelivery_failed: int = 0
    run_status: str = "success"

    @property
    def checks_run(self) -> int:
        return len(self.source_results)

    @property
    def sources_with_new_credits(self) -> int:
        return sum(1 for result in self.source_results if result.diff_count > 0)

    @property
    def found_new(self) -> bool:
        return self.sources_with_new_credits > 0

    @property
    def had_errors(self) -> bool:
        return self.run_status in {"failed", "partial_failure"} or any(
            result.notification_error for result in self.source_results
        )
