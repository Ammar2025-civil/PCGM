"""In-flight pickups: credits, ore, parts and power-ups, plus drop tables."""
import math
import random

import pygame

import art
from config import PF_W, PF_H

PART_KINDS = ('spread', 'wing', 'missile', 'laser', 'rear', 'drone')
# weights for random part drops
DROP_WEIGHTS = {
    'spread': 30, 'wing': 14, 'missile': 12, 'laser': 9, 'rear': 8, 'drone': 8,
    'shield': 10, 'repair': 8, 'bomb': 6, 'magnet': 5, 'overdrive': 4, 'bounty': 3,
}
RARE_WEIGHTS = {'drone': 10, 'laser': 10, 'missile': 8, 'overdrive': 6, 'bounty': 5, 'shield': 6, 'spread': 8}
COIN_VALUE = {'small': 1, 'big': 5, 'gem': 25, 'ore': 3, 'orb': 2}


class Pickup:
    __slots__ = ('x', 'y', 'vx', 'vy', 'kind', 't', 'alive', 'value', 'pulled', 'part')

    def __init__(self, x, y, kind, value=0, vx=0.0, vy=0.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.kind = kind
        self.value = value
        self.t = 0
        self.alive = True
        self.pulled = False
        self.part = kind not in COIN_VALUE

    def update(self, g):
        self.t += 1
        p = g.player
        if self.part:
            self.vx *= 0.94
            self.vy = self.vy * 0.94 + 0.04
            if self.vy < 0.55:
                self.vy += 0.02
            self.x += self.vx + math.sin(self.t * 0.07) * 0.3
            self.y += self.vy
            reach = 0
            if p.magnet_t > 0 or g.part_magnet:
                reach = p.magnet_radius() * 0.8
        else:
            self.vx *= 0.92
            self.vy = self.vy * 0.92 + 0.06
            self.x += self.vx
            self.y += self.vy + g.scroll * 0.4
            reach = p.magnet_radius()
        if p.alive and reach > 0:
            dx, dy = p.x - self.x, p.y - self.y
            d = math.hypot(dx, dy)
            if d < reach or self.pulled:
                self.pulled = True
                sp = 4.5 + max(0.0, (reach - d) * 0.03)
                if d > 0.1:
                    self.x += dx / d * sp
                    self.y += dy / d * sp
        self.x = max(4, min(PF_W - 4, self.x))
        if self.y > PF_H + 12 or (not self.part and self.t > 600):
            self.alive = False

    def draw(self, surf, frame):
        if self.part:
            s = art.pickup_sprite(self.kind, 1 if (self.t // 8) % 3 == 0 else 0)
            bob = int(math.sin(self.t * 0.12) * 1.5)
            surf.blit(s, (int(self.x) - 7, int(self.y) - 7 + bob))
            if (self.t // 10) % 2 == 0:
                r = 10 + (self.t % 20) // 4
                pygame.draw.circle(surf, art.PICKUP_STYLE[self.kind][1], (int(self.x), int(self.y) + bob), r, 1)
        else:
            if not self.pulled and self.t > 480 and self.t % 6 < 3:
                return
            k = 'big' if self.kind == 'big' else self.kind
            if self.kind == 'orb':
                k = 'gem'
            s = art.coin_sprite(k)
            if self.kind in ('small', 'big') and (self.t + int(self.x)) % 24 < 4:
                s = art.white(s)
            surf.blit(s, (int(self.x) - s.get_width() // 2, int(self.y) - s.get_height() // 2))


def scatter_coins(g, x, y, credits, spread=1.6, ore=False):
    """Split a credit value into coins and fling them out."""
    credits = max(0, int(round(credits)))
    coins = []
    if ore:
        while credits >= 3 and len(coins) < 12:
            coins.append(('ore', 3))
            credits -= 3
    while credits >= 25 and len(coins) < 10:
        coins.append(('gem', 25))
        credits -= 25
    while credits >= 5 and len(coins) < 16:
        coins.append(('big', 5))
        credits -= 5
    while credits >= 1 and len(coins) < 20:
        coins.append(('small', 1))
        credits -= 1
    if credits > 0 and coins:
        k, v = coins[0]
        coins[0] = (k, v + credits)
    for k, v in coins:
        a = random.uniform(0, math.tau)
        s = random.uniform(0.3, 1.0) * spread
        c = Pickup(x, y, k, v, math.cos(a) * s, math.sin(a) * s - 0.8)
        g.pickups.append(c)


def choose_part(g, weights=None, rnd=random):
    p = g.player
    weights = dict(weights or DROP_WEIGHTS)
    for k in list(weights):
        if p.is_maxed(k):
            weights.pop(k)
    if p.hp >= p.max_hp:
        weights.pop('repair', None)
    else:
        weights['repair'] = weights.get('repair', 8) * (1 + 2 * (1 - p.hp / p.max_hp))
    if p.bombs >= 5:
        weights.pop('bomb', None)
    if p.overdrive > 0:
        weights.pop('overdrive', None)
    if p.bounty > 0:
        weights.pop('bounty', None)
    if not weights:
        return None
    total = sum(weights.values())
    r = rnd.uniform(0, total)
    for k, w in weights.items():
        r -= w
        if r <= 0:
            return k
    return list(weights)[-1]


def drop_part(g, x, y, kind=None, weights=None):
    kind = kind or choose_part(g, weights)
    if kind is None:
        scatter_coins(g, x, y, 10 * g.diff['credits'])
        return None
    pk = Pickup(x, y, kind, 0, random.uniform(-0.6, 0.6), -1.4)
    g.pickups.append(pk)
    return pk
