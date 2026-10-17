"""Headless runner: plays the game with a simple bot, for crash tests and screenshots.

Usage examples:
  python tools/sim.py --level 1 --frames 3000 --shots 300,900,2000 --out /tmp/shots
  python tools/sim.py --level 10 --god --until-end
"""
import argparse
import math
import os
import random
import sys
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'void_vanguard'))

import pygame  # noqa: E402


def bot_input(g, inp, rnd, god=False):
    """Crude dodging bot: drift under the nearest enemy, push away from close bullets."""
    p = g.player
    inp.clear()
    if not p.alive:
        return
    tx = p.x
    tgt = g.nearest_target(p.x, p.y - 120)
    if tgt is not None:
        tx = tgt.x
    pull_x = (tx - p.x) * 0.05
    pull_y = ((300 if not god else 280) - p.y) * 0.03
    fx = fy = 0.0
    for b in g.ebullets:
        dx, dy = p.x - b.x, p.y - b.y
        d2 = dx * dx + dy * dy
        if d2 < 50 * 50 and d2 > 0.01:
            d = math.sqrt(d2)
            w = (50 - d) / 50.0
            fx += dx / d * w * 3
            fy += dy / d * w * 3
    for pk in g.pickups:
        if pk.part:
            pull_x += (pk.x - p.x) * 0.02
            pull_y += (pk.y - p.y) * 0.01
    vx = pull_x + fx
    vy = pull_y + fy
    inp.dx = 1 if vx > 0.3 else (-1 if vx < -0.3 else 0)
    inp.dy = 1 if vy > 0.3 else (-1 if vy < -0.3 else 0)
    if rnd.random() < 0.002 and len(g.ebullets) > 40:
        inp.bomb = True


def make_app(save_dir=None):
    import main
    screen = main.create_window()
    app = main.App(screen, headless=True)
    return app, screen


def run_level(app, screen, level, frames=None, god=False, shots=(), out=None, until_end=False, seed=1,
              draw_every=1, dmg_boost=1.0, verbose=True):
    import game
    rnd = random.Random(seed)
    app.start_level(level)
    g = app.scene
    if dmg_boost != 1.0:
        g.player.stats['dmg'] *= dmg_boost
    shots = set(shots)
    f = 0
    t0 = time.time()
    max_frames = frames or 60 * 60 * 8
    while f < max_frames:
        f += 1
        if not isinstance(app.scene, game.GameScene) or app.scene is not g:
            break
        bot_input(g, app.input, rnd, god)
        if g.state == 'over':
            break
        g.player.god = god
        g.update()
        app.audio.update()
        if f % draw_every == 0 or f in shots:
            g.draw(screen)
        if f in shots and out:
            os.makedirs(out, exist_ok=True)
            pygame.image.save(screen, os.path.join(out, 'L%03d_f%05d.png' % (level, f)))
        if g.result is not None:
            break
    dt = time.time() - t0
    res = dict(level=level, frames=f, state=g.state, score=g.score, kills=g.stats['kills'],
               escaped=g.stats['escaped'], credits=g.run_credits, boss_time=g.boss_t, secs=dt,
               finished=g.result is not None, hp=g.player.hp, parts=g.stats['parts'])
    if verbose:
        print('level %3d: %s frames=%d (%.1fs real) score=%d kills=%d esc=%d credits=%d boss_t=%.1fs hp=%d parts=%d' % (
            level, 'CLEAR' if res['finished'] else g.state, f, dt, g.score, g.stats['kills'], g.stats['escaped'],
            g.run_credits, g.boss_t / 60, g.player.hp, g.stats['parts']))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--levels', type=str, default=None)
    ap.add_argument('--frames', type=int, default=None)
    ap.add_argument('--god', action='store_true')
    ap.add_argument('--shots', type=str, default='')
    ap.add_argument('--out', type=str, default=None)
    ap.add_argument('--draw-every', type=int, default=1)
    ap.add_argument('--dmg', type=float, default=1.0)
    a = ap.parse_args()
    pygame.init()
    app, screen = make_app()
    shots = [int(s) for s in a.shots.split(',') if s]
    levels = [a.level]
    if a.levels:
        lo, hi = a.levels.split('-')
        levels = list(range(int(lo), int(hi) + 1))
    for lv in levels:
        run_level(app, screen, lv, a.frames, a.god, shots, a.out, draw_every=a.draw_every, dmg_boost=a.dmg)


if __name__ == '__main__':
    main()
