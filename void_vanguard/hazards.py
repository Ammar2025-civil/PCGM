"""Sector mechanics. Each one is a small system the HazardManager runs.

asteroids  destructible rocks that drop ore (credits)
nebula     fog patches that hide enemies + lightning strikes with a warning
crystals   crystal walls that bounce every bullet (yours and theirs)
flares     timed solar flares; hide in the shadow of floating debris
station    corridor walls, wall turrets and laser gates that open and close
gravity    pulls the ship and all bullets toward one side
hive       spawner nests that keep producing larvae until destroyed
wormhole   scroll surges, warp sections and brief mirror flips
"""
import math
import random

import pygame

import art
import enemies as E
import bullets as B
from pickups import Pickup
from config import PF_W, PF_H, WHITE

_cache = {}


class System:
    def __init__(self, mgr, game, intensity):
        self.mgr = mgr
        self.g = game
        self.i = intensity
        self.active = False
        self.calm = False
        self.fight = False
        self.rnd = random.Random(game.level * 977 + id(type(self)) % 1000)

    def update(self):
        pass

    def on_act(self, index, length):
        self.active = True
        self.calm = False

    def on_breather(self, frames):
        self.calm = True

    def end_fight(self):
        self.active = False
        self.fight = True

    def affect_bullets(self):
        pass

    def draw_back(self, surf):
        pass

    def draw_mid(self, surf):
        pass

    def draw_front(self, surf):
        pass


def push_out(player, rect):
    """Push the player's small body box out of a solid rect. Returns True if crushed."""
    pr = pygame.Rect(int(player.x) - 5, int(player.y) - 5, 10, 10)
    if not pr.colliderect(rect):
        return False
    dl = pr.right - rect.left
    dr = rect.right - pr.left
    du = pr.bottom - rect.top
    dd = rect.bottom - pr.top
    m = min(dl, dr, du, dd)
    if m == dl:
        player.x -= dl
    elif m == dr:
        player.x += dr
    elif m == du:
        player.y -= du
    else:
        player.y += dd
    return player.y > PF_H - 9 or player.x < 4 or player.x > PF_W - 4


# ====================================================================== asteroids
class Asteroids(System):
    def __init__(self, *a):
        super().__init__(*a)
        self.t = 60

    def update(self):
        if not self.active:
            return
        self.t -= 1
        if self.t > 0:
            return
        base = self.rnd.uniform(60, 120) / (0.3 + self.i)
        self.t = int(base * (0.6 if self.calm else 1.0))
        r = self.rnd.random()
        size = self.rnd.randint(11, 16) if r < 0.3 else (self.rnd.randint(7, 9) if r < 0.7 else self.rnd.randint(4, 5))
        ore = self.rnd.random() < (0.7 if self.calm else 0.35)
        self.spawn(self.rnd.uniform(12, PF_W - 12), -size - 4, self.rnd.uniform(-0.35, 0.35),
                   self.rnd.uniform(0.5, 1.1), size, ore)

    def spawn(self, x, y, vx, vy, size, ore):
        e = E.Enemy(self.g, 'asteroid', x, y, E.make_drift(vx, vy), size=size,
                    seed=self.rnd.randrange(60), ore=ore)
        self.g.add_enemy(e)
        return e

    def affect_bullets(self):
        rocks = [e for e in self.g.enemies if e.kind == 'asteroid' and e.alive and e.size >= 7]
        if not rocks:
            return
        for b in self.g.ebullets:
            for e in rocks:
                dx, dy = b.x - e.x, b.y - e.y
                if dx * dx + dy * dy < (e.size - 1) ** 2:
                    b.alive = False
                    if self.g.frame % 3 == 0:
                        self.g.fx.sparks(b.x, b.y, 2, (200, 170, 140), 1.2, 6)
                    break


def split_asteroid(mgr, e):
    if e.size < 7:
        return
    g = mgr.game
    child = max(4, int(e.size * 0.58))
    for s in (-1, 1):
        a = E.Enemy(g, 'asteroid', e.x + s * 3, e.y, E.make_drift(s * random.uniform(0.6, 1.1), random.uniform(0.6, 1.2)),
                    size=child, seed=random.randrange(60), ore=e.ore)
        a.entered = True
        g.add_enemy(a)


# ====================================================================== nebula
def fog_sprite(w, h, seed):
    key = ('fog', w, h, seed)
    s = _cache.get(key)
    if s is not None:
        return s
    import backgrounds
    hw, hh = w // 2, h // 2
    n = backgrounds.noise(hw, hh, seed, (10, 5, 3), (0.6, 0.3, 0.1))
    s = pygame.Surface((hw, hh), pygame.SRCALPHA)
    for y in range(hh):
        for x in range(hw):
            dx = (x - hw / 2) / (hw / 2)
            dy = (y - hh / 2) / (hh / 2)
            d = dx * dx + dy * dy
            v = n[y][x] * 1.25 - d * 0.9
            if v <= 0.12:
                continue
            t = (backgrounds.BAYER4[y & 3][x & 3] + 0.5) / 16.0
            if v < 0.3 and t > (v - 0.12) / 0.18:
                continue
            light = min(1.0, (v - 0.2) * 1.4)
            col = art.mix((52, 22, 78), (150, 90, 190), light * 0.6)
            s.set_at((x, y), (*col, 238))
    s = pygame.transform.scale(s, (w, h))
    _cache[key] = s
    return s


class Nebula(System):
    def __init__(self, *a):
        super().__init__(*a)
        self.fog = []
        self.fog_t = 30
        self.variants = [fog_sprite(w, h, k) for k, (w, h) in enumerate(((96, 72), (120, 90), (144, 104),
                                                                         (110, 80), (132, 96), (100, 100)))]
        self.bolt_t = 200
        self.strikes = []   # [x, warn, active, points]

    def update(self):
        g = self.g
        for f in self.fog:
            f[2] += f[3] * g.scroll_mult
        self.fog = [f for f in self.fog if f[2] < PF_H + 10]
        if self.active:
            self.fog_t -= 1
            if self.fog_t <= 0:
                self.fog_t = int(self.rnd.uniform(200, 340) / (0.25 + self.i))
                s = self.rnd.choice(self.variants)
                w, h = s.get_size()
                self.fog.append([s, self.rnd.uniform(-30, PF_W - w + 30), -h, self.rnd.uniform(0.6, 0.9)])
            if not self.calm:
                self.bolt_t -= 1
                if self.bolt_t <= 0:
                    self.bolt_t = max(140, int(self.rnd.uniform(300, 460) / (0.3 + self.i)))
                    n = 2 if self.i > 0.75 and self.rnd.random() < 0.5 else 1
                    for k in range(n):
                        x = g.player.x + self.rnd.uniform(-34, 34) + (k * 70 * (1 if self.rnd.random() < 0.5 else -1))
                        self.warn_strike(max(14, min(PF_W - 14, x)))
        for st in self.strikes:
            if st[1] > 0:
                st[1] -= 1
                if st[1] == 0:
                    self.strike(st)
            else:
                st[2] -= 1
        self.strikes = [st for st in self.strikes if st[1] > 0 or st[2] > 0]

    def warn_strike(self, x, warn=72):
        self.g.telegraph_rect((x - 11, 0, 22, PF_H), warn, (255, 240, 120))
        self.strikes.append([x, warn, 12, None])
        self.g.sfx('charge', 0.5)

    def strike(self, st):
        g = self.g
        x = st[0]
        pts = []
        y = -4
        cx = x
        while y < PF_H + 8:
            pts.append((int(cx), int(y)))
            y += random.randint(10, 22)
            cx = x + random.uniform(-8, 8)
        st[3] = pts
        g.fx.screen_flash(5, (230, 220, 255))
        g.fx.shake(0.35)
        g.sfx('thunder')
        p = g.player
        if p.alive and abs(p.x - x) < 11:
            p.hit(1)
        for e in list(g.enemies):
            if e.alive and abs(e.x - x) < 14 and e.y > -10:
                e.damage(20 * g.diff['enemy_hp'], 'bomb')
        for k in range(8):
            g.fx.sparks(x + random.uniform(-6, 6), random.uniform(0, PF_H), 3, (220, 220, 255), 2.5, 10)

    def draw_mid(self, surf):
        for s, x, y, _ in self.fog:
            surf.blit(s, (int(x), int(y)))

    def draw_front(self, surf):
        for x, warn, act, pts in self.strikes:
            if warn > 0:
                if (warn // 4) % 2 == 0:
                    pygame.draw.circle(surf, (255, 250, 200), (int(x), 6), 5)
                continue
            if pts:
                w = 3 if act > 6 else 1
                pygame.draw.lines(surf, (170, 140, 255), False, pts, w + 4)
                pygame.draw.lines(surf, (230, 220, 255), False, pts, w + 1)
                pygame.draw.lines(surf, WHITE, False, pts, 1)


# ====================================================================== crystals
class Crystals(System):
    def __init__(self, *a):
        super().__init__(*a)
        self.walls = []
        self.t = 40
        self.ping_t = 0

    def update(self):
        g = self.g
        for c in self.walls:
            c['y'] += c['vy'] * g.scroll_mult
            c['rect'].center = (int(c['x']), int(c['y']))
        self.walls = [c for c in self.walls if c['y'] - c['h'] / 2 < PF_H + 4]
        if self.ping_t:
            self.ping_t -= 1
        if self.active and not self.fight:
            self.t -= 1
            if self.t <= 0:
                self.t = int(self.rnd.uniform(160, 260) / (0.3 + self.i))
                self.spawn()
        p = g.player
        if p.alive:
            for c in self.walls:
                if push_out(p, c['rect']):
                    p.hit(1)

    def spawn_at(self, x, y, w=14, h=34):
        spr = art.crystal_sprite(w, h, self.rnd.randrange(8))
        rect = pygame.Rect(0, 0, w - 2, h - 6)
        rect.center = (int(x), int(y))
        self.walls.append(dict(x=x, y=y, w=w, h=h, vy=0.45, spr=spr, rect=rect))

    def spawn(self):
        w = self.rnd.randrange(10, 17)
        h = self.rnd.randrange(26, 48)
        for _ in range(6):
            x = self.rnd.uniform(w, PF_W - w)
            if all(abs(x - c['x']) > 50 or c['y'] > 60 for c in self.walls):
                break
        spr = art.crystal_sprite(w, h, self.rnd.randrange(8))
        rect = pygame.Rect(0, 0, w - 2, h - 6)
        rect.center = (int(x), int(-h))
        self.walls.append(dict(x=x, y=-h, w=w, h=h, vy=0.75, spr=spr, rect=rect))

    def reflect(self, bullets, player_side):
        g = self.g
        for b in bullets:
            if not b.alive or (player_side and b.kind == 'missile'):
                continue
            for c in self.walls:
                r = c['rect']
                if r.left <= b.x <= r.right and r.top <= b.y <= r.bottom:
                    if b.ox < r.left or b.ox > r.right:
                        b.vx = -b.vx
                    else:
                        b.vy = -b.vy
                    b.x, b.y = b.ox, b.oy
                    b.bounces -= 1
                    if b.bounces < 0:
                        b.alive = False
                    if self.ping_t == 0:
                        self.ping_t = 4
                        g.fx.sparks(b.x, b.y, 3, (200, 240, 255), 1.6, 8)
                        g.sfx('ping', 0.5)
                    if hasattr(b, 'grazed'):
                        b.grazed = False
                    break

    def affect_bullets(self):
        if not self.walls:
            return
        self.reflect(self.g.pbullets, True)
        self.reflect(self.g.ebullets, False)

    def draw_back(self, surf):
        t = self.g.frame
        for c in self.walls:
            s = c['spr']
            x, y = int(c['x'] - s.get_width() / 2), int(c['y'] - s.get_height() / 2)
            surf.blit(s, (x, y))
            gy = int((t * 0.7 + c['x']) % (c['h'] + 20)) - 10
            if 0 <= gy < c['h'] - 4:
                surf.fill(WHITE, (int(c['x']) - 1, y + gy, 2, 3))


# ====================================================================== solar flares
class Flares(System):
    WARN = 120
    SWEEP = 60

    def __init__(self, *a):
        super().__init__(*a)
        self.debris = []
        self.deb_t = 20
        self.state = 'idle'
        self.timer = 360
        self.band_y = -30
        self.hit_done = False

    def spawn_debris(self, y=None):
        w = self.rnd.randrange(20, 32)
        h = self.rnd.randrange(10, 16)
        for _ in range(8):
            x = self.rnd.uniform(w, PF_W - w)
            if all(abs(x - d['x']) > 46 for d in self.debris):
                break
        spr = art.debris_sprite(w, h, self.rnd.randrange(9))
        yy = -h if y is None else y
        rect = pygame.Rect(0, 0, w - 2, h - 2)
        rect.center = (int(x), int(yy))
        self.debris.append(dict(x=x, y=yy, w=w, h=h, vy=self.rnd.uniform(0.35, 0.55), spr=spr, rect=rect))

    def update(self):
        g = self.g
        for d in self.debris:
            d['y'] += d['vy'] * g.scroll_mult
            d['rect'].center = (int(d['x']), int(d['y']))
        self.debris = [d for d in self.debris if d['y'] - d['h'] < PF_H]
        p = g.player
        if p.alive:
            for d in self.debris:
                push_out(p, d['rect'])
        if hasattr(g.bg, 'glow'):
            g.bg.glow = 0.0
        if not self.active and self.state == 'idle':
            return
        self.deb_t -= 1
        if self.deb_t <= 0:
            self.deb_t = int(self.rnd.uniform(140, 220) / (0.4 + self.i))
            self.spawn_debris()
        if self.state == 'idle':
            if self.calm or self.fight or not self.active:
                return
            self.timer -= 1
            if self.timer <= 0:
                self.state = 'warn'
                self.timer = self.WARN
                visible = [d for d in self.debris if 20 < d['y'] < PF_H * 0.55]
                while len(visible) < 2:
                    self.spawn_debris(self.rnd.uniform(50, 150))
                    visible.append(self.debris[-1])
                g.banner('SOLAR FLARE!', (255, 170, 60), 80)
                g.sfx('warning_short')
        elif self.state == 'warn':
            self.timer -= 1
            if hasattr(g.bg, 'glow'):
                g.bg.glow = 1 - self.timer / self.WARN
            if self.timer <= 0:
                self.state = 'sweep'
                self.timer = self.SWEEP
                self.band_y = -30
                self.hit_done = False
                g.sfx('flare')
                g.fx.shake(0.3)
        elif self.state == 'sweep':
            self.timer -= 1
            self.band_y += (PF_H + 60) / self.SWEEP
            if hasattr(g.bg, 'glow'):
                g.bg.glow = 1.0
            if p.alive and not self.hit_done and abs(p.y - self.band_y) < 14 and not self.in_shadow(p.x, p.y):
                self.hit_done = True
                if not p.stats.get('flare_resist'):
                    p.hit(1)
                else:
                    g.popup_player('FLARE PROOF', (255, 220, 120))
            for e in g.enemies:
                if e.alive and abs(e.y - self.band_y) < 14 and not self.in_shadow(e.x, e.y) and e.kind != 'asteroid':
                    e.damage(e.maxhp * 0.05 + 0.5, 'bomb')
            if self.timer <= 0:
                self.state = 'idle'
                self.timer = int(self.rnd.uniform(420, 640) / (0.4 + self.i * 0.8))

    def in_shadow(self, x, y):
        for d in self.debris:
            if d['x'] - d['w'] / 2 + 2 < x < d['x'] + d['w'] / 2 - 2 and y > d['y'] + d['h'] / 2 - 2:
                return True
        return False

    def end_fight(self):
        super().end_fight()
        self.state = 'idle'

    def trigger(self):
        """Start a flare right now (used by bosses)."""
        if self.state != 'idle':
            return
        self.timer = 1
        was = (self.active, self.fight, self.calm)
        self.active, self.fight, self.calm = True, False, False
        self.update()
        self.active, self.fight, self.calm = was

    def affect_bullets(self):
        if not self.debris:
            return
        g = self.g
        for lst in (g.pbullets, g.ebullets):
            for b in lst:
                for d in self.debris:
                    if d['rect'].collidepoint(b.x, b.y):
                        b.alive = False
                        if g.frame % 2 == 0:
                            g.fx.sparks(b.x, b.y, 2, (255, 180, 90), 1.4, 6)
                        break

    def draw_back(self, surf):
        g = self.g
        if self.state in ('warn', 'sweep'):
            shade = _shadow_strip()
            for d in self.debris:
                top = int(d['y'] + d['h'] / 2)
                w = int(d['w'] - 4)
                if top < PF_H:
                    surf.blit(shade, (int(d['x'] - w / 2), top), (0, 0, w, PF_H - top))
        for d in self.debris:
            s = d['spr']
            surf.blit(s, (int(d['x'] - s.get_width() / 2), int(d['y'] - s.get_height() / 2)))

    def draw_front(self, surf):
        g = self.g
        if self.state == 'warn':
            k = 1 - self.timer / self.WARN
            h = int(8 + 30 * k)
            if (self.timer // 6) % 2 == 0 or k > 0.7:
                for i in range(h):
                    if i % 2 == 0 or k > 0.5:
                        surf.fill(art.mix((255, 240, 160), (120, 30, 10), i / h), (0, i, PF_W, 1))
            art.text(surf, 'HIDE BEHIND DEBRIS', PF_W // 2, 44, (255, 220, 140), 1, 'c')
        elif self.state == 'sweep':
            y = int(self.band_y)
            for i in range(-16, 17):
                c = art.mix((255, 255, 220), (255, 110, 30), abs(i) / 16)
                surf.fill(c, (0, y + i, PF_W, 1))
            for d in self.debris:
                if d['y'] < y:
                    w = int(d['w'] - 4)
                    top = int(d['y'] + d['h'] / 2)
                    surf.fill((40, 20, 30), (int(d['x'] - w / 2), max(top, y - 16), w, max(0, min(33, y + 17 - max(top, y - 16)))))
            if g.frame % 2 == 0:
                for _ in range(6):
                    g.fx.particle(random.uniform(0, PF_W), y + random.uniform(-10, 10), random.uniform(-1, 1), 1.5, 14, 2,
                                  (255, 200, 80), 'sq', 0.95)


def _shadow_strip():
    s = _cache.get('shadow')
    if s is None:
        s = pygame.Surface((40, PF_H), pygame.SRCALPHA)
        for y in range(PF_H):
            for x in range(40):
                if (x + y) % 2 == 0:
                    s.set_at((x, y), (10, 0, 20, 140))
        _cache['shadow'] = s
    return s


# ====================================================================== station
class Station(System):
    ROW = 6

    def __init__(self, *a):
        super().__init__(*a)
        self.rows = []          # [y, L, R] from top to bottom
        self.state = 'off'
        self.tl = 0.0
        self.tr = 0.0
        self.cur_l = 0.0
        self.cur_r = 0.0
        self.walk_t = 0
        self.gates = []         # dict(y, t, cycle)
        self.gate_t = 120
        self.leave_t = -1
        self.main = self.i >= 0.4

    def corridor_on(self):
        return self.state in ('entering', 'on')

    def on_act(self, index, length):
        super().on_act(index, length)
        if self.main or index % 2 == 1:
            self.state = 'entering'
            self.leave_t = length - 200 if self.main else length // 2
            self.cur_l = self.cur_r = 0.0

    def on_breather(self, frames):
        super().on_breather(frames)
        if self.state in ('entering', 'on'):
            self.state = 'leaving'

    def end_fight(self):
        super().end_fight()
        if self.state != 'off':
            self.state = 'leaving'

    def bounds(self, y):
        if not self.rows:
            return 0, PF_W
        top = self.rows[0][0]
        idx = int((y - top) / self.ROW)
        if idx < 0 or idx >= len(self.rows):
            return 0, PF_W
        r = self.rows[idx]
        return r[1], PF_W - r[2]

    def update(self):
        g = self.g
        v = 1.0 * g.scroll_mult
        for r in self.rows:
            r[0] += v
        while self.rows and self.rows[-1][0] > PF_H + self.ROW:
            self.rows.pop()
        if self.leave_t > 0:
            self.leave_t -= 1
            if self.leave_t == 0 and self.state in ('entering', 'on'):
                self.state = 'leaving'
        maxw = PF_W - 130
        while not self.rows or self.rows[0][0] > -self.ROW:
            if self.state in ('entering', 'on'):
                self.walk_t -= 1
                if self.walk_t <= 0:
                    self.walk_t = self.rnd.randint(12, 30)
                    total = self.rnd.uniform(40, maxw * (0.55 + 0.45 * self.i))
                    bias = self.rnd.uniform(0.2, 0.8)
                    self.tl, self.tr = total * bias, total * (1 - bias)
                step = 1.4 if self.state == 'on' else 2.5
                self.cur_l += max(-step, min(step, self.tl - self.cur_l))
                self.cur_r += max(-step, min(step, self.tr - self.cur_r))
                if self.state == 'entering' and abs(self.cur_l - self.tl) < 3:
                    self.state = 'on'
            else:
                self.cur_l = max(0.0, self.cur_l - 3)
                self.cur_r = max(0.0, self.cur_r - 3)
                if self.cur_l <= 0 and self.cur_r <= 0 and self.state == 'leaving':
                    self.state = 'off'
            y = self.rows[0][0] - self.ROW if self.rows else -self.ROW
            if self.state == 'off' and self.cur_l <= 0 and self.cur_r <= 0:
                if not self.rows:
                    break
                self.rows.insert(0, [y, 0, 0])
                if all(r[1] == 0 and r[2] == 0 for r in self.rows):
                    self.rows.clear()
                    break
            else:
                self.rows.insert(0, [y, self.cur_l, self.cur_r])
        # laser gates
        for gt in self.gates:
            gt['y'] += v
            gt['t'] += 1
        self.gates = [gt for gt in self.gates if gt['y'] < PF_H + 6]
        if self.state == 'on' and not self.fight:
            self.gate_t -= 1
            if self.gate_t <= 0:
                self.gate_t = int(self.rnd.uniform(220, 340) / (0.35 + self.i))
                self.gates.append(dict(y=-4, t=self.rnd.randrange(0, 100), off=100, warn=45, on=60))
        p = g.player
        if p.alive:
            for gt in self.gates:
                if self.gate_state(gt) == 'on' and abs(p.y - gt['y']) < 4:
                    p.hit(1)

    def gate_state(self, gt):
        cyc = gt['off'] + gt['warn'] + gt['on']
        k = gt['t'] % cyc
        if k < gt['off']:
            return 'off'
        if k < gt['off'] + gt['warn']:
            return 'warn'
        return 'on'

    def affect_bullets(self):
        if not self.rows:
            return
        g = self.g
        for lst in (g.pbullets, g.ebullets):
            for b in lst:
                lo, hi = self.bounds(b.y)
                if b.x < lo or b.x > hi:
                    b.alive = False
                    if g.frame % 2 == 0:
                        g.fx.sparks(max(lo, min(hi, b.x)), b.y, 2, (255, 200, 120), 1.3, 6)

    def draw_back(self, surf):
        if not self.rows:
            return
        base, dark, light = (58, 60, 74), (26, 26, 36), (110, 116, 136)
        for i, (y, L, R) in enumerate(self.rows):
            yy = int(y)
            seam = (int(y) // self.ROW) % 6 == 0
            for x0, w, edge in ((0, int(L), int(L)), (PF_W - int(R), int(R), PF_W - int(R))):
                if w <= 0:
                    continue
                surf.fill(dark if seam else base, (x0, yy, w, self.ROW))
                surf.fill(light, (edge - 1 if x0 == 0 else edge, yy, 2, self.ROW))
                if x0 == 0 and w > 8:
                    surf.fill((255, 150, 40) if (i // 2) % 2 else (40, 30, 10), (w - 6, yy, 3, self.ROW))
                elif w > 8:
                    surf.fill((255, 150, 40) if (i // 2) % 2 else (40, 30, 10), (x0 + 3, yy, 3, self.ROW))
        for gt in self.gates:
            st = self.gate_state(gt)
            lo, hi = self.bounds(gt['y'])
            y = int(gt['y'])
            surf.fill((150, 40, 40), (int(lo) - 4, y - 3, 6, 7))
            surf.fill((150, 40, 40), (int(hi) - 2, y - 3, 6, 7))
            if st == 'warn' and (gt['t'] // 4) % 2 == 0:
                pygame.draw.line(surf, (255, 90, 90), (int(lo), y), (int(hi), y), 1)
            elif st == 'on':
                pygame.draw.line(surf, (255, 40, 80), (int(lo), y), (int(hi), y), 5)
                pygame.draw.line(surf, (255, 200, 220), (int(lo), y), (int(hi), y), 2)


# ====================================================================== gravity
class Gravity(System):
    def __init__(self, *a):
        super().__init__(*a)
        self.side = -1 if self.rnd.random() < 0.5 else 1
        self.cur = 0.0
        self.switch_t = 900
        self.warn = 0
        self.main = self.i >= 0.4

    def strength(self):
        return 0.008 + 0.022 * self.i

    forced = False

    def update(self):
        g = self.g
        on = self.forced or (self.active and (not self.fight or self.main))
        target = self.side * self.strength() * (0.7 if self.fight else 1.0) if on else 0.0
        self.cur += (target - self.cur) * 0.02
        g.gravity_x = self.cur
        if hasattr(g.bg, 'side'):
            g.bg.side = self.side
        if not on or self.forced:
            if self.forced and self.warn > 0:
                self.warn -= 1
                if self.warn == 0:
                    self.side = -self.side
                    g.fx.screen_flash(6, (180, 120, 255))
            return
        if self.warn > 0:
            self.warn -= 1
            if self.warn == 0:
                self.side = -self.side
                g.fx.screen_flash(6, (180, 120, 255))
                g.sfx('phase')
        else:
            self.switch_t -= 1
            if self.switch_t <= 0:
                self.switch_t = self.rnd.randint(1000, 1500)
                self.warn = 90
                g.banner('GRAVITY SHIFT', (190, 140, 255), 80)
                g.sfx('warning_short')

    def draw_back(self, surf):
        g = self.g
        if abs(self.cur) < 0.002 or hasattr(g.bg, 'side'):
            return
        x0 = 0 if self.side < 0 else PF_W - 18
        t = g.frame
        for i in range(18):
            k = i if self.side < 0 else 17 - i
            c = art.mix((30, 10, 40), (8, 4, 16), k / 18)
            surf.fill(c, (x0 + i, 0, 1, PF_H))
        for j in range(6):
            y = (t * 2 + j * 60) % PF_H
            pygame.draw.arc(surf, (120, 60, 180), (x0 - 20 if self.side < 0 else x0, y, 40, 30), 0.5, 2.6, 1)

    def draw_front(self, surf):
        g = self.g
        if abs(self.cur) < 0.002:
            return
        t = g.frame
        d = 1 if self.cur > 0 else -1
        x = PF_W - 10 if d > 0 else 10
        for j in range(4):
            y = (j * 90 + t) % PF_H
            off = (t // 4) % 3 * d
            col = (150, 100, 220) if self.warn == 0 or (t // 6) % 2 else (255, 220, 120)
            art.text(surf, '>' if d > 0 else '<', x - 2 + off, y, col, 1, shadow=None)


# ====================================================================== hive
class Hive(System):
    def __init__(self, *a):
        super().__init__(*a)
        self.t = 300

    def update(self):
        if not self.active or self.calm or self.fight:
            return
        self.t -= 1
        if self.t <= 0:
            self.t = int(self.rnd.uniform(700, 1000) / (0.3 + self.i))
            if self.g.count_kind('nest') < 1 + int(self.i * 2):
                E.spawn_wave(self.g, dict(pattern='nests', kind='nest', count=1, seed=self.rnd.randrange(99999)))


# ====================================================================== wormhole
class Wormhole(System):
    def __init__(self, *a):
        super().__init__(*a)
        self.surge_t = 500
        self.surge = 0
        self.surge_warn = 0
        self.flip_t = 700
        self.flip_warn = 0
        self.flip_left = 0
        self.warp = 0
        self.orb_t = 0

    def on_act(self, index, length):
        super().on_act(index, length)
        self.warp = 0
        self.g.allow_enemy_fire = True

    def on_breather(self, frames):
        super().on_breather(frames)
        if self.i >= 0.4:
            self.warp = frames
            self.g.banner('WARP!', (120, 230, 255), 60)
            self.g.sfx('warp')

    def end_fight(self):
        super().end_fight()
        self.warp = 0
        self.surge = 0
        self.flip_left = 0
        self.flip_warn = 0
        self.g.mirror_x = False
        self.g.scroll_mult = 1.0

    def update(self):
        g = self.g
        bg = g.bg
        target = 1.0
        if self.surge > 0:
            self.surge -= 1
            target = 2.1
        g.scroll_mult += (target - g.scroll_mult) * 0.05
        g.scroll = g.scroll_base * g.scroll_mult * (3.5 if self.warp else 1.0)
        bg.warp += ((1.0 if self.warp else (0.4 if self.surge else 0.0)) - bg.warp) * 0.08
        if self.warp > 0:
            self.warp -= 1
            g.allow_enemy_fire = False
            self.orb_t -= 1
            if self.orb_t <= 0:
                self.orb_t = 70
                x0 = self.rnd.uniform(40, PF_W - 40)
                ph = self.rnd.uniform(0, 6)
                val = max(1, int(1 * g.diff['credits']))
                for k in range(8):
                    pk = Pickup(x0 + math.sin(ph + k * 0.5) * 30, -10 - k * 14, 'orb', val, 0, 1.6)
                    g.pickups.append(pk)
                if self.rnd.random() < 0.5 + self.i * 0.4:
                    B.shoot(g, self.rnd.uniform(10, PF_W - 10), -8, math.pi / 2, 1.9, 'l', 1, raw=True)
            if self.warp == 0:
                g.allow_enemy_fire = True
        if not self.active or self.fight:
            return
        if self.surge_warn > 0:
            self.surge_warn -= 1
            if self.surge_warn == 0:
                self.surge = int(180 + 120 * self.i)
                g.sfx('warp')
        elif self.surge == 0 and not self.calm:
            self.surge_t -= 1
            if self.surge_t <= 0:
                self.surge_t = int(self.rnd.uniform(600, 900) / (0.4 + self.i * 0.6))
                self.surge_warn = 50
                g.banner('SURGE!', (120, 230, 255), 50)
        if self.flip_warn > 0:
            self.flip_warn -= 1
            if self.flip_warn == 0:
                g.mirror_x = not g.mirror_x
                g.fx.screen_flash(6, (200, 120, 255))
                g.sfx('phase')
                if g.mirror_x:
                    self.flip_left = int(240 + 140 * self.i)
        elif self.flip_left > 0:
            self.flip_left -= 1
            if self.flip_left == 0:
                self.flip_warn = 45
                g.banner('FLIP BACK', (200, 150, 255), 45)
        elif not self.calm and self.i >= 0.3:
            self.flip_t -= 1
            if self.flip_t <= 0:
                self.flip_t = int(self.rnd.uniform(900, 1300) / (0.4 + self.i * 0.6))
                self.flip_warn = 120
                g.banner('MIRROR FLIP', (200, 150, 255), 100)
                g.sfx('warning_short')

    def draw_front(self, surf):
        g = self.g
        if self.flip_warn > 0 and (self.flip_warn // 6) % 2 == 0:
            pygame.draw.rect(surf, (200, 120, 255), (0, 0, PF_W, PF_H), 3)
            art.text(surf, '< >', PF_W // 2, 170, (230, 200, 255), 2, 'c')
        if self.surge_warn > 0 and (self.surge_warn // 5) % 2 == 0:
            for x in range(10, PF_W, 40):
                art.text(surf, '^', x, 10, (120, 230, 255), 1)


# ====================================================================== manager
SYSTEMS = {'asteroids': Asteroids, 'nebula': Nebula, 'crystals': Crystals, 'flares': Flares,
           'station': Station, 'gravity': Gravity, 'hive': Hive, 'wormhole': Wormhole}


class HazardManager:
    def __init__(self, game, hazards):
        self.game = game
        self.hazards = dict(hazards)
        self.systems = []
        self.station = None
        for mech, inten in hazards.items():
            cls = SYSTEMS.get(mech)
            if cls is None or inten <= 0:
                continue
            s = cls(self, game, inten)
            self.systems.append(s)
            if isinstance(s, Station):
                self.station = s
        # draw order: walls and rocks first, fog over enemies, flashes on top
        self.systems.sort(key=lambda s: 0 if isinstance(s, Station) else 1)

    def bounds_at(self, y):
        if self.station is not None:
            return self.station.bounds(y)
        return 0, PF_W

    def corridor_at(self, y):
        return self.bounds_at(y)

    def corridor_active(self):
        return self.station is not None and self.station.corridor_on()

    def update(self):
        for s in self.systems:
            s.update()

    def affect_bullets(self):
        for s in self.systems:
            s.affect_bullets()

    def on_act(self, index, length):
        for s in self.systems:
            s.on_act(index, length)

    def on_breather(self, frames):
        for s in self.systems:
            s.on_breather(frames)

    def end_fight(self):
        for s in self.systems:
            s.end_fight()

    def asteroid_destroyed(self, e):
        split_asteroid(self, e)

    def ensure(self, mech, intensity=0.5):
        """Get (or create) a mechanic so a boss can use it in its fight."""
        for s in self.systems:
            if isinstance(s, SYSTEMS[mech]):
                return s
        s = SYSTEMS[mech](self, self.game, intensity)
        s.fight = True
        self.systems.append(s)
        if isinstance(s, Station):
            self.station = s
        return s

    def shutdown(self):
        """Boss is dead: stop every mechanic and put the screen back to normal."""
        for s in self.systems:
            s.active = False
            s.fight = True
            if isinstance(s, Gravity):
                s.forced = False
        self.game.mirror_x = False
        self.game.scroll_mult = 1.0

    def draw_back(self, surf):
        for s in self.systems:
            s.draw_back(surf)

    def draw_mid(self, surf):
        for s in self.systems:
            s.draw_mid(surf)

    def draw_front(self, surf):
        for s in self.systems:
            s.draw_front(surf)
