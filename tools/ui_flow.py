"""Drive the menus with scripted key presses and screenshot each screen."""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402  (sets up paths + dummy drivers)
import pygame  # noqa: E402


def press(app, **keys):
    app.input.clear()
    for k, v in keys.items():
        setattr(app.input, k, v)
    app.scene.update()
    app.input.clear()


def tick(app, screen, n=1):
    for _ in range(n):
        app.input.clear()
        app.scene.update()
    app.scene.draw(screen)


def shot(screen, out, name):
    os.makedirs(out, exist_ok=True)
    pygame.image.save(screen, os.path.join(out, name + '.png'))


def main(out):
    pygame.init()
    app, screen = sim.make_app()
    import game
    import scenes
    tick(app, screen, 40)
    shot(screen, out, '01_title')
    press(app, confirm=True)          # PLAY (no save -> straight into level 1)
    assert isinstance(app.scene, game.GameScene), type(app.scene)
    g = app.scene
    g.player.stats['dmg'] *= 6
    rnd = random.Random(2)
    for f in range(20000):
        sim.bot_input(g, app.input, rnd, True)
        g.player.god = True
        g.update()
        if app.scene is not g:
            break
    assert isinstance(app.scene, scenes.ResultsScene), type(app.scene)
    tick(app, screen, 300)
    shot(screen, out, '02_results')
    press(app, confirm=True)
    assert isinstance(app.scene, scenes.HangarScene)
    d = app.data
    print('credits after level 1:', d['credits'], 'unlocked:', d['level_unlocked'], 'stars:', d['stars'])
    press(app, down=True)
    press(app, down=True)             # weapon damage row? (row 2 = hull strength)
    for _ in range(3):
        press(app, confirm=True)
    press(app, down=True)
    press(app, confirm=True)
    tick(app, screen, 5)
    shot(screen, out, '03_hangar')
    print('upgrades:', d['upgrades'], 'credits left:', d['credits'])
    press(app, back=True)
    tick(app, screen, 10)
    shot(screen, out, '04_title_with_save')
    press(app, up=True)
    press(app, confirm=True)
    tick(app, screen, 2)
    shot(screen, out, '05_confirm_new')
    # reload the save from disk to prove it was written
    import save
    data, existed = save.load()
    print('reloaded save exists:', existed, 'credits:', data['credits'], 'upgrades:', data['upgrades'])


if __name__ == '__main__':
    main(sys.argv[1])
