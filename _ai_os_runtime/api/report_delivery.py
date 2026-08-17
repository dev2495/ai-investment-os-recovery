"""Safe delivery selection for generated thesis report artifacts."""

from pathlib import Path


def select_thesis_report_delivery(artifact_path: Path, action: str) -> tuple[Path, str, str]:
    """Choose an HTML companion for browser view, otherwise deliver the binary safely."""
    normalized_action = str(action or "view").lower()
    selected = artifact_path
    if normalized_action == "view" and artifact_path.suffix.lower() == ".pdf":
        html_companion = artifact_path.with_suffix(".html")
        if html_companion.is_file():
            selected = html_companion
    suffix = selected.suffix.lower()
    content_type = {
        ".html": "text/html; charset=utf-8",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
    disposition = "attachment" if normalized_action == "download" else "inline"
    return selected, content_type, disposition
