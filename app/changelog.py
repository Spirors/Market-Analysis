"""Append-only per-day summary log for meaningful project changes.

Files written: data/logs/summary-YYYY-MM-DD.md
Format:
    ## YYYY-MM-DD

    ### HH:MM:SS — <category>
    <message>

    ### HH:MM:SS — <category>
    <message>
"""

from __future__ import annotations

import datetime
import os
import pathlib
import re
import tempfile

# Resolve LOG_DIR relative to the repo root: app/changelog.py → app/ → repo root.
LOG_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parents[1] / "data" / "logs"

_CATEGORY_RE = re.compile(r"^[a-z0-9_-]+$")


def today_path() -> pathlib.Path:
    """Return the file path for today's summary log (does not create it)."""
    day = datetime.date.today()
    return LOG_DIR / f"summary-{day.isoformat()}.md"


def _validate_category(category: str) -> None:
    if not category:
        raise ValueError("category must be non-empty")
    if not _CATEGORY_RE.match(category):
        raise ValueError(
            f"category {category!r} contains invalid characters; "
            "only [a-z0-9_-] are allowed"
        )


def _sanitize_message(message: str) -> str:
    """Collapse embedded newlines into spaces and strip."""
    return message.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def _append_entry(f: pathlib.Path, category: str, message: str, ts: str, day_str: str) -> None:
    """Append a single entry to an open file. Called from the temp+replace writer."""
    content = f.read_text(encoding="utf-8") if f.exists() else ""

    # Ensure the day header exists at the top.
    header = f"## {day_str}"
    if header not in content:
        content = f"{header}\n"

    entry = f"\n### {ts} — {category}\n{message}\n"

    # Find the header line; append entry after header line (and any trailing
    # newline immediately after it).
    lines = content.split("\n")
    header_idx = None
    for i, line in enumerate(lines):
        if line == header:
            header_idx = i
            break

    if header_idx is None:
        # Shouldn't happen, but defensive: just append.
        content = content.rstrip("\n") + entry
    else:
        # Insert entry right after the header line.
        insert_at = header_idx + 1
        # Skip past any single blank line after the header so entries don't
        # accumulate blank lines.
        if insert_at < len(lines) and lines[insert_at] == "":
            insert_at += 1
        lines.insert(insert_at, entry.rstrip("\n"))
        content = "\n".join(lines)
        # Ensure trailing newline.
        if not content.endswith("\n"):
            content += "\n"

    f.write_text(content, encoding="utf-8")


def log_change(
    category: str,
    message: str,
    *,
    day: datetime.date | None = None,
) -> pathlib.Path:
    """Append one entry to the day's summary log. Returns the file path.

    Creates ``LOG_DIR`` and the day file if they don't exist yet.  Uses
    atomic write (tmp + os.replace) so concurrent writers won't corrupt the
    file — last full-file rewrite wins, which is acceptable for a developer
    log.
    """
    _validate_category(category)
    message = _sanitize_message(message)

    if day is None:
        day = datetime.date.today()
    now = datetime.datetime.now()
    ts = now.strftime("%H:%M:%S")
    date_str = day.isoformat()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LOG_DIR / f"summary-{date_str}.md"

    # Atomic write: write to a temp file in the same directory, then replace.
    fd, tmp_path = tempfile.mkstemp(
        dir=str(LOG_DIR), prefix=f"summary-{date_str}-", suffix=".tmp"
    )
    try:
        # Close the fd immediately — on Windows os.replace() fails if the
        # file is still held open by the descriptor.
        os.close(fd)
        tmp_file = pathlib.Path(tmp_path)
        # Copy existing content into tmp if file exists.
        if file_path.exists():
            tmp_file.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

        _append_entry(tmp_file, category, message, ts, date_str)
        os.replace(str(tmp_file), str(file_path))
    except BaseException:
        # Clean up tmp on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return file_path


def read_day(day: datetime.date | None = None) -> str:
    """Return the full markdown content for *day*, or empty string if no file."""
    if day is None:
        day = datetime.date.today()
    file_path = LOG_DIR / f"summary-{day.isoformat()}.md"
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return ""
