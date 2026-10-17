"""Boss framework, the generic end-fight frigate, 10 mini-bosses and 10 sector bosses.

A boss has a main health pool split into phases. Each phase runs an attack
script written as a generator (one step per frame). Parts (turrets, armour,
cores) can be shot separately.
"""
import math
import random

import pygame

import art
import bullets as B
import enemies as E
import level_data as D
import levels
from config import PF_W, PF_H, WHITE, COMBO_WINDOW

_cache = {}


def wait(n):
    for _ in range(int(n)):
        yield


class Part:
    is_boss_part = True
    kind = 'part'
    counts = False
    ground = False

    def __init__(self, boss, ox, oy, w, h, sprite=None, hp=None, core=False, armor=1.0, name=''):
        self.boss = boss
        self.ox, self.oy = ox, oy
        self.w, self.h = w, h
        self.sprite = sprite
        self.max_hp = hp
        self.hp = hp
        self.core = core
        self.armor = armor
        self.name = name
        self.alive = True
        self.active = True
        self.visible = True
        self.flash = 0
        self.x = boss.x + ox
        self.y = boss.y + oy

    def damage(self, amount, kind='shot'):
        b = self.boss
        if not self.alive or not self.active:
            return False
        if b.invulnerable():
            if random.random() < 0.25:
                b.game.fx.sparks(self.x, self.y + self.h / 3, 2, (180, 180, 220), 1.5, 6)
            return False
        amount *= self.armor
        if amount <= 0:
            if random.random() < 0.3:
                b.game.fx.sparks(self.x, self.y + self.h / 3, 2, (120, 200, 255), 1.5, 6)
                b.game.sfx('deflect')
            return False
        self.flash = 3
        if self.hp is not None:
            self.hp -= amount
            b.take_damage(amount * 0.4, kind)
            if self.hp <= 0:
                self.alive = False
                b.part_destroyed(self)
        else:
            b.take_damage(amount, kind)
        return True


class Boss:
    name = 'FRIGATE'
    kind = 'frigate'
    phases = (1.0, 0.5)
    hp_scale = 1.0
    home_y = 74

    def __init__(self, game):
        self.game = game
        self.sector = game.sector
        self.level = game.level
        self.rnd = random.Random(game.level * 13 + 5)
        self.x = PF_W / 2
        self.y = -70.0
        hp = levels.expected_dps(game.level) * D.END_FIGHT_SECONDS[self.kind] * self.hp_scale
        self.max_hp = self.hp = hp
        self.t = 0
        self.alive = True
        self.fighting = False
        self.phase_index = 0
        self.trans = 0
        self.dying = 0
        self.flash = 0
        self.parts = []
        self.script = None
        self.mover = None
        self.last_freeze = -100
        self.body = None
        self.angry = False
        self.style = art.SECTOR_STYLE[self.sector]
        self.pal = art.sector_pal(self.sector)
        self.build()

    # ------------------------------------------------------------ to override
    def build(self):
        pass

    def phase_script(self, i):
        return wait(60)

    def move(self):
        self.x = PF_W / 2 + math.sin(self.t * 0.012) * 50
        self.y = self.home_y + math.sin(self.t * 0.025) * 5

    def on_phase(self, i):
        pass

    def draw_extra(self, surf):
        pass

    # ------------------------------------------------------------ framework
    def add_part(self, *a, **kw):
        p = Part(self, *a, **kw)
        self.parts.append(p)
        return p

    def hp_fraction(self):
        return max(0.0, self.hp) / self.max_hp

    def phase_marks(self):
        return list(self.phases[1:])

    def invulnerable(self):
        return (not self.fighting) or self.trans > 0 or self.dying > 0

    def targets(self):
        return [p for p in self.parts if p.alive and p.active and p.visible]

    def pos(self, src):
        if isinstance(src, Part):
            return src.x, src.y + src.h * 0.3
        if src is None:
            return self.x, self.y + (self.body.get_height() * 0.3 if self.body else 10)
        return self.x + src[0], self.y + src[1]

    def update(self):
        g = self.game
        self.t += 1
        if self.flash:
            self.flash -= 1
        for p in self.parts:
            if p.flash:
                p.flash -= 1
            p.x = self.x + p.ox
            p.y = self.y + p.oy
        if self.dying > 0:
            self.update_dying()
            return
        if not self.fighting:
            self.y += max(0.4, (self.home_y - self.y) * 0.035)
            if self.y >= self.home_y - 1:
                self.y = self.home_y
                self.fighting = True
                self.script = self.phase_script(0)
            return
        if self.trans > 0:
            self.trans -= 1
            if self.trans % 9 == 0:
                bw = self.body.get_width() if self.body else 40
                bh = self.body.get_height() if self.body else 30
                g.fx.explosion(self.x + random.uniform(-bw / 3, bw / 3), self.y + random.uniform(-bh / 3, bh / 3), 'm')
            if self.trans == 0:
                self.script = self.phase_script(self.phase_index)
            return
        if self.mover is not None:
            try:
                next(self.mover)
            except StopIteration:
                self.mover = None
        else:
            self.move()
        if self.script is not None:
            try:
                next(self.script)
            except StopIteration:
                self.script = self.phase_script(self.phase_index)

    def take_damage(self, amount, kind='shot'):
        if self.invulnerable():
            return
        g = self.game
        self.hp -= amount
        self.flash = 2
        if g.combo > 0:
            g.combo_t = max(g.combo_t, int(COMBO_WINDOW * 0.7))
        if kind in ('missile', 'bomb') and self.t - self.last_freeze > 24:
            self.last_freeze = self.t
            g.fx.freeze(2)
            g.fx.shake(0.12)
        nxt = self.phase_index + 1
        if self.hp <= 0:
            self.hp = 0
            self.start_dying()
        elif nxt < len(self.phases) and self.hp / self.max_hp <= self.phases[nxt]:
            self.start_transition(nxt)

    def start_transition(self, idx):
        g = self.game
        self.phase_index = idx
        self.trans = 100
        self.script = None
        self.mover = None
        g.beams.clear()
        g.telegraphs.clear()
        n = len(g.ebullets)
        for b in g.ebullets[:80]:
            g.fx.particle(b.x, b.y, 0, -0.5, 16, 2, (255, 240, 170), 'sq', 0.95)
        g.ebullets.clear()
        if n:
            g.add_score(n * 10)
        g.fx.explosion(self.x, self.y, 'l')
        g.fx.freeze(12)
        g.fx.shake(0.7)
        g.fx.screen_flash(10, (255, 255, 255))
        g.sfx('phase')
        if self.kind != 'frigate':
            self.angry = True
            last = idx >= len(self.phases) - 1 and len(self.phases) >= 3
            g.app.audio.play_music(('rage' if last else 'angry', self.sector))
            g.banner('PHASE %d' % (idx + 1), (255, 120, 80), 70)
        self.on_phase(idx)

    def part_destroyed(self, p):
        g = self.game
        g.fx.explosion(p.x, p.y, 'm', p.sprite)
        g.fx.freeze(5)
        g.fx.shake(0.3)
        g.sfx('explode_m')
        g.add_score(2000 * g.mult)
        g.add_combo(2)
        g.fx.popup(p.x, p.y - 8, 'PART DESTROYED', (255, 200, 120), 40)
        if p.core and p.hp is not None:
            self.take_damage(self.max_hp, 'bomb')

    def start_dying(self):
        g = self.game
        self.dying = 80
        self.script = None
        self.mover = None
        g.beams.clear()
        g.telegraphs.clear()
        g.ebullets.clear()
        g.fx.freeze(14)
        g.fx.screen_flash(8)
        g.sfx('boss_hit')

    def update_dying(self):
        g = self.game
        self.dying -= 1
        bw = self.body.get_width() if self.body else 40
        bh = self.body.get_height() if self.body else 30
        if self.dying % 5 == 0:
            g.fx.explosion(self.x + random.uniform(-bw / 2.2, bw / 2.2), self.y + random.uniform(-bh / 2.2, bh / 2.2),
                           random.choice(('m', 'm', 'l')))
            g.sfx('explode_m')
        self.x += random.uniform(-1, 1)
        self.y += 0.15
        g.fx.shake(0.08)
        if self.dying <= 0:
            self.alive = False
            g.fx.explosion(self.x, self.y, 'xl', self.body)
            for p in self.parts:
                if p.alive and p.sprite is not None:
                    g.fx.shatter(p.sprite, p.x, p.y, 4)
            g.fx.explosion(self.x - bw / 4, self.y, 'l')
            g.fx.explosion(self.x + bw / 4, self.y, 'l')
            g.fx.freeze(16)
            g.fx.screen_flash(22)
            g.fx.shake(1.0)
            g.sfx('boss_explode')
            g.boss_defeated(self)

    def touches(self, px, py):
        if self.body is None or self.dying > 0 or not self.fighting:
            return False
        return abs(px - self.x) < self.body.get_width() * 0.3 and abs(py - self.y) < self.body.get_height() * 0.28

    def bomb_hit(self, dmg):
        for p in self.targets():
            if p.hp is not None:
                p.damage(dmg * 0.3, 'bomb')
        self.take_damage(dmg, 'bomb')

    def reward_credits(self):
        return {'frigate': 60, 'miniboss': 160, 'boss': 320}[self.kind]

    def score_value(self):
        return {'frigate': 10000, 'miniboss': 30000, 'boss': 80000}[self.kind]

    # ------------------------------------------------------------ drawing
    def blit_center(self, surf, s, x, y, flash=False):
        if flash == 'full':
            s = art.white(s)
        elif flash:
            s = art.tinted(s, (255, 255, 255), 0.55)
        surf.blit(s, (int(x - s.get_width() / 2), int(y - s.get_height() / 2)))

    def draw(self, surf):
        if not self.alive:
            return
        if self.trans > 0 and (self.trans // 3) % 2 == 0:
            flash = 'full'
        else:
            flash = self.flash > 0 and self.t % 3 == 0
        if self.body is not None:
            body = self.body
            if self.angry and (self.t // 6) % 2 == 0:
                body = art.tinted(body, (255, 40, 40), 0.18)
            self.blit_center(surf, body, self.x, self.y, flash)
        for p in self.parts:
            if p.alive and p.visible and p.sprite is not None:
                self.blit_center(surf, p.sprite, p.x, p.y, flash or (p.flash > 0 and self.t % 3 == 0))
        self.draw_extra(surf)

    # ------------------------------------------------------------ attack helpers
    def charge(self, src, frames=40, color=(255, 120, 120)):
        """Visible charge-up at a gun: converging sparks + shrinking circle."""
        g = self.game
        x, y = self.pos(src)
        g.telegraph_circle(x, y, 16, frames, color)
        g.sfx('charge')
        for i in range(frames):
            if i % 3 == 0:
                x, y = self.pos(src)
                a = random.uniform(0, math.tau)
                r = random.uniform(14, 22)
                g.fx.particle(x + math.cos(a) * r, y + math.sin(a) * r, -math.cos(a) * r / 10, -math.sin(a) * r / 10,
                              10, 2, color, 'sq', 1.0)
            yield

    def aimed(self, src, n=3, spread=12, speed=1.9, size='s', style=0, **kw):
        x, y = self.pos(src)
        return B.aimed(self.game, x, y, speed, n, spread, size, style, **kw)

    def fan(self, src, center, n, spread, speed, size='s', style=0, **kw):
        x, y = self.pos(src)
        return B.fan(self.game, x, y, center, n, spread, speed, size, style, **kw)

    def ring(self, src, n, speed, size='s', style=1, offset=None, **kw):
        x, y = self.pos(src)
        return B.ring(self.game, x, y, n, speed, random.uniform(0, 1) if offset is None else offset, size, style, **kw)

    def g_spiral(self, src, frames, arms=3, rot=0.11, speed=1.5, gap=5, size='s', style=1):
        a = random.uniform(0, math.tau)
        for i in range(frames):
            if i % gap == 0:
                x, y = self.pos(src)
                for k in range(arms):
                    B.shoot(self.game, x, y, a + k * math.tau / arms, speed, size, style)
                a += rot * gap
            yield

    def g_bursts(self, src, count=3, gap=14, n=3, spread=10, speed=2.0, size='s', style=0):
        for _ in range(count):
            self.aimed(src, n, spread, speed, size, style)
            self.game.sfx('enemy_shot')
            yield from wait(gap)

    def g_laser(self, src, angle=None, warn=50, dur=70, width=10, color=None, spin=0.0):
        g = self.game
        x, y = self.pos(src)
        a = B.angle_to_player(g, x, y) if angle is None else angle
        col = color or self.style['bullets'][1]
        g.telegraph_angle(x, y, a, warn, (255, 70, 70), width=1)
        yield from self.charge(src, warn, (255, 140, 140))
        x, y = self.pos(src)
        bm = g.beam(x, y, a, dur, width, col)
        if spin:
            bm['spin'] = spin
        g.fx.shake(0.25)
        g.sfx('laser')
        yield from wait(dur)

    def g_sweep(self, src, a0, a1, frames, width=9, warn=45):
        g = self.game
        x, y = self.pos(src)
        g.telegraph_angle(x, y, a0, warn, (255, 70, 70))
        g.telegraph_angle(x, y, a1, warn, (255, 140, 70))
        yield from self.charge(src, warn)
        x, y = self.pos(src)
        bm = g.beam(x, y, a0, frames + 6, width, self.style['bullets'][1])
        bm['spin'] = (a1 - a0) / frames
        g.sfx('laser')
        yield from wait(frames)

    def g_rain(self, frames, every=4, speed=1.6, size='s', style=0):
        g = self.game
        for i in range(frames):
            if i % every == 0:
                B.shoot(g, random.uniform(6, PF_W - 6), -6, math.pi / 2 + random.uniform(-0.15, 0.15),
                        speed * random.uniform(0.8, 1.2), size, style)
            yield

    def g_wall(self, rows=3, gap_w=46, speed=1.3, spacing=40, style=1):
        g = self.game
        for r in range(rows):
            gx = random.uniform(30, PF_W - 30 - gap_w)
            g.telegraph_rect((gx, 0, gap_w, 12), 30, (120, 255, 140))
            yield from wait(18)
            x = 4
            while x < PF_W:
                if not (gx < x < gx + gap_w):
                    B.shoot(g, x, self.y + 10, math.pi / 2, speed, 'm', style, raw=False)
                x += 11
            yield from wait(spacing)

    def g_minions(self, kind, n=4, pattern='v'):
        E.spawn_wave(self.game, dict(pattern=pattern, kind=kind, count=n, seed=random.randrange(99999)))
        yield from wait(10)

    def g_mines(self, n=4):
        g = self.game
        for i in range(n):
            x, y = self.pos(None)
            B.shoot(g, x, y, math.pi / 2 + random.uniform(-0.9, 0.9), 0.9, 'm', 1, kind='mine',
                    life=110 + i * 10, ax=0, ay=-0.006)
            yield from wait(8)

    def g_missiles(self, src, n=4, turn=0.03):
        g = self.game
        for i in range(n):
            x, y = self.pos(src)
            a = math.pi / 2 + (i - (n - 1) / 2) * 0.5
            B.shoot(g, x, y, a, 1.6, 'm', 0, turn=turn, life=200)
            g.sfx('missile')
            yield from wait(7)

    def g_charge(self, frames_warn=45):
        """Ram: telegraph a lane at the player's x, then dash down and back."""
        g = self.game
        tx = g.player.x
        bw = self.body.get_width() if self.body else 40
        g.telegraph_rect((tx - bw / 2, self.y, bw, PF_H), frames_warn, (255, 80, 80))
        g.sfx('charge')
        sx = self.x
        for i in range(frames_warn):
            self.x = sx + (tx - sx) * min(1.0, i / (frames_warn * 0.6))
            yield
        sy = self.y
        vy = 2.0
        while self.y < PF_H - 30:
            vy = min(9.0, vy + 0.5)
            self.y += vy
            yield
        g.fx.shake(0.5)
        g.sfx('explode_m')
        self.ring(None, 12, 1.4, 's', 1)
        while self.y > sy:
            self.y -= 3.0
            yield
        self.y = sy


# ====================================================================== sprites
def turret_sprite(sector, big=False):
    key = ('turret', sector, big)
    s = _cache.get(key)
    if s is None:
        pal = art.sector_pal(sector)
        if big:
            rows = ["...MM", "..#MM", ".##CC", "##CCC", "###CC", ".####", "..###"]
        else:
            rows = ["..M", ".#M", "##C", "##C", ".##"]
        s = art.flip_v(art.sprite(rows, pal))
        _cache[key] = s
    return s


def frigate_sprite(sector, variant):
    key = ('frigate', sector, variant)
    s = _cache.get(key)
    if s is not None:
        return s
    w, h = 66, 42
    c = art.Canvas(w, h, mirror=True)
    if variant == 0:      # cruiser
        c.poly([(33, 0), (40, 12), (40, 38), (26, 38), (26, 12)], '#')
        c.poly([(26, 16), (4, 26), (4, 32), (26, 32)], '#')
        c.rect(6, 22, 6, 12, 'M')
        c.rect(26, 34, 5, 6, 'M')
        c.ellipse(33, 16, 4, 6, 'C')
        c.rect(14, 27, 10, 2, 'A')
        c.line(33, 22, 33, 36, '1')
    elif variant == 1:    # carrier
        c.ellipse(33, 20, 30, 14, '#')
        c.rect(6, 14, 54, 14, '#')
        c.rect(14, 18, 38, 6, 'K')
        c.rect(16, 19, 4, 4, 'Y')
        c.ellipse(33, 9, 6, 5, 'C')
        c.rect(8, 30, 6, 8, 'M')
        c.rect(20, 32, 4, 8, 'M')
        c.line(4, 20, 14, 20, 'A')
    else:                 # destroyer
        c.poly([(33, 0), (62, 30), (50, 36), (33, 30), (16, 36), (4, 30)], '#')
        c.poly([(33, 6), (44, 22), (33, 26), (22, 22)], 'A')
        c.ellipse(33, 16, 3, 5, 'C')
        c.rect(14, 30, 4, 8, 'M')
        c.rect(26, 28, 4, 10, 'M')
        c.line(10, 28, 24, 20, '1')
    pal = art.sector_pal(sector)
    s = art.flip_v(c.surface(pal))
    _cache[key] = s
    return s


# ====================================================================== frigate
class Frigate(Boss):
    name = 'FRIGATE'
    kind = 'frigate'
    phases = (1.0, 0.5)

    def build(self):
        v = self.level % 3
        self.variant = v
        self.body = frigate_sprite(self.sector, v)
        bw, bh = self.body.get_size()
        self.name = ('CRUISER', 'BATTLE BARGE', 'DESTROYER')[v]
        self.core = self.add_part(0, 0, bw * 0.5, bh * 0.6, None, None, core=True)
        tp = turret_sprite(self.sector)
        self.turrets = [self.add_part(-bw * 0.3, bh * 0.05, 9, 9, tp, self.max_hp * 0.12),
                        self.add_part(bw * 0.3, bh * 0.05, 9, 9, tp, self.max_hp * 0.12)]
        attacks = ['bursts', 'fan', 'ring', 'spiral', 'laser', 'minions', 'mines', 'missiles', 'wall', 'rain']
        rnd = self.rnd
        self.p1_attacks = rnd.sample(attacks[:6], 3)
        self.p2_attacks = rnd.sample(attacks, 3)

    def do_attack(self, name, hard=False):
        agg = self.game.diff['aggression']
        live = [t for t in self.turrets if t.alive]
        if name == 'bursts':
            for t in live or [None]:
                yield from self.g_bursts(t, 3 + int(hard), 12, 3, 12, 1.9)
        elif name == 'fan':
            for i in range(2 + int(hard)):
                self.aimed(None, 7 + int(agg * 4), 11, 1.6, 'm', 1)
                self.game.sfx('enemy_shot')
                yield from wait(26)
        elif name == 'ring':
            for i in range(3 + int(hard)):
                self.ring(None, 14 + int(agg * 8), 1.4, 's', 1, offset=i * 0.12)
                yield from wait(22)
        elif name == 'spiral':
            yield from self.g_spiral(None, 120, 3 + int(hard), 0.12, 1.45, 5)
        elif name == 'laser':
            src = live[0] if live else None
            yield from self.g_laser(src, None, 45, 60, 9)
        elif name == 'minions':
            yield from self.g_minions(random.choice(('dart', 'kamikaze')), 4 + int(hard) * 2, 'v')
        elif name == 'mines':
            yield from self.g_mines(4 + int(hard) * 2)
        elif name == 'missiles':
            yield from self.g_missiles(None, 4 + int(hard) * 2)
        elif name == 'wall':
            yield from self.g_wall(2 + int(hard), 50)
        elif name == 'rain':
            yield from self.g_rain(120, 5 - int(hard), 1.5)
        yield from wait(40 - int(hard) * 12)

    def phase_script(self, i):
        lst = self.p1_attacks if i == 0 else self.p2_attacks

        def run():
            while True:
                for a in lst:
                    yield from self.do_attack(a, i > 0)
        return run()


BOSS_CLASSES = {'frigate': Frigate}


def create(game, boss_id):
    cls = BOSS_CLASSES.get(boss_id, Frigate)
    b = cls(game)
    if cls is Frigate and boss_id != 'frigate':
        b.kind = game.plan.end_kind
    return b
