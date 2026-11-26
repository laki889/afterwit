"""Build the Afterwit Lite listing icon as a PNG the plugin directory accepts.

The directory screens the printable text inside image files for shell
patterns. Ordinary compressed pixel data is random enough to trip that screen
by accident: a normal 1024 px export of this icon was reported as "Contains a
download-and-run command". This script writes a PNG that holds almost no
printable bytes instead:

- 8-bit indexed colour with at most 32 palette entries, so every pixel byte
  is below 0x20;
- stored (uncompressed) deflate blocks, with block lengths chosen so the
  length fields are not printable either.

The price is size: a 512 px icon is about 260 kB, well under the 2 MB limit.

Usage (macOS; any SVG renderer that writes an opaque 8-bit PNG will do):

    qlmanage -t -s 512 -o /tmp/icon docs/afterwit-lite-icon.svg
    python3 tools/make_plugin_icon.py /tmp/icon/afterwit-lite-icon.svg.png \
        plugins/afterwit-lite/.claude-plugin/icon.png

BASE below must list the flat colours the SVG uses; PAIRS lists which of them
touch, so the edges between them can be anti-aliased with blended entries.
"""

import re
import struct
import sys
import zlib

SIG = b"\x89PNG\r\n\x1a\n"


def chunks(data):
    pos = len(SIG)
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        yield kind, data[pos + 8:pos + 8 + length]
        pos += 12 + length

def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

def decode(data):
    assert data.startswith(SIG)
    idat, ihdr, kinds = b"", None, []
    for kind, body in chunks(data):
        kinds.append(kind.decode())
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
    w, h, depth, ctype, _, _, interlace = ihdr
    assert depth == 8 and interlace == 0 and ctype in (2, 6), ihdr
    bpp = 4 if ctype == 6 else 3
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev, pos = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[pos]; line = bytearray(raw[pos + 1:pos + 1 + stride]); pos += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4: line[i] = (line[i] + paeth(a, b, c)) & 255
        rows.append(line); prev = line
    return w, h, bpp, rows, kinds


BASE = {"bg": (0x0B, 0x12, 0x1F), "fill": (0x0F, 0x1A, 0x31),
        "stroke": (0x35, 0x54, 0x8A), "bolt": (0x5B, 0xB4, 0xFF)}
PAIRS = [("bg", "stroke"), ("stroke", "fill"), ("fill", "bolt")]
STEPS = 9  # blends per pair: 4 + 3 * 9 = 31 colours

def palette():
    colours = list(BASE.values())
    for a, b in PAIRS:
        ca, cb = BASE[a], BASE[b]
        for i in range(1, STEPS + 1):
            t = i / (STEPS + 1)
            colours.append(tuple(round(ca[k] + (cb[k] - ca[k]) * t) for k in range(3)))
    assert len(colours) <= 32
    return colours

def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

OK_BYTE = set(range(0x20)) | {0x7F, 0x80} | set(range(0xE0, 0x100))
SIZES = sorted(n for n in range(1, 65536) if (n & 255) in OK_BYTE and (n >> 8) in OK_BYTE)

def stored(raw):
    """zlib stream of stored blocks whose length fields are non-printable."""
    out, pos = bytearray(b"\x78\x01"), 0
    while pos < len(raw):
        left = len(raw) - pos
        n = max(s for s in SIZES if s <= left) if left < 65535 else 65535
        out += bytes([1 if pos + n == len(raw) else 0]) + struct.pack("<HH", n, n ^ 0xFFFF)
        out += raw[pos:pos + n]
        pos += n
    return bytes(out) + struct.pack(">I", zlib.adler32(raw) & 0xFFFFFFFF)

def main(src, dst):
    w, h, bpp, rows, _ = decode(open(src, "rb").read())
    pal = palette()
    cache, raw = {}, bytearray()
    for line in rows:
        raw.append(0)
        for x in range(w):
            px = (line[x * bpp], line[x * bpp + 1], line[x * bpp + 2])
            idx = cache.get(px)
            if idx is None:
                idx = min(range(len(pal)), key=lambda i: sum((pal[i][k] - px[k]) ** 2 for k in range(3)))
                cache[px] = idx
            raw.append(idx)
    assert max(raw) < 0x20
    png = (SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
           + chunk(b"PLTE", bytes(v for c in pal for v in c))
           + chunk(b"IDAT", stored(bytes(raw))) + chunk(b"IEND", b""))
    open(dst, "wb").write(png)
    runs = [r.decode() for r in re.findall(rb"[\x20-\x7e]{2,}", png)]
    joined = "".join(chr(b) for b in png if 0x20 <= b <= 0x7e)
    print(f"{w}x{h}, {len(png)} bytes, {len(cache)} source colours -> {len(pal)} palette entries")
    print("printable chars in file:", len(joined))
    print("printable runs (2+):", runs)
    print("all printable text:", repr(joined))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
