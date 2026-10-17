"""All graphics are generated here, in code. Nothing is loaded from disk.

Small sprites are written as ASCII templates (left half + centre column, then
mirrored). Bigger sprites (bosses, rocks) are drawn with the Canvas helper.
Both go through the same shading pass that adds a light top edge, a dark
bottom edge and a 1px outline, which gives the chunky 16-bit look.

Template characters:
  .  empty                 #  body (auto shaded)     1 2 3  body dark/mid/light
  A  accent (auto shaded)  4 5 6  accent dark/mid/light
  M  metal (auto shaded)   7 8 9  metal dark/mid/light
  C  glass (auto shaded)   E e  engine glow / bright glow
  W white  K near-black  R red  Y yellow  G green  B blue  P pink  O orange
"""
import math
import random

import pygame

from config import WHITE

_cache = {}


# ---------------------------------------------------------------- colour helpers
def clamp8(v):
    return 0 if v < 0 else 255 if v > 255 else int(v)


def mix(a, b, t):
    return (clamp8(a[0] + (b[0] - a[0]) * t),
            clamp8(a[1] + (b[1] - a[1]) * t),
            clamp8(a[2] + (b[2] - a[2]) * t))


def scale(c, f):
    return (clamp8(c[0] * f), clamp8(c[1] * f), clamp8(c[2] * f))


def shade3(base):
    """Dark / mid / light ramp with hue-shifted shadows (cooler) and warm lights."""
    r, g, b = base
    dark = (clamp8(r * 0.5), clamp8(g * 0.46), clamp8(b * 0.6 + 22))
    light = mix(base, (255, 250, 232), 0.42)
    return (dark, tuple(base), light)


def make_pal(body, acc, glass=(80, 200, 255), glow=(255, 160, 50),
             glow2=(255, 244, 170), metal=(146, 152, 178), outline=(14, 12, 26)):
    return {
        'body': shade3(body), 'acc': shade3(acc), 'metal': shade3(metal),
        'glass': (mix(glass, (10, 16, 60), 0.45), mix(glass, (255, 255, 255), 0.4)),
        'glow': glow, 'glow2': glow2, 'outline': outline,
    }


FIXED = {
    'W': (255, 255, 255), 'K': (18, 16, 30), 'R': (255, 58, 70), 'Y': (255, 226, 90),
    'G': (110, 255, 130), 'B': (100, 180, 255), 'P': (255, 120, 220), 'O': (255, 140, 40),
}
_GROUP = {}
for _c in '#123':
    _GROUP[_c] = 'body'
for _c in 'A456':
    _GROUP[_c] = 'acc'
for _c in 'M789':
    _GROUP[_c] = 'metal'
_GROUP['C'] = 'glass'


# ---------------------------------------------------------------- sprite pipeline
def grid_from(rows, mirror='odd'):
    if mirror == 'odd':
        rows = [r + r[-2::-1] for r in rows]
    elif mirror == 'even':
        rows = [r + r[::-1] for r in rows]
    w = max(len(r) for r in rows)
    return [r.ljust(w, '.') for r in rows]


def render(grid, pal, outline=True):
    h = len(grid)
    w = len(grid[0]) if h else 0
    pad = 1 if outline else 0
    surf = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)

    def grp(x, y):
        if 0 <= y < h and 0 <= x < w:
            c = grid[y][x]
            if c == '.':
                return None
            return _GROUP.get(c, c)
        return None

    for y in range(h):
        row = grid[y]
        for x in range(w):
            c = row[x]
            if c == '.':
                continue
            if c == 'C':
                col = pal['glass'][1] if grp(x, y - 1) != 'glass' else pal['glass'][0]
            elif c in '#AM':
                g = _GROUP[c]
                sh = pal[g]
                if grp(x, y + 1) != g:
                    col = sh[0]
                elif grp(x, y - 1) != g:
                    col = sh[2]
                else:
                    col = sh[1]
            elif c in '123':
                col = pal['body'][int(c) - 1]
            elif c in '456':
                col = pal['acc'][int(c) - 4]
            elif c in '789':
                col = pal['metal'][int(c) - 7]
            elif c == 'E':
                col = pal['glow']
            elif c == 'e':
                col = pal['glow2']
            else:
                col = FIXED.get(c, (255, 0, 255))
            surf.set_at((x + pad, y + pad), col)
    if outline:
        oc = pal['outline']
        for y in range(-1, h + 1):
            for x in range(-1, w + 1):
                if grp(x, y) is not None:
                    continue
                if grp(x - 1, y) or grp(x + 1, y) or grp(x, y - 1) or grp(x, y + 1):
                    surf.set_at((x + pad, y + pad), oc)
    return surf


def sprite(rows, pal, mirror='odd', outline=True):
    return render(grid_from(rows, mirror), pal, outline)


class Canvas:
    """Region-grid drawing for big procedural sprites (bosses, rocks)."""

    def __init__(self, w, h, mirror=True):
        self.w, self.h, self.mirror = w, h, mirror
        self.g = [['.'] * w for _ in range(h)]

    def put(self, x, y, ch):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = ch
            if self.mirror:
                self.g[y][self.w - 1 - x] = ch

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.g[y][x]
        return '.'

    def rect(self, x, y, w, h, ch):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.put(xx, yy, ch)

    def ellipse(self, cx, cy, rx, ry, ch):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx = (x + 0.5 - cx) / max(rx, 0.1)
                dy = (y + 0.5 - cy) / max(ry, 0.1)
                if dx * dx + dy * dy <= 1.0:
                    self.put(x, y, ch)

    def ring(self, cx, cy, r0, r1, ch):
        for y in range(int(cy - r1) - 1, int(cy + r1) + 2):
            for x in range(int(cx - r1) - 1, int(cx + r1) + 2):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if r0 <= d <= r1:
                    self.put(x, y, ch)

    def poly(self, pts, ch):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        n = len(pts)
        for y in range(int(min(ys)), int(max(ys)) + 1):
            for x in range(int(min(xs)), int(max(xs)) + 1):
                px, py = x + 0.5, y + 0.5
                inside = False
                j = n - 1
                for i in range(n):
                    xi, yi = pts[i]
                    xj, yj = pts[j]
                    if (yi > py) != (yj > py):
                        if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                            inside = not inside
                    j = i
                if inside:
                    self.put(x, y, ch)

    def line(self, x0, y0, x1, y1, ch):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(steps + 1):
            t = i / max(steps, 1)
            self.put(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), ch)

    def replace_in(self, x, y, w, h, src, dst):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                if self.get(xx, yy) == src:
                    self.put(xx, yy, dst)

    def rows(self):
        return [''.join(r) for r in self.g]

    def surface(self, pal, outline=True):
        return render(self.rows(), pal, outline)


def flip_v(s):
    return pygame.transform.flip(s, False, True)


def white(s):
    key = ('white', id(s))
    w = _cache.get(key)
    if w is None:
        m = pygame.mask.from_surface(s)
        w = m.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        _cache[key] = w
        _cache[('keep', id(s))] = s   # keep id stable
    return w


def tinted(s, color, amount=0.55):
    key = ('tint', id(s), color, amount)
    t = _cache.get(key)
    if t is None:
        t = s.copy()
        over = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        over.fill((*color, int(255 * amount)))
        mask = pygame.mask.from_surface(s).to_surface(setcolor=(255, 255, 255, 255),
                                                       unsetcolor=(0, 0, 0, 0))
        over.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        t.blit(over, (0, 0))
        _cache[key] = t
        _cache[('keep', id(s))] = s
    return t


def silhouette(s, color):
    m = pygame.mask.from_surface(s)
    return m.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))


def outlined(s, color):
    """Return s with an extra 1px coloured outline (used for glows)."""
    w, h = s.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    sil = silhouette(s, color)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (dx, dy))
    out.blit(s, (1, 1))
    return out


# ---------------------------------------------------------------- pixel font
_FONT_SRC = {
    'A': ".###.|#...#|#...#|#####|#...#|#...#|#...#",
    'B': "####.|#...#|#...#|####.|#...#|#...#|####.",
    'C': ".###.|#...#|#....|#....|#....|#...#|.###.",
    'D': "####.|#...#|#...#|#...#|#...#|#...#|####.",
    'E': "#####|#....|#....|####.|#....|#....|#####",
    'F': "#####|#....|#....|####.|#....|#....|#....",
    'G': ".###.|#...#|#....|#.###|#...#|#...#|.####",
    'H': "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    'I': "###|.#.|.#.|.#.|.#.|.#.|###",
    'J': "..###|...#.|...#.|...#.|#..#.|#..#.|.##..",
    'K': "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#",
    'L': "#....|#....|#....|#....|#....|#....|#####",
    'M': "#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#",
    'N': "#...#|##..#|#.#.#|#..##|#...#|#...#|#...#",
    'O': ".###.|#...#|#...#|#...#|#...#|#...#|.###.",
    'P': "####.|#...#|#...#|####.|#....|#....|#....",
    'Q': ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#",
    'R': "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    'S': ".####|#....|#....|.###.|....#|....#|####.",
    'T': "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    'U': "#...#|#...#|#...#|#...#|#...#|#...#|.###.",
    'V': "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
    'W': "#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#",
    'X': "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    'Y': "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..",
    'Z': "#####|....#|...#.|..#..|.#...|#....|#####",
    '0': ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.",
    '1': ".#.|##.|.#.|.#.|.#.|.#.|###",
    '2': ".###.|#...#|....#|...#.|..#..|.#...|#####",
    '3': "####.|....#|....#|.###.|....#|....#|####.",
    '4': "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.",
    '5': "#####|#....|####.|....#|....#|#...#|.###.",
    '6': ".###.|#....|#....|####.|#...#|#...#|.###.",
    '7': "#####|....#|...#.|..#..|.#...|.#...|.#...",
    '8': ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    '9': ".###.|#...#|#...#|.####|....#|....#|.###.",
    ' ': "...|...|...|...|...|...|...",
    '.': ".|.|.|.|.|.|#",
    ',': "..|..|..|..|..|.#|#.",
    ':': ".|#|.|.|.|#|.",
    ';': "..|.#|..|..|..|.#|#.",
    '!': "#|#|#|#|#|.|#",
    '?': ".###.|#...#|....#|...#.|..#..|.....|..#..",
    '-': "...|...|...|###|...|...|...",
    '+': ".....|..#..|..#..|#####|..#..|..#..|.....",
    '×': ".....|.....|#...#|.#.#.|..#..|.#.#.|#...#",
    '/': "....#|...#.|...#.|..#..|.#...|.#...|#....",
    '%': "##..#|##..#|...#.|..#..|.#...|#..##|#..##",
    '(': ".#|#.|#.|#.|#.|#.|.#",
    ')': "#.|.#|.#|.#|.#|.#|#.",
    "'": "#|#|.|.|.|.|.",
    '"': "#.#|#.#|...|...|...|...|...",
    '>': "#...|.#..|..#.|...#|..#.|.#..|#...",
    '<': "...#|..#.|.#..|#...|.#..|..#.|...#",
    '*': "..#..|..#..|#####|.###.|.#.#.|#...#|.....",
    '=': ".....|.....|#####|.....|#####|.....|.....",
    '_': ".....|.....|.....|.....|.....|.....|#####",
    '[': "##|#.|#.|#.|#.|#.|##",
    ']': "##|.#|.#|.#|.#|.#|##",
    '$': "..#..|.####|#.#..|.###.|..#.#|####.|..#..",
    '#': ".#.#.|#####|.#.#.|.#.#.|.#.#.|#####|.#.#.",
    '^': "..#..|.###.|#.#.#|..#..|..#..|..#..|..#..",
    '~': ".....|.....|.#...|#.#.#|...#.|.....|.....",
}
FONT = {k: v.split('|') for k, v in _FONT_SRC.items()}
GLYPH_H = 7


def glyph_w(ch):
    g = FONT.get(ch) or FONT.get(ch.upper()) or FONT['?']
    return len(g[0])


def text_width(s, sc=1):
    if not s:
        return 0
    return sum((glyph_w(c) + 1) * sc for c in s) - sc


def _glyph_surface(ch, color, sc):
    key = ('g', ch, color, sc)
    s = _cache.get(key)
    if s is None:
        g = FONT.get(ch) or FONT.get(ch.upper()) or FONT['?']
        w = len(g[0])
        s = pygame.Surface((w * sc, GLYPH_H * sc), pygame.SRCALPHA)
        for y, row in enumerate(g):
            for x, c in enumerate(row):
                if c == '#':
                    s.fill(color, (x * sc, y * sc, sc, sc))
        _cache[key] = s
    return s


_text_cache = {}


def text_surface(s, color=WHITE, sc=1, shadow=(10, 8, 22)):
    key = (s, color, sc, shadow)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 3000:
            _text_cache.clear()
        w = max(1, text_width(s, sc))
        extra = sc if shadow else 0
        surf = pygame.Surface((w + extra, GLYPH_H * sc + extra), pygame.SRCALPHA)
        for pass_col, off in (((shadow, extra),) if shadow else ()) + ((color, 0),):
            x = 0
            for ch in s:
                surf.blit(_glyph_surface(ch, pass_col, sc), (x + off, off))
                x += (glyph_w(ch) + 1) * sc
        _text_cache[key] = surf
    return surf


def text(surf, s, x, y, color=WHITE, sc=1, align='l', shadow=(10, 8, 22)):
    ts = text_surface(str(s), color, sc, shadow)
    if align == 'c':
        x -= ts.get_width() // 2
    elif align == 'r':
        x -= ts.get_width()
    surf.blit(ts, (int(x), int(y)))
    return ts.get_width()


def big_text(s, sc, top, bottom, outline=(10, 8, 22), outline2=None):
    """Large title text with a vertical gradient and a thick outline."""
    key = ('big', s, sc, top, bottom, outline, outline2)
    surf = _cache.get(key)
    if surf is None:
        base = text_surface(s, WHITE, sc, None)
        w, h = base.get_size()
        grad = pygame.Surface((w, h), pygame.SRCALPHA)
        bands = max(1, h // sc)
        for i in range(bands):
            c = mix(top, bottom, i / max(1, bands - 1))
            grad.fill((*c, 255), (0, i * sc, w, sc))
        grad.blit(base, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        pad = 3
        surf = pygame.Surface((w + pad * 2, h + pad * 2 + 2), pygame.SRCALPHA)
        sil = silhouette(base, outline)
        if outline2:
            sil2 = silhouette(base, outline2)
            for dx in range(-2, 3):
                for dy in range(-2, 5):
                    surf.blit(sil2, (pad + dx, pad + dy))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1, 2):
                surf.blit(sil, (pad + dx, pad + dy))
        surf.blit(grad, (pad, pad))
        _cache[key] = surf
    return surf


# ---------------------------------------------------------------- palettes
# Enemy palettes per sector (index 0 unused). Bullet colours chosen to pop
# against that sector's background.
SECTOR_STYLE = {
    1: dict(body=(186, 58, 74), acc=(250, 168, 56), glass=(110, 230, 255),
            bullets=((255, 90, 160), (255, 150, 60)), ui=(90, 170, 255)),
    2: dict(body=(170, 116, 76), acc=(150, 220, 80), glass=(255, 220, 120),
            bullets=((255, 80, 150), (120, 255, 200)), ui=(230, 170, 90)),
    3: dict(body=(140, 64, 196), acc=(255, 110, 180), glass=(140, 255, 220),
            bullets=((255, 240, 120), (120, 255, 255)), ui=(210, 120, 255)),
    4: dict(body=(86, 140, 196), acc=(220, 250, 255), glass=(255, 120, 160),
            bullets=((255, 120, 50), (255, 70, 120)), ui=(150, 230, 255)),
    5: dict(body=(196, 74, 36), acc=(255, 220, 70), glass=(90, 40, 30),
            bullets=((120, 240, 255), (255, 255, 255)), ui=(255, 170, 60)),
    6: dict(body=(130, 138, 150), acc=(255, 150, 30), glass=(255, 60, 60),
            bullets=((255, 80, 220), (255, 200, 60)), ui=(200, 210, 220)),
    7: dict(body=(70, 64, 130), acc=(240, 80, 220), glass=(255, 240, 120),
            bullets=((255, 230, 90), (255, 110, 200)), ui=(190, 120, 255)),
    8: dict(body=(104, 168, 64), acc=(160, 70, 200), glass=(255, 230, 60),
            bullets=((255, 90, 170), (255, 170, 60)), ui=(140, 230, 90)),
    9: dict(body=(56, 156, 170), acc=(255, 80, 200), glass=(255, 255, 160),
            bullets=((255, 255, 140), (255, 120, 255)), ui=(90, 240, 230)),
    10: dict(body=(130, 36, 52), acc=(255, 196, 60), glass=(100, 255, 240),
             bullets=((90, 230, 255), (255, 90, 170)), ui=(255, 90, 90)),
}

GOLD_PAL = make_pal((236, 180, 40), (255, 240, 140), glass=(255, 255, 255),
                    glow=(255, 255, 200), metal=(200, 160, 60), outline=(60, 30, 0))


def sector_pal(sector):
    st = SECTOR_STYLE[sector]
    key = ('spal', sector)
    p = _cache.get(key)
    if p is None:
        p = make_pal(st['body'], st['acc'], glass=st['glass'])
        _cache[key] = p
    return p


# ---------------------------------------------------------------- player hulls
# Each hull: template (left half + centre col), palette, and anchor points for
# attachments measured from the hull sprite centre (after outline).
HULL_ART = {
    'falcon': dict(
        rows=[
            "........#",
            ".......##",
            ".......##",
            ".......#C",
            "......##C",
            "......#CC",
            "......##C",
            "......###",
            ".6...####",
            ".A..##1##",
            ".A.###1##",
            ".A####1##",
            "AA###4###",
            "A####4###",
            "A###.A###",
            "......MM.",
        ],
        pal=dict(body=(214, 222, 240), acc=(226, 60, 70), glass=(80, 200, 255)),
    ),
    'bulwark': dict(
        rows=[
            ".........##",
            "........###",
            "........##C",
            "...44..##CC",
            "..4AA4.##CC",
            "..AAAA###C#",
            ".AAAAA#####",
            ".AA6AA#####",
            ".AAAAA##1##",
            ".AAAAA#####",
            "..AAA.##1##",
            "..MM..#####",
            "..MM...###.",
            ".......MM..",
        ],
        pal=dict(body=(120, 150, 90), acc=(196, 170, 96), glass=(255, 210, 80)),
    ),
    'prospector': dict(
        rows=[
            "...6.....#",
            "...A....##",
            "..AA...###",
            "..A...##CC",
            "..A..###CC",
            "..AA.##CCC",
            "...A###CCC",
            "...A####CC",
            "...######C",
            "..#######3",
            ".##4######",
            ".##4######",
            "..##....##",
            "...MM..MM.",
        ],
        pal=dict(body=(230, 150, 50), acc=(130, 130, 150), glass=(120, 240, 255)),
    ),
    'wraith': dict(
        rows=[
            ".......#",
            ".......#",
            "......##",
            "......#C",
            "......#C",
            "..6...#C",
            "..AA..##",
            "...AA.##",
            "....AA##",
            "....A###",
            "...AA###",
            "..AA..##",
            ".AA...M#",
            "......M.",
        ],
        pal=dict(body=(90, 70, 150), acc=(170, 110, 255), glass=(255, 90, 200)),
    ),
    'prism': dict(
        rows=[
            "........C",
            ".......CC",
            "......C#C",
            ".....C##C",
            "....C###C",
            "...C####C",
            "..A#####C",
            ".AA####3C",
            "AAAA###3C",
            ".AA####3C",
            "..A#####C",
            "...#####.",
            "....#M#..",
            ".....M...",
        ],
        pal=dict(body=(70, 190, 210), acc=(230, 250, 255), glass=(160, 255, 255)),
    ),
    'helios': dict(
        rows=[
            "...........#",
            "..........##",
            "..........#C",
            "..........#C",
            "4444444..##C",
            "AAAAAAA.###C",
            "A5A5A5A####3",
            "AAAAAAA#####",
            "4444444.####",
            ".........M##",
            "..........M.",
        ],
        pal=dict(body=(240, 196, 70), acc=(60, 90, 200), glass=(255, 120, 60)),
    ),
    'breacher': dict(
        rows=[
            "........MM",
            ".......MMM",
            ".......M##",
            "......####",
            "......##CC",
            "..A...##CC",
            ".AA..#####",
            ".AA.######",
            ".A########",
            ".A##4#####",
            ".A##4##4##",
            ".AA.######",
            "..A..#MM#.",
            "......MM..",
        ],
        pal=dict(body=(200, 60, 50), acc=(240, 200, 80), glass=(100, 230, 255)),
    ),
    'singularity': dict(
        rows=[
            ".........#",
            "....AAA.##",
            "...A...###",
            "..A...##CC",
            ".A....#CCC",
            ".A...##CC#",
            ".A...#####",
            ".A...#####",
            "..A..#####",
            "...A######",
            "....AAA###",
            ".......M#.",
            ".......M..",
        ],
        pal=dict(body=(60, 50, 90), acc=(220, 90, 255), glass=(255, 240, 120)),
    ),
    'swarmlord': dict(
        rows=[
            "..6.......",
            "..A.......",
            "...A....##",
            "...AA..###",
            "....A.##CC",
            ".....###CC",
            "..A.####C#",
            ".AA#######",
            "AA..######",
            "A..#######",
            "..A.##44##",
            ".AA..#####",
            "......#M#.",
            ".......M..",
        ],
        pal=dict(body=(90, 170, 70), acc=(200, 230, 90), glass=(255, 80, 80)),
    ),
    'phase': dict(
        rows=[
            "...6.....",
            "...#.....",
            "...#.....",
            "..###....",
            "..#C#....",
            "..#C#....",
            "..###..#.",
            "..###.###",
            ".####A#C#",
            ".###AA#C#",
            ".##AAA###",
            "..AAAA###",
            "...M..#M.",
            "...M...M.",
        ],
        pal=dict(body=(50, 170, 170), acc=(240, 70, 180), glass=(255, 255, 255)),
    ),
    'sovereign': dict(
        rows=[
            "............#",
            "............3",
            "...........##",
            "...........#C",
            "..........##C",
            "...6......#CC",
            "...A.....##CC",
            "..AA....###CC",
            "..A6A..####C#",
            ".AAAA.######3",
            ".A6AA#######3",
            "AAAA########3",
            "A.AA###44####",
            "...A##4..4###",
            "....#M....#M#",
            ".....M.....M.",
        ],
        pal=dict(body=(240, 240, 250), acc=(240, 190, 50), glass=(150, 90, 255)),
    ),
    'starborn': dict(
        rows=[
            "........6",
            "........A",
            ".......#A",
            ".......#C",
            "..6...##C",
            "...A..#CC",
            "....A.##C",
            "....A####",
            "6AAAA####",
            "....A####",
            "....A.###",
            "...A..#1#",
            "..6...MM#",
            "......M..",
        ],
        pal=dict(body=(52, 50, 96), acc=(255, 220, 110), glass=(255, 255, 255)),
    ),
}

STARBORN_PAL = dict(body=(40, 40, 70), acc=(255, 230, 120), glass=(255, 255, 255))


def hull_palette(hull_id, paint=None):
    base = HULL_ART[hull_id]['pal']
    if paint == 'gold':
        return make_pal((236, 186, 50), (255, 245, 160), glass=base['glass'],
                        metal=(210, 170, 70), outline=(50, 26, 0))
    return make_pal(base['body'], base['acc'], glass=base['glass'])


def hull_sprite(hull_id, paint=None):
    key = ('hull', hull_id, paint)
    s = _cache.get(key)
    if s is None:
        s = sprite(HULL_ART[hull_id]['rows'], hull_palette(hull_id, paint))
        _cache[key] = s
    return s


def hull_geometry(hull_id):
    """Anchors measured from the hull sprite itself so every part sits on the hull."""
    key = ('geo', hull_id)
    g = _cache.get(key)
    if g is not None:
        return g
    s = hull_sprite(hull_id)
    w, h = s.get_size()
    m = pygame.mask.from_surface(s)
    cx, cy = w / 2.0, h / 2.0
    # widest row in the lower 70% = wing line
    best_y, best_w = h // 2, 0
    for y in range(int(h * 0.3), h):
        xs = [x for x in range(w) if m.get_at((x, y))]
        if xs and (xs[-1] - xs[0]) > best_w:
            best_w, best_y = xs[-1] - xs[0], y
    top = next((y for y in range(h) if any(m.get_at((x, y)) for x in range(w))), 0)
    bottom = next((y for y in range(h - 1, -1, -1) if any(m.get_at((x, y)) for x in range(w))), h - 1)
    g = dict(
        w=w, h=h,
        nose=(0, top - cy + 1),
        wing=(best_w / 2.0 + 1, best_y - cy - 1),
        under=(max(3, best_w / 4.0), best_y - cy + 2),
        tail=(0, bottom - cy),
        engines=[(-2.5, bottom - cy + 1), (2.5, bottom - cy + 1)],
    )
    _cache[key] = g
    return g


# ---------------------------------------------------------------- ship parts
PART_PAL = make_pal((150, 156, 180), (255, 150, 40), glass=(120, 240, 255),
                    glow=(255, 170, 60), metal=(120, 126, 150))
PART_ROWS = {
    # nose cannons (spread levels 2..5) - centred
    'nose2': ["9..", "M..", "M#.", "MA#"],
    'nose3': ["9..9", "M..M", "M..M", "MA#M", ".A##"],
    'nose4': ["9...9", "M.9.M", "M.M.M", "MAMAM", "#AAA#", ".###A"],
    'nose5': ["e...e.", "9...9.", "M.e.M.", "M.M.M9", "MAMAMM", "#AAA#M", ".####A"],
    # wing pods (left side, mirrored for right)
    'wing1': [".9.", ".M.", "#A#", "#A#", "#A#", ".M."],
    'wing2': [".9.9.", ".M.M.", "#MAM#", "#AAA#", "#A6A#", ".#M#."],
    'wing3': [".9.9.9.", ".M.M.M.", "#M#M#M#", "#AAAAA#", "#A666A#", "#AAAAA#", ".##M##."],
    # missile racks (left side)
    'missile1': ["R.R", "W.W", "8.8", "7.7"],
    'missile2': ["R.R.R", "W.W.W", "8.8.8", "7.7.7", "MMMMM"],
    'missile3': ["R.R.R.R", "W.W.W.W", "8.8.8.8", "8.8.8.8", "7.7.7.7", "MMMMMMM"],
    # laser lens - centred
    'laser1': [".C", "CC"],
    'laser2': ["..C", ".CC", "MCC"],
    'laser3': ["...C", "..CC", ".CCC", "MMCC"],
    # rear guns - centred, pointing down
    'rear1': ["M#", ".M", ".M"],
    'rear2': ["MA#", "MAM", ".7M", "..M"],
    'rear3': ["MAA#", "MAAA", "M.MM", "7..M", "...M"],
    # magnet coils (left side)
    'magnet': ["Y.", "Y4", "YA", "YA", "Y."],
}
_PART_MIRROR = {'nose': 'odd', 'laser': 'odd', 'rear': 'odd', 'wing': None,
                'missile': None, 'magnet': None}


def part_sprite(name, hull='falcon', paint=None):
    """Parts are tinted with the hull's own colours so every ship keeps its identity."""
    key = ('part', name, hull, paint)
    s = _cache.get(key)
    if s is None:
        stem = name.rstrip('0123456789')
        mirror = _PART_MIRROR.get(stem)
        if paint == 'gold':
            pal = hull_palette(hull, 'gold')
        else:
            base = HULL_ART[hull]['pal']
            pal = make_pal(base['body'], base['acc'], glass=(120, 240, 255), glow=(255, 170, 60),
                           metal=(132, 138, 164))
        s = sprite(PART_ROWS[name], pal, mirror=mirror)
        _cache[key] = s
    return s


DRONE_ROWS = ["..##", ".#CC", "##CW", "#AAA", ".#M.", "..E."]


def drone_sprite():
    s = _cache.get('drone')
    if s is None:
        s = sprite(DRONE_ROWS, make_pal((170, 180, 210), (80, 150, 255), glass=(120, 255, 200)),
                   mirror='even')
        _cache['drone'] = s
    return s


# ---------------------------------------------------------------- enemies
# Authored facing UP, flipped to face down when used.
ENEMY_ROWS = {
    'dart': [
        "....#",
        "...##",
        "...#C",
        "..##C",
        ".A###",
        "AA.##",
        "A...M",
    ],
    'gunner': [
        ".M....",
        ".M..##",
        "####CC",
        "#AA#CC",
        "#AA###",
        "######",
        ".#4.##",
        "..M..M",
    ],
    'heavy': [
        ".M..M...",
        ".M..M###",
        "#####CCC",
        "##A##CCC",
        "#AAA####",
        "##A#####",
        "####1###",
        ".##.4###",
        "..M.4.MM",
    ],
    'weaver': [
        "......#",
        "A....##",
        "AA..##C",
        ".AA.##C",
        "..AA###",
        "...A###",
        "..AA.##",
        ".AA...M",
    ],
    'kamikaze': [
        "....A",
        "..A.#",
        "...##",
        ".A#RR",
        "..##R",
        "...##",
        "..A.#",
        "....A",
    ],
    'splitter': [
        ".##....",
        "#CC#..#",
        "####.##",
        "#AA#.#C",
        ".##.###",
        "....AAA",
        ".....A.",
    ],
    'shielded': [
        "..MMMMM",
        ".M.....",
        "...####",
        "..##CC#",
        ".#####C",
        "#AA####",
        "#AA##AA",
        ".#..#..",
    ],
    'sniper': [
        "...9",
        "...M",
        "...M",
        "...M",
        "..##",
        "..#C",
        ".##C",
        ".###",
        "A###",
        "A.##",
        "A.##",
        "..#M",
    ],
    'minelayer': [
        "....####",
        "..###CCC",
        ".####CCC",
        "####AA##",
        "#..#####",
        "....#RRR",
        ".....#R.",
    ],
    'carrier': [
        ".....####",
        "....##CC#",
        "...######",
        ".AA###YYY",
        "AAA##YYYY",
        "AAA##YYYY",
        ".AA###YYY",
        "...######",
        "....M..M.",
    ],
    'golden': [
        "......#",
        ".....##",
        "#...##C",
        "##.###C",
        ".######",
        "..#####",
        ".##.###",
        "#....M.",
    ],
    'larva': [
        "..A.",
        ".#.A",
        "####",
        "#CC#",
        ".###",
        "..#.",
    ],
    'mini': [
        "..#",
        ".#C",
        "A##",
        "A.M",
    ],
    'turret': [
        "..###",
        ".#####",
        "##CC##",
        "#CRRC#",
        "#CRRC#",
        "##CC##",
        ".#####",
        "..###",
    ],
}
_ENEMY_MIRROR = {'turret': 'even', 'larva': 'even'}


def enemy_sprite(kind, sector):
    key = ('enemy', kind, sector)
    s = _cache.get(key)
    if s is None:
        pal = GOLD_PAL if kind == 'golden' else sector_pal(sector)
        if kind == 'nest':
            s = nest_sprite(sector)
        else:
            s = flip_v(sprite(ENEMY_ROWS[kind], pal, mirror=_ENEMY_MIRROR.get(kind, 'odd')))
        _cache[key] = s
    return s


def nest_sprite(sector):
    pal = make_pal((150, 60, 120), (220, 200, 90), glass=(255, 90, 90))
    rnd = random.Random(77)
    c = Canvas(22, 20, mirror=True)
    c.ellipse(11, 11, 10, 8.5, '#')
    for _ in range(5):
        x = rnd.uniform(3, 9)
        y = rnd.uniform(4, 16)
        c.ellipse(x, y, 2.2, 1.6, 'A')
    c.ellipse(11, 10, 4, 3.6, 'K')
    c.ellipse(11, 10, 2.6, 2.4, 'R')
    c.put(10, 9, 'Y')
    c.rect(2, 16, 3, 3, '4')
    return c.surface(pal)


def asteroid_sprite(size, seed, ore=False):
    """Lumpy rock; size is the radius in pixels."""
    key = ('rock', size, seed, ore)
    s = _cache.get(key)
    if s is None:
        rnd = random.Random(seed * 31 + size)
        d = size * 2 + 2
        c = Canvas(d, d, mirror=False)
        pts = []
        n = 9 + size // 2
        for i in range(n):
            a = i / n * math.tau
            r = size * rnd.uniform(0.72, 1.0)
            pts.append((d / 2 + math.cos(a) * r, d / 2 + math.sin(a) * r))
        c.poly(pts, '#')
        for _ in range(max(1, size // 3)):
            cx = d / 2 + rnd.uniform(-size * 0.5, size * 0.5)
            cy = d / 2 + rnd.uniform(-size * 0.5, size * 0.5)
            r = rnd.uniform(1.0, max(1.5, size * 0.28))
            for y in range(int(cy - r), int(cy + r) + 1):
                for x in range(int(cx - r), int(cx + r) + 1):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= r * r and c.get(x, y) == '#':
                        c.put(x, y, '1' if y < cy else '3')
        if ore:
            for _ in range(max(2, size // 2)):
                x = int(d / 2 + rnd.uniform(-size * 0.6, size * 0.6))
                y = int(d / 2 + rnd.uniform(-size * 0.6, size * 0.6))
                if c.get(x, y) != '.':
                    c.put(x, y, 'G')
                    if c.get(x + 1, y) != '.':
                        c.put(x + 1, y, '6')
        pal = make_pal((138, 112, 92), (120, 240, 140))
        s = c.surface(pal)
        _cache[key] = s
    return s


def crystal_sprite(w, h, seed):
    key = ('crystal', w, h, seed)
    s = _cache.get(key)
    if s is None:
        rnd = random.Random(seed)
        c = Canvas(w, h, mirror=False)
        c.poly([(w / 2, 0), (w, h * 0.35), (w * 0.8, h), (w * 0.2, h), (0, h * 0.35)], 'A')
        c.line(w / 2, 1, w / 2, h - 2, '6')
        for _ in range(3):
            x = rnd.uniform(w * 0.25, w * 0.75)
            c.line(x, h * 0.3, x + rnd.uniform(-2, 2), h * 0.9, '4')
        pal = make_pal((150, 220, 255), (170, 230, 255))
        s = c.surface(pal, outline=True)
        _cache[key] = s
    return s


def debris_sprite(w, h, seed):
    key = ('debris', w, h, seed)
    s = _cache.get(key)
    if s is None:
        rnd = random.Random(seed)
        c = Canvas(w, h, mirror=False)
        pts = [(rnd.uniform(0, w * 0.3), rnd.uniform(0, h * 0.3)),
               (rnd.uniform(w * 0.7, w), rnd.uniform(0, h * 0.4)),
               (rnd.uniform(w * 0.6, w), rnd.uniform(h * 0.7, h)),
               (rnd.uniform(0, w * 0.4), rnd.uniform(h * 0.6, h))]
        c.poly(pts, 'M')
        for _ in range(3):
            c.rect(rnd.randint(1, max(1, w - 4)), rnd.randint(1, max(1, h - 4)), 2, 2, '7')
        c.line(w * 0.2, h * 0.5, w * 0.8, h * 0.5, '4')
        pal = make_pal((90, 80, 90), (255, 120, 40), metal=(110, 100, 110))
        s = c.surface(pal)
        _cache[key] = s
    return s


# ---------------------------------------------------------------- bullets
def orb(r, color):
    key = ('orb', r, color)
    s = _cache.get(key)
    if s is None:
        size = r * 2 + 3
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(s, scale(color, 0.45), (c, c), r + 1)
        pygame.draw.circle(s, color, (c, c), r)
        if r >= 2:
            pygame.draw.circle(s, mix(color, WHITE, 0.55), (c, c), max(1, r - 1))
        pygame.draw.circle(s, WHITE, (c, c), max(1, r // 2))
        _cache[key] = s
    return s


def needle(length, color):
    key = ('needle', length, color)
    s = _cache.get(key)
    if s is None:
        s = pygame.Surface((5, length + 2), pygame.SRCALPHA)
        s.fill(scale(color, 0.5), (0, 1, 5, length))
        s.fill(color, (1, 0, 3, length + 2))
        s.fill(WHITE, (2, 1, 1, length))
        _cache[key] = s
    return s


def player_shot(kind):
    key = ('pshot', kind)
    s = _cache.get(key)
    if s is not None:
        return s
    if kind == 'main':
        s = pygame.Surface((3, 9), pygame.SRCALPHA)
        s.fill((255, 170, 40), (0, 2, 3, 7))
        s.fill((255, 240, 150), (0, 0, 3, 5))
        s.fill(WHITE, (1, 0, 1, 4))
    elif kind == 'main_big':
        s = pygame.Surface((5, 11), pygame.SRCALPHA)
        s.fill((255, 120, 30), (0, 3, 5, 8))
        s.fill((255, 230, 120), (1, 0, 3, 8))
        s.fill(WHITE, (2, 0, 1, 6))
    elif kind == 'spread':
        s = pygame.Surface((4, 4), pygame.SRCALPHA)
        s.fill((255, 200, 70))
        s.fill(WHITE, (1, 1, 2, 2))
    elif kind == 'wing':
        s = pygame.Surface((3, 7), pygame.SRCALPHA)
        s.fill((60, 200, 255), (0, 1, 3, 6))
        s.fill((200, 250, 255), (1, 0, 1, 6))
    elif kind == 'rear':
        s = pygame.Surface((3, 6), pygame.SRCALPHA)
        s.fill((120, 255, 140), (0, 0, 3, 6))
        s.fill(WHITE, (1, 1, 1, 4))
    elif kind == 'drone':
        s = pygame.Surface((2, 5), pygame.SRCALPHA)
        s.fill((150, 220, 255))
        s.fill(WHITE, (0, 0, 2, 2))
    elif kind == 'missile':
        s = sprite(["W", "9", "8", "R"], PART_PAL, mirror=None, outline=True)
    else:
        s = pygame.Surface((3, 3), pygame.SRCALPHA)
        s.fill(WHITE)
    _cache[key] = s
    return s


def mine_sprite(color):
    key = ('mine', color)
    s = _cache.get(key)
    if s is None:
        s = pygame.Surface((11, 11), pygame.SRCALPHA)
        pygame.draw.circle(s, (40, 36, 50), (5, 5), 4)
        pygame.draw.circle(s, (90, 86, 100), (5, 5), 3)
        for dx, dy in ((0, -5), (0, 5), (-5, 0), (5, 0)):
            s.fill((90, 86, 100), (5 + dx - (1 if dx else 0) // 2, 5 + dy, 1, 1))
        s.fill(color, (4, 4, 3, 3))
        _cache[key] = s
    return s


# ---------------------------------------------------------------- pickups & icons
PICKUP_STYLE = {
    'spread': ('S', (255, 140, 40)), 'wing': ('W', (255, 140, 40)),
    'missile': ('M', (255, 140, 40)), 'laser': ('L', (255, 140, 40)),
    'rear': ('R', (255, 140, 40)), 'drone': ('D', (90, 200, 255)),
    'shield': ('O', (90, 160, 255)), 'repair': ('+', (90, 230, 120)),
    'bomb': ('B', (255, 90, 90)), 'magnet': ('U', (255, 220, 60)),
    'overdrive': ('!', (255, 40, 60)), 'bounty': ('$', (200, 90, 255)),
}


def pickup_sprite(kind, frame=0):
    key = ('pick', kind, frame)
    s = _cache.get(key)
    if s is None:
        letter, col = PICKUP_STYLE[kind]
        s = pygame.Surface((15, 15), pygame.SRCALPHA)
        dark = scale(col, 0.4)
        pygame.draw.rect(s, (14, 12, 26), (0, 0, 15, 15), border_radius=4)
        pygame.draw.rect(s, col, (1, 1, 13, 13), border_radius=3)
        pygame.draw.rect(s, dark, (2, 2, 11, 11), border_radius=2)
        if kind in ('overdrive', 'bounty'):
            for i in range(-12, 14, 4):
                pygame.draw.line(s, scale(col, 0.7), (2 + i, 12), (12 + i, 2))
            pygame.draw.rect(s, dark, (4, 3, 7, 9))
        if frame:
            pygame.draw.line(s, mix(col, WHITE, 0.6), (2, 3), (3, 2))
            pygame.draw.line(s, WHITE, (3, 2), (6, 2))
        g = text_surface(letter, WHITE, 1, (10, 8, 22))
        s.blit(g, (8 - g.get_width() // 2, 4))
        _cache[key] = s
    return s


def coin_sprite(kind):
    key = ('coin', kind)
    s = _cache.get(key)
    if s is None:
        if kind == 'small':
            s = pygame.Surface((5, 5), pygame.SRCALPHA)
            pygame.draw.circle(s, (120, 90, 10), (2, 2), 2)
            s.fill((255, 210, 60), (1, 1, 2, 2))
            s.fill(WHITE, (1, 1, 1, 1))
        elif kind == 'big':
            s = pygame.Surface((9, 9), pygame.SRCALPHA)
            pygame.draw.circle(s, (120, 80, 0), (4, 4), 4)
            pygame.draw.circle(s, (255, 196, 40), (4, 4), 3)
            s.fill((255, 240, 150), (3, 2, 2, 4))
            s.fill(WHITE, (3, 2, 1, 2))
        elif kind == 'gem':
            s = pygame.Surface((9, 11), pygame.SRCALPHA)
            pygame.draw.polygon(s, (20, 90, 120), [(4, 0), (8, 4), (4, 10), (0, 4)])
            pygame.draw.polygon(s, (90, 230, 255), [(4, 1), (7, 4), (4, 9), (1, 4)])
            pygame.draw.line(s, WHITE, (3, 3), (4, 2))
        elif kind == 'ore':
            s = pygame.Surface((7, 7), pygame.SRCALPHA)
            pygame.draw.polygon(s, (20, 80, 40), [(3, 0), (6, 3), (3, 6), (0, 3)])
            pygame.draw.polygon(s, (110, 255, 140), [(3, 1), (5, 3), (3, 5), (1, 3)])
            s.fill(WHITE, (3, 2, 1, 1))
        else:
            s = pygame.Surface((3, 3), pygame.SRCALPHA)
            s.fill(WHITE)
        _cache[key] = s
    return s


ICON_ROWS = {
    'heart': [".##.##.", "#######", "#######", ".#####.", "..###..", "...#..."],
    'shield': [".#####.", "#.....#", "#.....#", "#.....#", ".#...#.", "..###.."],
    'bomb': ["....#.", "...#..", ".###..", "#####.", "#####.", ".###.."],
    'star': ["...#...", "..###..", "#######", ".#####.", ".##.##.", "#.....#"],
    'lock': [".###.", "#...#", "#...#", "#####", "##.##", "#####"],
}


def icon(name, color):
    key = ('icon', name, color)
    s = _cache.get(key)
    if s is None:
        rows = ICON_ROWS[name]
        s = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
        for y, r in enumerate(rows):
            for x, ch in enumerate(r):
                if ch == '#':
                    s.set_at((x, y), color)
        s = outlined(s, (10, 8, 22))
        _cache[key] = s
    return s


def clear_cache():
    _cache.clear()
    _text_cache.clear()
