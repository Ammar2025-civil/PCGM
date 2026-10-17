"""Play levels in order with a bot that banks credits and buys upgrades like a player.

Prints one line per level and writes a CSV. Usage:
  python tools/balance_run.py OUT.csv [first_level] [last_level]
"""
import csv
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
import pygame  # noqa: E402

PRIORITY = ['damage', 'rate', 'hull', 'damage', 'speed', 'magnet', 'drones', 'bombs']


def shop_spree(d):
    import shop
    bought = True
    while bought:
        bought = False
        best = None
        for uid in PRIORITY:
            c = shop.cost(uid, d['upgrades'][uid])
            if c is not None and c <= d['credits']:
                w = c * (0.7 if uid in ('damage', 'rate') else 1.0)
                if best is None or w < best[0]:
                    best = (w, uid, c)
        if best:
            d['credits'] -= best[2]
            d['upgrades'][best[1]] += 1
            bought = True


def main(out, first=1, last=100):
    pygame.init()
    app, screen = sim.make_app()
    import shop
    d = app.data
    d['started'] = True
    rows = []
    for lv in range(first, last + 1):
        best_hull = max((h for h in shop.HULLS if shop.hull_unlocked(d, h['id']) and h['unlock'] != 'stars'),
                        key=lambda h: h['unlock'])
        d['hull'] = best_hull['id']
        app.start_level(lv)
        g = app.scene
        rnd = random.Random(lv)
        t0 = time.time()
        f = 0
        while f < 60 * 60 * 9:
            f += 1
            sim.bot_input(g, app.input, rnd, True)
            g.player.god = True
            g.update()
            app.audio.update()
            if app.scene is not g:
                break
        r = g.result or {}
        hits = g.stats.get('god_hits', 0)
        b = g.boss
        dps = (getattr(b, 'dmg_taken', 0) / max(1, g.boss_t / 60.0)) if b else 0
        import levels as LV
        shop_spree(d)
        ups = sum(d['upgrades'].values())
        row = dict(level=lv, finished=int(g.result is not None), banked=r.get('banked', 0), bank_after=d['credits'],
                   upgrades=ups, upgrade_pct=round(100 * ups / 66.0), boss_s=round(g.boss_t / 60.0, 1),
                   kill_pct=round(g.kill_pct()), hits=hits, dps=round(dps), exp_dps=round(LV.expected_dps(lv)), parts=g.stats['parts'], stars=bin(r.get('stars', 0)).count('1'),
                   hull=d['hull'], secs=round(time.time() - t0, 1))
        rows.append(row)
        print(' '.join('%s=%s' % (k, v) for k, v in row.items()), flush=True)
        d['level_unlocked'] = max(d['level_unlocked'], lv + 1)
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], int(a[1]) if len(a) > 1 else 1, int(a[2]) if len(a) > 2 else 100)
