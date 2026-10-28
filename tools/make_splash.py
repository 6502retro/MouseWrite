"""Build MW.SPLASH: the double hi-res (560x192) title picture for MouseWrite 3.0.

    python3 tools/make_splash.py CHARROM.bin [MW.SPLASH] [preview.png]

CHARROM.bin is an Apple //e enhanced character ROM (4K, e.g. 342-0265-A); its
font is used for all text.  The ROM is Apple's and isn't included here; the
finished picture is in prebuilt/MW.SPLASH.
File layout = 8K aux page + 8K main page, hi-res page layout (like Mouse Calc's
splash).  Needs Pillow only for the preview image."""
import sys

ROM = open(sys.argv[1], 'rb').read()
if len(ROM) == 4096 and ROM[8:16] != bytes([0x08,0x14,0x22,0x22,0x3e,0x22,0x22,0x00]):
    sys.exit('unexpected character ROM layout')
W, H = 560, 192
pix = [[0] * W for _ in range(H)]          # 1 = dot on (white)

def glyph(ch):
    c = ord(ch)
    i = c - 0x40 if 0x40 <= c < 0x60 else c
    return ROM[i * 8:i * 8 + 8]

def text(x, y, s, sx=1, sy=1, color=1, inverse=False):
    for n, ch in enumerate(s):
        g = glyph(ch)
        for r in range(8):
            for b in range(7):
                on = (g[r] >> b) & 1
                if inverse: on ^= 1
                for yy in range(sy):
                    for xx in range(sx):
                        X = x + (n * 7 + b) * sx + xx; Y = y + r * sy + yy
                        if 0 <= X < W and 0 <= Y < H:
                            if inverse or on: pix[Y][X] = on * color if color in (0, 1) else on
    return x + len(s) * 7 * sx

def ctext(y, s, sx=1, sy=1, **k):
    w = len(s) * 7 * sx
    return text((W - w) // 2, y, s, sx, sy, **k)

def rect(x0, y0, x1, y1, v=1):
    for y in range(y0, y1):
        for x in range(x0, x1): pix[y][x] = v

def hline(x0, x1, y, v=1): rect(x0, y, x1, y + 1, v)
def vline(x, y0, y1, v=1, w=2): rect(x, y0, x + w, y1, v)

# DHGR colour fill: colour c (0-15) as its 4-dot pattern, aligned to x % 4
def cfill(x0, y0, x1, y1, c):
    for y in range(y0, y1):
        for x in range(x0, x1): pix[y][x] = (c >> (x % 4)) & 1

# ---------------------------------------------------------------- layout
# menu bar (dark text on white, like MouseWrite's own)
rect(0, 0, W, 9)
text(0, 0, ' MouseWrite  File  Edit  Find  Style   ', sx=2, inverse=True)

# window frame
X0, X1, Y0, Y1 = 14, 546, 13, 189
rect(X0, Y0, X1, Y0 + 2); rect(X0, Y1 - 2, X1, Y1)
vline(X0, Y0, Y1, w=4); vline(X1 - 4, Y0, Y1, w=4)
# title bar: horizontal stripes with a centred title and a close box
for y in range(Y0 + 4, Y0 + 12, 2): hline(X0 + 6, X1 - 6, y)
t = ' MouseWrite 3.0 '
tx = (W - len(t) * 14) // 2
rect(tx, Y0 + 3, tx + len(t) * 14, Y0 + 13, 0)
text(tx, Y0 + 4, t, sx=2)
rect(X0 + 12, Y0 + 3, X0 + 30, Y0 + 13, 0)
rect(X0 + 14, Y0 + 4, X0 + 28, Y0 + 12); rect(X0 + 16, Y0 + 5, X0 + 26, Y0 + 11, 0)
hline(X0 + 4, X1 - 4, Y0 + 14)

# ruler like MouseWrite's
ry = Y0 + 17
for i, n in enumerate('L  2  3  4  5  6  7  R'.split('  ')):
    pass
x = X0 + 14
for col in range(70):
    X = x + col * 7
    if col % 10 == 0:
        rect(X + 2, ry + 9, X + 5, ry + 12)
        if col: text(X - 3, ry, str(col // 10 + 1), sx=2)
    else:
        rect(X + 3, ry + 10, X + 4, ry + 11)
hline(X0 + 4, X1 - 4, ry + 14)

# big logo
ly = Y0 + 36
ctext(ly, 'MouseWrite', sx=4, sy=3)
# colour stripe under the logo (Apple-style rainbow)
sy0 = ly + 27
colours = [12, 13, 9, 1, 3, 6]            # green yellow orange magenta purple blue
seg = 280 // len(colours)
sx0 = (W - seg * len(colours)) // 2
for i, c in enumerate(colours):
    cfill(sx0 + i * seg, sy0, sx0 + (i + 1) * seg, sy0 + 4, c)

ctext(sy0 + 10, 'Word Processing Software', sx=2)
ctext(sy0 + 24, 'by Steve Cochard', sx=2)
ctext(sy0 + 38, 'V: 3.0', sx=2, sy=2)
ctext(sy0 + 62, 'Updated by 6502 Retro 2026', sx=2, sy=2)

# little mouse (left) and page (right)
def mouse(cx, cy):
    rx, ry = 26, 17
    for y in range(-ry, ry + 1):
        for x in range(-rx, rx + 1):
            if (x / rx) ** 2 + (y / ry) ** 2 <= 1: pix[cy + y][cx + x] = 1
            if (x / (rx - 5)) ** 2 + (y / (ry - 2)) ** 2 <= 1: pix[cy + y][cx + x] = 0
    rect(cx - rx + 4, cy - 6, cx + rx - 4, cy - 5)     # button edge
    rect(cx - 1, cy - ry + 2, cx + 2, cy - 5)          # button split
    for i in range(16):                                # cable
        y = cy - ry - i; x = cx + int(10 * (i / 16) ** 2)
        rect(x, y, x + 3, y + 1)
def page(x0, y0):
    rect(x0, y0, x0 + 60, y0 + 36); rect(x0 + 4, y0 + 1, x0 + 56, y0 + 35, 0)
    for i, w in enumerate([44, 38, 44, 28, 44]):
        rect(x0 + 8, y0 + 5 + i * 6, x0 + 8 + w, y0 + 7 + i * 6)
mouse(78, sy0 + 44)
page(450, sy0 + 26)

# copyright
hline(X0 + 4, X1 - 4, Y1 - 22)
ctext(Y1 - 16, '(c)1985-87 Roger Wagner Publishing', sx=2)

# ---------------------------------------------------------------- encode
def rowaddr(y): return (y & 7) * 0x400 + ((y >> 3) & 7) * 0x80 + (y >> 6) * 0x28
aux = bytearray(0x2000); main = bytearray(0x2000)
for y in range(H):
    for k in range(80):
        b = 0
        for i in range(7):
            if pix[y][k * 7 + i]: b |= 1 << i
        (aux if k % 2 == 0 else main)[rowaddr(y) + k // 2] = b
open(sys.argv[2] if len(sys.argv) > 2 else 'MW.SPLASH', 'wb').write(bytes(aux + main))

if len(sys.argv) > 3:
    from PIL import Image
    img = Image.new('1', (W, H))
    img.putdata([pix[y][x] for y in range(H) for x in range(W)])
    img.resize((W, H * 2)).save(sys.argv[3])
print('ok')
