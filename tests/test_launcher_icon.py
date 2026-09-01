"""Tests for the pure-Python favicon -> multi-resolution ICO renderer.

The renderer is byte-level and has zero external dependencies, so the
tests assert the ICO container shape (ICONDIR + N x ICONDIRENTRY +
N x image bodies), each entry's per-image metrics, and the pixel data
quality at multiple output sizes.
"""

from __future__ import annotations

import struct

import pytest

from app.launcher_icon import (
    _BG_RGBA,
    _DEFAULT_SIZES,
    _LINE_RGBA,
    build_launcher_ico,
    render_rgba_pixels,
)


def _icondir(ico: bytes) -> tuple[int, int, int]:
    reserved, type_, count = struct.unpack("<HHH", ico[:6])
    return reserved, type_, count


def _icondirentry(ico: bytes, idx: int) -> dict:
    base = 6 + idx * 16
    b = ico[base : base + 16]
    bw, bh, bc, br, wp, wb, dw_size, dw_offset = struct.unpack("<BBBBHHII", b)
    return {
        "width": bw,
        "height": bh,
        "planes": wp,
        "bpp": wb,
        "bytes": dw_size,
        "offset": dw_offset,
    }


# ---- ICO container shape ----------------------------------------------------

def test_default_sizes_match_known_set():
    """Default sizes cover taskbar, Alt-Tab, and large-icon views."""
    assert _DEFAULT_SIZES == (16, 32, 48, 64, 128, 256)


def test_icondir_header_is_valid_for_multi_image():
    """Reserved=0, type=1 (icon), count=6."""
    ico = build_launcher_ico()
    reserved, type_, count = _icondir(ico)
    assert reserved == 0
    assert type_ == 1
    assert count == len(_DEFAULT_SIZES)


def test_each_entry_references_a_valid_image():
    """Each ICONDIRENTRY's offset must point to the right image body."""
    ico = build_launcher_ico()
    _, _, count = _icondir(ico)

    # Image body offsets must be monotonically increasing and contiguous.
    cursor = 6 + count * 16
    for i in range(count):
        entry = _icondirentry(ico, i)
        assert entry["offset"] == cursor
        # Width/height: 256 is encoded as 0 per ICO spec.
        assert entry["width"] in (16, 32, 48, 64, 128, 0)
        assert entry["height"] == entry["width"]
        assert entry["planes"] == 1
        assert entry["bpp"] == 32

        # The image body must contain: BIH(40) + size*size*4 XOR + mask.
        width = entry["width"] or 256
        body = ico[entry["offset"] : entry["offset"] + entry["bytes"]]
        expected = 40 + width * width * 4 + ((width + 31) // 32) * 4 * width
        assert len(body) == expected, f"size {width}x{width} body length mismatch"
        cursor += entry["bytes"]


def test_256x256_is_encoded_as_zero_per_spec():
    """ICONDIRENTRY uses 0 to mean 256 (one byte can't fit 256)."""
    ico = build_launcher_ico()
    assert _icondirentry(ico, 5)["width"] == 0
    assert _icondirentry(ico, 5)["height"] == 0


# ---- Per-image BITMAPINFOHEADER --------------------------------------------

def test_bih_is_conformant_at_each_size():
    """biSize=40, biWidth/biHeight (doubled for AND mask), 32bpp, BI_RGB."""
    ico = build_launcher_ico()
    _, _, count = _icondir(ico)
    for i in range(count):
        entry = _icondirentry(ico, i)
        size = entry["width"] or 256
        bih = ico[entry["offset"] : entry["offset"] + 40]
        bi_size, bi_w, bi_h, bi_planes, bi_bpp, bi_comp = struct.unpack(
            "<IiiHHI", bih[:20]
        )
        assert bi_size == 40
        assert bi_w == size
        assert bi_h == size * 2  # ICO doubles biHeight for the AND mask slot
        assert bi_planes == 1
        assert bi_bpp == 32
        assert bi_comp == 0  # BI_RGB


# ---- Pixel content ----------------------------------------------------------

@pytest.mark.parametrize("size", [16, 32, 48, 64, 128, 256])
def test_pixels_contain_both_colors_at_each_size(size):
    """A blank icon would be a silent failure: both BG and line colors must
    appear in the rendered pixels at every output size."""
    pixels = render_rgba_pixels(size)
    assert len(pixels) == size * size * 4
    pixel_set = set()
    for i in range(0, len(pixels), 4):
        pixel_set.add(tuple(pixels[i : i + 4]))
    assert _BG_RGBA in pixel_set, f"missing BG fill at {size}x{size}"
    assert _LINE_RGBA in pixel_set, f"missing chart line at {size}x{size}"


@pytest.mark.parametrize("size", [16, 32, 48, 128, 256])
def test_corners_are_transparent_at_each_size(size):
    """Top-left and bottom-right corners must be transparent (outside the
    rounded rect)."""
    pixels = render_rgba_pixels(size)
    for (px, py) in [(0, 0), (size - 1, size - 1), (0, size - 1), (size - 1, 0)]:
        idx = (py * size + px) * 4
        assert tuple(pixels[idx : idx + 4]) == (0, 0, 0, 0), \
            f"corner ({px},{py}) at {size}x{size} not transparent"


# ---- Determinism / rendering performance -----------------------------------

def test_render_is_deterministic():
    """Two calls must produce identical bytes (no randomness in AA)."""
    a = render_rgba_pixels(64)
    b = render_rgba_pixels(64)
    assert a == b


def test_render_256_completes_in_reasonable_time():
    """The 256x256 path renders at 1024x1024 internally (4x AA). Must finish
    well under a second on a typical workstation."""
    import time
    started = time.monotonic()
    pixels = render_rgba_pixels(256)
    elapsed = time.monotonic() - started
    assert len(pixels) == 256 * 256 * 4
    assert elapsed < 2.0, f"render took {elapsed:.2f}s"
