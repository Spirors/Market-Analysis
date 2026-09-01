"""Generate the desktop launcher's ``launcher.ico`` from the favicon SVG.

The favicon (inline SVG in ``static/index.html``) is a 32x32 dark-gray
rounded rectangle with a green up-trending line chart. This module
rasterizes that design at multiple resolutions and packs them into a
single multi-image ICO so Windows can pick the size that matches each
display context (taskbar, Alt-Tab, Start tile, large-icon view) without
scaling a 32-pixel raster into a 256-pixel blob.

Implementation is **pure Python standard library** (struct + zlib) — no
Pillow, no cairosvg — so the project does not grow a new dependency
just to ship a custom icon.

Anti-aliasing is done via 4x supersampling: each output pixel is the
average of 16 sub-pixels rendered at the target's coordinate space.
That is enough to make the rounded-rect corners and chart-line caps
look crisp at 128x128 and 256x256 without the stair-step artifacts
you get from a plain nearest-neighbor upscaling.

Run as a script::

    python -m app.launcher_icon                       # writes static/launcher.ico
    python -m app.launcher_icon out/path.ico          # writes to a custom path

Regenerate whenever the favicon SVG changes; the design constants in
this file mirror the data URI in ``static/index.html`` and must be
kept in sync.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# Source-of-truth colors must match the data URI in static/index.html.
_BG_RGBA = (0x1F, 0x29, 0x37, 0xFF)    # dark gray
_LINE_RGBA = (0x99, 0xD3, 0x34, 0xFF)  # green (#34d399)
_RECT_RADIUS = 6                       # in source viewBox units (32x32)
_LINE_THICKNESS = 2.5                  # in source viewBox units
_SOURCE_SIZE = 32                      # SVG viewBox edge length

# SVG path "M7 21 l5 -6 4 4 6 -9" -> three line segments.
_LINE_SEGMENTS = (
    (7, 21, 12, 15),
    (12, 15, 16, 19),
    (16, 19, 22, 10),
)

# Standard ICO sizes; Windows picks the closest match to the target DPI.
# 16/32/48 cover taskbar + Alt-Tab; 128/256 cover large-icon / Start tiles.
_DEFAULT_SIZES = (16, 32, 48, 64, 128, 256)

# Supersampling factor. 4 gives clean edges at 256 without being slow.
_AA_FACTOR = 4


def _in_rounded_rect(x: int, y: int, w: int, h: int, r: float) -> bool:
    """True iff the pixel center (x+0.5, y+0.5) is inside a rounded rect."""
    # Use sub-pixel-correct quarter-circle math so the corners stay
    # smooth at high output sizes.
    cx = x + 0.5
    cy = y + 0.5
    if (r <= cx < w - r) or (r <= cy < h - r):
        return True
    if cx < r and cy < r:
        dx, dy = (r - cx), (r - cy)
    elif cx >= w - r and cy < r:
        dx, dy = (cx - (w - r)), (r - cy)
    elif cx < r and cy >= h - r:
        dx, dy = (r - cx), (cy - (h - r))
    else:
        dx, dy = (cx - (w - r)), (cy - (h - r))
    return dx * dx + dy * dy <= r * r


def _scaled_line_pixel_set(
    internal_size: int, scale: float, line_thickness: float
) -> set[tuple[int, int]]:
    """Pixel positions covered by the chart line at the internal scale.

    Includes round end-caps to match the SVG ``stroke-linecap="round"``.
    """
    half = line_thickness / 2.0
    out: set[tuple[int, int]] = set()

    scaled = [
        (x0 * scale, y0 * scale, x1 * scale, y1 * scale)
        for x0, y0, x1, y1 in _LINE_SEGMENTS
    ]

    for x0, y0, x1, y1 in scaled:
        # Segment interior (closest-point distance <= half).
        dx, dy = x1 - x0, y1 - y0
        length_sq = dx * dx + dy * dy
        if length_sq > 0:
            minx = max(0, int(min(x0, x1) - line_thickness) - 1)
            maxx = min(internal_size - 1, int(max(x0, x1) + line_thickness) + 1)
            miny = max(0, int(min(y0, y1) - line_thickness) - 1)
            maxy = min(internal_size - 1, int(max(y0, y1) + line_thickness) + 1)
            for y in range(miny, maxy + 1):
                for x in range(minx, maxx + 1):
                    t = ((x + 0.5 - x0) * dx + (y + 0.5 - y0) * dy) / length_sq
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                    proj_x = x0 + t * dx
                    proj_y = y0 + t * dy
                    if (x + 0.5 - proj_x) ** 2 + (y + 0.5 - proj_y) ** 2 <= half * half:
                        out.add((x, y))

        # Round caps at both endpoints.
        for cx, cy in ((x0, y0), (x1, y1)):
            minx = max(0, int(cx - line_thickness) - 1)
            maxx = min(internal_size - 1, int(cx + line_thickness) + 1)
            miny = max(0, int(cy - line_thickness) - 1)
            maxy = min(internal_size - 1, int(cy + line_thickness) + 1)
            for y in range(miny, maxy + 1):
                for x in range(minx, maxx + 1):
                    if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= half * half:
                        out.add((x, y))

    return out


def _render_internal(
    internal_size: int, scale: float
) -> bytes:
    """Render the favicon design at ``internal_size x internal_size``.

    Returns RGBA pixels (row-major, top-down).
    """
    rect_radius = _RECT_RADIUS * scale
    line_thickness = _LINE_THICKNESS * scale

    line_pixels = _scaled_line_pixel_set(internal_size, scale, line_thickness)

    out = bytearray()
    for y in range(internal_size):
        for x in range(internal_size):
            if _in_rounded_rect(x, y, internal_size, internal_size, rect_radius):
                if (x, y) in line_pixels:
                    out.extend(_LINE_RGBA)
                else:
                    out.extend(_BG_RGBA)
            else:
                out.extend((0, 0, 0, 0))  # transparent
    return bytes(out)


def _downsample_box(
    pixels: bytes, internal_size: int, target_size: int, aa: int
) -> bytes:
    """Box-filter downsample from internal_size to target_size."""
    out = bytearray()
    for ty in range(target_size):
        for tx in range(target_size):
            r_sum = g_sum = b_sum = a_sum = 0
            for dy in range(aa):
                for dx in range(aa):
                    ix = tx * aa + dx
                    iy = ty * aa + dy
                    idx = (iy * internal_size + ix) * 4
                    r, g, b, a = pixels[idx : idx + 4]
                    r_sum += r
                    g_sum += g
                    b_sum += b
                    a_sum += a
            n = aa * aa
            out.extend((r_sum // n, g_sum // n, b_sum // n, a_sum // n))
    return bytes(out)


def render_rgba_pixels(size: int = 32) -> bytes:
    """Render the favicon design at ``size x size`` with AA.

    Uses ``_AA_FACTOR`` supersampling internally and box-filters down
    to the requested size, returning RGBA pixels (row-major, top-down).
    """
    internal = size * _AA_FACTOR
    scale = internal / _SOURCE_SIZE
    internal_pixels = _render_internal(internal, scale)
    return _downsample_box(internal_pixels, internal, size, _AA_FACTOR)


def _make_bmp_image_data(rgba_pixels: bytes, size: int) -> bytes:
    """Encode RGBA pixels as a BMP (BITMAPINFOHEADER + BGRA XOR + AND mask).

    The ICO container expects images bottom-up and biHeight doubled to
    reserve space for an AND mask (zero-filled for 32bpp icons, since
    transparency is carried in the alpha channel).
    """
    bih = struct.pack(
        "<IiiHHIIiiII",
        40,           # biSize
        size,         # biWidth
        size * 2,     # biHeight (image + AND mask slot)
        1,            # biPlanes
        32,           # biBitCount
        0,            # biCompression = BI_RGB
        0,            # biSizeImage
        0, 0, 0, 0,   # XPels, YPels, ClrUsed, ClrImportant
    )

    # XOR mask: BGRA, bottom-up.
    stride = size * 4
    xor_mask = bytearray()
    for y in range(size - 1, -1, -1):
        row = rgba_pixels[y * stride : (y + 1) * stride]
        bgra_row = bytearray()
        for i in range(0, len(row), 4):
            r, g, b, a = row[i : i + 4]
            bgra_row.extend((b, g, r, a))
        xor_mask.extend(bgra_row)

    # AND mask: 1 bit per pixel, zero-filled, padded to 32-bit rows.
    and_mask_row_bytes = ((size + 31) // 32) * 4
    and_mask = bytes(and_mask_row_bytes * size)

    return bih + bytes(xor_mask) + and_mask


def build_launcher_ico(
    sizes: tuple[int, ...] = _DEFAULT_SIZES,
) -> bytes:
    """Render the favicon at each requested size and pack a multi-image ICO.

    Each image is rendered with ``_AA_FACTOR`` supersampling so the
    largest sizes (128, 256) come out crisp. The returned bytes are a
    valid ICO file that Windows / macOS / most Linux DEs can decode.
    """
    rendered: list[tuple[int, bytes]] = []
    for size in sizes:
        rgba = render_rgba_pixels(size)
        rendered.append((size, _make_bmp_image_data(rgba, size)))

    n = len(rendered)
    header_size = 6 + n * 16
    icondir = struct.pack("<HHH", 0, 1, n)  # reserved, type=icon, count

    entries = bytearray()
    body = bytearray()
    for size, image_data in rendered:
        offset = header_size + len(body)
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,                # bColorCount
                0,                # bReserved
                1,                # wPlanes
                32,               # wBitCount
                len(image_data),
                offset,
            )
        )
        body.extend(image_data)

    return icondir + bytes(entries) + bytes(body)


def _cli(argv: list[str]) -> int:
    out_path = Path(argv[1]) if len(argv) > 1 else Path("static/launcher.ico")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(build_launcher_ico())
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
