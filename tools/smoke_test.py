"""Crash test: plays every level (god mode, boosted damage) start to finish, drawing frames too.

Usage: python tools/smoke_test.py [first] [last]
Exits with code 1 if any level crashes or fails to finish.
"""
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
import pygame  # noqa: E402


def main(first=1, last=100):
    pygame.init()
    app, screen = sim.make_app()
    import shop
    # fly a well-upgraded ship so late levels finish in reasonable time
    for u in shop.UPGRADES:
        app.data['upgrades'][u['id']] = u['max'] * 3 // 4
    bad = []
    t0 = time.time()
    for lv in range(first, last + 1):
        try:
            res = sim.run_level(app, screen, lv, 60 * 60 * 6, True, draw_every=7, dmg_boost=2.0, verbose=False)
            ok = res['finished']
            print('level %3d %-6s %5.1fs real, %d frames, boss %.0fs' % (
                lv, 'OK' if ok else 'STUCK', res['secs'], res['frames'], res['boss_time'] / 60.0), flush=True)
            if not ok:
                bad.append((lv, 'did not finish'))
        except Exception:
            traceback.print_exc()
            bad.append((lv, 'exception'))
            print('level %3d CRASH' % lv, flush=True)
    print('\n%d levels in %.0fs, problems: %s' % (last - first + 1, time.time() - t0, bad or 'none'))
    return 1 if bad else 0


if __name__ == '__main__':
    a = sys.argv[1:]
    sys.exit(main(int(a[0]) if a else 1, int(a[1]) if len(a) > 1 else 100))
