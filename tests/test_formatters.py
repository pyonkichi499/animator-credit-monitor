from animator_credit_monitor.formatters import format_anilist_diff, format_bangumi_diff


def test_単一作品の差分フォーマット() -> None:
    diff: list[dict] = [
        {"title": "アポカリプスホテル", "role": "原画", "info": "ep.5"},
    ]
    result = format_bangumi_diff(diff)
    assert result == "検知件数: 1\n1. アポカリプスホテル [原画] (ep.5)"


def test_複数作品の差分フォーマット() -> None:
    diff: list[dict] = [
        {"title": "作品A", "role": "原画", "info": "ep.1"},
        {"title": "作品B", "role": "動画", "info": "ep.3"},
    ]
    result = format_bangumi_diff(diff)
    assert result == (
        "検知件数: 2\n"
        "1. 作品A [原画] (ep.1)\n"
        "2. 作品B [動画] (ep.3)"
    )


def test_infoフィールドがある場合に括弧表示される() -> None:
    diff: list[dict] = [
        {"title": "テスト作品", "role": "作画監督", "info": "ep.10"},
    ]
    result = format_bangumi_diff(diff)
    assert "(ep.10)" in result


def test_roleがない場合は角括弧表示されない() -> None:
    diff: list[dict] = [
        {"title": "テスト作品", "info": "ep.1"},
    ]
    result = format_bangumi_diff(diff)
    assert "[" not in result
    assert "]" not in result
    assert result == "検知件数: 1\n1. テスト作品 (ep.1)"


def test_dateフィールドが括弧表示される() -> None:
    diff: list[dict] = [
        {"title": "ウマ娘 シンデレラグレイ", "role": "原画 (OP)", "date": "2025-04"},
    ]
    result = format_anilist_diff(diff)
    assert result == "検知件数: 1\n1. ウマ娘 シンデレラグレイ [原画 (OP)] (2025-04)"


def test_titleがない場合はUnknownと表示される() -> None:
    diff: list[dict] = [
        {"role": "原画", "date": "2025-01"},
    ]
    result = format_anilist_diff(diff)
    assert "Unknown" in result
    assert result == "検知件数: 1\n1. Unknown [原画] (2025-01)"


def test_空リストの場合は検知件数0のみ() -> None:
    result_bangumi = format_bangumi_diff([])
    result_anilist = format_anilist_diff([])
    assert result_bangumi == "検知件数: 0"
    assert result_anilist == "検知件数: 0"
