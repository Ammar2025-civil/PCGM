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


def dimmed(surf, factor):
    d = pygame.Surface(surf.get_size())
    v = int(255 * factor)
    d.fill((v, v, v))
    surf.blit(d, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return surf


def vtile(surf):
    """Make a texture wrap seamlessly by stacking it on a mirrored copy."""
    w, h = surf.get_size()
    out = pygame.Surface((w, h * 2), surf.get_flags(), surf)
    out.blit(surf, (0, 0))
    out.blit(pygame.transform.flip(surf, False, True), (0, h))
    return out


def textured(w, h, seed, fn, cells=(24, 12, 6), weights=(0.55, 0.3, 0.15), alpha=False):
    """Paint a half-resolution texture from noise with fn(n, x, y) -> colour or None, scaled 2x."""
    hw, hh = w // 2, h // 2
    n = noise(hw, hh, seed, cells, weights)
    s = pygame.Surface((hw, hh), pygame.SRCALPHA if alpha else 0)
    for y in range(hh):
        row = n[y]
        for x in range(hw):
            c = fn(row[x], x, y)
            if c is not None:
                s.set_at((x, y), c)
    return pygame.transform.scale(s, (w, h))


# ====================================================================== 2 asteroid belt
def _giant_col(n, n2, lit, x, y):
    band = (math.sin(y * 0.22 + n * 6) + 1) / 2
    base = ramp([(90, 50, 30), (170, 100, 50), (220, 160, 90), (240, 210, 150)], band * 0.7 + lit * 0.3, x, y)
    if lit < 0.12:
        base = art.mix(base, (20, 10, 20), 0.7)
    return art.mix(base, (30, 20, 30), 0.35)


class AsteroidBelt(Background):
    def setup(self):
        self.base = gradient((16, 10, 14), (34, 22, 26))
        self.planet = sphere(160, 21 + self.level % 4, _giant_col, (0.6, -0.5, 0.5), rim=(255, 180, 120))
        self.far = star_layer(self.level, 60, [(90, 70, 70), (120, 90, 80)])
        key = ('belt_rocks', self.level % 3)
        lay = _cache.get(key)
        if lay is None:
            rnd = random.Random(self.level % 3)
            lay = pygame.Surface((PF_W, PF_H), pygame.SRCALPHA)
            for _ in range(26):
                r = rnd.randint(2, 7)
                rock = art.asteroid_sprite(r, rnd.randrange(50))
                dim = rock.copy()
                dim.fill((60, 60, 70, 0), special_flags=pygame.BLEND_RGBA_SUB)
                lay.blit(dim, (rnd.randrange(PF_W), rnd.randrange(PF_H)))
            _cache[key] = lay
        self.rocks = lay
        self.dust = star_layer(self.level + 9, 50, [(150, 120, 90), (110, 90, 70)])
        self.py = -60

    def update_items(self, scroll):
        self.py += 0.03

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        blit_scroll(surf, self.far, self.off[0])
        surf.blit(self.planet, (PF_W - 150, int(self.py)))
        blit_scroll(surf, self.rocks, self.off[1])
        blit_scroll(surf, self.dust, self.off[2])
        self.draw_near(surf)


# ====================================================================== 3 nebula
def _nebula_fn(n, x, y):
    if n < 0.47:
        return None
    return ramp([(40, 14, 60), (80, 26, 110), (140, 50, 160), (200, 90, 200), (240, 150, 230)], (n - 0.47) / 0.53, x, y)


def _nebula_fn2(n, x, y):
    if n < 0.5:
        return None
    return ramp([(30, 20, 80), (60, 40, 140), (90, 80, 200)], (n - 0.5) / 0.5, x, y)


class Nebula(Background):
    def setup(self):
        self.base = gradient((10, 4, 22), (26, 8, 40))
        key = ('nebula', self.level % 3)
        layers = _cache.get(key)
        if layers is None:
            a = vtile(dimmed(textured(PF_W, PF_H, 300 + self.level % 3, _nebula_fn2, (40, 20, 10), (0.6, 0.3, 0.1), True), 0.6))
            b = vtile(dimmed(textured(PF_W, PF_H, 400 + self.level % 3, _nebula_fn, (30, 14, 6), (0.55, 0.3, 0.15), True), 0.5))
            layers = (a, b)
            _cache[key] = layers
        self.cloud_far, self.cloud_near = layers

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        blit_scroll(surf, self.far, self.off[0])
        blit_scroll(surf, self.cloud_far, self.off[1])
        blit_scroll(surf, self.mid, self.off[1])
        blit_scroll(surf, self.cloud_near, self.off[2])
        self.draw_near(surf)


# ====================================================================== 4 ice moon
def _ice_fn(n, x, y):
    if n < 0.36:
        return ramp([(20, 40, 80), (40, 70, 120)], n / 0.36, x, y)
    if n < 0.42:
        return (90, 140, 190)
    return ramp([(110, 160, 210), (150, 200, 235), (190, 225, 250), (225, 240, 255)], (n - 0.42) / 0.58, x, y)


class IceMoon(Background):
    factors = (0.08, 0.25, 0.6, 1.0, 1.4, 2.0)

    def setup(self):
        key = ('ice', self.level % 3)
        tex = _cache.get(key)
        if tex is None:
            t = textured(PF_W, PF_H, 500 + self.level % 3, _ice_fn, (28, 12, 5), (0.5, 0.33, 0.17))
            rnd = random.Random(self.level)
            for _ in range(14):
                cx, cy, r = rnd.randrange(PF_W), rnd.randrange(PF_H), rnd.randint(6, 20)
                pygame.draw.circle(t, (70, 110, 160), (cx, cy), r)
                pygame.draw.circle(t, (120, 170, 220), (cx - 1, cy - 1), r - 2)
                pygame.draw.arc(t, (230, 245, 255), (cx - r, cy - r, r * 2, r * 2), 3.6, 5.4, 2)
            for _ in range(10):
                x, y = rnd.randrange(PF_W), rnd.randrange(PF_H)
                pts = [(x, y)]
                for _ in range(6):
                    x += rnd.randint(-14, 14)
                    y += rnd.randint(4, 16)
                    pts.append((x, y))
                pygame.draw.lines(t, (40, 70, 120), False, pts, 2)
            dim = pygame.Surface(t.get_size())
            dim.fill((84, 94, 112))
            t.blit(dim, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            tex = vtile(t)
            _cache[key] = tex
        self.ground = tex

    def draw(self, surf, frame):
        blit_scroll(surf, self.ground, self.off[2])
        blit_scroll(surf, self.near, self.off[3])


# ====================================================================== 5 solar flare zone
class SolarZone(Background):
    def setup(self):
        self.base = gradient((60, 14, 10), (24, 6, 12))
        self.far = star_layer(self.level, 40, [(160, 90, 60), (200, 120, 70)])
        self.embers = star_layer(self.level + 3, 70, [(255, 200, 90), (255, 140, 50), (255, 90, 40)])
        self.glow = 0.0

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        blit_scroll(surf, self.far, self.off[0])
        pulse = math.sin(self.t * 0.05) * 4 + self.glow * 30
        cx = PF_W // 2
        for r, col in ((124 + pulse, (80, 22, 10)), (104 + pulse, (140, 42, 14)), (88 + pulse * 0.6, (210, 96, 26)),
                       (78, (255, 164, 56)), (70, (255, 220, 140))):
            pygame.draw.circle(surf, col, (cx, -44), int(r))
        rnd = random.Random(self.t // 6)
        for _ in range(6):
            a = rnd.uniform(0.2, math.pi - 0.2)
            r0 = 70
            x0 = cx + math.cos(a) * r0
            y0 = -44 + math.sin(a) * r0
            ln = rnd.randint(8, 26)
            pygame.draw.line(surf, (255, 200, 90), (int(x0), int(y0)),
                             (int(x0 + math.cos(a) * ln), int(y0 + math.sin(a) * ln)), 2)
        blit_scroll(surf, self.embers, self.off[2])
        self.draw_near(surf)


# ====================================================================== 6 derelict station
def station_tile(seed, palette):
    key = ('stile', seed, palette)
    s = _cache.get(key)
    if s is not None:
        return s
    rnd = random.Random(seed)
    base, dark, light, accent = palette
    s = pygame.Surface((PF_W, PF_H))
    s.fill(base)
    T = 30
    for ty in range(0, PF_H, T):
        for tx in range(-T // 2 + (ty // T % 2) * T // 2, PF_W, T):
            r = pygame.Rect(tx + 1, ty + 1, T - 2, T - 2)
            kind = rnd.random()
            pygame.draw.rect(s, light, r, 1)
            pygame.draw.line(s, dark, r.bottomleft, r.bottomright)
            pygame.draw.line(s, dark, r.topright, r.bottomright)
            if kind < 0.25:
                for i in range(r.left + 3, r.right - 3, 4):
                    pygame.draw.line(s, dark, (i, r.top + 4), (i, r.bottom - 4))
            elif kind < 0.4:
                pygame.draw.circle(s, dark, r.center, 8)
                pygame.draw.circle(s, light, r.center, 8, 1)
                pygame.draw.circle(s, accent, r.center, 2)
            elif kind < 0.5:
                for i in range(-T, T, 6):
                    pygame.draw.line(s, (90, 70, 20), (r.left + i, r.bottom - 2), (r.left + i + 6, r.bottom - 8), 2)
            for cx, cy in ((r.left + 2, r.top + 2), (r.right - 3, r.top + 2), (r.left + 2, r.bottom - 3), (r.right - 3, r.bottom - 3)):
                s.set_at((cx, cy), light)
    for _ in range(4):
        x = rnd.randrange(10, PF_W - 10)
        pygame.draw.line(s, dark, (x, 0), (x, PF_H), 5)
        pygame.draw.line(s, light, (x - 2, 0), (x - 2, PF_H), 1)
    s = vtile(s)
    _cache[key] = s
    return s


class Station(Background):
    PAL = ((40, 42, 52), (24, 24, 32), (62, 66, 80), (255, 150, 40))

    def setup(self):
        self.floor = station_tile(self.level % 2, self.PAL)
        rnd = random.Random(self.level)
        self.lights = [(rnd.randrange(PF_W), rnd.randrange(PF_H * 2), rnd.random()) for _ in range(14)]

    def draw(self, surf, frame):
        blit_scroll(surf, self.floor, self.off[2])
        h = PF_H * 2
        for x, y, ph in self.lights:
            yy = int((y + self.off[2]) % h) - PF_H // 2
            if 0 <= yy < PF_H and (self.t // 20 + int(ph * 10)) % 3:
                surf.fill(self.PAL[3] if ph > 0.5 else (90, 200, 255), (x, yy, 2, 2))


# ====================================================================== 7 black hole rim
def accretion_disk(frame):
    key = ('disk', frame)
    s = _cache.get(key)
    if s is not None:
        return s
    rnd = random.Random(frame)
    w, h = 360, 170
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cols = [(60, 14, 40), (120, 30, 40), (200, 70, 30), (250, 140, 50), (255, 210, 120), (255, 245, 210)]
    for i, c in enumerate(cols):
        rx = 178 - i * 22
        ry = 82 - i * 11
        pygame.draw.ellipse(s, c, (w // 2 - rx, h // 2 - ry, rx * 2, ry * 2))
    for _ in range(140):
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(0.4, 1.0)
        x = w / 2 + math.cos(a) * 176 * rr
        y = h / 2 + math.sin(a) * 80 * rr
        ln = rnd.randint(3, 12)
        pygame.draw.line(s, art.mix(cols[int((1 - rr) * 5)], (0, 0, 0), 0.35), (x, y), (x + ln * -math.sin(a), y + ln * 0.45 * math.cos(a)))
    s = dimmed(s, 0.7)
    _cache[key] = s
    return s


class BlackHole(Background):
    def setup(self):
        self.base = gradient((4, 2, 12), (12, 6, 24))
        self.side = -1
        self.far = star_layer(self.level, 90, [(110, 90, 140), (150, 130, 180), (90, 80, 120)])

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        cx = -40 if self.side < 0 else PF_W + 40
        cy = PF_H // 2 - 20
        blit_scroll(surf, self.far, self.off[0])
        rnd = random.Random(3)
        for i in range(46):
            y = (rnd.randrange(PF_H) + self.t * (0.3 + rnd.random())) % PF_H
            d = rnd.randrange(40, 240)
            x = cx - self.side * d
            ln = max(1, 40 - d // 6)
            col = (170, 130, 220) if d < 110 else (100, 84, 140)
            surf.fill(col, (int(min(x, x + self.side * ln)), int(y), ln, 1))
        disk = accretion_disk((self.t // 8) % 3)
        surf.blit(disk, (cx - disk.get_width() // 2, cy - disk.get_height() // 2))
        pygame.draw.circle(surf, (255, 220, 160), (cx, cy), 58, 2)
        pygame.draw.circle(surf, (0, 0, 0), (cx, cy), 56)
        top = pygame.Rect(0, 0, 220, 60)
        top.center = (cx, cy - 6)
        pygame.draw.arc(surf, (255, 200, 130), top, 0.15, math.pi - 0.15, 2)
        self.draw_near(surf)


# ====================================================================== 8 alien hive
def _hive_fn(n, x, y):
    if 0.48 < n < 0.52:
        return (190, 70, 150)
    if n < 0.48:
        return ramp([(30, 10, 30), (60, 20, 50), (90, 30, 70)], n / 0.48, x, y)
    return ramp([(50, 80, 30), (80, 120, 40), (120, 160, 60)], (n - 0.52) / 0.48, x, y)


class Hive(Background):
    def setup(self):
        key = ('hive', self.level % 3)
        tex = _cache.get(key)
        if tex is None:
            t = textured(PF_W, PF_H, 800 + self.level % 3, _hive_fn, (26, 10, 4), (0.55, 0.3, 0.15))
            rnd = random.Random(self.level)
            for _ in range(16):
                cx, cy, r = rnd.randrange(PF_W), rnd.randrange(PF_H), rnd.randint(5, 13)
                pygame.draw.circle(t, (40, 14, 40), (cx, cy), r + 2)
                pygame.draw.circle(t, (150, 60, 120), (cx, cy), r)
                pygame.draw.circle(t, (230, 120, 190), (cx - r // 3, cy - r // 3), max(1, r // 3))
            dim = pygame.Surface(t.get_size())
            dim.fill((115, 105, 115))
            t.blit(dim, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            tex = vtile(t)
            _cache[key] = tex
        self.ground = tex
        self.pulse = pygame.Surface((PF_W, PF_H))

    def draw(self, surf, frame):
        blit_scroll(surf, self.ground, self.off[2])
        p = (math.sin(self.t * 0.04) + 1) / 2
        self.pulse.fill((int(30 * p), 0, int(24 * p)))
        surf.blit(self.pulse, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


# ====================================================================== 9 wormhole
class Wormhole(Background):
    def setup(self):
        self.base = pygame.Surface((PF_W, PF_H))
        self.base.fill((6, 4, 18))
        self.rings = [i * 0.1 for i in range(10)]
        self.cols = [(255, 80, 200), (90, 220, 255), (160, 90, 255), (255, 240, 140)]

    def update_items(self, scroll):
        spd = 0.004 * (1 + scroll * 1.5) * (1 + self.warp * 4)
        self.rings = [(r + spd) % 1.0 for r in self.rings]

    def draw(self, surf, frame):
        surf.blit(self.base, (0, 0))
        cx = PF_W / 2 + math.sin(self.t * 0.01) * 40
        cy = PF_H * 0.3 + math.cos(self.t * 0.013) * 30
        for i, r in enumerate(sorted(self.rings)):
            k = r * r
            rx = 6 + k * 330
            ry = 4 + k * 260
            col = art.mix((10, 6, 30), self.cols[(i + self.t // 30) % 4], min(0.55, r * 0.8))
            rect = pygame.Rect(0, 0, int(rx * 2), int(ry * 2))
            rect.center = (int(cx), int(cy))
            pygame.draw.ellipse(surf, col, rect, max(1, int(1 + k * 5)))
        blit_scroll(surf, self.mid, self.off[2])
        self.draw_near(surf)


# ====================================================================== 10 mothership core
class Mothership(Background):
    PAL = ((48, 18, 26), (24, 8, 14), (90, 34, 44), (255, 80, 80))

    def setup(self):
        self.floor = station_tile(7 + self.level % 2, self.PAL)
        self.conduits = [random.Random(self.level + i).randrange(20, PF_W - 20) for i in range(3)]

    def draw(self, surf, frame):
        blit_scroll(surf, self.floor, self.off[2])
        for i, x in enumerate(self.conduits):
            surf.fill((20, 6, 10), (x - 4, 0, 9, PF_H))
            surf.fill((120, 20, 30), (x - 2, 0, 5, PF_H))
            for k in range(6):
                y = int((self.t * 3 + k * 70 + i * 23) % (PF_H + 40)) - 20
                surf.fill((190, 60, 60), (x - 1, y, 3, 14))
                surf.fill((240, 140, 130), (x, y + 4, 1, 6))


SECTOR_BG = {1: EarthOrbit, 2: AsteroidBelt, 3: Nebula, 4: IceMoon, 5: SolarZone, 6: Station, 7: BlackHole,
             8: Hive, 9: Wormhole, 10: Mothership}
def make(sector, level):
    cls = SECTOR_BG.get(sector, Background)
    return cls(sector, level)
