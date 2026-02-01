import pytest

from animator_credit_monitor.notifier import ConsoleNotifier, Notifier


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

    def test_コンソール通知でタイトルとメッセージが区別して表示される(self, capsys: pytest.CaptureFixture[str]) -> None:
        notifier = ConsoleNotifier()
        notifier.notify("新着クレジット", "作品Aに原画として参加")

        captured = capsys.readouterr()
        assert "新着クレジット" in captured.out
        assert "作品Aに原画として参加" in captured.out
