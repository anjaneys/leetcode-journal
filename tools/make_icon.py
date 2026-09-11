"""Generate assets/lc.ico and assets/lc.png - a LeetCode-orange record button.

Pure standard library (zlib + struct), so no imaging dependency is needed.
The ICO embeds PNG frames, which Windows has supported since Vista.

    python tools/make_icon.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

BG = (40, 40, 40)
DOT = (255, 161, 22)  # LeetCode orange
SUPERSAMPLE = 4


def _sample(u: float, v: float):
    """RGBA at normalised coordinates: rounded dark square, orange dot."""
    margin, radius = 0.06, 0.22
    lo, hi = margin, 1 - margin
    if not (lo <= u <= hi and lo <= v <= hi):
        return None
    cx = min(max(u, lo + radius), hi - radius)
    cy = min(max(v, lo + radius), hi - radius)
    if (u - cx) ** 2 + (v - cy) ** 2 > radius ** 2:
        return None
    if (u - 0.5) ** 2 + (v - 0.5) ** 2 <= 0.27 ** 2:
        return DOT
    return BG


def _pixels(size: int) -> bytes:
    rows = bytearray()
    n = SUPERSAMPLE * SUPERSAMPLE
    for y in range(size):
        rows.append(0)  # PNG filter type: none
        for x in range(size):
            r = g = b = hits = 0
            for sy in range(SUPERSAMPLE):
                for sx in range(SUPERSAMPLE):
                    c = _sample((x + (sx + 0.5) / SUPERSAMPLE) / size,
                                (y + (sy + 0.5) / SUPERSAMPLE) / size)
                    if c:
                        r, g, b, hits = r + c[0], g + c[1], b + c[2], hits + 1
            if hits:
                rows += bytes((r // hits, g // hits, b // hits, 255 * hits // n))
            else:
                rows += b"\0\0\0\0"
    return bytes(rows)


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def png(size: int) -> bytes:
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(_pixels(size), 9)) + _chunk(b"IEND", b""))


def ico(sizes=(16, 32, 48, 256)) -> bytes:
    frames = [png(s) for s in sizes]
    out = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    for size, data in zip(sizes, frames):
        dim = 0 if size >= 256 else size  # 0 means 256 in an ICO entry
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return out + b"".join(frames)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "lc.ico").write_bytes(ico())
    (ASSETS / "lc.png").write_bytes(png(64))
    print("wrote", ASSETS / "lc.ico", "and", ASSETS / "lc.png")


if __name__ == "__main__":
    main()
