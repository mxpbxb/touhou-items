"""Makes the Max Doll Point's texture: the Doll Point's (thkaguyamod:item/point_item) with a yellow
border round its edge.

    python3 -I tools/make_max_doll_point.py <thkaguyamod.hmod> <out.png> [preview.png]

Reads the hmod as data only. Plain Python (zlib), no image library.
"""
import struct
import sys
import zipfile
import zlib

YELLOW = (255, 216, 0, 255)
EDGE = (176, 128, 0, 255)  # darker yellow on the outer edge, so the border reads on light slots


def read_png(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, plte, trns = 8, b"", None, None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            plte = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat += body
    assert depth == 8 and interlace == 0, (depth, interlace)
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * chans
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - chans] if x >= chans else 0
            b = prev[x]
            c = prev[x - chans] if x >= chans else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    px = []
    for line in rows:
        out = []
        for x in range(w):
            v = line[x * chans:(x + 1) * chans]
            if ctype == 6:
                out.append(tuple(v))
            elif ctype == 2:
                out.append((*v, 255))
            elif ctype == 4:
                out.append((v[0], v[0], v[0], v[1]))
            elif ctype == 0:
                out.append((v[0], v[0], v[0], 255))
            else:
                idx = v[0]
                alpha = trns[idx] if trns and idx < len(trns) else 255
                out.append((*plte[idx], alpha))
        px.append(out)
    return w, h, px


def write_png(w, h, px):
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def bordered(w, h, px):
    """A yellow border hugging the picture: the clear pixels next to it (sides or corners) turn
    yellow, the ring outside that dark yellow. The picture itself is unchanged."""
    def near(x, y, r):
        return any(0 <= x + dx < w and 0 <= y + dy < h and px[y + dy][x + dx][3] >= 128
                   for dy in range(-r, r + 1) for dx in range(-r, r + 1))

    out = [row[:] for row in px]
    for y in range(h):
        for x in range(w):
            if px[y][x][3] >= 128:
                continue
            if near(x, y, 1):
                out[y][x] = YELLOW
            elif near(x, y, 2):
                out[y][x] = EDGE
    return out


def main():
    z = zipfile.ZipFile(sys.argv[1])
    w, h, px = read_png(z.read("assets/thkaguyamod/textures/item/point_item.png"))
    out = bordered(w, h, px)
    with open(sys.argv[2], "wb") as f:
        f.write(write_png(w, h, out))
    if len(sys.argv) > 3:  # 8x preview, source and result side by side
        s = 8
        big = [[(40, 40, 40, 255) if p[3] == 0 else p for p in (row[x // s] for x in range(w * s))]
               for row in (r for r in px for _ in range(s))]
        big2 = [[(40, 40, 40, 255) if p[3] == 0 else p for p in (row[x // s] for x in range(w * s))]
                for row in (r for r in out for _ in range(s))]
        side = [a + [(255, 255, 255, 255)] * 8 + b for a, b in zip(big, big2)]
        with open(sys.argv[3], "wb") as f:
            f.write(write_png(len(side[0]), len(side), side))
    print("opaque edge pixels in source:", sum(1 for y in range(h) for x in range(w)
                                               if px[y][x][3] and min(x, y, w - 1 - x, h - 1 - y) == 0))


main()
