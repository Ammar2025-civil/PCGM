"""Fight every boss level in god mode and screenshot each phase. Usage: python tools/boss_test.py OUTDIR [levels]"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402
import pygame  # noqa: E402


def main(out, levels):
    pygame.init()
    app, screen = sim.make_app()
    from config import PF_X, PF_W, PF_H
    os.makedirs(out, exist_ok=True)
    for lv in levels:
        app.start_level(lv)
        g = app.scene
        # jump straight to the end fight
        g.wave_frame = g.plan.wave_end - 2
        g.ev_i = len([e for e in g.plan.events if e[0] < g.plan.wave_end - 2])
        g.player.stats['dmg'] *= float(os.environ.get('BOSS_DMG', '2.5'))
        rnd = random.Random(lv)
        shots = set()
        phases_seen = set()
        f = 0
        while f < 60 * 60 * 5:
            f += 1
            sim.bot_input(g, app.input, rnd, True)
            g.player.god = True
            g.update()
            if g.boss is not None:
                ph = g.boss.phase_index
                phases_seen.add(ph)
                key = (ph, g.boss.trans > 0)
                if key not in shots and g.boss.fighting and g.boss.trans == 0 and g.boss.t % 200 == 150:
                    shots.add(key)
                    g.draw(screen)
                    pygame.image.save(screen.subsurface((PF_X, 0, PF_W, PF_H)), os.path.join(out, 'B%03d_p%d.png' % (lv, ph)))
            if app.scene is not g or g.result is not None:
                break
        b = g.boss
        print('level %3d %-24s phases seen %s/%d  fight %.1fs  finished=%s' % (
            lv, b.name if b else '-', sorted(phases_seen), len(b.phases) if b else 0, g.boss_t / 60.0,
            g.result is not None or app.scene is not g))


if __name__ == '__main__':
    lv = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(range(5, 101, 5))
    main(sys.argv[1], lv)
