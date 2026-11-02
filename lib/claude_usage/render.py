"""PNG helpers for SwiftBar dropdown rows. Pillow optional: text rows fall back to plain SwiftBar text."""
import base64, struct, zlib

try:
    from PIL import Image, ImageDraw, ImageFont
    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False

ACTION = " bash=/usr/bin/true terminal=false refresh=true"


def png(w, h, px):
    rows = b"".join(b"\0" + bytes(px[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    ck = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + ck(b"pHYs", struct.pack(">IIB", 5669, 5669, 1)) + ck(b"IDAT", zlib.compress(rows)) + ck(b"IEND", b"")).decode()


def bar(p, w=80, h=12):
    """Retina pill as template PNG (alpha only): faint track, solid fill. macOS tints it."""
    p, r = min(max(p, 0), 1), h / 2
    fx = w * p
    px = bytearray()
    for y in range(h):
        for x in range(w):
            cx = min(max(x + .5, r), w - r)
            inside = min(max(r - ((x + .5 - cx) ** 2 + (y + .5 - r) ** 2) ** .5 + .5, 0), 1)
            fill = min(max(fx - x, 0), 1)
            px += bytes((0, 0, 0, round(255 * inside * (.3 + .7 * fill))))
    return png(w, h, px)


def chart(vals, hi, w=300, h=56, color=(217, 119, 87)):
    """Colored column chart @2x. hi = index drawn at full strength; others dimmed."""
    n, m = len(vals), max(max(vals), 1)
    px = bytearray(w * h * 4)
    gap = 3
    bw = max((w - gap * (n - 1)) // n, 1)
    x0 = (w - (bw * n + gap * (n - 1))) // 2
    for i, v in enumerate(vals):
        bh = max(round((h - 2) * v / m), 2 if v else 1)
        a = 255 if i == hi else 130
        for x in range(x0 + i * (bw + gap), x0 + i * (bw + gap) + bw):
            for y in range(h - bh, h):
                o = (y * w + x) * 4
                px[o:o + 4] = bytes((*color, a if v else 50))
    return png(w, h, px)


def row(text, size=12, mono=False, pct=None, w=300):
    """Text as a white PNG so macOS can't dim it. Without Pillow: plain text line."""
    if not HAVE_PIL:
        prefix = f"{'█' * round(10 * min(max(pct or 0, 0), 1))}{'░' * (10 - round(10 * min(max(pct or 0, 0), 1)))} " if pct is not None else ""
        return f"{prefix}{text} | size={size}{' font=Menlo' if mono else ''}{ACTION}"
    import io
    k = 2
    try:
        f = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc" if mono else "/System/Library/Fonts/SFNS.ttf", size * k)
    except Exception:
        f = ImageFont.load_default()
    h = (size + 8) * k
    im = Image.new("RGBA", (w * k, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 0
    if pct is not None:
        bw, bh = 60 * k, 8 * k
        y = (h - bh) // 2
        d.rounded_rectangle((0, y, bw, y + bh), bh // 2, fill=(255, 255, 255, 70))
        if pct > 0:
            d.rounded_rectangle((0, y, max(bw * min(pct, 1), bh), y + bh), bh // 2, fill=(255, 255, 255, 255))
        x = bw + 8 * k
    d.text((x, h // 2), text, font=f, fill=(255, 255, 255, 255), anchor="lm")
    b = io.BytesIO(); im.save(b, "PNG", dpi=(144, 144))
    return f"| image={base64.b64encode(b.getvalue()).decode()} width={w} height={size + 8}{ACTION}"


def fmt(n):
    n = n or 0
    return f"{n/1e9:.2f}B" if n >= 1e9 else f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}K" if n >= 1e3 else str(int(n))


def money(x):
    return f"${x:,.2f}" if x >= 1 else f"${x:.3f}"
