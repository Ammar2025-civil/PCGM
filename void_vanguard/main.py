"""VOID VANGUARD - run this file:  python main.py"""
import os
import sys

import pygame

from config import SCREEN_W, SCREEN_H, FPS, TITLE, SAMPLE_RATE


class Input:
    __slots__ = ('dx', 'dy', 'bomb', 'pause', 'confirm', 'back', 'up', 'down', 'left', 'right')

    def __init__(self):
        self.clear()

    def clear(self):
        self.dx = self.dy = 0
        self.bomb = self.pause = self.confirm = self.back = False
        self.up = self.down = self.left = self.right = False


MOVE_KEYS = {
    pygame.K_LEFT: 'left', pygame.K_a: 'left', pygame.K_RIGHT: 'right', pygame.K_d: 'right',
    pygame.K_UP: 'up', pygame.K_w: 'up', pygame.K_DOWN: 'down', pygame.K_s: 'down',
}


class App:
    def __init__(self, screen, headless=False):
        import audio
        import save
        import scenes
        self.screen = screen
        self.headless = headless
        self.clock = pygame.time.Clock()
        self.input = Input()
        self.idle_input = Input()
        self.running = True
        self.data, self.has_save = save.load()
        self.audio = audio.Audio(self.data['music_vol'], self.data['sfx_vol'])
        self.level = 1
        self.joy = []
        self.axis_state = {}
        self._init_joysticks()
        self.scene = scenes.TitleScene(self)

    # ------------------------------------------------------------ save
    def save_now(self):
        import save
        save.write(self.data)

    def best_score(self, level):
        return self.data['best'].get(str(level), 0)

    def bank_credits(self):
        return self.data['credits']

    def record_death(self, level):
        key = str(level)
        self.data['deaths'][key] = self.data['deaths'].get(key, 0) + 1
        self.save_now()

    def change_volume(self, which, step):
        """which = 'music_vol' or 'sfx_vol'; volumes go 0..10 and are saved straight away."""
        d = self.data
        d[which] = max(0, min(10, d[which] + step))
        self.audio.set_volumes(d['music_vol'], d['sfx_vol'])
        self.save_now()
        if which == 'sfx_vol':
            self.audio.sfx('explode_s')

    # ------------------------------------------------------------ scenes
    def goto_title(self):
        import scenes
        self.scene = scenes.TitleScene(self)

    def goto_hangar(self):
        import scenes
        self.scene = scenes.HangarScene(self)

    def new_game(self):
        import save
        vols = self.data['music_vol'], self.data['sfx_vol']
        self.data = save.default_save()
        self.data['music_vol'], self.data['sfx_vol'] = vols
        self.data['started'] = True
        self.has_save = True
        self.save_now()
        self.start_level(1)

    def start_level(self, level):
        import game
        import shop
        self.level = level
        d = self.data
        deaths = d['deaths'].get(str(level), 0)
        extra_shield = 2 if deaths >= 6 else (1 if deaths >= 3 else 0)   # quiet adaptive difficulty
        stats = shop.compute_stats(d, extra_shield)
        self.scene = game.GameScene(self, level, stats, shop.game_flags(d))

    def retry_level(self):
        self.start_level(self.level)

    def level_complete(self, result):
        import scenes
        import shop
        d = self.data
        level = result['level']
        key = str(level)
        hull = shop.HULL_BY_ID.get(d['hull'], shop.HULLS[0])
        mult = hull.get('credit_mult', 1.0)
        banked = int((result['run_credits'] + result['clear_bonus'] + result['star_bonus']) * mult)
        result['banked'] = banked
        result['credit_mult'] = mult
        d['credits'] += banked
        before = shop.owned_star_unlocks(d)
        d['stars'][key] = d['stars'].get(key, 0) | result['stars']
        prev_best = d['best'].get(key, 0)
        result['new_best'] = prev_best > 0 and result['score'] > prev_best
        if result['score'] > prev_best:
            d['best'][key] = result['score']
        d['deaths'].pop(key, None)
        d['level_unlocked'] = max(d['level_unlocked'], min(100, level + 1))
        d['selected'] = min(d['level_unlocked'], level + 1)
        d['total_kills'] += result['kills']
        if result['golden']:
            d['golden'] += 1
        unlocks = []
        if level % 10 == 0:
            for h in shop.HULLS:
                if h['unlock'] == level // 10 and h['id'] not in d['hulls']:
                    d['hulls'].append(h['id'])
                    unlocks.append(('hull', h['id']))
        after = shop.owned_star_unlocks(d)
        for need, k, txt in shop.STAR_UNLOCKS:
            if k in after and k not in before:
                unlocks.append(('star', txt))
        result['first_complete'] = level == 100 and not d['complete']
        if level == 100:
            d['complete'] = True
        self.save_now()
        self.scene = scenes.ResultsScene(self, result, unlocks)

    def after_results(self, result):
        import scenes
        if result.get('first_complete'):
            self.scene = scenes.VictoryScene(self)
        else:
            self.goto_hangar()

    def quit(self):
        self.running = False

    # ------------------------------------------------------------ input
    def _init_joysticks(self):
        try:
            pygame.joystick.init()
            self.joy = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        except pygame.error:
            self.joy = []

    def poll(self):
        inp = self.input
        inp.clear()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_F11:
                    self.toggle_fullscreen()
                elif k in (pygame.K_p, pygame.K_ESCAPE):
                    inp.pause = True
                    if k == pygame.K_ESCAPE:
                        inp.back = True
                elif k == pygame.K_SPACE:
                    inp.bomb = True
                    inp.confirm = True
                elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_z):
                    inp.confirm = True
                elif k == pygame.K_BACKSPACE:
                    inp.back = True
                if k in MOVE_KEYS:
                    setattr(inp, MOVE_KEYS[k], True)
            elif ev.type == pygame.JOYDEVICEADDED or ev.type == pygame.JOYDEVICEREMOVED:
                self._init_joysticks()
            elif ev.type == pygame.JOYBUTTONDOWN:
                if ev.button == 0:
                    inp.bomb = inp.confirm = True
                elif ev.button == 1:
                    inp.back = True
                elif ev.button in (6, 7, 9):
                    inp.pause = True
            elif ev.type == pygame.JOYHATMOTION:
                hx, hy = ev.value
                if hx < 0:
                    inp.left = True
                elif hx > 0:
                    inp.right = True
                if hy > 0:
                    inp.up = True
                elif hy < 0:
                    inp.down = True
            elif ev.type == pygame.JOYAXISMOTION and ev.axis in (0, 1):
                prev = self.axis_state.get(ev.axis, 0)
                cur = -1 if ev.value < -0.6 else (1 if ev.value > 0.6 else 0)
                if cur != prev and cur != 0:
                    if ev.axis == 0:
                        setattr(inp, 'left' if cur < 0 else 'right', True)
                    else:
                        setattr(inp, 'up' if cur < 0 else 'down', True)
                self.axis_state[ev.axis] = cur
        keys = pygame.key.get_pressed()
        dx = (1 if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0) - (1 if (keys[pygame.K_LEFT] or keys[pygame.K_a]) else 0)
        dy = (1 if (keys[pygame.K_DOWN] or keys[pygame.K_s]) else 0) - (1 if (keys[pygame.K_UP] or keys[pygame.K_w]) else 0)
        for j in self.joy:
            try:
                ax, ay = j.get_axis(0), j.get_axis(1)
                if abs(ax) > 0.35:
                    dx = 1 if ax > 0 else -1
                if abs(ay) > 0.35:
                    dy = 1 if ay > 0 else -1
                if j.get_numhats():
                    hx, hy = j.get_hat(0)
                    if hx:
                        dx = hx
                    if hy:
                        dy = -hy
            except pygame.error:
                pass
        inp.dx, inp.dy = dx, dy

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            pass

    # ------------------------------------------------------------ loop
    def run(self):
        while self.running:
            self.poll()
            self.scene.update()
            self.audio.update()
            self.scene.draw(self.screen)
            pygame.display.flip()
            self.clock.tick(FPS)


def create_window():
    # Fullscreen by default (F11 switches to a window). Tests and the headless
    # build check use the dummy video driver, so they stay windowed.
    windowed = os.environ.get('SDL_VIDEODRIVER') == 'dummy' or os.environ.get('VV_WINDOWED')
    flags = pygame.SCALED if windowed else (pygame.SCALED | pygame.FULLSCREEN)
    try:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, vsync=1)
    except pygame.error:
        try:
            screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        except pygame.error:
            # some drivers refuse fullscreen; a window beats a crash
            screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED)
    pygame.display.set_caption(TITLE)
    try:
        import art
        ic = art.hull_sprite('falcon')
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        big = pygame.transform.scale(ic, (ic.get_width() * 32 // max(ic.get_size()), ic.get_height() * 32 // max(ic.get_size())))
        icon.blit(big, (16 - big.get_width() // 2, 16 - big.get_height() // 2))
        pygame.display.set_icon(icon)
    except pygame.error:
        pass
    return screen


def main():
    try:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
    except pygame.error:
        pass
    pygame.init()
    screen = create_window()
    app = App(screen)
    app.run()
    pygame.quit()


if __name__ == '__main__':
    # make sure we run from the game folder so imports work from anywhere
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    main()
