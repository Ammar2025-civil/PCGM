"""Enemy archetypes, movement paths (as generators) and wave pattern spawners."""
import math
import random

import pygame

import art
import bullets as B
from config import PF_W, PF_H, WHITE

# hp = base hit points before the difficulty multiplier
ARCH = {
    'dart':      dict(hp=3, score=100, credits=2, fire=None, contact=True),
    'gunner':    dict(hp=9, score=220, credits=4, fire='aimed', interval=100),
    'heavy':     dict(hp=34, score=650, credits=11, fire='fan', interval=120),
    'weaver':    dict(hp=7, score=180, credits=3, fire='drop', interval=80),
    'kamikaze':  dict(hp=4, score=160, credits=3, fire=None, contact=True),
    'splitter':  dict(hp=14, score=300, credits=5, fire='aimed', interval=130),
    'shielded':  dict(hp=16, score=380, credits=7, fire='burst', interval=110),
    'sniper':    dict(hp=11, score=350, credits=6, fire='snipe', interval=150),
    'minelayer': dict(hp=18, score=420, credits=8, fire='mines', interval=95),
    'carrier':   dict(hp=24, score=800, credits=14, fire=None),
    'golden':    dict(hp=34, score=5000, credits=0, fire=None),
    'larva':     dict(hp=2, score=60, credits=1, fire=None, contact=True),
    'mini':      dict(hp=2, score=60, credits=1, fire=None, contact=True),
    'turret':    dict(hp=20, score=400, credits=7, fire='burst', interval=100),
    'nest':      dict(hp=70, score=1500, credits=24, fire='spawn', interval=110),
    'asteroid':  dict(hp=6, score=50, credits=0, fire=None, contact=True),
}
NO_KILL_COUNT = {'mini', 'larva', 'asteroid', 'golden'}


class Enemy:
    is_boss_part = False

    def __init__(self, game, kind, x, y, path=None, hp_mult=1.0, **opts):
        a = ARCH[kind]
        self.game = game
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.hp = max(1.0, a['hp'] * game.diff['enemy_hp'] * hp_mult)
        self.maxhp = self.hp
        self.score = a['score']
        self.credits = a['credits']
        self.fire_kind = a['fire']
        self.interval = a.get('interval', 100)
        self.contact = a.get('contact', False)
        self.counts = kind not in NO_KILL_COUNT and opts.get('counts', True)
        self.size = opts.get('size', 0)
        self.ore = opts.get('ore', False)
        if kind == 'asteroid':
            self.hp = max(1.0, (4 + self.size * 2.2) * (0.6 + 0.4 * game.diff['enemy_hp']))
            self.maxhp = self.hp
            self.spr_frames = [art.asteroid_sprite(self.size, opts.get('seed', 1), self.ore)]
            for _ in range(3):
                self.spr_frames.append(pygame.transform.rotate(self.spr_frames[-1], 90))
            self.spr = self.spr_frames[0]
        else:
            self.spr = art.enemy_sprite(kind, game.sector)
        self.w = self.spr.get_width() * 0.8
        self.h = self.spr.get_height() * 0.8
        self.flash = 0
        self.alive = True
        self.escaped = False
        self.t = 0
        self.entered = False
        self.fire_t = random.randint(30, 30 + self.interval)
        self.telegraph = 0
        self.ground = kind in ('turret', 'nest')
        self.no_fire = opts.get('no_fire', False)
        self.deflect_t = 0
        self.snipe_angle = None
        self.path = (path or p_straight)(self, game)

    # ------------------------------------------------------------ update
    def update(self):
        g = self.game
        self.t += 1
        if self.flash:
            self.flash -= 1
        if self.deflect_t:
            self.deflect_t -= 1
        try:
            next(self.path)
        except StopIteration:
            self.alive = False
            self.escaped = True
            return
        on = -8 < self.y < PF_H - 8 and -10 < self.x < PF_W + 10
        if on:
            self.entered = True
        elif self.entered and (self.y > PF_H + 40 or self.y < -70 or self.x < -60 or self.x > PF_W + 60):
            self.alive = False
            self.escaped = True
            return
        if self.kind == 'asteroid':
            self.spr = self.spr_frames[(self.t // 20) % 4]
        if self.kind == 'golden' and self.t % 4 == 0:
            g.fx.particle(self.x + random.uniform(-6, 6), self.y + random.uniform(-4, 4), 0, 0.3, 14, 1,
                          (255, 240, 140), 'spark', 0.95)
        if self.kind == 'carrier' and self.t % 6 == 0:
            g.fx.particle(self.x + random.uniform(-7, 7), self.y - 5, 0, -0.5, 12, 2, (255, 230, 90), 'sq', 0.95)
        if self.fire_kind and not self.no_fire and on and self.t > 25 and g.player.alive and g.allow_enemy_fire:
            self.update_fire()

    def update_fire(self):
        g = self.game
        p = g.player
        if self.telegraph > 0:
            self.telegraph -= 1
            if self.telegraph == 0:
                self.do_fire()
            return
        rate = g.diff['fire_rate'] * g.fire_mult
        self.fire_t -= rate
        if self.fire_t <= 0:
            self.fire_t = self.interval * random.uniform(0.8, 1.25)
            if math.hypot(p.x - self.x, p.y - self.y) < 46 and self.fire_kind != 'spawn':
                return  # no point-blank cheap shots
            if self.fire_kind == 'snipe':
                self.telegraph = 48
                self.snipe_angle = g.telegraph_line(self.x, self.y, p.x, p.y, 48, (255, 60, 60), follow=self)
                return
            self.do_fire()

    def do_fire(self):
        g = self.game
        agg = g.diff['aggression']
        x, y = self.x, self.y + self.h / 2
        k = self.fire_kind
        if k == 'aimed':
            n = 1 + (2 if agg > 0.55 and random.random() < agg else 0)
            B.aimed(g, x, y, 1.75, n, 14, 's', 0)
        elif k == 'fan':
            n = 5 + int(agg * 4)
            B.aimed(g, x, y, 1.45, n, 13, 'm', 1)
        elif k == 'drop':
            B.shoot(g, x, y, math.pi / 2, 1.5, 'm', 1)
            if agg > 0.4:
                B.shoot(g, x, y, math.pi / 2 + 0.35, 1.3, 's', 1)
                B.shoot(g, x, y, math.pi / 2 - 0.35, 1.3, 's', 1)
        elif k == 'burst':
            n = 3 + int(agg * 2)
            for i in range(n):
                B.aimed(g, x, y, 2.0 + i * 0.12, 1, 0, 's', 0, delay=i * 6)
        elif k == 'snipe':
            a = self.snipe_angle if self.snipe_angle is not None else B.angle_to_player(g, x, y)
            for i in range(3 + int(agg * 2)):
                B.shoot(g, x, y, a, 3.2 + i * 0.25, 'needle', 0, delay=i * 4)
            g.sfx('snipe')
        elif k == 'mines':
            B.shoot(g, x, y, math.pi / 2, 0.55, 'm', 1, kind='mine', life=150 + random.randint(0, 40))
        elif k == 'spawn':
            if g.count_kind('larva') < 14:
                for _ in range(1 + int(agg * 1.5)):
                    e = Enemy(g, 'larva', self.x + random.uniform(-6, 6), self.y + 6, p_larva)
                    g.add_enemy(e)

    # ------------------------------------------------------------ damage
    def damage(self, amount, kind='shot'):
        if not self.alive:
            return False
        g = self.game
        if self.kind == 'shielded' and kind in ('shot', 'drone'):
            amount *= 0.25
            if self.deflect_t == 0:
                self.deflect_t = 8
                g.fx.sparks(self.x, self.y + self.h / 2, 3, (120, 200, 255), 2, 8)
                g.sfx('deflect')
        self.hp -= amount
        self.flash = 3
        if self.hp <= 0:
            self.alive = False
            g.kill_enemy(self)
            return True
        return False

    # ------------------------------------------------------------ draw
    def draw(self, surf):
        s = art.white(self.spr) if self.flash else self.spr
        x = int(self.x) - s.get_width() // 2
        y = int(self.y) - s.get_height() // 2
        if self.kind == 'carrier':
            glow = art.outlined(s, (255, 230, 90)) if (self.t // 8) % 2 else None
            if glow:
                surf.blit(glow, (x - 1, y - 1))
        surf.blit(s, (x, y))
        if self.kind == 'shielded':
            col = (120, 200, 255) if self.deflect_t == 0 else WHITE
            yy = int(self.y + self.h / 2 + 3)
            pygame.draw.arc(surf, col, (int(self.x) - 9, yy - 8, 18, 10), math.pi * 1.1, math.pi * 1.9, 2)
        elif self.kind == 'turret' and self.game.player.alive:
            p = self.game.player
            a = math.atan2(p.y - self.y, p.x - self.x)
            pygame.draw.line(surf, (40, 36, 56), (int(self.x), int(self.y)),
                             (int(self.x + math.cos(a) * 9), int(self.y + math.sin(a) * 9)), 4)
            pygame.draw.line(surf, (190, 190, 210), (int(self.x), int(self.y)),
                             (int(self.x + math.cos(a) * 8), int(self.y + math.sin(a) * 8)), 2)
        elif self.kind == 'nest':
            pulse = (self.t // 10) % 2
            if pulse:
                pygame.draw.circle(surf, (255, 90, 90), (int(self.x), int(self.y) - 1), 3)


# ====================================================================== paths
# Each path is a generator: one step per frame. It moves the enemy and yields.

def p_straight(e, g, vx=0.0, vy=1.3):
    while True:
        e.x += vx
        e.y += vy * g.scroll_mult
        yield


def make_straight(vx=0.0, vy=1.3):
    return lambda e, g: p_straight(e, g, vx, vy)


def p_dive(e, g, vy=1.6, steer=0.03):
    while True:
        e.y += vy * g.scroll_mult
        p = g.player
        if 40 < e.y < p.y - 40:
            e.vx += max(-steer, min(steer, (p.x - e.x) * 0.002))
            e.vx *= 0.97
        e.x += e.vx
        yield


def make_dive(vy=1.6, steer=0.03):
    return lambda e, g: p_dive(e, g, vy, steer)


def p_sine(e, g, vy=1.0, amp=40, freq=0.03, phase=0.0):
    x0 = e.x
    t = 0
    while True:
        t += 1
        e.y += vy * g.scroll_mult
        e.x = x0 + math.sin(t * freq + phase) * amp
        yield


def make_sine(vy=1.0, amp=40, freq=0.03, phase=0.0):
    return lambda e, g: p_sine(e, g, vy, amp, freq, phase)


def bezier(p0, p1, p2, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def p_swoop(e, g, start, ctrl, slot, hold=240, enter=70):
    """Galaga style: curve into a formation slot, sway, then dive at the player."""
    for i in range(enter):
        e.x, e.y = bezier(start, ctrl, slot, (i + 1) / enter)
        yield
    t = 0
    while t < hold:
        t += 1
        e.x = slot[0] + math.sin(g.frame * 0.025) * 10
        e.y = slot[1] + math.sin(g.frame * 0.05 + slot[0] * 0.1) * 2
        yield
    # dive
    vx = 0.0
    vy = 0.5
    side = 1 if e.x < PF_W / 2 else -1
    for i in range(30):
        e.y -= 0.6
        e.x += side * 0.8
        yield
    while True:
        vy = min(3.2, vy + 0.08)
        p = g.player
        if e.y < p.y - 30:
            vx += max(-0.08, min(0.08, (p.x - e.x) * 0.004))
        vx *= 0.98
        e.x += vx
        e.y += vy
        yield


def p_hover(e, g, target_y=70, hold=300, strafe=40):
    while e.y < target_y:
        e.y += max(0.5, (target_y - e.y) * 0.05)
        yield
    t = 0
    x0 = e.x
    while t < hold:
        t += 1
        e.x = x0 + math.sin(t * 0.02) * strafe
        yield
    while True:
        e.y += 1.4
        yield


def make_hover(target_y=70, hold=300, strafe=40):
    return lambda e, g: p_hover(e, g, target_y, hold, strafe)


def p_kamikaze(e, g, stop_y=50):
    while e.y < stop_y:
        e.y += 2.0
        yield
    for i in range(24):
        e.flash = 1 if i % 6 < 2 else 0
        yield
    p = g.player
    a = math.atan2(p.y - e.y, p.x - e.x)
    spd = 1.0
    for i in range(400):
        spd = min(4.2, spd + 0.12)
        if i < 30 and p.alive:
            want = math.atan2(p.y - e.y, p.x - e.x)
            d = (want - a + math.pi) % math.tau - math.pi
            a += max(-0.05, min(0.05, d))
        e.x += math.cos(a) * spd
        e.y += math.sin(a) * spd
        if i % 2 == 0:
            g.fx.particle(e.x, e.y, 0, 0, 8, 2, (255, 120, 60), 'sq', 0.9)
        yield


def p_larva(e, g):
    a = math.pi / 2 + random.uniform(-0.8, 0.8)
    spd = 1.2
    for i in range(500):
        p = g.player
        if p.alive and i % 3 == 0:
            want = math.atan2(p.y - e.y, p.x - e.x)
            d = (want - a + math.pi) % math.tau - math.pi
            a += max(-0.04, min(0.04, d))
        spd = min(2.0, spd + 0.01)
        e.x += math.cos(a) * spd
        e.y += math.sin(a) * spd + g.scroll * 0.3
        yield


def p_behind(e, g, vy=-1.5, amp=24):
    x0 = e.x
    t = 0
    while True:
        t += 1
        e.y += vy
        e.x = x0 + math.sin(t * 0.04) * amp
        yield


def p_circle(e, g, cx, cy, r, direction=1, laps=1.3, phase=0.0):
    # enter straight down to the circle top
    sx = cx + math.cos(phase) * r
    sy = cy + math.sin(phase) * r
    while e.y < sy:
        e.y += 2.2
        e.x += (sx - e.x) * 0.08
        yield
    a = phase
    total = laps * math.tau
    done = 0.0
    while done < total:
        a += 0.035 * direction
        done += 0.035
        e.x = cx + math.cos(a) * r
        e.y = cy + math.sin(a) * r
        yield
    while True:
        e.y += 2.0
        yield


def p_ground(e, g):
    while True:
        e.y += g.scroll
        yield


def p_wall(e, g, side):
    """Turret clamped to a station corridor wall."""
    while True:
        e.y += g.scroll
        lo, hi = g.hazards.corridor_at(e.y) if g.hazards else (0, PF_W)
        e.x = (lo + 7) if side < 0 else (hi - 7)
        yield


def p_golden(e, g):
    rnd = random.Random(g.frame)
    tx, ty = e.x, 60
    t = 0
    while t < 400:
        t += 1
        if t % 28 == 0 or math.hypot(tx - e.x, ty - e.y) < 6:
            tx = rnd.uniform(24, PF_W - 24)
            ty = rnd.uniform(30, 150)
        e.x += (tx - e.x) * 0.09
        e.y += (ty - e.y) * 0.09
        yield
    g.popup_world(e.x, e.y + 12, 'IT ESCAPED!', (255, 200, 80))
    while True:
        e.y -= 4.5
        yield


def p_carrier(e, g):
    x0 = e.x
    t = 0
    while True:
        t += 1
        e.y += 0.55 * g.scroll_mult
        e.x = x0 + math.sin(t * 0.015) * 30
        yield


def p_drift(e, g, vx, vy):
    while True:
        e.x += vx
        e.y += vy * g.scroll_mult
        yield


def make_drift(vx, vy):
    return lambda e, g: p_drift(e, g, vx, vy)


def p_snake(e, g, idx, vy=1.25, amp=70, freq=0.025):
    x0 = PF_W / 2
    t = -idx * 14
    while True:
        t += 1
        e.y += vy * g.scroll_mult
        e.x = x0 + math.sin(max(0, t) * freq) * amp
        yield


# ====================================================================== waves
def spawn_wave(g, w):
    """Spawn a wave described by a dict from the level timeline."""
    pat = w['pattern']
    kind = w.get('kind', 'dart')
    n = max(1, int(w.get('count', 5)))
    rnd = random.Random(w.get('seed', 0))
    side = w.get('side', rnd.choice((-1, 1)))
    hp = w.get('hp', 1.0)

    def add(k, x, y, path, delay=0, **kw):
        def make():
            g.add_enemy(Enemy(g, k, x, y, path, hp, **kw))
        if delay:
            g.schedule(delay, make)
        else:
            make()

    if pat == 'v':
        cx = w.get('x', rnd.uniform(70, PF_W - 70))
        path = make_dive(1.5, 0.02) if kind in ('dart', 'kamikaze') else make_straight(0, 1.2)
        for i in range(n):
            k = (i + 1) // 2
            s = -1 if i % 2 else 1
            add(kind, cx + s * k * 15, -14 - k * 12, path)
    elif pat == 'line':
        gap = PF_W / (n + 1)
        for i in range(n):
            add(kind, gap * (i + 1), -14, make_straight(0, 0.9), i * 4)
    elif pat == 'column':
        x = w.get('x', rnd.uniform(40, PF_W - 40))
        path = make_dive(1.8, 0.04) if kind in ('dart',) else make_straight(0, 1.5)
        for i in range(n):
            add(kind, x, -14, path, i * 14)
    elif pat == 'swoop':
        rows = 1 if n <= 6 else 2
        per = math.ceil(n / rows)
        hold = w.get('hold', 260)
        for i in range(n):
            r, c = divmod(i, per)
            slot = (PF_W / 2 + (c - (per - 1) / 2) * 24, 52 + r * 22)
            sx = -20 if side < 0 else PF_W + 20
            start = (sx, 30 + r * 10)
            ctrl = (PF_W / 2 - side * 30, 190)
            delay = i * 9
            add(kind, start[0], start[1],
                (lambda st, ct, sl, hd: (lambda e, gg: p_swoop(e, gg, st, ct, sl, hd)))(start, ctrl, slot, hold + (n - i) * 9),
                delay)
    elif pat == 'pincer':
        half = max(1, n // 2)
        for s in (-1, 1):
            for i in range(half):
                start = (-20 if s < 0 else PF_W + 20, 20)
                ctrl = (PF_W / 2, 140)
                slot = (PF_W / 2 + s * (30 + i * 22), 70 + i * 6)
                add(kind, start[0], start[1],
                    (lambda st, ct, sl: (lambda e, gg: p_swoop(e, gg, st, ct, sl, 90)))(start, ctrl, slot),
                    i * 10)
    elif pat == 'circle':
        cx = w.get('x', PF_W / 2)
        for i in range(n):
            ph = -math.pi / 2
            add(kind, cx, -14,
                (lambda d: (lambda e, gg: p_circle(e, gg, cx, 110, 60, side, 1.25, ph)))(i),
                i * 12)
    elif pat == 'snake':
        amp = rnd.uniform(50, 95)
        for i in range(n):
            add(kind, PF_W / 2, -14, (lambda ii: (lambda e, gg: p_snake(e, gg, ii, 1.25, amp)))(i), i * 12)
    elif pat == 'wall':
        gap_i = rnd.randrange(n)
        step = PF_W / n
        for i in range(n):
            if i == gap_i:
                continue
            add(kind, step * (i + 0.5), -14, make_straight(0, 1.0))
    elif pat == 'ambush':
        for i in range(n):
            x = 40 + rnd.uniform(0, PF_W - 80)
            g.warn_marker(x, PF_H - 10, 60)
            add(kind, x, PF_H + 16, lambda e, gg: p_behind(e, gg, -1.5, 20), 60 + i * 16)
    elif pat == 'hover':
        for i in range(n):
            x = PF_W * (i + 1) / (n + 1)
            add(kind, x, -16, make_hover(50 + (i % 2) * 26, w.get('hold', 360), 34), i * 20)
    elif pat == 'rush':
        for i in range(n):
            add(kind, rnd.uniform(20, PF_W - 20), -14,
                (lambda sy: (lambda e, gg: p_kamikaze(e, gg, sy)))(rnd.uniform(30, 90)), i * 18)
    elif pat == 'rain':
        for i in range(n):
            add(kind, rnd.uniform(16, PF_W - 16), -14, make_straight(rnd.uniform(-0.3, 0.3), rnd.uniform(1.4, 2.1)),
                i * 10)
    elif pat == 'sine':
        for i in range(n):
            add(kind, PF_W / 2 + side * 60, -14, make_sine(1.0, 70, 0.028, i * 0.5), i * 14)
    elif pat == 'single':
        add(kind, w.get('x', rnd.uniform(50, PF_W - 50)), -18,
            p_carrier if kind == 'carrier' else make_straight(0, 0.9))
    elif pat == 'nests':
        for i in range(n):
            x = rnd.uniform(36, PF_W - 36)
            add('nest', x, -20, p_ground, i * 50)
    elif pat == 'turrets':
        if not g.hazards.corridor_active():
            spawn_wave(g, dict(w, pattern='line', kind='gunner'))
            return
        for i in range(n):
            s = -1 if i % 2 == 0 else 1
            add('turret', 0, -12, (lambda ss: (lambda e, gg: p_wall(e, gg, ss)))(s), i * 40)
    else:
        for i in range(n):
            add(kind, rnd.uniform(20, PF_W - 20), -14, make_straight(0, 1.3), i * 12)


def spawn_golden(g):
    side = random.choice((-1, 1))
    e = Enemy(g, 'golden', -14 if side < 0 else PF_W + 14, 50, p_golden)
    g.add_enemy(e)
    g.sfx('golden')
    g.banner('GOLDEN SHIP!', (255, 220, 80), 70)
    return e
