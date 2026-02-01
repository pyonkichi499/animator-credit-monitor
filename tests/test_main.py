from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from animator_credit_monitor.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLI:
    @patch("animator_credit_monitor.main.load_dotenv")
    def test_環境変数が未設定の場合はエラー終了する(
        self,
        mock_dotenv: MagicMock,
        runner: CliRunner,
    ) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code != 0
        assert "TARGET_BANGUMI_ID" in result.output or "設定" in result.output

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.SakugaWikiScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_差分がある場合に通知が呼ばれる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_wiki_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]

        mock_bangumi = mock_bangumi_cls.return_value
        mock_bangumi.fetch_works.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]

        mock_wiki = mock_wiki_cls.return_value
        mock_wiki.search.return_value = []

        mock_anilist = mock_anilist_cls.return_value
        mock_anilist.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "新作品" in result.output

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.SakugaWikiScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_差分がない場合は通知が呼ばれない(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_wiki_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = []

        mock_bangumi = mock_bangumi_cls.return_value
        mock_bangumi.fetch_works.return_value = [{"id": "1", "title": "既存作品"}]

        mock_wiki = mock_wiki_cls.return_value
        mock_wiki.search.return_value = []

        mock_anilist = mock_anilist_cls.return_value
        mock_anilist.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "新しいクレジット" not in result.output

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.SakugaWikiScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_dry_runオプションで状態が保存されない(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_wiki_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]

        mock_bangumi = mock_bangumi_cls.return_value
        mock_bangumi.fetch_works.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]

        mock_wiki = mock_wiki_cls.return_value
        mock_wiki.search.return_value = []

        mock_anilist = mock_anilist_cls.return_value
        mock_anilist.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--dry-run"])

        assert result.exit_code == 0
        mock_history.save.assert_not_called()

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.SakugaWikiScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_bangumi_onlyオプションでwikiとAniListがスキップされる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_wiki_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = []

        mock_bangumi = mock_bangumi_cls.return_value
        mock_bangumi.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--bangumi-only"])

        assert result.exit_code == 0
        mock_wiki_cls.return_value.search.assert_not_called()
        mock_anilist_cls.return_value.fetch_works.assert_not_called()

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.SakugaWikiScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_作画wiki失敗時にAniListにフォールバックする(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_wiki_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        anilist_item = {
            "id": "1", "title": "AniList作品",
            "role": "Key Animation", "date": "2026-01",
        }
        mock_history.detect_diff.return_value = [anilist_item]

        mock_bangumi = mock_bangumi_cls.return_value
        mock_bangumi.fetch_works.return_value = []

        mock_wiki = mock_wiki_cls.return_value
        mock_wiki.search.return_value = []  # wiki fails

        mock_anilist = mock_anilist_cls.return_value
        mock_anilist.fetch_works.return_value = [anilist_item]

        env = {
            "TARGET_BANGUMI_ID": "",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "AniList作品" in result.output
        assert "falling back to AniList" in result.output
        mock_anilist.fetch_works.assert_called_once_with("テスト")
