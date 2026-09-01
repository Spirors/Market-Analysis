"""Tests for the pure-Python favicon -> ICO renderer in app/launcher_icon.py.

The renderer has zero external dependencies, so the tests are byte-level:
verify the ICO container shape, the BITMAPINFOHEADER values, and that the
pixel data actually contains both the background fill and the chart line
colors (i.e. the rendering pipeline didn't silently produce a blank icon).
"""

from __future__ import annotations

import struct

import pytest

from app.launcher_icon import (
    _LINE_RGBA,
    _BG_RGBA,
    build_launcher_ico,
    make_ico,
    render_rgba_pixels,
)


SIZE = 32


def test_build_launcher_ico_returns_expected_size():
    """ICO size = ICONDIR(6) + ICONDIRENTRY(16) + BIH(40) + XOR(32*32*4) + AND(32*4)."""
    data = build_launcher_ico()
    assert len(data) == 6 + 16 + 40 + (SIZE * SIZE * 4) + (SIZE * 4)


def test_icondir_header_is_valid():
    """Reserved=0, type=1 (icon), count=1."""
    data = build_launcher_ico()
    reserved, type_, count = struct.unpack("<HHH", data[:6])
    assert reserved == 0
    assert type_ == 1
    assert count == 1


def test_icondirentry_references_full_image():
    """The single entry must report 32x32, 32bpp, and point at offset 22."""
    data = build_launcher_ico()
    entry = data[6:22]
    b_width, b_height, b_colors, b_reserved, w_planes, w_bitcount, dw_size, dw_offset = struct.unpack(
        "<BBBBHHII", entry
    )
    assert b_width == SIZE
    assert b_height == SIZE
    assert b_colors == 0       # 0 for >=8bpp icons
    assert b_reserved == 0
    assert w_planes == 1
    assert w_bitcount == 32
    assert dw_offset == 6 + 16


def test_bitmapinfoheader_is_ico_spec_conformant():
    """biSize=40, biWidth=32, biHeight=64 (image+AND mask), 32bpp, BI_RGB."""
    data = build_launcher_ico()
    bih = data[22:62]
    bi_size, bi_w, bi_h, bi_planes, bi_bpp, bi_comp = struct.unpack(
        "<IiiHHI", bih[:20]
    )
    assert bi_size == 40
    assert bi_w == SIZE
    assert bi_h == SIZE * 2  # ICO spec: doubled for the AND mask slot
    assert bi_planes == 1
    assert bi_bpp == 32
    assert bi_comp == 0  # BI_RGB


def test_pixels_contain_both_bg_and_line_colors():
    """A blank icon would be a silent failure; check both colors are present."""
    pixels = render_rgba_pixels()
    assert len(pixels) == SIZE * SIZE * 4
    pixel_set = set()
    for i in range(0, len(pixels), 4):
        pixel_set.add(tuple(pixels[i : i + 4]))
    assert _BG_RGBA in pixel_set, "expected dark-gray fill pixels"
    assert _LINE_RGBA in pixel_set, "expected green chart-line pixels"


def test_corners_are_transparent():
    """The rounded rect should leave the four corner cells outside the radius
    fully transparent (alpha = 0)."""
    pixels = render_rgba_pixels()
    # Top-left corner pixel (0,0) is well outside the radius-6 curve.
    idx = (0 * SIZE + 0) * 4
    assert tuple(pixels[idx : idx + 4]) == (0, 0, 0, 0)


def test_make_ico_accepts_arbitrary_rgba_pixels():
    """make_ico should accept any 32x32x4 byte input and wrap it correctly."""
    blank = bytes(SIZE * SIZE * 4)  # all zeros (fully transparent)
    ico = make_ico(blank)
    assert len(ico) == 6 + 16 + 40 + (SIZE * SIZE * 4) + (SIZE * 4)
    # The XOR mask should still be embedded and parseable.
    xor_offset = 6 + 16 + 40
    assert ico[xor_offset : xor_offset + 4] == blank[:4]
