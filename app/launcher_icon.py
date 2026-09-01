"""Generate the desktop launcher's ``launcher.ico`` from the favicon SVG.

The favicon (inline SVG in ``static/index.html``) is a 32x32 dark-gray
rounded rectangle with a green up-trending line chart. This module
rasterizes that design to a 32x32 BGRA bitmap and wraps it in the
ICO container format using **only the Python standard library** (no
Pillow, no cairosvg) so the project does not need a new dependency just
to give the desktop shortcut a custom icon.

Run as a script::

    python -m app.launcher_icon               # writes static/launcher.ico
    python -m app.launcher_icon out/path.ico  # writes to a custom path

Regenerate whenever the favicon SVG changes (the data URI in
``static/index.html`` is the source of truth; update this file in lockstep).
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

# Source-of-truth colors must match the data URI in static/index.html.
_BG_RGBA = (0x1F, 0x29, 0x37, 0xFF)   # dark gray
_LINE_RGBA = (0x99, 0xD3, 0x34, 0xFF)  # green (#34d399)
_RECT_RADIUS = 6
_LINE_THICKNESS = 2.5
_SIZE = 32

# Path: M7 21 l5 -6 4 4 6 -9 -> three segments, same as the SVG path.
_LINE_SEGMENTS = (
    (7, 21, 12, 15),
    (12, 15, 16, 19),
    (16, 19, 22, 10),
)


def _in_rounded_rect(x: int, y: int, w: int, h: int, r: int) -> bool:
    """True iff pixel (x, y) is inside a w*h rounded rect of radius r.

    Uses sub-pixel-correct quarter-circle math so the corners look smooth
    at 32x32 (the icon's native size).
    """
    if x < 0 or x >= w or y < 0 or y >= h:
        return False
    if (r <= x < w - r) or (r <= y < h - r):
        return True
    if x < r and y < r:
        dx, dy = (r - x - 0.5), (r - y - 0.5)
    elif x >= w - r and y < r:
        dx, dy = (x - (w - r - 1) + 0.5), (r - y - 0.5)
    elif x < r and y >= h - r:
        dx, dy = (r - x - 0.5), (y - (h - r - 1) + 0.5)
    else:
        dx, dy = (x - (w - r - 1) + 0.5), (y - (h - r - 1) + 0.5)
    return dx * dx + dy * dy <= r * r


def _line_pixel_set(thickness: float = _LINE_THICKNESS) -> set[tuple[int, int]]:
    """Pixel positions within thickness/2 of any line segment."""
    out: set[tuple[int, int]] = set()
    half = thickness / 2.0
    for x0, y0, x1, y1 in _LINE_SEGMENTS:
        dx, dy = x1 - x0, y1 - y0
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            continue
        minx = max(0, int(min(x0, x1) - thickness) - 1)
        maxx = min(_SIZE - 1, int(max(x0, x1) + thickness) + 1)
        miny = max(0, int(min(y0, y1) - thickness) - 1)
        maxy = min(_SIZE - 1, int(max(y0, y1) + thickness) + 1)
        for y in range(miny, maxy + 1):
            for x in range(minx, maxx + 1):
                # Closest-point-on-segment distance
                t = ((x - x0) * dx + (y - y0) * dy) / length_sq
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                proj_x = x0 + t * dx
                proj_y = y0 + t * dy
                if (x - proj_x) ** 2 + (y - proj_y) ** 2 <= half * half:
                    out.add((x, y))
    return out


def render_rgba_pixels() -> bytes:
    """Return ``_SIZE * _SIZE * 4`` bytes (RGBA, row-major, top-down)."""
    line_pixels = _line_pixel_set()
    out = bytearray()
    for y in range(_SIZE):
        for x in range(_SIZE):
            if _in_rounded_rect(x, y, _SIZE, _SIZE, _RECT_RADIUS):
                if (x, y) in line_pixels:
                    out.extend(_LINE_RGBA)
                else:
                    out.extend(_BG_RGBA)
            else:
                out.extend((0, 0, 0, 0))  # transparent
    return bytes(out)


def make_ico(rgba_pixels: bytes, size: int = _SIZE) -> bytes:
    """Wrap RGBA pixels in a BMP-based ICO container.

    Uses the classic BMP-inside-ICO layout (Windows XP+ compatible, more
    reliably rendered by .lnk ShellExecute than PNG-inside-ICO on older
    builds). 32bpp icons store transparency in the alpha channel; we still
    emit a zero-filled AND mask because the ICO spec reserves
    ``biHeight == 2 * image_height`` of space for it.
    """
    # BITMAPINFOHEADER (40 bytes), biHeight doubled per ICO spec.
    bih = struct.pack(
        "<IiiHHIIiiII",
        40,            # biSize
        size,          # biWidth
        size * 2,      # biHeight (XOR + AND mask)
        1,             # biPlanes
        32,            # biBitCount
        0,             # biCompression = BI_RGB
        0,             # biSizeImage
        0, 0, 0, 0,    # XPels, YPels, ClrUsed, ClrImportant
    )

    # XOR mask: BGRA, bottom-up, 4-byte aligned per row.
    stride = size * 4
    xor_mask = bytearray()
    for y in range(size - 1, -1, -1):
        row = rgba_pixels[y * stride : (y + 1) * stride]
        bgra_row = bytearray()
        for i in range(0, len(row), 4):
            r, g, b, a = row[i : i + 4]
            bgra_row.extend((b, g, r, a))
        xor_mask.extend(bgra_row)

    # AND mask: 1 bit per pixel, padded to 32-bit rows, bottom-up.
    # All zeros (alpha channel handles transparency; AND mask unused).
    and_mask_row_bytes = ((size + 31) // 32) * 4
    and_mask = bytes(and_mask_row_bytes * size)

    image_data = bih + bytes(xor_mask) + and_mask

    # ICONDIR + ICONDIRENTRY.
    icondir = struct.pack("<HHH", 0, 1, 1)  # reserved, type=icon, count=1
    icondirentry = struct.pack(
        "<BBBBHHII",
        size if size < 256 else 0,   # bWidth (0 = 256)
        size if size < 256 else 0,   # bHeight
        0,                            # bColorCount
        0,                            # bReserved
        1,                            # wPlanes
        32,                           # wBitCount
        len(image_data),
        6 + 16,                       # offset to image data
    )
    return icondir + icondirentry + image_data


def build_launcher_ico() -> bytes:
    """Top-level: render the favicon design and return ICO bytes."""
    return make_ico(render_rgba_pixels())


def _cli(argv: list[str]) -> int:
    out_path = Path(argv[1]) if len(argv) > 1 else Path("static/launcher.ico")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(build_launcher_ico())
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
