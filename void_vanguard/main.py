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
        self.screen = screen
        self.headless = headless
        self.clock = pygame.time.Clock()
        self.input = Input()
        self.idle_input = Input()
        self.running = True
        self.audio = audio.Audio()
        self.level = 1
        self.scene = None
        self.joy = []
        self.axis_state = {}
        self._init_joysticks()
        self.start_level(1)

    # ------------------------------------------------------------ scenes
    def start_level(self, level):
        import game
        import shop
        self.level = level
        self.scene = game.GameScene(self, level, shop.default_stats())

    def retry_level(self):
        self.start_level(self.level)

    def goto_hangar(self):
        self.start_level(self.level)

    def level_complete(self, result):
        self.start_level(min(100, self.level + 1))

    def record_death(self, level):
        pass

    def best_score(self, level):
        return 0

    def bank_credits(self):
        return 0

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
    flags = pygame.SCALED
    try:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
    pygame.display.set_caption(TITLE)
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
