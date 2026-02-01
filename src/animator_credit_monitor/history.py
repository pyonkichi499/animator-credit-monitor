import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class HistoryManager:
    def __init__(self, data_dir: Path | str = "data") -> None:
        self._data_dir = Path(data_dir)

    def _get_path(self, source: str) -> Path:
        return self._data_dir / f"{source}_history.json"

    def load(self, source: str) -> list[dict]:
        """Load previous data from JSON file. Returns empty list if not found."""
        path = self._get_path(source)
        if not path.exists():
            logger.info("No history file found for %s (first run)", source)
            return []

        with open(path, encoding="utf-8") as f:
            data: list[dict] = json.load(f)
        logger.info("Loaded %d items from %s history", len(data), source)
        return data

    def save(self, source: str, data: list[dict]) -> None:
        """Save current data to JSON file for next comparison."""
        path = self._get_path(source)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d items to %s history", len(data), source)

    def detect_diff(self, source: str, new_data: list[dict]) -> list[dict]:
        """Detect new items by comparing with saved history."""
        old_data = self.load(source)
        if not old_data:
            return new_data

        old_set = {json.dumps(item, sort_keys=True) for item in old_data}
        diff = [item for item in new_data if json.dumps(item, sort_keys=True) not in old_set]

        logger.info("Detected %d new items for %s", len(diff), source)
        return diff
