from unittest.mock import MagicMock, patch

import pytest

from animator_credit_monitor.notifier import (
    ConsoleNotifier,
    EmailNotifier,
    MultiNotifier,
    MultiNotifierError,
    Notifier,
)


class TestNotifier:
    def test_Notifier抽象クラスは直接インスタンス化できない(self) -> None:
        with pytest.raises(TypeError):
            Notifier()  # type: ignore[abstract]

    def test_コンソール通知が正しく出力される(self, capsys: pytest.CaptureFixture[str]) -> None:
        notifier = ConsoleNotifier()
        notifier.notify("テストタイトル", "テストメッセージ")

        captured = capsys.readouterr()
        assert "テストタイトル" in captured.out
        assert "テストメッセージ" in captured.out

    def test_MultiNotifierで全通知先に配信される(self) -> None:
        n1 = MagicMock()
        n2 = MagicMock()
        notifier = MultiNotifier([n1, n2])

        notifier.notify("title", "message")

        n1.notify.assert_called_once_with("title", "message")
        n2.notify.assert_called_once_with("title", "message")

    def test_MultiNotifierは一部失敗しても他通知先を実行する(self) -> None:
        n1 = MagicMock()
        n2 = MagicMock()
        n1.notify.side_effect = RuntimeError("smtp failed")
        notifier = MultiNotifier([n1, n2])

        with pytest.raises(MultiNotifierError) as exc_info:
            notifier.notify("title", "message")

        n1.notify.assert_called_once_with("title", "message")
        n2.notify.assert_called_once_with("title", "message")
        assert "smtp failed" in str(exc_info.value)

    @patch("animator_credit_monitor.notifier.smtplib.SMTP")
    def test_EmailNotifierがSMTPで通知送信する(self, mock_smtp_cls: MagicMock) -> None:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addr="to@example.com",
            username="user",
            password="pass",
            use_tls=True,
        )
        notifier.notify("件名", "本文")

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user", "pass")
        mock_smtp.send_message.assert_called_once()

    @patch("animator_credit_monitor.notifier.smtplib.SMTP")
    def test_EmailNotifierテンプレートが適用される(self, mock_smtp_cls: MagicMock) -> None:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addr="to@example.com",
            subject_template="[ACM] {title}",
            body_template="---\n{title}\n---\n{message}",
        )
        notifier.notify("新規", "本文メッセージ")

        sent_msg = mock_smtp.send_message.call_args.args[0]
        assert sent_msg["Subject"] == "[ACM] 新規"
        assert "本文メッセージ" in sent_msg.get_content()

    @patch("animator_credit_monitor.notifier.smtplib.SMTP")
    def test_EmailNotifierでバックスラッシュnを改行として解釈する(self, mock_smtp_cls: MagicMock) -> None:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addr="to@example.com",
            body_template="{title}\\n\\n{message}",
        )
        notifier.notify("新規", "本文メッセージ")

        sent_msg = mock_smtp.send_message.call_args.args[0]
        assert "新規\n\n本文メッセージ" in sent_msg.get_content()

    @patch("animator_credit_monitor.notifier.smtplib.SMTP")
    def test_EmailNotifierで未知のテンプレート変数はエラー(self, mock_smtp_cls: MagicMock) -> None:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addr="to@example.com",
            subject_template="{unknown}",
        )

        with pytest.raises(ValueError):
            notifier.notify("件名", "本文")

    @patch("animator_credit_monitor.notifier.smtplib.SMTP")
    def test_EmailNotifierで認証情報なしならloginしない(self, mock_smtp_cls: MagicMock) -> None:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        notifier = EmailNotifier(
            host="smtp.example.com",
            port=25,
            from_addr="from@example.com",
            to_addr="to@example.com",
            use_tls=False,
        )
        notifier.notify("件名", "本文")

        mock_smtp.starttls.assert_not_called()
        mock_smtp.login.assert_not_called()
        mock_smtp.send_message.assert_called_once()
