"""The player's ship: movement, auto-fire, visible attachments, drones, shield."""
import math

import pygame

import art
from bullets import PBullet
from config import (PF_W, PF_H, PLAYER_HITBOX, PLAYER_GRAZE, INVULN_FRAMES, BASE_FIRE_INTERVAL,
                    MIN_FIRE_INTERVAL, MAX_BOMBS, MAX_SHIELD, WHITE)

PART_MAX = {'spread': 5, 'wing': 3, 'missile': 3, 'laser': 3, 'rear': 3}
OVERDRIVE_FRAMES = 20 * 60
BOUNTY_FRAMES = 20 * 60
MAGNET_FRAMES = 25 * 60

# main cannon layouts: (x offset, angle degrees, kind, damage factor)
SPREAD_LAYOUT = {
    1: [(-3, 0, 'main', 1.0), (3, 0, 'main', 1.0)],
    2: [(-3, 0, 'main', 1.0), (3, 0, 'main', 1.0), (-5, -9, 'spread', 0.7), (5, 9, 'spread', 0.7)],
    3: [(-4, 0, 'main', 1.0), (0, 0, 'main', 1.0), (4, 0, 'main', 1.0),
        (-5, -10, 'spread', 0.7), (5, 10, 'spread', 0.7)],
    4: [(-4, 0, 'main', 1.0), (0, 0, 'main', 1.0), (4, 0, 'main', 1.0),
        (-5, -8, 'spread', 0.75), (5, 8, 'spread', 0.75), (-6, -18, 'spread', 0.7), (6, 18, 'spread', 0.7)],
    5: [(-5, 0, 'main_big', 1.2), (-2, 0, 'main_big', 1.2), (2, 0, 'main_big', 1.2), (5, 0, 'main_big', 1.2),
        (-5, -8, 'spread', 0.75), (5, 8, 'spread', 0.75), (-6, -16, 'spread', 0.75), (6, 16, 'spread', 0.75),
        (-7, -26, 'spread', 0.7), (7, 26, 'spread', 0.7)],
}
LASER_WIDTH = {1: 3, 2: 5, 3: 8}
LASER_DPS = {1: 0.24, 2: 0.34, 3: 0.48}     # damage per frame per target


class Drone:
    def __init__(self, idx):
        self.angle = idx * 2.1
        self.x = self.y = 0.0
        self.fire_t = idx * 4


class Player:
    def __init__(self, game, stats):
        self.game = game
        self.stats = stats
        self.hull = stats['hull']
        self.paint = stats.get('paint')
        self.x = PF_W / 2
        self.y = PF_H - 46
        self.max_hp = stats['hp']
        self.hp = self.max_hp
        self.shield = stats.get('shield', 0)
        self.bombs = stats['bombs']
        self.speed = stats['speed']
        self.hitbox = stats.get('hitbox', PLAYER_HITBOX)
        self.graze_r = stats.get('graze', PLAYER_GRAZE)
        self.magnet_range = stats['magnet']
        self.drone_slots = stats['drone_slots']
        self.loadout = {'spread': 1, 'wing': 0, 'missile': 0, 'laser': 0, 'rear': 0}
        for k, v in stats.get('start', {}).items():
            if k == 'drone':
                pass
            elif k in self.loadout:
                self.loadout[k] = max(self.loadout[k], v)
        self.drones = []
        for _ in range(min(self.drone_slots, stats.get('start', {}).get('drone', 0))):
            self.drones.append(Drone(len(self.drones)))
        self.invuln = 60
        self.alive = True
        self.fire_t = 0
        self.wing_t = 3
        self.missile_t = 10
        self.rear_t = 5
        self.overdrive = 0
        self.bounty = 0
        self.magnet_t = 0
        self.stored_shield = 0
        self.bomb_cd = 0
        self.bomb_regen = 0
        self.moving = (0, 0)
        self.laser_on = False
        self.laser_hits = []
        self.flicker = 0
        self.lean = 0.0
        self.god = False
        self.safe = False        # set after a level is won: nothing can hurt you any more
        self._sprite_key = None
        self._sprite = None

    # ------------------------------------------------------------ helpers
    @property
    def dmg_mult(self):
        return self.stats['dmg'] * (2.0 if self.overdrive > 0 else 1.0)

    def fire_interval(self):
        # fractional: the timer carries the remainder so every fire-rate upgrade counts
        return max(MIN_FIRE_INTERVAL, BASE_FIRE_INTERVAL * self.stats['rate'])

    def part_count(self):
        lo = self.loadout
        return (lo['spread'] - 1) + lo['wing'] + lo['missile'] + lo['laser'] + lo['rear'] + len(self.drones)

    # ------------------------------------------------------------ update
    def update(self, inp):
        g = self.game
        if not self.alive:
            return
        dx, dy = inp.dx, inp.dy
        if g.mirror_x:
            dx = -dx
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.moving = (dx, dy)
        self.lean += (dx - self.lean) * 0.25
        self.x += dx * self.speed + g.gravity_x * 14.0 * self.stats.get('gravity_resist', 1.0)
        self.y += dy * self.speed
        lo, hi = g.play_bounds()
        self.x = max(lo + 7, min(hi - 7, self.x))
        self.y = max(14, min(PF_H - 10, self.y))
        if self.invuln > 0:
            self.invuln -= 1
        if self.bomb_cd > 0:
            self.bomb_cd -= 1
        if self.overdrive > 0:
            self.overdrive -= 1
            if self.overdrive == 0:
                self.shield = min(MAX_SHIELD, self.shield + self.stored_shield)
                self.stored_shield = 0
                g.popup_player('OVERDRIVE OFF', (255, 160, 160))
        if self.bounty > 0:
            self.bounty -= 1
        if self.magnet_t > 0:
            self.magnet_t -= 1
        if self.stats.get('bomb_regen'):
            self.bomb_regen += 1
            if self.bomb_regen >= self.stats['bomb_regen'] and self.bombs < MAX_BOMBS:
                self.bomb_regen = 0
                self.bombs += 1
                g.popup_player('+1 BOMB', (255, 120, 120))
        if inp.bomb:
            self.use_bomb()
        self.fire()
        for i, d in enumerate(self.drones):
            d.angle += 0.05
            n = len(self.drones)
            a = d.angle + i * math.tau / n
            d.x = self.x + math.cos(a) * 21
            d.y = self.y + 2 + math.sin(a) * 15
        self.flicker = (self.flicker + 1) % 1000

    def magnet_radius(self):
        return self.magnet_range * (1.8 if self.magnet_t > 0 else 1.0)

    def use_bomb(self):
        if self.bombs > 0 and self.bomb_cd == 0:
            self.bombs -= 1
            self.bomb_cd = 50
            self.game.detonate_bomb(self.x, self.y)

    # ------------------------------------------------------------ weapons
    def fire(self):
        g = self.game
        add = g.pbullets.append
        dmg = self.dmg_mult
        geo = art.hull_geometry(self.hull)
        x, y = self.x, self.y
        lo = self.loadout
        self.fire_t -= 1
        if self.fire_t <= 0:
            self.fire_t += self.fire_interval()
            ny = y + geo['nose'][1]
            for ox, ang, kind, f in SPREAD_LAYOUT[lo['spread']]:
                a = math.radians(ang)
                sp = 9.0 if kind != 'spread' else 8.0
                b = PBullet(x + ox, ny + 2, math.sin(a) * sp, -math.cos(a) * sp, dmg * f,
                            art.player_shot(kind), 3 if kind != 'main_big' else 5, 9)
                add(b)
            g.sfx('shot')
            g.fx.particle(x, ny, 0, -0.5, 3, 4, (255, 240, 170), 'sq', 1.0)
        if lo['wing']:
            self.wing_t -= 1
            if self.wing_t <= 0:
                self.wing_t = 9
                wx, wy = geo['wing']
                angles = {1: (0,), 2: (0, 5), 3: (0, 5, 11)}[lo['wing']]
                pod_w = art.part_sprite('wing%d' % lo['wing'], self.hull).get_width()
                for side in (-1, 1):
                    px = x + side * (wx + pod_w / 2 - 2)
                    for a in angles:
                        r = math.radians(a * side)
                        add(PBullet(px, y + wy - 5, math.sin(r) * 8, -math.cos(r) * 8, dmg * 0.8,
                                    art.player_shot('wing'), 3, 7))
        if lo['missile']:
            self.missile_t -= 1
            if self.missile_t <= 0:
                self.missile_t = {1: 50, 2: 38, 3: 30}[lo['missile']]
                n = 4 if lo['missile'] == 3 else 2
                ux, uy = geo['under']
                for i in range(n):
                    side = -1 if i % 2 == 0 else 1
                    spread = 1 + (i // 2)
                    b = PBullet(x + side * ux, y + uy, side * 1.4 * spread, -1.0, dmg * 4.5,
                                art.player_shot('missile'), 5, 5, 'missile')
                    b.life = 150
                    add(b)
                g.sfx('missile')
        if lo['rear']:
            self.rear_t -= 1
            if self.rear_t <= 0:
                self.rear_t = 10
                angles = {1: (0,), 2: (-10, 10), 3: (-18, 0, 18)}[lo['rear']]
                ty = y + geo['tail'][1] + 3
                for a in angles:
                    r = math.radians(a)
                    add(PBullet(x, ty, math.sin(r) * 7, math.cos(r) * 7, dmg * 0.9,
                                art.player_shot('rear'), 3, 6))
        for d in self.drones:
            d.fire_t -= 1
            if d.fire_t <= 0:
                d.fire_t = 10
                t = g.nearest_target(d.x, d.y, 170)
                if t is not None:
                    a = math.atan2(t.y - d.y, t.x - d.x)
                else:
                    a = -math.pi / 2
                add(PBullet(d.x, d.y - 3, math.cos(a) * 7, math.sin(a) * 7, dmg * 1.0,
                            art.player_shot('drone'), 3, 5))
        self.laser_on = lo['laser'] > 0

    def laser_rect(self):
        lv = self.loadout['laser']
        w = LASER_WIDTH[lv] + (2 if self.overdrive else 0)
        geo = art.hull_geometry(self.hull)
        top = self.y + geo['nose'][1] - 4
        return pygame.Rect(int(self.x - w / 2), 0, w, int(top))

    def laser_damage(self):
        return LASER_DPS[self.loadout['laser']] * self.dmg_mult

    # ------------------------------------------------------------ damage
    def hit(self, dmg=1):
        """Returns True if the hit landed (shield or hull)."""
        if self.invuln > 0 or not self.alive or self.safe:
            return False
        g = self.game
        if self.god:                      # test bots: count the hit, take no damage
            self.invuln = INVULN_FRAMES
            g.stats['god_hits'] = g.stats.get('god_hits', 0) + 1
            return False
        if self.shield > 0:
            self.shield -= 1
            self.invuln = 70
            g.fx.ring(self.x, self.y, 10, 1.8, 18, (120, 200, 255), 2)
            g.fx.sparks(self.x, self.y, 14, (140, 210, 255), 3)
            g.sfx('shield_hit')
            g.on_player_hit(shield=True)
            return True
        self.hp -= dmg
        self.invuln = INVULN_FRAMES
        g.fx.explosion(self.x, self.y, 's')
        g.fx.shake(0.45)
        g.fx.screen_flash(6, (255, 60, 60))
        g.sfx('player_hit')
        g.on_player_hit(shield=False)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            g.on_player_death()
        return True

    # ------------------------------------------------------------ pickups
    def collect(self, kind):
        """Apply a pickup. Returns the popup text."""
        lo = self.loadout
        if kind in PART_MAX:
            if lo[kind] >= PART_MAX[kind]:
                return None
            lo[kind] += 1
            names = {'spread': 'SPREAD', 'wing': 'WING GUNS', 'missile': 'MISSILES',
                     'laser': 'LASER', 'rear': 'REAR GUN'}
            return '%s LV%d' % (names[kind], lo[kind])
        if kind == 'drone':
            if len(self.drones) >= self.drone_slots:
                return None
            self.drones.append(Drone(len(self.drones)))
            return 'DRONE %d/%d' % (len(self.drones), self.drone_slots)
        if kind == 'shield':
            if self.overdrive > 0:
                self.stored_shield = min(MAX_SHIELD, self.stored_shield + 1)
                return 'SHIELD STORED'
            if self.shield >= MAX_SHIELD:
                return None
            self.shield += 1
            return 'SHIELD'
        if kind == 'repair':
            if self.hp >= self.max_hp:
                return None
            self.hp = min(self.max_hp, self.hp + 2)
            return 'REPAIR'
        if kind == 'bomb':
            if self.bombs >= MAX_BOMBS:
                return None
            self.bombs += 1
            return '+1 BOMB'
        if kind == 'magnet':
            self.magnet_t = MAGNET_FRAMES
            return 'MAGNET'
        if kind == 'overdrive':
            if self.overdrive <= 0:
                self.stored_shield = self.shield
                self.shield = 0
            self.overdrive = int(OVERDRIVE_FRAMES * self.stats.get('overdrive_mult', 1.0))
            return 'OVERDRIVE!'
        if kind == 'bounty':
            self.bounty = BOUNTY_FRAMES
            return 'BOUNTY x2!'
        return None

    def is_maxed(self, kind):
        if kind in PART_MAX:
            return self.loadout[kind] >= PART_MAX[kind]
        if kind == 'drone':
            return len(self.drones) >= self.drone_slots
        return False

    # ------------------------------------------------------------ drawing
    def sprite(self):
        lo = self.loadout
        key = (self.hull, self.paint, lo['spread'], lo['wing'], lo['missile'], lo['laser'],
               lo['rear'], self.magnet_t > 0)
        if key != self._sprite_key:
            self._sprite_key = key
            self._sprite = compose_ship(self.hull, lo, self.magnet_t > 0, self.paint)
        return self._sprite

    def draw(self, surf):
        if not self.alive:
            return
        x, y = int(self.x), int(self.y)
        geo = art.hull_geometry(self.hull)
        if self.laser_on:
            self.draw_laser(surf)
        # engine flames
        boost = 3 if self.moving[1] < 0 else (-1 if self.moving[1] > 0 else 0)
        for ex, ey in geo['engines']:
            n = 3 + boost + (self.flicker // 2) % 3
            fx, fy = x + int(ex), y + int(ey)
            surf.fill((255, 120, 40), (fx - 1, fy, 2, n + 2))
            surf.fill((255, 230, 120), (fx - 1, fy, 2, n))
            surf.fill(WHITE, (fx - 1 + (0 if ex < 0 else 1), fy, 1, max(1, n - 2)))
        if self.invuln > 0 and self.invuln % 6 < 3 and self.shield == 0:
            return
        s = self.sprite()
        if self.overdrive > 0 and (self.flicker // 3) % 2 == 0:
            s = art.tinted(s, (255, 40, 40), 0.45)
        surf.blit(s, (x - s.get_width() // 2, y - s.get_height() // 2))
        for d in self.drones:
            ds = art.drone_sprite()
            surf.blit(ds, (int(d.x) - ds.get_width() // 2, int(d.y) - ds.get_height() // 2))
        # visible hit core
        surf.fill((255, 60, 140), (x - 2, y - 1, 4, 3))
        surf.fill((255, 60, 140), (x - 1, y - 2, 2, 5))
        surf.fill(WHITE, (x - 1, y - 1, 2, 3))
        if self.shield > 0:
            t = self.flicker
            r = 15 + self.shield
            col = (110, 190, 255) if self.invuln % 6 < 3 else WHITE
            pygame.draw.circle(surf, (40, 80, 160), (x, y), r, 1)
            for i in range(self.shield + 1):
                a = t * 0.06 + i * math.tau / (self.shield + 1)
                pygame.draw.arc(surf, col, (x - r, y - r, r * 2, r * 2), a, a + 0.9, 2)

    def draw_laser(self, surf):
        r = self.laser_rect()
        if r.height <= 0:
            return
        t = self.flicker
        core = max(1, r.width // 3)
        wob = 1 if t % 4 < 2 else 0
        surf.fill((40, 120, 255), (r.x - 1 - wob, 0, r.width + 2 + wob * 2, r.height))
        surf.fill((90, 220, 255), r)
        surf.fill(WHITE, (int(self.x - core / 2), 0, core, r.height))
        # muzzle glow
        pygame.draw.circle(surf, (150, 240, 255), (int(self.x), r.height), r.width // 2 + 3)
        pygame.draw.circle(surf, WHITE, (int(self.x), r.height), max(2, r.width // 2))


def compose_ship(hull, lo, magnet=False, paint=None):
    """Build the ship sprite with every attached part visible."""
    geo = art.hull_geometry(hull)
    W, H = 76, 64
    cx, cy = W // 2, H // 2
    out = pygame.Surface((W, H), pygame.SRCALPHA)
    hs = art.hull_sprite(hull, paint)

    def part(name):
        return art.part_sprite(name, hull, paint)

    def put(s, x, y, flip=False):
        if flip:
            s = pygame.transform.flip(s, True, False)
        out.blit(s, (int(round(cx + x - s.get_width() / 2)), int(round(cy + y - s.get_height() / 2))))

    wx, wy = geo['wing']
    nx, ny = geo['nose']
    # behind the hull: missile racks peek out ahead of the wings, wing pods hang off the tips
    if lo['missile']:
        ps = part('missile%d' % lo['missile'])
        ux = max(geo['under'][0], ps.get_width() / 2 + 2)
        put(ps, -ux, wy - ps.get_height() / 2 - 1)
        put(ps, ux, wy - ps.get_height() / 2 - 1, True)
    if lo['wing']:
        ps = part('wing%d' % lo['wing'])
        off = wx + ps.get_width() / 2 - 2
        put(ps, -off, wy - 1)
        put(ps, off, wy - 1, True)
    if lo['rear']:
        ps = part('rear%d' % lo['rear'])
        tx, ty = geo['tail']
        put(ps, 0, ty + ps.get_height() / 2 - 3)
    out.blit(hs, (cx - hs.get_width() // 2, cy - hs.get_height() // 2))
    # on top: the nose cannon grows forward, the laser lens sits on the tip
    if lo['spread'] >= 2:
        ps = part('nose%d' % lo['spread'])
        put(ps, 0, ny - ps.get_height() / 2 + 3)
    if lo['laser']:
        ps = part('laser%d' % lo['laser'])
        top = ny - (part('nose%d' % lo['spread']).get_height() - 3 if lo['spread'] >= 2 else 0)
        put(ps, 0, top - ps.get_height() / 2 + 3)
    if magnet:
        ps = part('magnet')
        put(ps, -wx * 0.5, wy - 6)
        put(ps, wx * 0.5, wy - 6, True)
    return out
