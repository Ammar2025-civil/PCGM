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
from config import PF_W, PF_H, COMBO_WINDOW

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
        self.blink_t = 0
        self.mirror_pending = 0
        self.mirror_t = 0
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
        if self.mirror_pending > 0:
            self.mirror_pending -= 1
            if self.mirror_pending == 0:
                g.mirror_x = True
                g.fx.screen_flash(6, (200, 120, 255))
                g.sfx('phase')
        elif self.mirror_t > 0:
            self.mirror_t -= 1
            if self.mirror_t == 0 and g.mirror_x:
                g.mirror_x = False
                g.fx.screen_flash(6, (200, 120, 255))
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
        self.dmg_taken = getattr(self, 'dmg_taken', 0.0) + amount
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
        if self.blink_t > 0 and (self.blink_t // 2) % 2 == 0:
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
    def g_move(self, x, y, frames=40):
        sx, sy = self.x, self.y
        for i in range(frames):
            t = (i + 1) / frames
            e = t * t * (3 - 2 * t)
            self.x = sx + (x - sx) * e
            self.y = sy + (y - sy) * e
            yield

    def g_blink(self, x, y, frames=34):
        g = self.game
        g.telegraph_circle(x, y, 24, frames, (210, 160, 255))
        g.sfx('warp')
        self.blink_t = frames
        yield from wait(frames)
        g.fx.sparks(self.x, self.y, 18, (210, 160, 255), 3)
        self.x, self.y = x, y
        g.fx.ring(x, y, 4, 2.4, 18, (230, 190, 255), 2)
        self.blink_t = 0

    def g_lightning(self, xs, warn=56):
        g = self.game
        for x in xs:
            g.telegraph_rect((x - 9, 0, 18, PF_H), warn, (255, 240, 140))
        g.sfx('charge')
        yield from wait(warn)
        for x in xs:
            g.beam(x, -10, math.pi / 2, 16, 16, (200, 180, 255), PF_H + 20)
        g.sfx('thunder')
        g.fx.screen_flash(4, (230, 220, 255))
        g.fx.shake(0.3)
        yield from wait(16)

    def g_gate(self, y, gap_x, gap_w=46, warn=50, dur=48):
        g = self.game
        col = self.style['bullets'][0]
        g.telegraph_rect((0, y - 3, gap_x, 6), warn)
        g.telegraph_rect((gap_x + gap_w, y - 3, PF_W - gap_x - gap_w, 6), warn)
        g.telegraph_rect((gap_x, y - 7, gap_w, 14), warn, (120, 255, 140))
        g.sfx('charge')
        yield from wait(warn)
        if gap_x > 2:
            g.beam(0, y, 0, dur, 7, col, gap_x)
        if gap_x + gap_w < PF_W - 2:
            g.beam(gap_x + gap_w, y, 0, dur, 7, col, PF_W - gap_x - gap_w)
        g.sfx('laser')

    def bounce_fan(self, src, n=7, spread=14, speed=1.6, size='s', style=0, wb=2):
        for b in self.aimed(src, n, spread, speed, size, style):
            if b is not None:
                b.wb = wb

    def well_ring(self, src, n=16, speed=1.8, k=0.0011, life=330, style=1):
        x, y = self.pos(src)
        for b in B.ring(self.game, x, y, n, speed, random.uniform(0, 1), 's', style):
            if b is not None:
                b.well = (x, y, k)
                b.life = life

    def g_rocks(self, n=3, size=9):
        g = self.game
        for i in range(n):
            x, y = self.pos(None)
            a = B.angle_to_player(g, x, y) + random.uniform(-0.4, 0.4)
            sp = random.uniform(1.1, 1.6)
            e = E.Enemy(g, 'asteroid', x, y, E.make_drift(math.cos(a) * sp, math.sin(a) * sp), 0.3, size=size,
                        seed=random.randrange(60), ore=random.random() < 0.4)
            e.entered = True
            e.frail = True
            g.add_enemy(e)
            g.sfx('explode_s')
            yield from wait(16)

    def g_larva(self, src, n=4):
        g = self.game
        for i in range(n):
            if g.count_kind('larva') >= 16:
                break
            x, y = self.pos(src)
            g.add_enemy(E.Enemy(g, 'larva', x + random.uniform(-6, 6), y, E.p_larva))
            yield from wait(8)

    def acid(self, src, n=6, speed=2.2, style=1):
        x, y = self.pos(src)
        for i in range(n):
            a = -math.pi / 2 + random.uniform(-1.1, 1.1)
            B.shoot(self.game, x, y, a, speed * random.uniform(0.8, 1.2), 'm', style, ay=0.045)

    def g_dash(self, y=None, speed=6.0):
        g = self.game
        y = g.player.y - 20 if y is None else y
        y = max(60, min(PF_H - 60, y))
        side = -1 if self.x > PF_W / 2 else 1
        start = -40 if side > 0 else PF_W + 40
        g.telegraph_rect((0, y - 10, PF_W, 20), 50, (255, 90, 90))
        g.sfx('charge')
        yield from self.g_move(start, y, 30)
        yield from wait(20)
        while (side > 0 and self.x < PF_W + 40) or (side < 0 and self.x > -40):
            self.x += side * speed
            if int(self.x) % 18 < speed:
                B.shoot(g, self.x, self.y, -math.pi / 2, 1.2, 's', 0)
                B.shoot(g, self.x, self.y, math.pi / 2, 1.2, 's', 0)
            yield
        yield from self.g_move(PF_W / 2, self.home_y, 50)

    def start_mirror(self, frames=300):
        if self.mirror_pending or self.game.mirror_x:
            return
        self.game.banner('MIRROR FLIP', (200, 150, 255), 70)
        self.game.sfx('warning_short')
        self.mirror_pending = 70
        self.mirror_t = frames

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
        E.spawn_wave(self.game, dict(pattern=pattern, kind=kind, count=n, seed=random.randrange(99999), minion=True))
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


# ====================================================================== roster helpers
def boss_pal(body, acc, glass=(120, 240, 255), metal=(140, 146, 170)):
    return art.make_pal(body, acc, glass=glass, metal=metal)


def build_sprite(key, w, h, pal, fn):
    s = _cache.get(key)
    if s is None:
        c = art.Canvas(w, h, mirror=True)
        fn(c)
        s = c.surface(pal)
        _cache[key] = s
    return s


def pod_sprite(key, pal, rows):
    s = _cache.get(key)
    if s is None:
        s = art.sprite(rows, pal)
        _cache[key] = s
    return s


POD_ROWS = ["..MM", ".#MM", "##CC", "##CC", "####", ".#M.", "..M."]
SAC_ROWS = ["..###", ".#AAA", "#A6AA", "#AAAA", "#AAA4", ".#AA.", "..#.."]


def rnd_x(margin=40):
    return random.uniform(margin, PF_W - margin)


# ====================================================================== MINI-BOSSES
class Sentinel(Boss):
    name = 'SENTINEL GUNSHIP'
    kind = 'miniboss'
    phases = (1.0, 0.5)
    hp_scale = 1.05

    def build(self):
        pal = boss_pal((200, 206, 224), (220, 60, 70))

        def f(c):
            c.poly([(32, 40), (10, 24), (4, 8), (16, 2), (32, 8)], '#')
            c.rect(8, 6, 7, 18, 'A')
            c.rect(16, 30, 4, 8, 'M')
            c.ellipse(32, 20, 10, 9, 'M')
            c.ellipse(32, 21, 6, 6, 'C')
            c.line(16, 12, 26, 18, '1')
            c.put(10, 4, 'R')
        self.body = build_sprite('sentinel', 64, 42, pal, f)
        pod = pod_sprite('sentinel_pod', pal, POD_ROWS)
        self.guns = [self.add_part(-20, 10, 10, 12, pod, self.max_hp * 0.14),
                     self.add_part(20, 10, 10, 12, pod, self.max_hp * 0.14)]
        self.core = self.add_part(0, 0, 30, 24, None, None, core=True)

    def phase_script(self, i):
        def p1():
            while True:
                for gun in self.guns:
                    if gun.alive:
                        yield from self.g_bursts(gun, 3, 12, 3, 12, 1.9)
                yield from wait(20)
                for _ in range(2):
                    self.aimed(None, 9, 10, 1.6, 'm', 1)
                    self.game.sfx('enemy_shot')
                    yield from wait(30)
                yield from wait(30)

        def p2():
            while True:
                yield from self.g_spiral(None, 140, 2, 0.16, 1.5, 4)
                yield from self.g_minions('dart', 5, 'swoop')
                yield from self.g_laser(None, None, 45, 60, 10)
                self.ring(None, 18, 1.4)
                yield from wait(40)
        return p1() if i == 0 else p2()


class Crusher(Boss):
    name = 'ROCK CRUSHER'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((206, 126, 56), (240, 206, 70), metal=(150, 150, 160))

        def f(c):
            c.ellipse(30, 18, 26, 16, '#')
            c.poly([(30, 50), (20, 30), (30, 26)], 'M')
            for y in range(32, 48, 4):
                c.line(23 + (y - 30) // 3, y, 30, y + 2, '7')
            c.rect(4, 14, 8, 14, 'A')
            c.poly([(4, 28), (12, 28), (6, 38)], 'M')
            c.ellipse(30, 12, 6, 5, 'C')
            c.rect(16, 6, 4, 4, 'Y')
        self.body = build_sprite('crusher', 60, 52, pal, f)
        self.core = self.add_part(0, 0, 44, 30, None, None, core=True)

    def phase_script(self, i):
        def p1():
            while True:
                yield from self.g_rocks(3, 9)
                for _ in range(2):
                    self.aimed(None, 7, 9, 1.8, 'm', 0)
                    self.game.sfx('enemy_shot')
                    yield from wait(26)
                yield from wait(30)

        def p2():
            while True:
                yield from self.g_charge(45)
                yield from wait(20)
                yield from self.g_rocks(4, 6)
                for k in range(3):
                    self.ring(None, 16, 1.4, offset=k * 0.1)
                    yield from wait(18)
                yield from wait(30)
        return p1() if i == 0 else p2()


class Wisp(Boss):
    name = 'STORM WISP'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((150, 80, 210), (255, 140, 220), glass=(255, 250, 160))

        def f(c):
            c.ellipse(28, 14, 24, 13, '#')
            c.ellipse(28, 10, 14, 7, 'A')
            c.ellipse(28, 12, 5, 4, 'C')
            for x in (8, 15, 22):
                c.line(x, 22, x - 2, 40, 'A')
                c.line(x + 1, 22, x + 1, 36, '#')
        self.body = build_sprite('wisp', 56, 44, pal, f)
        self.core = self.add_part(0, -4, 44, 26, None, None, core=True)

    def move(self):
        self.x += math.sin(self.t * 0.03) * 0.6
        self.y = self.home_y + math.sin(self.t * 0.05) * 6

    def phase_script(self, i):
        def p1():
            while True:
                yield from self.g_blink(rnd_x(), random.uniform(50, 110))
                self.ring(None, 16, 1.4)
                yield from wait(24)
                yield from self.g_bursts(None, 2, 14, 3, 14, 1.9)
                yield from self.g_lightning([self.game.player.x], 60)
                yield from wait(30)

        def p2():
            while True:
                yield from self.g_blink(rnd_x(), random.uniform(50, 110), 26)
                yield from self.g_spiral(None, 90, 3, 0.13, 1.5, 5)
                px = self.game.player.x
                yield from self.g_lightning([px - 40, px + 40], 54)
                yield from self.g_lightning([px], 46)
                yield from wait(20)
        return p1() if i == 0 else p2()


class Glacier(Boss):
    name = 'GLACIER TANK'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((150, 196, 236), (240, 250, 255), glass=(255, 110, 160), metal=(110, 130, 170))

        def f(c):
            c.rect(6, 8, 52, 26, '#')
            c.rect(2, 4, 12, 34, 'M')
            for x in (16, 24):
                c.poly([(x, 8), (x + 4, 0), (x + 8, 8)], 'A')
            c.ellipse(32, 22, 8, 7, 'C')
            c.rect(28, 32, 8, 10, 'M')
        self.body = build_sprite('glacier', 64, 44, pal, f)
        self.core = self.add_part(0, 0, 46, 30, None, None, core=True)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for _ in range(2):
                    self.bounce_fan(None, 9, 14, 1.5, 's', 0, 2)
                    g.sfx('enemy_shot')
                    yield from wait(34)
                yield from self.g_bursts(None, 3, 10, 1, 0, 2.6, 'needle', 1)
                yield from wait(30)

        def p2():
            cr = g.hazards.ensure('crystals', 0.6)
            while True:
                for x in (rnd_x(60), rnd_x(60)):
                    cr.spawn_at(x, self.y + 50)
                yield from wait(30)
                for _ in range(3):
                    self.bounce_fan(None, 7, 18, 1.7, 'm', 1, 3)
                    yield from wait(28)
                yield from self.g_laser(None, None, 45, 60, 9)
                yield from wait(40)
        return p1() if i == 0 else p2()


class Moth(Boss):
    name = 'SUN MOTH'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((240, 150, 50), (255, 230, 120), glass=(255, 60, 40))

        def f(c):
            c.ellipse(16, 14, 16, 12, 'A')
            c.ellipse(18, 32, 12, 9, 'A')
            c.ellipse(16, 14, 8, 6, '4')
            c.ellipse(34, 22, 6, 18, '#')
            c.ellipse(34, 10, 4, 3, 'C')
            c.line(30, 2, 26, -2, 'M')
        self.body = build_sprite('moth', 68, 44, pal, f)
        self.core = self.add_part(0, 0, 20, 34, None, None, core=True)
        self.wings = [(-22, 0), (22, 0)]

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for w in self.wings:
                    self.aimed(w, 5, 12, 1.7, 's', 0)
                    yield from wait(18)
                yield from self.g_rain(80, 6, 1.4, 's', 1)
                yield from wait(20)

        def p2():
            fl = g.hazards.ensure('flares', 0.5)
            while True:
                fl.trigger()
                yield from self.g_missiles(None, 4, 0.025)
                yield from wait(30)
                for k in range(3):
                    self.ring(None, 14, 1.3, 'm', 0, offset=k * 0.2)
                    yield from wait(24)
                yield from wait(140)
        return p1() if i == 0 else p2()


class SecDrone(Boss):
    name = 'SECURITY DRONE MK-IX'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((150, 156, 176), (255, 150, 40), glass=(255, 50, 60))

        def f(c):
            c.rect(12, 6, 40, 30, '#')
            c.rect(16, 10, 32, 22, '2')
            c.ellipse(32, 21, 9, 8, 'K')
            c.ellipse(32, 21, 6, 5, 'C')
            c.rect(12, 6, 40, 3, 'A')
            for x in (14, 20):
                c.put(x, 34, 'Y')
        self.body = build_sprite('secdrone', 64, 42, pal, f)
        pod = pod_sprite('sec_pod', pal, POD_ROWS)
        self.pods = [self.add_part(dx, dy, 10, 12, pod, self.max_hp * 0.1) for dx, dy in ((-30, -10), (30, -10), (-30, 14), (30, 14))]
        self.core = self.add_part(0, 0, 36, 28, None, None, core=True)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                yield from self.g_laser(None, math.pi / 2 - 0.9, 40, 100, 8, spin=0.018)
                for p in self.pods:
                    if p.alive:
                        self.aimed(p, 2, 10, 1.8)
                yield from wait(30)

        def p2():
            while True:
                yield from self.g_gate(g.player.y - 30, rnd_x(60) - 23)
                yield from wait(30)
                yield from self.g_gate(g.player.y + 10, rnd_x(60) - 23, 42)
                yield from self.g_spiral(None, 100, 4, 0.1, 1.4, 6)
                yield from wait(20)
        return p1() if i == 0 else p2()


class Graviton(Boss):
    name = 'GRAVITON'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((70, 50, 120), (240, 90, 230), glass=(255, 220, 120))

        def f(c):
            c.ellipse(24, 24, 18, 18, '#')
            c.ellipse(24, 24, 10, 10, 'K')
            c.ellipse(24, 24, 6, 6, 'C')
        self.body = build_sprite('graviton', 48, 48, pal, f)
        self.core = self.add_part(0, 0, 32, 32, None, None, core=True)

    def draw_extra(self, surf):
        for k in range(3):
            a = self.t * 0.04 + k * 2.1
            r = pygame.Rect(0, 0, 70, 22)
            r.center = (int(self.x), int(self.y))
            pygame.draw.arc(surf, (240, 120, 255), r, a, a + 1.6, 2)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                self.well_ring(None, 14, 1.9, 0.0012)
                yield from wait(50)
                yield from self.g_bursts(None, 3, 12, 3, 12, 1.9)
                yield from wait(40)

        def p2():
            gv = g.hazards.ensure('gravity', 0.6)
            gv.forced = True
            while True:
                gv.warn = 60
                g.banner('GRAVITY SHIFT', (190, 140, 255), 60)
                yield from wait(60)
                yield from self.g_spiral(None, 120, 3, 0.12, 1.5, 5)
                self.well_ring(None, 18, 2.0, 0.0012)
                yield from wait(60)
        return p1() if i == 0 else p2()


class Brood(Boss):
    name = 'BROOD MOTHER'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((110, 176, 70), (170, 80, 210), glass=(255, 70, 70))

        def f(c):
            c.ellipse(32, 14, 14, 12, '#')
            c.ellipse(32, 32, 10, 12, 'A')
            c.ellipse(32, 10, 6, 4, 'C')
            for k in range(3):
                c.line(20, 14 + k * 6, 6, 8 + k * 10, '1')
        self.body = build_sprite('brood', 64, 46, pal, f)
        sac = pod_sprite('brood_sac', pal, SAC_ROWS)
        self.sacs = [self.add_part(-22, 10, 10, 12, sac, self.max_hp * 0.12),
                     self.add_part(22, 10, 10, 12, sac, self.max_hp * 0.12)]
        self.core = self.add_part(0, 0, 26, 34, None, None, core=True)

    def phase_script(self, i):
        def p1():
            while True:
                for sac in self.sacs:
                    if sac.alive:
                        yield from self.g_larva(sac, 3)
                self.acid(None, 6)
                yield from wait(60)
                yield from self.g_bursts(None, 2, 16, 5, 12, 1.6)
                yield from wait(30)

        def p2():
            while True:
                yield from self.g_minions('kamikaze', 4, 'rush')
                for _ in range(4):
                    self.acid(None, 4, 2.4)
                    yield from wait(16)
                yield from self.g_rain(90, 5, 1.6, 'm', 1)
                yield from wait(30)
        return p1() if i == 0 else p2()


class Stalker(Boss):
    name = 'PHASE STALKER'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((60, 170, 180), (255, 80, 200), glass=(255, 255, 255))

        def f(c):
            c.poly([(28, 44), (16, 18), (2, 4), (20, 8), (28, 0)], '#')
            c.poly([(28, 36), (22, 16), (28, 10)], 'A')
            c.ellipse(28, 14, 3, 5, 'C')
        self.body = build_sprite('stalker', 56, 46, pal, f)
        self.core = self.add_part(0, 0, 30, 34, None, None, core=True)

    def phase_script(self, i):
        def p1():
            while True:
                yield from self.g_blink(rnd_x(), random.uniform(50, 110), 30)
                yield from self.g_bursts(None, 3, 10, 3, 8, 2.8, 'needle', 0)
                yield from wait(20)
                yield from self.g_dash()
                yield from wait(30)

        def p2():
            while True:
                self.start_mirror(300)
                yield from self.g_spiral(None, 100, 3, 0.14, 1.5, 5)
                yield from self.g_blink(rnd_x(), random.uniform(50, 110), 26)
                yield from self.g_bursts(None, 2, 12, 5, 9, 2.6, 'needle', 1)
                yield from self.g_dash()
                yield from wait(30)
        return p1() if i == 0 else p2()


class Guardian(Boss):
    name = 'CORE GUARDIAN'
    kind = 'miniboss'
    phases = (1.0, 0.5)

    def build(self):
        pal = boss_pal((180, 182, 204), (255, 196, 60), glass=(255, 60, 90))

        def f(c):
            c.poly([(34, 44), (8, 30), (4, 10), (20, 2), (34, 6)], '#')
            c.rect(8, 10, 6, 18, 'A')
            c.ellipse(34, 22, 10, 10, 'K')
            c.ellipse(34, 22, 7, 7, 'C')
            c.rect(30, 36, 8, 8, 'M')
        self.body = build_sprite('guardian', 68, 46, pal, f)
        pod = pod_sprite('guard_pod', pal, POD_ROWS)
        self.pods = [self.add_part(-24, 8, 10, 12, pod, self.max_hp * 0.1),
                     self.add_part(24, 8, 10, 12, pod, self.max_hp * 0.1)]
        self.core = self.add_part(0, 0, 34, 30, None, None, core=True)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                yield from self.g_gate(g.player.y - 20, rnd_x(60) - 23)
                for p in self.pods:
                    if p.alive:
                        yield from self.g_bursts(p, 2, 10, 3, 12, 2.0)
                self.bounce_fan(None, 9, 14, 1.6)
                yield from wait(40)

        def p2():
            while True:
                yield from self.g_lightning([g.player.x], 50)
                yield from self.g_spiral(None, 110, 4, 0.11, 1.6, 5)
                yield from self.g_minions('splitter', 3, 'v')
                yield from self.g_laser(None, None, 40, 50, 10)
                yield from wait(20)
        return p1() if i == 0 else p2()


# ====================================================================== SECTOR BOSSES
class Aegis(Boss):
    name = 'AEGIS DEFENSE PLATFORM'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)
    home_y = 80

    def build(self):
        pal = boss_pal((206, 210, 228), (220, 60, 70))

        def f(c):
            c.rect(0, 26, 26, 16, 'A')
            for x in range(2, 26, 4):
                c.rect(x, 27, 1, 14, '4')
            c.rect(24, 31, 14, 6, 'M')
            c.ring(60, 34, 30, 37, '#')
            c.ellipse(60, 34, 22, 20, '#')
            c.ellipse(60, 34, 15, 14, 'M')
            c.ellipse(60, 35, 9, 9, 'C')
            for a in range(4):
                ang = a * math.pi / 2 + math.pi / 4
                c.line(60 + math.cos(ang) * 22, 34 + math.sin(ang) * 20, 60 + math.cos(ang) * 31, 34 + math.sin(ang) * 31, 'A')
            c.put(60, 0, 'R')
        self.body = build_sprite('aegis', 120, 72, pal, f)
        pod = pod_sprite('aegis_pod', pal, POD_ROWS)
        self.turrets = [self.add_part(dx, dy, 10, 12, pod, self.max_hp * 0.09)
                        for dx, dy in ((-34, -6), (34, -6), (-22, 26), (22, 26))]
        self.core = self.add_part(0, 0, 40, 36, None, None, core=True)

    def move(self):
        self.x = PF_W / 2 + math.sin(self.t * 0.01) * 40
        self.y = self.home_y + math.sin(self.t * 0.02) * 6

    def phase_script(self, i):
        def p1():
            while True:
                for t in self.turrets:
                    if t.alive:
                        self.aimed(t, 3, 10, 1.8)
                        self.game.sfx('enemy_shot')
                        yield from wait(14)
                for _ in range(2):
                    self.aimed(None, 9, 10, 1.6, 'm', 1)
                    yield from wait(30)
                yield from wait(20)

        def p2():
            while True:
                yield from self.g_spiral(None, 150, 3, 0.11, 1.45, 5)
                yield from self.g_minions('dart', 7, 'swoop')
                for t in self.turrets:
                    if t.alive:
                        self.ring(t, 8, 1.3, 's', 0)
                yield from wait(50)

        def p3():
            while True:
                yield from self.g_sweep(None, math.pi / 2 - 1.0, math.pi / 2 + 1.0, 110, 10)
                for k in range(4):
                    self.ring(None, 20, 1.5, offset=k * 0.08)
                    yield from wait(16)
                yield from self.g_spiral(None, 100, 4, 0.13, 1.6, 4)
                yield from wait(30)
        return (p1, p2, p3)[i]()


class Grinder(Boss):
    name = 'GRINDER ASTEROID TITAN'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)
    home_y = 76

    def build(self):
        pal = boss_pal((196, 120, 56), (240, 206, 70), glass=(120, 240, 255), metal=(140, 140, 150))

        def f(c):
            c.poly([(58, 70), (34, 52), (20, 20), (34, 4), (58, 0)], '#')
            c.rect(30, 16, 12, 30, 'M')
            c.ellipse(58, 22, 12, 10, 'K')
            c.ellipse(58, 22, 8, 7, 'C')
            c.rect(40, 50, 6, 14, 'M')
            c.line(30, 40, 52, 56, '1')
            c.put(36, 8, 'Y')
            c.put(36, 10, 'Y')
        self.body = build_sprite('grinder', 116, 72, pal, f)
        drill = pod_sprite('grinder_drill', pal, ["MMMM", "M77M", "MMMM", ".M7M", ".MM.", "..M.", "..M."])
        self.arms = [self.add_part(-42, 18, 12, 14, drill, self.max_hp * 0.1),
                     self.add_part(42, 18, 12, 14, drill, self.max_hp * 0.1)]
        self.core = self.add_part(0, 0, 50, 46, None, None, core=True)

    def phase_script(self, i):
        def p1():
            while True:
                yield from self.g_rocks(2, 7)
                for a in self.arms:
                    if a.alive:
                        self.aimed(a, 6, 9, 1.8, 's', 0)
                        yield from wait(20)
                yield from wait(30)

        def p2():
            while True:
                yield from self.g_charge(48)
                yield from self.g_rocks(3, 6)
                yield from self.g_rain(100, 4, 1.5, 's', 1)
                yield from wait(20)

        def p3():
            while True:
                yield from self.g_spiral(None, 140, 4, 0.12, 1.5, 4)
                yield from self.g_laser(self.arms[0] if self.arms[0].alive else None, None, 40, 50, 9)
                yield from self.g_laser(self.arms[1] if self.arms[1].alive else None, None, 34, 50, 9)
                yield from self.g_rocks(2, 8)
                yield from wait(20)
        return (p1, p2, p3)[i]()


class Leviathan(Boss):
    name = 'NEBULA LEVIATHAN'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)
    home_y = 70
    SEGS = 9

    def build(self):
        pal = boss_pal((130, 60, 186), (255, 130, 210), glass=(255, 250, 140))

        def head(c):
            c.ellipse(16, 14, 14, 12, '#')
            c.poly([(16, 32), (8, 20), (24, 20)], 'A')
            c.ellipse(9, 12, 3, 3, 'C')
            c.line(4, 2, 1, -4, 'A')
        self.body = build_sprite('lev_head', 32, 32, pal, head)

        def seg(c):
            c.ellipse(10, 9, 9, 8, '#')
            c.ellipse(10, 7, 4, 3, 'A')
        sseg = build_sprite('lev_seg', 20, 18, pal, seg)
        self.segs = [self.add_part(0, -i * 12, 14, 12, sseg, None) for i in range(1, self.SEGS + 1)]
        self.core = self.add_part(0, 0, 26, 26, None, None, core=True)
        self.trail = []
        self.path_t = 0.0
        self.coil = False

    def update(self):
        super().update()
        if self.fighting or self.y > -40:
            self.trail.insert(0, (self.x, self.y))
            del self.trail[200:]
            for k, sp in enumerate(self.segs):
                idx = min(len(self.trail) - 1, (k + 1) * 6)
                if idx >= 0:
                    tx, ty = self.trail[idx]
                    sp.ox, sp.oy = tx - self.x, ty - self.y
                    sp.x, sp.y = tx, ty

    def move(self):
        self.path_t += 0.012
        if self.coil:
            self.x = PF_W / 2 + math.cos(self.path_t * 3) * 70
            self.y = 110 + math.sin(self.path_t * 3) * 55
        else:
            self.x = PF_W / 2 + math.sin(self.path_t * 2.1) * 95
            self.y = 90 + math.sin(self.path_t * 3.3) * 50

    def touches(self, px, py):
        if not self.fighting or self.dying:
            return False
        if abs(px - self.x) < 10 and abs(py - self.y) < 10:
            return True
        return any(abs(px - sg.x) < 6 and abs(py - sg.y) < 6 for sg in self.segs)

    def draw(self, surf):
        if not self.alive:
            return
        flash = 'full' if self.trans > 0 and (self.trans // 3) % 2 == 0 else (self.flash > 0 and self.t % 3 == 0)
        for sg in reversed(self.segs):
            self.blit_center(surf, sg.sprite, sg.x, sg.y, flash)
        body = self.body
        if self.angry and (self.t // 6) % 2 == 0:
            body = art.tinted(body, (255, 40, 40), 0.18)
        self.blit_center(surf, body, self.x, self.y, flash)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                yield from self.g_bursts(None, 3, 14, 3, 12, 1.9)
                for k, sg in enumerate(self.segs):
                    if k % 2 == 0:
                        B.shoot(g, sg.x, sg.y, math.pi / 2, 1.3, 's', 1)
                yield from wait(40)

        def p2():
            while True:
                px = g.player.x
                yield from self.g_lightning([px - 50, px + 50], 56)
                yield from self.g_spiral(None, 90, 3, 0.15, 1.5, 5)
                for sg in self.segs[::3]:
                    B.aimed(g, sg.x, sg.y, 1.7, 1, 0, 'm', 1)
                yield from wait(30)

        def p3():
            self.coil = True
            while True:
                for sg in self.segs[::2]:
                    B.ring(g, sg.x, sg.y, 6, 1.3, random.uniform(0, 1), 's', 1)
                yield from wait(40)
                yield from self.g_lightning([g.player.x], 46)
                yield from self.g_bursts(None, 2, 12, 5, 10, 2.0)
                yield from wait(20)
        return (p1, p2, p3)[i]()


class Cryo(Boss):
    name = 'CRYO WARDEN'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)

    def build(self):
        pal = boss_pal((150, 200, 240), (240, 250, 255), glass=(255, 100, 150), metal=(100, 120, 170))

        def f(c):
            c.poly([(54, 70), (30, 50), (14, 24), (30, 4), (54, 12)], '#')
            for x, h in ((10, 30), (20, 40), (32, 26)):
                c.poly([(x, 30), (x + 5, 30 - h), (x + 10, 30)], 'A')
            c.ellipse(54, 36, 12, 12, 'K')
            c.ellipse(54, 36, 8, 8, 'C')
            c.rect(46, 56, 16, 6, 'M')
        self.body = build_sprite('cryo', 108, 72, pal, f)
        self.core = self.add_part(0, 0, 48, 44, None, None, core=True)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for _ in range(3):
                    self.bounce_fan(None, 9, 14, 1.6, 's', 0, 2)
                    yield from wait(30)
                yield from self.g_bursts(None, 3, 10, 3, 6, 2.8, 'needle', 1)
                yield from wait(30)

        def p2():
            cr = g.hazards.ensure('crystals', 0.6)
            while True:
                for x in (60, PF_W - 60, PF_W / 2):
                    cr.spawn_at(x + random.uniform(-20, 20), self.y + 60, 16, 38)
                for _ in range(3):
                    self.bounce_fan(None, 11, 14, 1.7, 'm', 1, 3)
                    yield from wait(32)
                yield from self.g_laser(None, None, 40, 60, 10)
                yield from wait(30)

        def p3():
            while True:
                yield from self.g_rain(120, 3, 1.7, 'needle', 0)
                yield from self.g_spiral(None, 100, 5, 0.09, 1.5, 6)
                self.bounce_fan(None, 13, 12, 1.8, 's', 1, 3)
                yield from wait(40)
        return (p1, p2, p3)[i]()


class Seraph(Boss):
    name = 'SOLAR SERAPH'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)

    def build(self):
        pal = boss_pal((246, 196, 80), (255, 244, 200), glass=(255, 60, 40))

        def f(c):
            c.poly([(56, 68), (46, 30), (56, 4)], '#')
            c.ellipse(56, 14, 8, 8, 'A')
            c.ellipse(56, 14, 4, 4, 'C')
            for k, (y, ln) in enumerate(((14, 52), (28, 46), (42, 36))):
                c.poly([(46, y), (46 - ln, y - 8 + k * 2), (46 - ln + 6, y + 6), (46, y + 8)], 'A' if k % 2 == 0 else '#')
            c.ring(56, 14, 11, 12, 'Y')
        self.body = build_sprite('seraph', 112, 70, pal, f)
        self.core = self.add_part(0, 0, 30, 50, None, None, core=True)
        self.wings = [(-40, -10), (40, -10), (-34, 10), (34, 10)]

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for w in self.wings:
                    self.aimed(w, 4, 14, 1.7, 's', 0)
                    yield from wait(12)
                yield from wait(30)
                self.ring(None, 18, 1.4, 'm', 1)
                yield from wait(40)

        def p2():
            fl = g.hazards.ensure('flares', 0.5)
            while True:
                fl.trigger()
                yield from self.g_rain(150, 5, 1.5, 's', 1)
                for w in self.wings[:2]:
                    self.aimed(w, 5, 12, 1.8)
                yield from wait(60)

        def p3():
            while True:
                yield from self.g_spiral(None, 150, 3, 0.1, 1.3, 7, 'l', 0)
                for w in self.wings:
                    self.aimed(w, 3, 16, 2.0)
                yield from self.g_laser(None, None, 40, 60, 12)
                yield from wait(30)
        return (p1, p2, p3)[i]()


class Warden(Boss):
    name = 'STATION AI WARDEN'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)

    def build(self):
        pal = boss_pal((150, 156, 178), (255, 150, 40), glass=(255, 50, 60))

        def f(c):
            c.rect(28, 4, 52, 46, '#')
            c.rect(32, 8, 44, 36, '2')
            c.ellipse(54, 26, 16, 14, 'K')
            c.ellipse(54, 26, 10, 9, 'C')
            c.ellipse(54, 26, 4, 4, 'W')
            c.rect(28, 4, 52, 4, 'A')
            c.rect(6, 20, 22, 10, 'M')
            c.rect(44, 50, 20, 10, 'M')
        self.body = build_sprite('warden', 108, 62, pal, f)
        arm = pod_sprite('warden_arm', pal, ["MMMM.", "M##MM", "M#CCM", "M#CCM", "MMMMM", ".M.M.", ".M.M."])
        self.arms = [self.add_part(-46, 8, 12, 14, arm, self.max_hp * 0.1),
                     self.add_part(46, 8, 12, 14, arm, self.max_hp * 0.1)]
        self.core = self.add_part(0, 0, 50, 44, None, None, core=True)

    def move(self):
        self.x = PF_W / 2 + math.sin(self.t * 0.008) * 30
        self.y = self.home_y

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for a in self.arms:
                    if a.alive:
                        yield from self.g_bursts(a, 3, 10, 3, 10, 2.0)
                yield from self.g_laser(None, math.pi / 2 + 0.9, 40, 110, 9, spin=-0.017)
                yield from wait(20)

        def p2():
            while True:
                y0 = g.player.y
                yield from self.g_gate(y0 - 40, rnd_x(60) - 23)
                yield from self.g_gate(y0, rnd_x(60) - 23, 44, 40)
                for a in self.arms:
                    if a.alive:
                        self.aimed(a, 5, 12, 1.8)
                yield from wait(40)

        def p3():
            while True:
                x, y = self.pos(None)
                for k in range(4):
                    a0 = k * math.pi / 2 + math.pi / 4
                    g.telegraph_angle(x, y, a0, 40)
                yield from self.charge(None, 40)
                x, y = self.pos(None)
                for k in range(4):
                    bm = g.beam(x, y, k * math.pi / 2 + math.pi / 4, 140, 8, self.style['bullets'][0])
                    bm['spin'] = 0.012
                g.sfx('laser')
                yield from self.g_spiral(None, 140, 2, 0.17, 1.4, 6)
                yield from wait(30)
        return (p1, p2, p3)[i]()


class Horizon(Boss):
    name = 'EVENT HORIZON'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)

    def build(self):
        pal = boss_pal((60, 40, 110), (240, 90, 230), glass=(255, 200, 100))

        def f(c):
            c.ellipse(48, 34, 46, 14, 'A')
            c.ellipse(48, 34, 34, 9, '4')
            c.ellipse(48, 34, 24, 24, '#')
            c.ellipse(48, 34, 17, 17, 'K')
            c.ring(48, 34, 17, 19, 'Y')
        self.body = build_sprite('horizon', 96, 68, pal, f)
        self.core = self.add_part(0, 0, 44, 44, None, None, core=True)

    def draw_extra(self, surf):
        for k in range(4):
            a = -self.t * 0.03 + k * 1.57
            r = pygame.Rect(0, 0, 120, 36)
            r.center = (int(self.x), int(self.y))
            pygame.draw.arc(surf, (255, 170, 80), r, a, a + 0.8, 2)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                self.well_ring(None, 16, 2.0, 0.0011)
                yield from wait(40)
                self.well_ring(None, 12, 1.6, 0.0014, style=0)
                yield from wait(40)
                yield from self.g_bursts(None, 3, 12, 3, 12, 1.9)
                yield from wait(30)

        def p2():
            gv = g.hazards.ensure('gravity', 0.7)
            gv.forced = True
            while True:
                gv.warn = 60
                g.banner('GRAVITY SHIFT', (190, 140, 255), 60)
                yield from self.g_spiral(None, 120, 4, 0.12, 1.5, 5)
                self.well_ring(None, 20, 2.1, 0.0011)
                yield from wait(80)

        def p3():
            while True:
                yield from self.g_spiral(None, 160, 6, 0.06, 1.3, 6)
                yield from self.g_laser(None, None, 40, 60, 12)
                self.well_ring(None, 24, 2.2, 0.001)
                yield from wait(40)
        return (p1, p2, p3)[i]()


class Queen(Boss):
    name = 'HIVE QUEEN'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)

    def build(self):
        pal = boss_pal((104, 176, 70), (170, 80, 210), glass=(255, 70, 70))

        def f(c):
            c.ellipse(56, 16, 18, 14, '#')
            c.ellipse(56, 44, 22, 20, 'A')
            c.ellipse(56, 44, 14, 12, '4')
            c.ellipse(48, 12, 4, 3, 'C')
            for k in range(4):
                c.line(40, 18 + k * 6, 6 + k * 4, 6 + k * 14, '1')
                c.line(6 + k * 4, 6 + k * 14, 4 + k * 4, 14 + k * 14, '1')
            c.poly([(48, 0), (42, -6), (46, 4)], 'A')
        self.body = build_sprite('queen', 112, 68, pal, f)
        sac = pod_sprite('queen_sac', pal, SAC_ROWS)
        self.sacs = [self.add_part(-26, 14, 10, 12, sac, self.max_hp * 0.09),
                     self.add_part(26, 14, 10, 12, sac, self.max_hp * 0.09)]
        self.core = self.add_part(0, 0, 40, 52, None, None, core=True)

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for sc in self.sacs:
                    if sc.alive:
                        yield from self.g_larva(sc, 3)
                self.acid(None, 7)
                yield from wait(50)
                yield from self.g_bursts(None, 2, 16, 5, 12, 1.7)
                yield from wait(30)

        def p2():
            while True:
                E.spawn_wave(g, dict(pattern='nests', kind='nest', count=1, seed=random.randrange(9999), minion=True))
                for _ in range(4):
                    self.acid(None, 5, 2.4)
                    yield from wait(18)
                yield from self.g_rain(90, 4, 1.6, 'm', 1)
                yield from wait(60)

        def p3():
            while True:
                yield from self.g_charge(44)
                yield from self.g_minions('kamikaze', 6, 'rush')
                for k in range(3):
                    self.ring(None, 18, 1.5, offset=k * 0.1)
                    yield from wait(18)
                self.acid(None, 8, 2.6)
                yield from wait(30)
        return (p1, p2, p3)[i]()


class Phantom(Boss):
    name = 'RIFT PHANTOM'
    kind = 'boss'
    phases = (1.0, 0.66, 0.33)

    def build(self):
        pal = boss_pal((60, 170, 186), (255, 80, 200), glass=(255, 255, 255))

        def f(c):
            c.poly([(50, 66), (32, 40), (4, 30), (22, 18), (36, 2), (50, 10)], '#')
            c.poly([(50, 56), (40, 34), (50, 22)], 'A')
            c.ellipse(50, 22, 5, 7, 'C')
            c.line(10, 30, 30, 36, 'A')
        self.body = build_sprite('phantom', 100, 68, pal, f)
        self.core = self.add_part(0, 0, 44, 46, None, None, core=True)

    def draw_extra(self, surf):
        if self.phase_index >= 1 and self.body is not None:
            ghost = art.tinted(self.body, (120, 255, 255), 0.5)
            ghost.set_alpha(70)
            off = math.sin(self.t * 0.07) * 30
            surf.blit(ghost, (int(self.x - ghost.get_width() / 2 + off), int(self.y - ghost.get_height() / 2)))
            ghost.set_alpha(255)

    def phase_script(self, i):
        def p1():
            while True:
                yield from self.g_blink(rnd_x(), random.uniform(60, 110), 30)
                yield from self.g_bursts(None, 3, 10, 5, 8, 2.8, 'needle', 0)
                self.ring(None, 16, 1.4)
                yield from wait(40)

        def p2():
            while True:
                self.start_mirror(360)
                yield from self.g_dash()
                yield from self.g_blink(rnd_x(), random.uniform(60, 110), 26)
                yield from self.g_spiral(None, 110, 3, 0.15, 1.5, 5)
                yield from wait(30)

        def p3():
            while True:
                yield from self.g_blink(rnd_x(), random.uniform(60, 110), 22)
                yield from self.g_spiral(None, 120, 5, 0.1, 1.6, 5)
                yield from self.g_dash(None, 7.0)
                self.start_mirror(240)
                yield from self.g_bursts(None, 2, 12, 7, 8, 2.6, 'needle', 1)
                yield from wait(20)
        return (p1, p2, p3)[i]()


class MothershipCore(Boss):
    name = 'MOTHERSHIP CORE'
    kind = 'boss'
    phases = (1.0, 0.75, 0.5, 0.25)
    hp_scale = 1.35
    home_y = 84

    def build(self):
        pal = boss_pal((150, 40, 60), (255, 196, 60), glass=(120, 255, 240), metal=(120, 110, 130))

        def f(c):
            c.poly([(70, 92), (40, 70), (6, 52), (2, 28), (24, 10), (70, 2)], '#')
            c.rect(12, 30, 18, 20, 'M')
            c.rect(36, 14, 10, 50, 'A')
            for y in range(18, 62, 6):
                c.rect(37, y, 8, 2, '4')
            c.ellipse(70, 46, 20, 20, 'K')
            c.ellipse(70, 46, 14, 14, 'C')
            c.ellipse(70, 46, 6, 6, 'W')
            c.rect(62, 74, 16, 14, 'M')
            c.put(20, 14, 'R')
            c.put(50, 8, 'R')
        self.body = build_sprite('mothership', 140, 94, pal, f)
        pod = pod_sprite('ms_pod', pal, POD_ROWS)
        self.turrets = [self.add_part(dx, dy, 10, 12, pod, self.max_hp * 0.06)
                        for dx, dy in ((-50, -16), (50, -16), (-46, 14), (46, 14))]
        self.core = self.add_part(0, 0, 50, 50, None, None, core=True)

    def move(self):
        self.x = PF_W / 2 + math.sin(self.t * 0.007) * 30
        self.y = self.home_y + math.sin(self.t * 0.017) * 4

    def phase_script(self, i):
        g = self.game

        def p1():
            while True:
                for t in self.turrets:
                    if t.alive:
                        self.aimed(t, 3, 10, 1.9)
                        yield from wait(12)
                yield from self.g_gate(g.player.y - 30, rnd_x(60) - 23)
                self.bounce_fan(None, 9, 14, 1.6)
                yield from wait(40)

        def p2():
            gv = g.hazards.ensure('gravity', 0.6)
            gv.forced = True
            while True:
                gv.warn = 60
                yield from self.g_spiral(None, 120, 3, 0.13, 1.5, 5)
                yield from self.g_lightning([g.player.x - 40, g.player.x + 40], 50)
                self.well_ring(None, 16, 2.0, 0.0012)
                yield from wait(50)

        def p3():
            gv = g.hazards.ensure('gravity', 0.6)
            gv.forced = False
            cr = g.hazards.ensure('crystals', 0.6)
            while True:
                for x in (50, PF_W - 50):
                    cr.spawn_at(x, self.y + 70, 14, 36)
                self.start_mirror(300)
                yield from self.g_minions('kamikaze', 5, 'rush')
                yield from self.g_bursts(None, 3, 12, 5, 10, 2.0)
                yield from self.g_laser(None, None, 40, 60, 12)
                yield from wait(40)

        def p4():
            while True:
                x, y = self.pos(None)
                for k in range(3):
                    bm = g.beam(x, y, math.pi / 2 + (k - 1) * 0.9, 150, 8, self.style['bullets'][1], owner=self)
                    bm['spin'] = 0.01 * (1 if k % 2 else -1)
                    bm['follow'] = 0
                g.sfx('laser')
                yield from self.g_spiral(None, 150, 4, 0.12, 1.5, 5)
                yield from self.g_rain(80, 5, 1.6, 's', 0)
                self.ring(None, 24, 1.6)
                yield from wait(30)
        return (p1, p2, p3, p4)[i]()

    def beam_origin(self, which):
        return self.pos(None)


BOSS_CLASSES = {
    'frigate': Frigate,
    'sentinel': Sentinel, 'crusher': Crusher, 'wisp': Wisp, 'glacier': Glacier, 'moth': Moth,
    'secdrone': SecDrone, 'graviton': Graviton, 'brood': Brood, 'stalker': Stalker, 'guardian': Guardian,
    'aegis': Aegis, 'grinder': Grinder, 'leviathan': Leviathan, 'cryo': Cryo, 'seraph': Seraph,
    'warden': Warden, 'horizon': Horizon, 'queen': Queen, 'phantom': Phantom, 'mothership': MothershipCore,
}


def create(game, boss_id):
    cls = BOSS_CLASSES.get(boss_id, Frigate)
    return cls(game)
