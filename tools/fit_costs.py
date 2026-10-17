"""Given per-level income from a balance run CSV, show how fast the shop gets bought out.

Usage: python tools/fit_costs.py run.csv [cost_scale]
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'void_vanguard'))
import shop  # noqa: E402

PRIORITY = ['damage', 'rate', 'hull', 'damage', 'speed', 'magnet', 'drones', 'bombs']


def main(path, scale=None):
    if scale is not None:
        shop.COST_SCALE = scale
    income = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            income[int(row['level'])] = int(row['banked'])
    total_cost = sum(shop.cost(u['id'], i) for u in shop.UPGRADES for i in range(u['max']))
    total_lv = sum(u['max'] for u in shop.UPGRADES)
    ups = {u['id']: 0 for u in shop.UPGRADES}
    bank = 0
    marks = {}
    print('total cost of every upgrade: %d   total income: %d' % (total_cost, sum(income.values())))
    for lv in sorted(income):
        bank += income[lv]
        while True:
            best = None
            for uid in PRIORITY:
                c = shop.cost(uid, ups[uid])
                if c is not None and c <= bank:
                    w = c * (0.7 if uid in ('damage', 'rate') else 1.0)
                    if best is None or w < best[0]:
                        best = (w, uid, c)
            if not best:
                break
            bank -= best[2]
            ups[best[1]] += 1
        pct = 100 * sum(ups.values()) / total_lv
        for m in (10, 25, 50, 75, 85, 100):
            if pct >= m and m not in marks:
                marks[m] = lv
        if lv in (1, 2, 3, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
            print('after level %3d: %3d%% owned  bank %7d  %s' % (lv, pct, bank, ups))
    print('milestones (percent owned -> level):', marks)


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else None)
