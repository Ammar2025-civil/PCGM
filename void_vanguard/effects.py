"""Particles, chunky explosions, debris, shockwaves, popups, screen shake and hitstop."""
import math
import random

import pygame

import art
from config import PF_W, PF_H, WHITE

FIRE = [(255, 255, 255), (255, 244, 160), (255, 200, 60), (255, 130, 40),
        (230, 60, 40), (140, 30, 50), (70, 20, 50)]


def fire_color(frac):
    """frac 1 = fresh, 0 = dying."""
    i = int((1.0 - frac) * (len(FIRE) - 1))
    return FIRE[max(0, min(len(FIRE) - 1, i))]


class Effects:
    MAX_PARTS = 1100

    def __init__(self):
        self.parts = []     # [x, y, vx, vy, life, max, size, color, kind, drag]
        self.rings = []     # [x, y, r, growth, life, max, color, width]
        self.debris = []    # [surf, x, y, vx, vy, life, spin_timer, frame]
        self.popups = []    # [x, y, surf, life, max]
        self.flashes = []   # [x, y, r, life, max]
        self.trauma = 0.0
        self.hitstop = 0
        self.flash = 0
        self.flash_max = 1
        self.flash_color = WHITE
        self.rnd = random.Random()
        self._overlay = pygame.Surface((PF_W, PF_H))

    # ------------------------------------------------------------ API
    def shake(self, amount):
        self.trauma = min(1.0, self.trauma + amount)

    def freeze(self, frames):
        self.hitstop = max(self.hitstop, frames)

    def screen_flash(self, frames=8, color=WHITE):
        self.flash = frames
        self.flash_max = frames
        self.flash_color = color

    def offset(self):
        if self.trauma <= 0.01:
            return 0, 0
        m = 7.0 * self.trauma * self.trauma
        return int(self.rnd.uniform(-m, m)), int(self.rnd.uniform(-m, m))

    def particle(self, x, y, vx, vy, life, size, color, kind='sq', drag=0.94):
        if len(self.parts) < self.MAX_PARTS:
            self.parts.append([x, y, vx, vy, life, life, size, color, kind, drag])

    def sparks(self, x, y, n, color, speed=2.5, life=14):
        r = self.rnd
        for _ in range(n):
            a = r.uniform(0, math.tau)
            s = r.uniform(0.4, 1.0) * speed
            self.particle(x, y, math.cos(a) * s, math.sin(a) * s, r.randint(life // 2, life),
                          1, color, 'spark', 0.9)

    def hit_spark(self, x, y, color=(255, 240, 160)):
        r = self.rnd
        for _ in range(3):
            a = r.uniform(math.pi * 1.1, math.pi * 1.9)
            s = r.uniform(1.0, 2.6)
            self.particle(x, y, math.cos(a) * s, math.sin(a) * s, r.randint(5, 10), 1, color, 'spark', 0.85)

    def ring(self, x, y, r0, growth, life, color=WHITE, width=2):
        self.rings.append([x, y, r0, growth, life, life, color, width])

    def popup(self, x, y, s, color=WHITE, life=45, sc=1):
        surf = art.text_surface(str(s), color, sc)
        self.popups.append([x - surf.get_width() / 2, y, surf, life, life])

    def explosion(self, x, y, size='s', sprite=None, colors=None):
        r = self.rnd
        cfg = {
            's': (10, 6, 2, 0.10, 7, 0),
            'm': (22, 12, 5, 0.22, 12, 1),
            'l': (40, 20, 10, 0.45, 18, 2),
            'xl': (80, 36, 20, 0.85, 28, 3),
        }[size]
        n_chunks, n_sparks, n_smoke, shake, flash_r, rings = cfg
        self.flashes.append([x, y, flash_r, 5, 5])
        for _ in range(n_chunks):
            a = r.uniform(0, math.tau)
            s = r.uniform(0.3, 1.0) * (1.6 + flash_r * 0.11)
            life = r.randint(14, 30 + flash_r)
            sz = r.choice((2, 2, 3, 3, 4)) + (1 if size in ('l', 'xl') else 0)
            col = r.choice(colors) if colors and r.random() < 0.35 else None
            self.particle(x, y, math.cos(a) * s, math.sin(a) * s, life, sz,
                          col, 'fire' if col is None else 'sq', 0.93)
        self.sparks(x, y, n_sparks, (255, 240, 170), 2.5 + flash_r * 0.12, 16)
        for _ in range(n_smoke):
            a = r.uniform(0, math.tau)
            s = r.uniform(0.1, 0.6)
            self.particle(x + r.uniform(-4, 4), y + r.uniform(-4, 4), math.cos(a) * s,
                          math.sin(a) * s - 0.1, r.randint(26, 50), r.randint(3, 5 + flash_r // 4),
                          (52, 44, 66), 'smoke', 0.96)
        for i in range(rings):
            self.ring(x, y, 3 + i * 4, 1.6 + i * 0.9, 16 + i * 6, (255, 230, 170), 2 if i == 0 else 1)
        if sprite is not None:
            self.shatter(sprite, x, y, 4 if size == 's' else 6 if size == 'm' else 10)
        self.shake(shake)

    def shatter(self, sprite, x, y, pieces=6):
        """Cut a sprite into chunks and fling them."""
        r = self.rnd
        w, h = sprite.get_size()
        if w < 4 or h < 4:
            return
        for _ in range(pieces):
            pw = r.randint(3, max(3, w // 2))
            ph = r.randint(3, max(3, h // 2))
            px = r.randint(0, max(0, w - pw))
            py = r.randint(0, max(0, h - ph))
            try:
                chunk = sprite.subsurface((px, py, pw, ph)).copy()
            except ValueError:
                continue
            a = math.atan2(py + ph / 2 - h / 2, px + pw / 2 - w / 2) + r.uniform(-0.5, 0.5)
            s = r.uniform(0.8, 2.6)
            self.debris.append([chunk, x + px - w / 2, y + py - h / 2, math.cos(a) * s,
                                math.sin(a) * s, r.randint(30, 60), r.randint(4, 9), 0])

    def bomb_wave(self, x, y):
        self.ring(x, y, 4, 6.5, 40, WHITE, 4)
        self.ring(x, y, 2, 4.5, 46, (255, 220, 120), 2)
        self.ring(x, y, 1, 3.0, 52, (255, 120, 60), 1)
        self.sparks(x, y, 50, (255, 240, 200), 6, 30)
        self.screen_flash(14)
        self.shake(0.7)
        self.freeze(5)

    # ------------------------------------------------------------ update/draw
    def update(self):
        self.trauma = max(0.0, self.trauma - 0.022)
        if self.flash > 0:
            self.flash -= 1
        parts = self.parts
        for p in parts:
            p[2] *= p[9]
            p[3] *= p[9]
            p[0] += p[2]
            p[1] += p[3]
            p[4] -= 1
        if parts:
            self.parts = [p for p in parts if p[4] > 0]
        for g in self.rings:
            g[2] += g[3]
            g[3] *= 0.97
            g[4] -= 1
        self.rings = [g for g in self.rings if g[4] > 0]
        for d in self.debris:
            d[1] += d[3]
            d[2] += d[4]
            d[3] *= 0.97
            d[4] = d[4] * 0.97 + 0.03
            d[5] -= 1
            d[6] -= 1
            if d[6] <= 0:
                d[6] = 6
                d[0] = pygame.transform.rotate(d[0], 90)
        self.debris = [d for d in self.debris if d[5] > 0]
        for p in self.popups:
            p[1] -= 0.45 if p[3] > p[4] * 0.4 else 0.1
            p[3] -= 1
        self.popups = [p for p in self.popups if p[3] > 0]
        for f in self.flashes:
            f[3] -= 1
        self.flashes = [f for f in self.flashes if f[3] > 0]

    def draw(self, surf):
        fill = surf.fill
        for d in self.debris:
            if d[5] > 12 or d[5] % 4 < 2:
                surf.blit(d[0], (int(d[1]), int(d[2])))
        for p in self.parts:
            kind = p[8]
            frac = p[4] / p[5]
            if kind == 'smoke':
                rad = max(1, int(p[6] * (0.6 + (1 - frac) * 0.8)))
                col = p[7] if frac > 0.35 else (34, 30, 46)
                pygame.draw.circle(surf, col, (int(p[0]), int(p[1])), rad)
            elif kind == 'spark':
                col = p[7] if frac > 0.4 else (255, 140, 60)
                pygame.draw.line(surf, col, (int(p[0]), int(p[1])),
                                 (int(p[0] - p[2] * 2.2), int(p[1] - p[3] * 2.2)))
            else:
                col = fire_color(frac) if kind == 'fire' else p[7]
                s = max(1, int(p[6] * (0.4 + frac * 0.6) + 0.5))
                fill(col, (int(p[0] - s / 2), int(p[1] - s / 2), s, s))
        for f in self.flashes:
            frac = f[3] / f[4]
            pygame.draw.circle(surf, (255, 250, 220) if frac > 0.5 else (255, 200, 90),
                               (int(f[0]), int(f[1])), max(1, int(f[2] * (0.5 + frac * 0.5))))
        for g in self.rings:
            frac = g[4] / g[5]
            w = max(1, int(g[7] * frac + 0.5))
            if g[2] > w:
                col = g[6] if frac > 0.5 else art.mix(g[6], (255, 90, 50), 0.6)
                pygame.draw.circle(surf, col, (int(g[0]), int(g[1])), int(g[2]), w)

    def draw_popups(self, surf, mirror=False):
        for p in self.popups:
            if p[3] > 10 or p[3] % 4 < 2:
                x = p[0] if not mirror else PF_W - p[0] - p[2].get_width()
                surf.blit(p[2], (int(x), int(p[1])))

    def draw_flash(self, surf):
        if self.flash > 0:
            self._overlay.fill(self.flash_color)
            self._overlay.set_alpha(int(200 * self.flash / self.flash_max))
            surf.blit(self._overlay, (0, 0))

    def clear(self):
        self.parts.clear()
        self.rings.clear()
        self.debris.clear()
        self.popups.clear()
        self.flashes.clear()
