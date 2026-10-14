"""Timestamped full-data backup with CRC validation and retention.

Zips every file under the app's data directory into a timestamped archive in a
destination directory, reopens the archive to validate it (entry-name set and
per-entry CRC32 against the sources), then prunes old archives by retention
count. Nothing outside the ``market-analysis-data-*.zip`` naming pattern is ever
touched.

    python scripts/backup_data.py --dest D:\\backups --keep 14

The destination is fully configurable and required: pass ``--dest DIR`` or set
the ``MARKET_ANALYSIS_BACKUP_DIR`` environment variable. When neither is
present the tool exits nonzero with a message naming both ways to set it, so a
second physical destination can be pointed at without a code change.

A backup is only pruned after it validates. A corrupt archive is kept as
evidence and the run exits 1. Output is sanitized: file names, counts and byte
sizes only — never file contents.
"""

from __future__ import annotations

import argparse
import os
import sys
import zlib
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

# Allow ``python scripts/backup_data.py`` from the repo root: the script dir
# (``scripts/``) is sys.path[0], not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402

DEST_ENV = "MARKET_ANALYSIS_BACKUP_DIR"
ARCHIVE_PREFIX = "market-analysis-data-"
ARCHIVE_SUFFIX = ".zip"
_CHUNK = 64 * 1024


def _source_files(data_dir: Path) -> list[tuple[str, Path]]:
    """``(relative_posix_name, absolute_path)`` for every file under ``data_dir``."""
    data_dir = Path(data_dir)
    files: list[tuple[str, Path]] = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file():
            files.append((path.relative_to(data_dir).as_posix(), path))
    return files


def _crc32(path: Path) -> int:
    """Streaming CRC32 of ``path``'s contents (matches ``zipfile``'s entry.CRC)."""
    crc = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def archive_name(now: datetime | None = None) -> str:
    """``market-analysis-data-YYYYMMDD-HHMMSS.zip`` for ``now`` (default: local now)."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{ARCHIVE_PREFIX}{stamp}{ARCHIVE_SUFFIX}"


def create_archive(data_dir: Path, archive_path: Path) -> int:
    """Write every file under ``data_dir`` into ``archive_path``; return file count.

    Fails loudly on any unreadable source file: the partial archive is removed
    and the error propagates so the caller can exit nonzero.
    """
    files = _source_files(data_dir)
    try:
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as zf:
            for name, path in files:
                try:
                    zf.write(path, arcname=name)
                except OSError as exc:
                    print(f"backup failed: cannot read {path}: {exc}", file=sys.stderr)
                    raise
    except BaseException:
        Path(archive_path).unlink(missing_ok=True)
        raise
    return len(files)


def validate_archive(archive_path: Path, data_dir: Path) -> dict:
    """Reopen ``archive_path`` and check it against the files under ``data_dir``.

    Returns ``{"ok", "entry_count", "checked", "bytes", "problems"}``. Compares
    the entry-name set with the source file set, then reads each entry (which
    forces decompression and an internal CRC check) and compares its stored
    CRC32 with the source file's streamed CRC32.
    """
    archive_path = Path(archive_path)
    sources = dict(_source_files(data_dir))
    problems: list[str] = []
    entry_names: list[str] = []
    checked = 0
    try:
        with ZipFile(archive_path) as zf:
            entry_names = zf.namelist()
            entry_set = set(entry_names)
            source_set = set(sources)
            for name in sorted(source_set - entry_set):
                problems.append(f"missing from archive: {name}")
            for name in sorted(entry_set - source_set):
                problems.append(f"unexpected in archive: {name}")
            for name in entry_names:
                if name not in sources:
                    continue
                try:
                    zf.read(name)  # forces decompression + internal CRC check
                except (BadZipFile, zlib.error, OSError) as exc:
                    problems.append(f"unreadable entry {name}: {exc}")
                    continue
                if zf.getinfo(name).CRC != _crc32(sources[name]):
                    problems.append(f"crc mismatch: {name}")
                else:
                    checked += 1
    except (BadZipFile, OSError) as exc:
        problems.append(f"cannot open archive: {exc}")

    return {
        "ok": not problems,
        "entry_count": len(entry_names),
        "checked": checked,
        "bytes": archive_path.stat().st_size if archive_path.exists() else 0,
        "problems": problems,
    }


def prune_archives(dest: Path, keep: int) -> list[str]:
    """Delete all but the newest ``keep`` (by filename) ``*-data-*.zip`` files.

    Only files matching the backup naming pattern are considered; unrelated
    files in ``dest`` are never touched.
    """
    dest = Path(dest)
    archives = sorted(dest.glob(f"{ARCHIVE_PREFIX}*{ARCHIVE_SUFFIX}"))
    if keep < 1:
        return []
    removed: list[str] = []
    for path in archives[:-keep]:
        path.unlink()
        removed.append(path.name)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Timestamped full-data backup (validated, pruned)")
    parser.add_argument("--data-dir", default=None, help="source data directory (default: app config.DATA_DIR)")
    parser.add_argument("--dest", default=None, help=f"archive destination (or set ${DEST_ENV})")
    parser.add_argument("--keep", type=int, default=14, help="archives to retain (default: 14)")
    parser.add_argument("--verify-only", default=None, metavar="ARCHIVE",
                        help="validate an existing archive against --data-dir instead of creating one")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir) if args.data_dir else config.DATA_DIR

    if args.verify_only:
        result = validate_archive(Path(args.verify_only), data_dir)
        if result["ok"]:
            print(f"verify ok: {Path(args.verify_only).name} entries={result['entry_count']} "
                  f"crc_checked={result['checked']} bytes={result['bytes']}")
            return 0
        print(f"verify FAILED: {Path(args.verify_only).name} entries={result['entry_count']}", file=sys.stderr)
        for problem in result["problems"]:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    dest_raw = args.dest or os.environ.get(DEST_ENV)
    if not dest_raw:
        print(
            "error: no backup destination set. Pass --dest DIR or set the "
            f"{DEST_ENV} environment variable to the archive directory.",
            file=sys.stderr,
        )
        return 2

    dest = Path(dest_raw)
    dest.mkdir(parents=True, exist_ok=True)
    archive_path = dest / archive_name()

    count = create_archive(data_dir, archive_path)

    result = validate_archive(archive_path, data_dir)
    if not result["ok"]:
        print(f"backup INVALID, kept for evidence: {archive_path.name} "
              f"entries={result['entry_count']}", file=sys.stderr)
        for problem in result["problems"]:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    removed = prune_archives(dest, args.keep)
    print(f"backup ok: {archive_path.name} files={count} bytes={result['bytes']} pruned={len(removed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
