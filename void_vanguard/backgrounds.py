"""Parallax backgrounds for the 10 sectors, all generated in code."""
import math
import random

import pygame

import art
from config import PF_W, PF_H

BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
_cache = {}


def dith(v, x, y, levels):
    """Ordered-dither a 0..1 value into an integer 0..levels-1."""
    t = (BAYER4[y & 3][x & 3] + 0.5) / 16.0
    i = int(v * (levels - 1) + t)
    return 0 if i < 0 else (levels - 1 if i >= levels else i)


def noise(w, h, seed, cells=(48, 24, 12), weights=(0.55, 0.3, 0.15)):
    """Smooth value noise as a list of rows of floats 0..1 (fractal sum of octaves)."""
    rnd = random.Random(seed)
    acc = [[0.0] * w for _ in range(h)]
    for cell, wt in zip(cells, weights):
        gw, gh = w // cell + 3, h // cell + 3
        small = pygame.Surface((gw, gh))
        for yy in range(gh):
            for xx in range(gw):
                v = rnd.randint(0, 255)
                small.set_at((xx, yy), (v, v, v))
        big = pygame.transform.smoothscale(small, (gw * cell, gh * cell))
        ox, oy = rnd.randint(0, cell), rnd.randint(0, cell)
        for yy in range(h):
            row = acc[yy]
            for xx in range(w):
                row[xx] += big.get_at((xx + ox, yy + oy))[0] / 255.0 * wt
    return acc


def gradient(top, bottom, w=PF_W, h=PF_H, bands=24):
    s = pygame.Surface((w, h))
    for y in range(h):
        t = y / (h - 1)
        # banded + dithered for a retro look
        tb = round(t * bands) / bands
        c1 = art.mix(top, bottom, tb)
        s.fill(c1, (0, y, w, 1))
        tb2 = min(1.0, tb + 1.0 / bands)
        c2 = art.mix(top, bottom, tb2)
        frac = (t - tb) * bands
        if frac > 0:
            for x in range(0, w, 1):
                if (BAYER4[y & 3][x & 3] + 0.5) / 16.0 < frac:
                    s.set_at((x, y), c2)
    return s


def star_layer(seed, count, colors, big=0, w=PF_W, h=PF_H):
    rnd = random.Random(seed)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(count):
        x, y = rnd.randrange(w), rnd.randrange(h)
        s.set_at((x, y), rnd.choice(colors))
    for _ in range(big):
        x, y = rnd.randrange(2, w - 2), rnd.randrange(2, h - 2)
        c = rnd.choice(colors)
        s.set_at((x, y), (255, 255, 255))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s.set_at((x + dx, y + dy), c)
    return s


def blit_scroll(surf, layer, offset, x=0):
    h = layer.get_height()
    y = int(offset) % h
    surf.blit(layer, (x, y))
    surf.blit(layer, (x, y - h))


def sphere(radius, seed, color_fn, light=(-0.55, -0.6, 0.6), rim=None, half=True):
    """Dithered shaded sphere. color_fn(n, n2, lit, x, y) -> colour."""
    key = ('sphere', radius, seed, id(color_fn), light, rim)
    s = _cache.get(key)
    if s is not None:
        return s
    r = radius // 2 if half else radius
    d = r * 2 + 4
    nmap = noise(d, d, seed, (max(6, r // 3), max(3, r // 6), 3), (0.6, 0.28, 0.12))
    nmap2 = noise(d, d, seed + 99, (max(5, r // 4), 4), (0.7, 0.3))
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    lx, ly, lz = light
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ln, ly / ln, lz / ln
    for y in range(d):
        for x in range(d):
            nx = (x - d / 2 + 0.5) / r
            ny = (y - d / 2 + 0.5) / r
            q = nx * nx + ny * ny
            if q > 1.0:
                if rim and q < 1.12:
                    if (BAYER4[y & 3][x & 3] + 0.5) / 16.0 < (1.12 - q) / 0.12:
                        s.set_at((x, y), rim)
                continue
            nz = math.sqrt(1.0 - q)
            lit = max(0.0, nx * lx + ny * ly + nz * lz)
            col = color_fn(nmap[y][x], nmap2[y][x], lit, x, y)
            if rim and nz < 0.28:
                col = art.mix(col, rim, (0.28 - nz) / 0.28 * 0.7)
            s.set_at((x, y), col)
    if half:
        s = pygame.transform.scale(s, (d * 2, d * 2))
    _cache[key] = s
    return s


def ramp(cols, v, x, y):
    return cols[dith(v, x, y, len(cols))]


# ====================================================================== base
class Background:
    speed_factor = 1.0

    def __init__(self, sector, level):
        self.sector = sector
        self.level = level
        self.rnd = random.Random(level * 101 + sector)
        self.t = 0
        self.off = [0.0] * 6
        self.factors = (0.08, 0.25, 0.6, 1.0, 1.4, 2.0)
        self.items = []
        self.warp = 0.0          # 0..1 warp streak strength (wormhole)
        self.base = gradient((6, 8, 22), (16, 18, 44))
        self.far = star_layer(level, 70, [(70, 80, 120), (90, 90, 140), (60, 70, 110)])
        self.mid = star_layer(level + 1, 40, [(150, 160, 210), (120, 140, 200), (200, 200, 230)], 4)
        self.near = star_layer(level + 2, 14, [(255, 255, 255), (200, 220, 255)], 3)
        self.setup()

    def setup(self):
        pass

    def update(self, scroll):
        self.t += 1
        for i, f in enumerate(self.factors):
            self.off[i] += scroll * f * self.speed_factor
        self.update_items(scroll)

    def update_items(self, scroll):
        pass

    def draw_stars(self, surf):
        blit_scroll(surf, self.far, self.off[0])
        blit_scroll(surf, self.mid, self.off[1])

    def draw_near(self, surf):
        blit_scroll(surf, self.near, self.off[3])
        if self.warp > 0.05:
            rnd = random.Random(self.t // 2)
            n = int(30 * self.warp)
            for _ in range(n):
                x = rnd.randrange(PF_W)
                y = rnd.randrange(PF_H)
                ln = int(10 + 50 * self.warp * rnd.random())
                c = rnd.choice(((180, 220, 255), (255, 160, 255), (255, 255, 255)))
                surf.fill(c, (x, y, 1, ln))

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        self.draw_stars(surf)
        self.draw_near(surf)


# ====================================================================== 1 earth orbit
def _earth_col(n, n2, lit, x, y):
    if n2 > 0.6:
        base = ramp([(60, 70, 110), (150, 160, 200), (230, 236, 250), (255, 255, 255)], min(1.0, lit * 1.1), x, y)
    elif n < 0.5:
        base = ramp([(8, 16, 50), (16, 40, 110), (30, 80, 170), (60, 140, 220)], lit, x, y)
    elif n < 0.6:
        base = ramp([(14, 40, 20), (40, 100, 40), (80, 150, 60), (130, 190, 90)], lit, x, y)
    else:
        base = ramp([(40, 30, 20), (110, 80, 50), (160, 130, 80), (200, 180, 120)], lit, x, y)
    if lit < 0.08:
        base = art.mix(base, (6, 8, 20), 0.75)
    return art.mix(base, (8, 12, 40), 0.3)


def satellite_sprite(seed):
    key = ('sat', seed)
    s = _cache.get(key)
    if s is None:
        rnd = random.Random(seed)
        w = rnd.choice((25, 29, 33))
        c = art.Canvas(w, 13, mirror=True)
        c.rect(0, 4, w // 2 - 3, 5, 'A')
        for x in range(1, w // 2 - 3, 3):
            c.rect(x, 4, 1, 5, '4')
        c.rect(w // 2 - 3, 5, 3, 3, 'M')
        c.ellipse(w / 2, 6.5, 3.5, 5, '#')
        c.put(w // 2, 0, 'M')
        c.put(w // 2, 1, 'M')
        c.put(w // 2, 3, 'R')
        pal = art.make_pal((200, 200, 210), (50, 80, 170), metal=(150, 150, 170))
        s = c.surface(pal)
        s = pygame.transform.rotate(s, rnd.choice((0, 90, 0, 0)))
        dim = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 30, 90))
        s.blit(dim, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        _cache[key] = s
    return s


class EarthOrbit(Background):
    def setup(self):
        self.base = gradient((4, 6, 20), (12, 18, 46))
        side = 1 if self.level % 2 else -1
        self.planet = sphere(200, 7 + self.level % 3, _earth_col, (-0.5 * side, -0.7, 0.5), rim=(120, 190, 255))
        pw = self.planet.get_width()
        self.px = PF_W / 2 + side * 80 - pw / 2
        self.py = PF_H - 150
        self.sat_t = 60

    def update_items(self, scroll):
        self.py += 0.022
        self.sat_t -= 1
        if self.sat_t <= 0:
            self.sat_t = self.rnd.randint(260, 520)
            s = satellite_sprite(self.rnd.randrange(1000))
            self.items.append([s, self.rnd.uniform(-10, PF_W - 20), -s.get_height(), self.rnd.uniform(-0.12, 0.12)])
        for it in self.items:
            it[2] += scroll * 0.55
            it[1] += it[3]
        self.items = [it for it in self.items if it[2] < PF_H + 10]

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        self.draw_stars(surf)
        surf.blit(self.planet, (int(self.px), int(self.py)))
        for s, x, y, _ in self.items:
            surf.blit(s, (int(x), int(y)))
        self.draw_near(surf)


SECTOR_BG = {1: EarthOrbit}


def make(sector, level):
    cls = SECTOR_BG.get(sector, Background)
    return cls(sector, level)
