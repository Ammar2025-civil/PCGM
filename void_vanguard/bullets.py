"""Projectiles and bullet-pattern emitters (rings, fans, aimed bursts...)."""
import math

import art
from config import PF_W, PF_H

MAX_ENEMY_BULLETS = 650
SIZES = {'s': 2, 'm': 3, 'l': 5, 'xl': 8}


class EBullet:
    __slots__ = ('x', 'y', 'vx', 'vy', 'r', 'spr', 'grazed', 'ax', 'ay', 'life', 'kind',
                 'delay', 'turn', 'spd', 'bounces', 'dmg', 'color', 'alive', 'ox', 'oy', 'wb', 'well')

    def __init__(self, x, y, vx, vy, r, spr, kind='orb'):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.ox, self.oy = x, y
        self.r = r
        self.spr = spr
        self.kind = kind
        self.grazed = False
        self.ax = self.ay = 0.0
        self.life = -1
        self.delay = 0
        self.turn = 0.0
        self.spd = math.hypot(vx, vy)
        self.bounces = 2
        self.dmg = 1
        self.color = None
        self.alive = True
        self.wb = 0          # bounces left off the playfield sides
        self.well = None     # (x, y, k): spring pull toward a point


class PBullet:
    __slots__ = ('x', 'y', 'vx', 'vy', 'w', 'h', 'dmg', 'spr', 'pierce', 'kind', 'target',
                 'life', 'bounces', 'hits', 'alive', 'ox', 'oy')

    def __init__(self, x, y, vx, vy, dmg, spr, w=3, h=8, kind='shot'):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.ox, self.oy = x, y
        self.dmg = dmg
        self.spr = spr
        self.w, self.h = w, h
        self.kind = kind
        self.pierce = 0
        self.target = None
        self.life = 200
        self.bounces = 2
        self.hits = None
        self.alive = True


# ---------------------------------------------------------------- emitters
def _sprite_for(game, size, style):
    cols = game.bullet_colors
    color = cols[style % len(cols)]
    if size == 'needle':
        return art.needle(9, color), 2, color
    r = SIZES.get(size, 2)
    return art.orb(r, color), r, color


def shoot(game, x, y, angle, speed, size='s', style=0, raw=False, kind='orb', **kw):
    """Spawn one enemy bullet. angle in radians (pi/2 = straight down)."""
    if len(game.ebullets) >= MAX_ENEMY_BULLETS:
        return None
    if not raw:
        speed *= game.diff['bullet_speed']
    spr, r, color = _sprite_for(game, size, style)
    b = EBullet(x, y, math.cos(angle) * speed, math.sin(angle) * speed, r, spr,
                'needle' if size == 'needle' else kind)
    b.color = color
    for k, v in kw.items():
        setattr(b, k, v)
    game.ebullets.append(b)
    return b


def angle_to_player(game, x, y):
    p = game.player
    return math.atan2(p.y - y, p.x - x)


def aimed(game, x, y, speed, n=1, spread=0.0, size='s', style=0, **kw):
    """n bullets fanned around the angle to the player. spread in degrees between bullets."""
    base = angle_to_player(game, x, y)
    return fan(game, x, y, base, n, spread, speed, size, style, **kw)


def fan(game, x, y, center, n, spread, speed, size='s', style=0, **kw):
    out = []
    step = math.radians(spread)
    start = center - step * (n - 1) / 2.0
    for i in range(n):
        out.append(shoot(game, x, y, start + step * i, speed, size, style, **kw))
    return out


def ring(game, x, y, n, speed, offset=0.0, size='s', style=0, **kw):
    out = []
    for i in range(n):
        out.append(shoot(game, x, y, offset + math.tau * i / n, speed, size, style, **kw))
    return out


def line(game, x, y, angle, n, speed0, speed1, size='s', style=0, **kw):
    """A stream of bullets in one direction with increasing speed (a 'snake')."""
    out = []
    for i in range(n):
        sp = speed0 + (speed1 - speed0) * i / max(1, n - 1)
        out.append(shoot(game, x, y, angle, sp, size, style, **kw))
    return out


# ---------------------------------------------------------------- update helpers
def update_enemy_bullets(game):
    margin = 20
    gx = game.gravity_x
    player = game.player
    keep = []
    append = keep.append
    for b in game.ebullets:
        if not b.alive:
            continue
        if b.delay > 0:
            b.delay -= 1
            append(b)
            continue
        b.ox, b.oy = b.x, b.y
        if b.turn and player.alive:
            want = math.atan2(player.y - b.y, player.x - b.x)
            cur = math.atan2(b.vy, b.vx)
            d = (want - cur + math.pi) % math.tau - math.pi
            cur += max(-b.turn, min(b.turn, d))
            b.vx, b.vy = math.cos(cur) * b.spd, math.sin(cur) * b.spd
        if b.ax or b.ay:
            b.vx += b.ax
            b.vy += b.ay
        if b.well is not None:
            wx, wy, k = b.well
            b.vx += (wx - b.x) * k
            b.vy += (wy - b.y) * k
        if gx:
            b.vx += gx * 0.6
        b.x += b.vx
        b.y += b.vy
        if b.wb and (b.x < 2 or b.x > PF_W - 2):
            b.vx = -b.vx
            b.x = 2 if b.x < 2 else PF_W - 2
            b.wb -= 1
            b.grazed = False
        if b.life > 0:
            b.life -= 1
            if b.life == 0:
                if b.kind == 'mine':
                    game.mine_burst(b)
                continue
        if -margin < b.x < PF_W + margin and -margin - 40 < b.y < PF_H + margin:
            append(b)
    game.ebullets = keep


def update_player_bullets(game):
    keep = []
    gx = game.gravity_x
    for b in game.pbullets:
        if not b.alive:
            continue
        b.ox, b.oy = b.x, b.y
        if b.kind == 'missile':
            t = b.target
            if t is None or not t.alive:
                t = b.target = game.nearest_target(b.x, b.y)
            spd = math.hypot(b.vx, b.vy)
            spd = min(6.0, spd + 0.18)
            if t is not None:
                want = math.atan2(t.y - b.y, t.x - b.x)
                cur = math.atan2(b.vy, b.vx)
                d = (want - cur + math.pi) % math.tau - math.pi
                cur += max(-0.16, min(0.16, d))
            else:
                cur = math.atan2(b.vy, b.vx)
            b.vx, b.vy = math.cos(cur) * spd, math.sin(cur) * spd
            if game.frame % 2 == 0:
                game.fx.particle(b.x, b.y + 2, 0, 0.4, 10, 2, (200, 200, 220), 'smoke', 0.9)
        if gx:
            b.vx += gx * 0.4
        b.x += b.vx
        b.y += b.vy
        b.life -= 1
        if b.life > 0 and -20 < b.x < PF_W + 20 and -20 < b.y < PF_H + 20:
            keep.append(b)
    game.pbullets = keep


def draw_enemy_bullets(surf, bullets):
    blit = surf.blit
    for b in bullets:
        s = b.spr
        if b.kind == 'needle':
            # pick a rotated copy based on direction (8 directions, cached)
            s = _rot_needle(s, b.vx, b.vy)
        blit(s, (int(b.x) - s.get_width() // 2, int(b.y) - s.get_height() // 2))


_needle_rot = {}


def _rot_needle(s, vx, vy):
    a = int(round(math.degrees(math.atan2(vx, vy)) / 22.5)) % 16
    key = (id(s), a)
    r = _needle_rot.get(key)
    if r is None:
        import pygame
        r = pygame.transform.rotate(s, a * 22.5)
        _needle_rot[key] = r
        _needle_rot[('keep', id(s))] = s
    return r


def draw_player_bullets(surf, bullets):
    blit = surf.blit
    for b in bullets:
        s = b.spr
        if b.kind == 'missile':
            s = _rot_needle(s, -b.vx, -b.vy)
        blit(s, (int(b.x) - s.get_width() // 2, int(b.y) - s.get_height() // 2))
