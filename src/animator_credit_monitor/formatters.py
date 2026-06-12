def _format_diff_with_metadata(diff: list[dict], trailing_fields: list[str]) -> str:
    lines = [f"検知件数: {len(diff)}"]
    for i, item in enumerate(diff, start=1):
        title = item.get("title", "Unknown")
        role = item.get("role", "")
        line = f"{i}. {title}"
        if role:
            line += f" [{role}]"
        for field in trailing_fields:
            value = item.get(field, "")
            if value:
                line += f" ({value})"
                break
        lines.append(line)
    return "\n".join(lines)


def format_bangumi_diff(diff: list[dict]) -> str:
    return _format_diff_with_metadata(diff, trailing_fields=["info"])


def format_anilist_diff(diff: list[dict]) -> str:
    return _format_diff_with_metadata(diff, trailing_fields=["date"])

