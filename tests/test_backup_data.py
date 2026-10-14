"""Tests for ``scripts/backup_data.py``.

Every case uses pytest's ``tmp_path`` for both the source data dir and the
archive destination, so a test can never read or write the user's live
``data/`` tree.
"""

from __future__ import annotations

import struct
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import backup_data


def _make_tree(root: Path) -> set[str]:
    """Build a small nested source tree and return its expected relative names."""
    (root / "sub" / "deeper").mkdir(parents=True)
    (root / "a.txt").write_text("hello world\n", encoding="utf-8")
    (root / "sub" / "b.json").write_text('{"x": 1}\n', encoding="utf-8")
    (root / "sub" / "deeper" / "blob.bin").write_bytes(bytes(range(256)) * 4)
    return {"a.txt", "sub/b.json", "sub/deeper/blob.bin"}


def test_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "data"
    dest = tmp_path / "dest"
    expected = _make_tree(src)

    rc = backup_data.main(["--data-dir", str(src), "--dest", str(dest), "--keep", "5"])
    assert rc == 0

    archives = list(dest.glob("market-analysis-data-*.zip"))
    assert len(archives) == 1
    with ZipFile(archives[0]) as zf:
        assert set(zf.namelist()) == expected
        assert zf.testzip() is None


def test_corrupted_archive_detected(tmp_path: Path) -> None:
    src = tmp_path / "data"
    dest = tmp_path / "dest"
    _make_tree(src)

    assert backup_data.main(["--data-dir", str(src), "--dest", str(dest)]) == 0
    archive = next(dest.glob("market-analysis-data-*.zip"))

    # Flip a byte inside the first entry's payload (past its local file header).
    raw = bytearray(archive.read_bytes())
    name_len = struct.unpack_from("<H", raw, 26)[0]
    extra_len = struct.unpack_from("<H", raw, 28)[0]
    offset = 30 + name_len + extra_len + 4
    raw[offset] ^= 0xFF
    archive.write_bytes(bytes(raw))

    rc = backup_data.main(["--verify-only", str(archive), "--data-dir", str(src)])
    assert rc != 0


def test_retention_prunes_oldest(tmp_path: Path) -> None:
    src = tmp_path / "data"
    dest = tmp_path / "dest"
    dest.mkdir()
    _make_tree(src)
    for stamp in ("20200101-000000", "20210101-000000", "20220101-000000", "20230101-000000"):
        (dest / f"market-analysis-data-{stamp}.zip").write_bytes(b"fake")
    unrelated = dest / "notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")

    assert backup_data.main(["--data-dir", str(src), "--dest", str(dest), "--keep", "2"]) == 0

    remaining = sorted(p.name for p in dest.glob("market-analysis-data-*.zip"))
    # Newest = today's fresh archive; second newest = 20230101; older three pruned.
    assert len(remaining) == 2
    assert "market-analysis-data-20230101-000000.zip" in remaining
    for stamp in ("20200101-000000", "20210101-000000", "20220101-000000"):
        assert f"market-analysis-data-{stamp}.zip" not in remaining
    assert unrelated.exists()


def test_dest_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "data"
    _make_tree(src)
    monkeypatch.delenv(backup_data.DEST_ENV, raising=False)

    rc = backup_data.main(["--data-dir", str(src)])
    assert rc != 0
    err = capsys.readouterr().err
    assert backup_data.DEST_ENV in err


def test_dest_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "data"
    dest = tmp_path / "env-dest"
    _make_tree(src)
    monkeypatch.setenv(backup_data.DEST_ENV, str(dest))

    assert backup_data.main(["--data-dir", str(src)]) == 0
    assert len(list(dest.glob("market-analysis-data-*.zip"))) == 1
