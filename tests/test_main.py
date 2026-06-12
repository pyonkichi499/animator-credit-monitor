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
        assert "TARGET_BANGUMI_ID" in result.output

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_差分がある場合に通知が呼ばれる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]

        mock_bangumi_cls.return_value.fetch_works.return_value = [
            {"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"},
        ]
        mock_anilist_cls.return_value.fetch_works.return_value = []

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
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_dry_runオプションで状態が保存されない(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]
        mock_bangumi_cls.return_value.fetch_works.return_value = [{"id": "1", "title": "新作品"}]
        mock_anilist_cls.return_value.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--dry-run"])

        assert result.exit_code == 0
        mock_history.save.assert_not_called()

    @patch("animator_credit_monitor.main.ConsoleNotifier")
    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_通知失敗時は履歴を保存せずエラー終了する(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        mock_console_notifier_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history = mock_history_cls.return_value
        mock_history.detect_diff.return_value = [{"id": "1", "title": "新作品", "role": "原画", "info": "2026-01"}]
        mock_bangumi_cls.return_value.fetch_works.return_value = [{"id": "1", "title": "新作品"}]
        mock_anilist_cls.return_value.fetch_works.return_value = []
        mock_console_notifier_cls.return_value.notify.side_effect = RuntimeError("notify failed")

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--bangumi-only"])

        assert result.exit_code != 0
        mock_history.save.assert_not_called()
        assert "Notification failed (Bangumi)" in result.output

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_bangumi_onlyオプションでAniListがスキップされる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history_cls.return_value.detect_diff.return_value = []
        mock_bangumi_cls.return_value.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--bangumi-only"])

        assert result.exit_code == 0
        mock_anilist_cls.return_value.fetch_works.assert_not_called()

    def test_bangumi_onlyとanilist_only同時指定はエラー終了する(
        self,
        runner: CliRunner,
    ) -> None:
        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--bangumi-only", "--anilist-only"])

        assert result.exit_code != 0
        assert "--bangumi-only and --anilist-only" in result.output

    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_nameベース監視はAniListを直接チェックする(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        anilist_item = {"id": "1", "title": "AniList作品", "role": "原画", "date": "2026-01"}
        mock_history_cls.return_value.detect_diff.return_value = [anilist_item]
        mock_bangumi_cls.return_value.fetch_works.return_value = []
        mock_anilist_cls.return_value.fetch_works.return_value = [anilist_item]

        env = {
            "TARGET_BANGUMI_ID": "",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        assert "Checking AniList" in result.output
        assert "AniList作品" in result.output
        assert "検知件数: 1" in result.output

    @patch("animator_credit_monitor.main.EmailNotifier")
    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_NOTIFIER_email設定でEmailNotifierが使われる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        mock_email_notifier_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history_cls.return_value.detect_diff.return_value = []
        mock_bangumi_cls.return_value.fetch_works.return_value = []
        mock_anilist_cls.return_value.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
            "NOTIFIER": "email",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_FROM": "from@example.com",
            "SMTP_TO": "to@example.com",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        mock_email_notifier_cls.assert_called_once()

    @patch("animator_credit_monitor.main.LineNotifier")
    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_NOTIFIER_line設定でLineNotifierが使われる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        mock_line_notifier_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history_cls.return_value.detect_diff.return_value = []
        mock_bangumi_cls.return_value.fetch_works.return_value = []
        mock_anilist_cls.return_value.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
            "NOTIFIER": "line",
            "LINE_NOTIFY_TOKEN": "token",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        mock_line_notifier_cls.assert_called_once_with(
            token="token",
            api_url="https://notify-api.line.me/api/notify",
            message_template="{title}\n{message}",
        )

    @patch("animator_credit_monitor.main.LineNotifier")
    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_NOTIFIER_line設定でAPI_URLが空文字でもデフォルトURLを使う(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        mock_line_notifier_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history_cls.return_value.detect_diff.return_value = []
        mock_bangumi_cls.return_value.fetch_works.return_value = []
        mock_anilist_cls.return_value.fetch_works.return_value = []

        env = {
            "TARGET_BANGUMI_ID": "12345",
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
            "NOTIFIER": "line",
            "LINE_NOTIFY_TOKEN": "token",
            "LINE_NOTIFY_API_URL": "",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check"])

        assert result.exit_code == 0
        mock_line_notifier_cls.assert_called_once_with(
            token="token",
            api_url="https://notify-api.line.me/api/notify",
            message_template="{title}\n{message}",
        )

    @patch("animator_credit_monitor.main.MultiNotifier")
    @patch("animator_credit_monitor.main.LineNotifier")
    @patch("animator_credit_monitor.main.EmailNotifier")
    @patch("animator_credit_monitor.main.AniListScraper")
    @patch("animator_credit_monitor.main.BangumiScraper")
    @patch("animator_credit_monitor.main.HistoryManager")
    def test_NOTIFIERSで複数通知を同時利用できる(
        self,
        mock_history_cls: MagicMock,
        mock_bangumi_cls: MagicMock,
        mock_anilist_cls: MagicMock,
        mock_email_notifier_cls: MagicMock,
        mock_line_notifier_cls: MagicMock,
        mock_multi_notifier_cls: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_history_cls.return_value.detect_diff.return_value = []
        mock_bangumi_cls.return_value.fetch_works.return_value = []
        mock_anilist_cls.return_value.fetch_works.return_value = []

        env = {
            "TARGET_NAME": "テスト",
            "DATA_DIR": str(tmp_path),
            "NOTIFIERS": "email,line",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_FROM": "from@example.com",
            "SMTP_TO": "to@example.com",
            "LINE_NOTIFY_TOKEN": "token",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--anilist-only"])

        assert result.exit_code == 0
        mock_email_notifier_cls.assert_called_once()
        mock_line_notifier_cls.assert_called_once()
        mock_multi_notifier_cls.assert_called_once()

    def test_NOTIFIER_email設定で必須環境変数不足時はエラー終了する(
        self,
        runner: CliRunner,
    ) -> None:
        env = {
            "TARGET_NAME": "テスト",
            "NOTIFIER": "email",
            "SMTP_HOST": "smtp.example.com",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--anilist-only"])

        assert result.exit_code != 0
        assert "SMTP_HOST, SMTP_FROM, SMTP_TO" in result.output

    def test_NOTIFIER_line設定でトークン不足時はエラー終了する(
        self,
        runner: CliRunner,
    ) -> None:
        env = {
            "TARGET_NAME": "テスト",
            "NOTIFIER": "line",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--anilist-only"])

        assert result.exit_code != 0
        assert "LINE_NOTIFY_TOKEN" in result.output

    def test_NOTIFIER未知値でエラー終了する(
        self,
        runner: CliRunner,
    ) -> None:
        env = {
            "TARGET_NAME": "テスト",
            "NOTIFIER": "unknown",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--anilist-only"])

        assert result.exit_code != 0
        assert "Notifier type must be one of" in result.output

    def test_NOTIFIERS重複値はエラー終了する(
        self,
        runner: CliRunner,
    ) -> None:
        env = {
            "TARGET_NAME": "テスト",
            "NOTIFIERS": "email,email",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_FROM": "from@example.com",
            "SMTP_TO": "to@example.com",
        }
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(cli, ["check", "--anilist-only"])

        assert result.exit_code != 0
        assert "Duplicate notifier types are not allowed" in result.output
