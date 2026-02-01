import json
from pathlib import Path

import pytest

from animator_credit_monitor.history import HistoryManager


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


class TestHistoryManager:
    def test_初回実行時は全件が新規として検出される(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)
        new_data = [
            {"id": "1", "title": "作品A"},
            {"id": "2", "title": "作品B"},
        ]

        diff = manager.detect_diff("bangumi", new_data)

        assert len(diff) == 2
        assert diff[0]["id"] == "1"
        assert diff[1]["id"] == "2"

    def test_前回と同じデータなら差分なし(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)
        data = [
            {"id": "1", "title": "作品A"},
            {"id": "2", "title": "作品B"},
        ]

        # Save initial data
        manager.save("bangumi", data)

        # Check with same data
        diff = manager.detect_diff("bangumi", data)

        assert diff == []

    def test_新しい作品が追加された場合に検出される(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)
        old_data = [
            {"id": "1", "title": "作品A"},
        ]
        new_data = [
            {"id": "1", "title": "作品A"},
            {"id": "2", "title": "作品B"},
        ]

        manager.save("bangumi", old_data)
        diff = manager.detect_diff("bangumi", new_data)

        assert len(diff) == 1
        assert diff[0]["id"] == "2"

    def test_履歴ファイルの保存と読み込みが正しく動作する(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)
        data = [
            {"id": "100", "title": "テスト作品", "role": "原画"},
        ]

        manager.save("bangumi", data)
        loaded = manager.load("bangumi")

        assert loaded == data

    def test_存在しないソースのloadは空リストを返す(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)

        loaded = manager.load("nonexistent")

        assert loaded == []

    def test_sakugawikiソースの差分検知も動作する(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)
        old_data = [
            {"title": "ページA", "url": "https://example.com/a"},
        ]
        new_data = [
            {"title": "ページA", "url": "https://example.com/a"},
            {"title": "ページB", "url": "https://example.com/b"},
        ]

        manager.save("sakugawiki", old_data)
        diff = manager.detect_diff("sakugawiki", new_data)

        assert len(diff) == 1
        assert diff[0]["title"] == "ページB"

    def test_保存先ファイルがJSON形式で正しく書き込まれる(self, tmp_data_dir: Path) -> None:
        manager = HistoryManager(data_dir=tmp_data_dir)
        data = [{"id": "1", "title": "テスト"}]

        manager.save("bangumi", data)

        file_path = tmp_data_dir / "bangumi_history.json"
        assert file_path.exists()
        with open(file_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert saved == data
