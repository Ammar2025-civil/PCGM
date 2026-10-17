"""Title menu, hangar/shop, results and victory screens."""
import math

import pygame

import art
import backgrounds
import level_data
import levels
import shop
from config import SCREEN_W, SCREEN_H, WHITE, GOLD, VERSION
from hud import bar, fmt, LABEL

HULL_UNLOCK_TEXT = 'BEAT THE SECTOR %d BOSS'


def draw_flame(surf, x, y, scale, t):
    n = (3 + (t // 2) % 3) * scale
    surf.fill((255, 120, 40), (x - scale, y, scale * 2, n + scale * 2))
    surf.fill((255, 230, 120), (x - scale, y, scale * 2, n))
    surf.fill(WHITE, (x - scale // 2, y, max(1, scale), max(1, n - scale * 2)))


def logo(surf, cx, y, t):
    a = art.big_text('VOID', 6, (255, 250, 200), (255, 120, 40), (20, 8, 30), (90, 20, 70))
    b = art.big_text('VANGUARD', 4, (200, 240, 255), (70, 120, 255), (10, 10, 40), (30, 40, 120))
    surf.blit(a, (cx - a.get_width() // 2, y))
    surf.blit(b, (cx - b.get_width() // 2, y + a.get_height() - 4))
    # shine sweep
    sx = (t * 4) % 900 - 200
    if 0 <= sx < SCREEN_W:
        for i in range(6):
            surf.fill((255, 255, 255), (sx + i - 20, y + 4 + i * 10, 2, 4))


class Confirm:
    def __init__(self, text, sub=None, yes='YES', no='NO'):
        self.text, self.sub, self.yes, self.no = text, sub, yes, no
        self.sel = 1

    def update(self, inp):
        if inp.left or inp.right or inp.up or inp.down:
            self.sel = 1 - self.sel
            return 'move'
        if inp.confirm:
            return 'yes' if self.sel == 0 else 'no'
        if inp.back:
            return 'no'
        return None

    def draw(self, screen):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        screen.blit(dim, (0, 0))
        w, h = 330, 86
        x, y = SCREEN_W // 2 - w // 2, SCREEN_H // 2 - h // 2
        pygame.draw.rect(screen, (14, 10, 28), (x, y, w, h))
        pygame.draw.rect(screen, (255, 120, 90), (x, y, w, h), 1)
        art.text(screen, self.text, SCREEN_W // 2, y + 12, WHITE, 1, 'c')
        if self.sub:
            art.text(screen, self.sub, SCREEN_W // 2, y + 26, (255, 150, 130), 1, 'c')
        for i, label in enumerate((self.yes, self.no)):
            bx = SCREEN_W // 2 - 70 + i * 80
            sel = self.sel == i
            pygame.draw.rect(screen, (90, 40, 40) if sel else (30, 26, 50), (bx, y + 52, 60, 18))
            if sel:
                pygame.draw.rect(screen, WHITE, (bx, y + 52, 60, 18), 1)
            art.text(screen, label, bx + 30, y + 57, WHITE if sel else (150, 150, 180), 1, 'c')


class Backdrop:
    """Full-screen starfield with Earth, for the title and ending."""

    def __init__(self, seed=3):
        self.base = backgrounds.gradient((4, 6, 20), (12, 18, 46), SCREEN_W, SCREEN_H, 20)
        self.layers = [
            backgrounds.star_layer(seed, 160, [(70, 80, 120), (90, 90, 140)], 0, SCREEN_W, SCREEN_H),
            backgrounds.star_layer(seed + 1, 70, [(150, 160, 210), (200, 200, 230)], 6, SCREEN_W, SCREEN_H),
            backgrounds.star_layer(seed + 2, 24, [(255, 255, 255), (200, 220, 255)], 4, SCREEN_W, SCREEN_H),
        ]
        self.planet = backgrounds.sphere(220, 8, backgrounds._earth_col, (-0.5, -0.7, 0.5), rim=(120, 190, 255))
        self.off = [0.0, 0.0, 0.0]

    def update(self, speed=1.0):
        for i, f in enumerate((0.1, 0.35, 1.0)):
            self.off[i] += speed * f

    def draw(self, screen, planet_y=170):
        screen.blit(self.base, (0, 0))
        for layer, off in zip(self.layers, self.off):
            backgrounds.blit_scroll(screen, layer, off)
        screen.blit(self.planet, (SCREEN_W - self.planet.get_width() + 150, planet_y + 30))


# ====================================================================== title
class TitleScene:
    def __init__(self, app):
        self.app = app
        self.t = 0
        self.sel = 0 if not app.has_save else 1
        self.bg = Backdrop(3)
        self.confirm = None
        self.ship_x = SCREEN_W / 2
        self.shots = []
        self.app.audio.play_music('title')
        self.app.audio.set_intensity(2)

    def options(self):
        return ['PLAY', 'CONTINUE', 'MUTE: ' + ('ON' if self.app.audio.muted else 'OFF')]

    def update(self):
        inp = self.app.input
        self.t += 1
        self.bg.update(0.8)
        self.ship_x = SCREEN_W / 2 + math.sin(self.t * 0.02) * 60
        if self.t % 7 == 0:
            self.shots.append([self.ship_x - 3, 300])
            self.shots.append([self.ship_x + 3, 300])
        for s in self.shots:
            s[1] -= 8
        self.shots = [s for s in self.shots if s[1] > 150]
        if self.confirm is not None:
            r = self.confirm.update(inp)
            if r == 'move':
                self.app.audio.sfx('menu_move')
            elif r == 'yes':
                self.app.audio.sfx('menu_select')
                kind = self.confirm.kind
                self.confirm = None
                if kind == 'new':
                    self.app.new_game()
                else:
                    self.app.quit()
            elif r == 'no':
                self.app.audio.sfx('menu_move')
                self.confirm = None
            return
        if inp.up:
            self.sel = (self.sel - 1) % 3
            self.app.audio.sfx('menu_move')
        if inp.down:
            self.sel = (self.sel + 1) % 3
            self.app.audio.sfx('menu_move')
        if inp.back:
            self.confirm = Confirm('QUIT THE GAME?', None, 'QUIT', 'STAY')
            self.confirm.kind = 'quit'
            return
        if inp.confirm or (self.sel == 2 and (inp.left or inp.right)):
            if self.sel == 0:
                self.app.audio.sfx('menu_select')
                if self.app.has_save:
                    self.confirm = Confirm('START A NEW GAME?', 'THIS ERASES YOUR SAVED PROGRESS', 'ERASE', 'CANCEL')
                    self.confirm.kind = 'new'
                else:
                    self.app.new_game()
            elif self.sel == 1:
                if self.app.has_save:
                    self.app.audio.sfx('menu_select')
                    self.app.goto_hangar()
                else:
                    self.app.audio.sfx('error')
            else:
                self.app.toggle_mute()
                self.app.audio.sfx('menu_select')

    def draw(self, screen):
        self.bg.draw(screen, 190)
        logo(screen, SCREEN_W // 2, 34, self.t)
        for x, y in self.shots:
            screen.fill((255, 230, 140), (int(x) - 1, int(y), 2, 6))
        ship = art.hull_sprite('falcon')
        ship2 = pygame.transform.scale(ship, (ship.get_width() * 2, ship.get_height() * 2))
        sx, sy = int(self.ship_x), 304
        draw_flame(screen, sx - 5, sy + ship2.get_height() // 2 - 2, 1, self.t)
        draw_flame(screen, sx + 5, sy + ship2.get_height() // 2 - 2, 1, self.t)
        screen.blit(ship2, (sx - ship2.get_width() // 2, sy - ship2.get_height() // 2))
        opts = self.options()
        for i, o in enumerate(opts):
            y = 176 + i * 22
            disabled = (i == 1 and not self.app.has_save)
            if i == self.sel:
                w = art.text_width(o, 2) + 40
                pygame.draw.rect(screen, (40, 30, 80), (SCREEN_W // 2 - w // 2, y - 4, w, 22))
                pygame.draw.rect(screen, (255, 210, 90), (SCREEN_W // 2 - w // 2, y - 4, w, 22), 1)
                blink = (self.t // 15) % 2
                art.text(screen, '>', SCREEN_W // 2 - w // 2 + 6 + blink, y, (255, 210, 90), 2)
                art.text(screen, '<', SCREEN_W // 2 + w // 2 - 16 - blink, y, (255, 210, 90), 2)
            col = (90, 90, 110) if disabled else (WHITE if i == self.sel else (180, 180, 210))
            art.text(screen, o, SCREEN_W // 2, y, col, 2, 'c')
        if self.app.has_save:
            d = self.app.data
            art.text(screen, 'SAVED: LEVEL %s   %d STARS   %s CREDITS' % (
                levels.level_name(d['level_unlocked']), shop.total_stars(d), fmt(d['credits'])),
                SCREEN_W // 2, 246, (150, 150, 190), 1, 'c')
        art.text(screen, 'ARROWS/WASD MOVE   AUTO FIRE   SPACE BOMB   P/ESC PAUSE   F11 FULLSCREEN',
                 SCREEN_W // 2, 344, (120, 120, 160), 1, 'c')
        art.text(screen, 'V' + VERSION, 6, 6, (70, 70, 100))
        if self.confirm is not None:
            self.confirm.draw(screen)


# ====================================================================== hangar
class HangarScene:
    ROW_LAUNCH, ROW_HULL = 0, 1
    ROW_UP0 = 2

    def __init__(self, app):
        self.app = app
        self.t = 0
        self.sel = 0
        self.msg = None
        self.msg_t = 0
        self.flash_row = -1
        self.flash_t = 0
        d = app.data
        d['selected'] = max(1, min(d['level_unlocked'], d['selected']))
        self.hull_ids = [h['id'] for h in shop.HULLS]
        self.hull_i = self.hull_ids.index(d['hull']) if d['hull'] in self.hull_ids else 0
        self.bg = self.make_bg()
        self.rows = 2 + len(shop.UPGRADES) + 1
        self.app.audio.play_music('hangar')
        self.app.audio.set_intensity(1)

    def make_bg(self):
        s = backgrounds.gradient((18, 16, 34), (8, 8, 18), SCREEN_W, SCREEN_H, 16)
        for x in range(0, SCREEN_W, 32):
            s.fill((24, 22, 44), (x, 0, 1, SCREEN_H))
        for y in range(0, SCREEN_H, 32):
            s.fill((24, 22, 44), (0, y, SCREEN_W, 1))
        for i in range(0, SCREEN_W + 40, 16):
            pygame.draw.polygon(s, (60, 50, 20), [(i, 0), (i + 8, 0), (i, 8), (i - 8, 8)])
        return s

    def say(self, text, color=WHITE):
        self.msg = (text, color)
        self.msg_t = 120

    def current_hull(self):
        return shop.HULLS[self.hull_i]

    def update(self):
        app = self.app
        inp = app.input
        d = app.data
        self.t += 1
        if self.msg_t:
            self.msg_t -= 1
        if self.flash_t:
            self.flash_t -= 1
        if inp.back:
            app.audio.sfx('menu_move')
            app.goto_title()
            return
        if inp.up:
            self.sel = (self.sel - 1) % self.rows
            app.audio.sfx('menu_move')
        if inp.down:
            self.sel = (self.sel + 1) % self.rows
            app.audio.sfx('menu_move')
        if self.sel == self.ROW_LAUNCH and (inp.left or inp.right):
            step = -1 if inp.left else 1
            d['selected'] = max(1, min(d['level_unlocked'], d['selected'] + step))
            app.audio.sfx('menu_move')
        if self.sel == self.ROW_HULL and (inp.left or inp.right):
            step = -1 if inp.left else 1
            self.hull_i = (self.hull_i + step) % len(shop.HULLS)
            app.audio.sfx('menu_move')
            h = self.current_hull()
            if shop.hull_unlocked(d, h['id']) and d['hull'] != h['id']:
                d['hull'] = h['id']
                app.save_now()
        if inp.confirm:
            if self.sel == self.ROW_LAUNCH:
                if not shop.hull_unlocked(d, d['hull']):
                    d['hull'] = 'falcon'
                app.audio.sfx('launch')
                app.start_level(d['selected'])
                return
            elif self.sel == self.ROW_HULL:
                h = self.current_hull()
                if shop.hull_unlocked(d, h['id']):
                    d['hull'] = h['id']
                    app.save_now()
                    app.audio.sfx('menu_select')
                    self.say('%s READY' % h['name'], (140, 255, 160))
                else:
                    app.audio.sfx('error')
                    self.say('LOCKED', (255, 120, 120))
            elif self.sel == self.rows - 1:
                app.audio.sfx('menu_move')
                app.goto_title()
                return
            else:
                self.buy(shop.UPGRADES[self.sel - self.ROW_UP0])

    def buy(self, u):
        app = self.app
        d = app.data
        lv = d['upgrades'][u['id']]
        c = shop.cost(u['id'], lv)
        if c is None:
            app.audio.sfx('error')
            self.say('ALREADY MAXED', (255, 200, 120))
            return
        if d['credits'] < c:
            app.audio.sfx('error')
            self.say('NEED %s MORE CREDITS' % fmt(c - d['credits']), (255, 120, 120))
            return
        d['credits'] -= c
        d['upgrades'][u['id']] = lv + 1
        app.save_now()
        app.audio.sfx('buy')
        self.flash_row = self.sel
        self.flash_t = 20
        self.say('%s UPGRADED TO LV%d' % (u['name'], lv + 1), (140, 255, 160))

    # ------------------------------------------------------------ drawing
    def row_box(self, screen, idx, rect):
        r = pygame.Rect(rect)
        sel = self.sel == idx
        col = (255, 210, 90) if sel else (60, 60, 100)
        fill = (40, 32, 70) if sel else (14, 12, 30)
        if self.flash_t and self.flash_row == idx and self.flash_t % 4 < 2:
            fill = (90, 200, 120)
        pygame.draw.rect(screen, fill, r)
        pygame.draw.rect(screen, col, r, 1)
        return sel

    def draw(self, screen):
        d = self.app.data
        screen.blit(self.bg, (0, 0))
        t = art.big_text('HANGAR', 2, (255, 240, 200), (255, 150, 60))
        screen.blit(t, (10, 12))
        art.text(screen, 'CREDITS', 400, 12, LABEL)
        art.text(screen, fmt(d['credits']), 400, 22, GOLD, 2)
        stars = shop.total_stars(d)
        screen.blit(art.icon('star', GOLD), (540, 12))
        art.text(screen, '%d / 300' % stars, 552, 13, WHITE)
        nxt = next(((n, txt) for n, k, txt in shop.STAR_UNLOCKS if stars < n), None)
        if nxt:
            art.text(screen, 'NEXT AT %d' % nxt[0], 540, 25, (150, 150, 190))

        # ---------------- ship column
        h = self.current_hull()
        unlocked = shop.hull_unlocked(d, h['id'])
        bx, by = 10, 44
        pygame.draw.rect(screen, (10, 9, 22), (bx, by, 196, 150))
        pygame.draw.rect(screen, (60, 60, 100), (bx, by, 196, 150), 1)
        for i in range(5):
            pygame.draw.line(screen, (30, 40, 80), (bx + 40 + i * 30, by + 120), (bx + 20 + i * 40, by + 148))
        pygame.draw.ellipse(screen, (30, 40, 90), (bx + 48, by + 112, 100, 18))
        pygame.draw.ellipse(screen, (60, 90, 180), (bx + 48, by + 112, 100, 18), 1)
        paint = 'gold' if 'gold' in shop.owned_star_unlocks(d) else None
        hs = art.hull_sprite(h['id'], paint)
        sc = 4
        big = pygame.transform.scale(hs, (hs.get_width() * sc, hs.get_height() * sc))
        if not unlocked:
            big = art.silhouette(big, (40, 40, 70))
        hover = int(math.sin(self.t * 0.05) * 3)
        cx, cy = bx + 98, by + 66 + hover
        if unlocked:
            geo = art.hull_geometry(h['id'])
            for ex, ey in geo['engines']:
                draw_flame(screen, int(cx + ex * sc), int(cy + ey * sc), 2, self.t)
        screen.blit(big, (cx - big.get_width() // 2, cy - big.get_height() // 2))
        if not unlocked:
            screen.blit(art.icon('lock', (200, 200, 220)), (cx - 3, cy - 3))
        art.text(screen, '<', bx + 6, by + 64, (255, 210, 90) if self.sel == self.ROW_HULL else (80, 80, 120), 2)
        art.text(screen, '>', bx + 180, by + 64, (255, 210, 90) if self.sel == self.ROW_HULL else (80, 80, 120), 2)
        art.text(screen, '%d/%d' % (self.hull_i + 1, len(shop.HULLS)), bx + 190, by + 4, (90, 90, 130), 1, 'r')

        self.row_box(screen, self.ROW_HULL, (bx, by + 154, 196, 34))
        name_col = WHITE if unlocked else (120, 120, 150)
        tag = '' if not unlocked else (' (FLYING)' if d['hull'] == h['id'] else '')
        art.text(screen, 'SHIP: ' + h['name'] + tag, bx + 6, by + 159, name_col)
        if unlocked:
            art.text(screen, h['desc'], bx + 6, by + 172, (180, 200, 255))
        else:
            how = 'EARN 200 STARS' if h['unlock'] == 'stars' else HULL_UNLOCK_TEXT % h['unlock']
            art.text(screen, 'LOCKED: ' + how, bx + 6, by + 172, (255, 140, 140))

        # stats preview for the shown hull
        tmp = dict(d)
        tmp['hull'] = h['id']
        st = shop.compute_stats(tmp)
        sy = by + 196
        pygame.draw.rect(screen, (10, 9, 22), (bx, sy, 196, 96))
        pygame.draw.rect(screen, (60, 60, 100), (bx, sy, 196, 96), 1)
        rows = [('HULL', st['hp'] / 13.0, '%d' % st['hp']), ('DAMAGE', st['dmg'] / 2.6, '%d%%' % int(st['dmg'] * 100)),
                ('FIRE RATE', (1 / st['rate']) / 2.3, '%d%%' % int(100 / st['rate'])),
                ('SPEED', st['speed'] / 4.0, '%.1f' % st['speed']), ('MAGNET', st['magnet'] / 190.0, '%d' % st['magnet']),
                ('BOMBS', st['bombs'] / 7.0, '%d' % st['bombs']), ('DRONES', st['drone_slots'] / 5.0, '%d' % st['drone_slots'])]
        for i, (lab, frac, val) in enumerate(rows):
            yy = sy + 6 + i * 12
            art.text(screen, lab, bx + 6, yy, LABEL)
            bar(screen, bx + 72, yy + 1, 86, 5, frac, (90, 170, 255))
            art.text(screen, val, bx + 190, yy, WHITE, 1, 'r')

        # ---------------- upgrades column
        ux, uy = 214, 44
        art.text(screen, 'PERMANENT UPGRADES', ux, uy, LABEL)
        for i, u in enumerate(shop.UPGRADES):
            idx = self.ROW_UP0 + i
            yy = uy + 12 + i * 30
            sel = self.row_box(screen, idx, (ux, yy, 210, 27))
            lv = d['upgrades'][u['id']]
            art.text(screen, u['name'], ux + 6, yy + 4, WHITE if sel else (200, 200, 230))
            for j in range(u['max']):
                c = (255, 170, 50) if j < lv else (40, 38, 70)
                screen.fill(c, (ux + 6 + j * 9, yy + 16, 7, 5))
            c = shop.cost(u['id'], lv)
            if c is None:
                art.text(screen, 'MAX', ux + 204, yy + 4, (140, 255, 160), 1, 'r')
            else:
                afford = d['credits'] >= c
                art.text(screen, fmt(c), ux + 204, yy + 4, GOLD if afford else (130, 90, 90), 1, 'r')
            if sel:
                art.text(screen, u['desc'], ux + 204, yy + 16, (170, 190, 255), 1, 'r')
        sel_exit = self.row_box(screen, self.rows - 1, (ux, uy + 12 + len(shop.UPGRADES) * 30, 210, 16))
        art.text(screen, 'BACK TO TITLE', ux + 105, uy + 16 + len(shop.UPGRADES) * 30, WHITE if sel_exit else (150, 150, 180), 1, 'c')

        # ---------------- mission column
        mx, my = 432, 44
        lv = d['selected']
        sec = levels.sector_of(lv)
        ui = art.SECTOR_STYLE[sec]['ui']
        sel_launch = self.row_box(screen, self.ROW_LAUNCH, (mx, my, 198, 70))
        art.text(screen, '<', mx + 6, my + 14, (255, 210, 90) if sel_launch else (80, 80, 120), 2)
        art.text(screen, '>', mx + 182, my + 14, (255, 210, 90) if sel_launch else (80, 80, 120), 2)
        art.text(screen, 'LEVEL ' + levels.level_name(lv), mx + 99, my + 6, WHITE, 2, 'c')
        art.text(screen, level_data.SECTORS[sec]['name'], mx + 99, my + 24, ui, 1, 'c')
        ek = levels.end_kind(lv)
        art.text(screen, {'boss': 'SECTOR BOSS', 'miniboss': 'MINI-BOSS', 'frigate': 'FRIGATE'}[ek], mx + 99, my + 34,
                 (255, 120, 120) if ek == 'boss' else (200, 160, 160), 1, 'c')
        sm = d['stars'].get(str(lv), 0)
        for i in range(3):
            got = sm & (1 << i)
            screen.blit(art.icon('star', GOLD if got else (60, 60, 90)), (mx + 78 + i * 12, my + 44))
        best = d['best'].get(str(lv), 0)
        if best:
            art.text(screen, 'BEST ' + fmt(best), mx + 99, my + 56, (150, 150, 190), 1, 'c')
        go = 'PRESS ENTER TO LAUNCH' if sel_launch else ''
        if go and (self.t // 20) % 2 == 0:
            art.text(screen, go, mx + 99, my + 74, (255, 220, 120), 1, 'c')

        # level map: 10 sectors x 10 levels
        gx, gy = mx, my + 86
        art.text(screen, 'MAP', gx, gy, LABEL)
        for s in range(10):
            for k in range(10):
                L = s * 10 + k + 1
                x = gx + k * 19 + 10
                y = gy + 10 + s * 11
                if L > d['level_unlocked']:
                    col = (24, 22, 40)
                else:
                    col = art.scale(art.SECTOR_STYLE[s + 1]['ui'], 0.45)
                screen.fill(col, (x, y, 17, 9))
                n = bin(d['stars'].get(str(L), 0)).count('1')
                for j in range(n):
                    screen.fill(GOLD, (x + 3 + j * 4, y + 3, 3, 3))
                if L % 10 == 0:
                    screen.fill((180, 60, 70), (x + 15, y, 2, 9))
                if L == lv:
                    pygame.draw.rect(screen, WHITE, (x - 1, y - 1, 19, 11), 1)
            art.text(screen, str(s + 1), gx, gy + 11 + s * 11, (90, 90, 130))

        # star rewards
        ry = gy + 124
        art.text(screen, 'STAR REWARDS', mx, ry, LABEL)
        owned = shop.owned_star_unlocks(d)
        shown = [u for u in shop.STAR_UNLOCKS if u[1] not in owned][:2]
        got = [u for u in shop.STAR_UNLOCKS if u[1] in owned][-1:]
        yy = ry + 10
        for n, k, txt in got + shown:
            has = k in owned
            screen.blit(art.icon('star', GOLD if has else (90, 90, 130)), (mx, yy))
            art.text(screen, ('OWNED' if has else 'AT %d STARS' % n), mx + 12, yy, GOLD if has else (130, 130, 170))
            art.text(screen, txt, mx + 12, yy + 9, (200, 255, 200) if has else (190, 190, 220))
            yy += 22

        if self.msg_t and self.msg:
            art.text(screen, self.msg[0], SCREEN_W // 2, 344, self.msg[1], 1, 'c')
        else:
            art.text(screen, 'UP/DOWN SELECT   LEFT/RIGHT CHANGE   ENTER BUY/LAUNCH   ESC TITLE',
                     SCREEN_W // 2, 344, (100, 100, 140), 1, 'c')


# ====================================================================== results
class ResultsScene:
    def __init__(self, app, result, unlocks):
        self.app = app
        self.r = result
        self.unlocks = unlocks
        self.t = 0
        self.shown_credits = 0
        self.total = result['banked']
        self.done = False
        self.app.audio.play_music('hangar')
        self.app.audio.set_intensity(1)

    def update(self):
        inp = self.app.input
        self.t += 1
        if self.t > 150 and self.shown_credits < self.total:
            step = max(1, self.total // 70)
            self.shown_credits = min(self.total, self.shown_credits + step)
            if self.t % 3 == 0:
                self.app.audio.sfx('coin', 0.5)
        for i in range(3):
            if self.t == 70 + i * 22 and self.r['challenge_done'][i]:
                self.app.audio.sfx('star')
        if inp.confirm and self.t > 30:
            if self.shown_credits < self.total:
                self.shown_credits = self.total
                self.t = max(self.t, 230)
            else:
                self.app.audio.sfx('menu_select')
                self.app.after_results(self.r)

    def draw(self, screen):
        r = self.r
        screen.fill((8, 8, 20))
        for i in range(0, SCREEN_W, 4):
            screen.fill((14, 12, 30), (i, 0, 1, SCREEN_H))
        title = 'SECTOR CLEAR!' if r['end_kind'] == 'boss' else 'LEVEL CLEAR!'
        t = art.big_text(title, 3, (200, 255, 220), (60, 200, 120), (10, 20, 10), (20, 60, 40))
        screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 14))
        art.text(screen, 'LEVEL ' + levels.level_name(r['level']), SCREEN_W // 2, 50, LABEL, 1, 'c')
        rows = [('SCORE', fmt(r['score']) + ('  NEW BEST!' if r.get('new_best') else '')),
                ('BEST CHAIN', '%d   (MAX ×%d)' % (r['best_combo'], r['max_mult'])),
                ('ENEMIES DESTROYED', '%d%%' % int(r['kill_pct'])),
                ('BULLETS GRAZED', '%d' % r['grazes']),
                ('PARTS COLLECTED', '%d' % r['parts']),
                ('DAMAGE TAKEN', '%d' % r['damage'])]
        if r['boss_time']:
            rows.append(('END FIGHT TIME', '%.1fS' % (r['boss_time'] / 60.0)))
        x0 = 40
        for i, (a, b) in enumerate(rows):
            if self.t > 10 + i * 6:
                y = 70 + i * 13
                art.text(screen, a, x0, y, LABEL)
                art.text(screen, b, x0 + 250, y, WHITE if 'NEW' not in b else GOLD, 1, 'r')
        # challenges
        cx = 330
        art.text(screen, 'CHALLENGES', cx, 70, LABEL)
        for i, ch in enumerate(r['challenges']):
            y = 84 + i * 18
            done = r['challenge_done'][i]
            show = self.t > 70 + i * 22
            ic = art.icon('star', GOLD if (done and show) else (60, 60, 90))
            if done and show and self.t < 70 + i * 22 + 12:
                ic = pygame.transform.scale(ic, (ic.get_width() * 2, ic.get_height() * 2))
                screen.blit(ic, (cx - 3, y - 3))
            else:
                screen.blit(ic, (cx, y))
            col = (255, 230, 140) if (done and show) else (130, 130, 160)
            art.text(screen, ch['text'], cx + 14, y, col)
            if show:
                art.text(screen, 'DONE' if done else 'MISSED', cx + 290, y, (140, 255, 160) if done else (150, 80, 90), 1, 'r')
        # credits
        y = 170
        pygame.draw.rect(screen, (14, 12, 30), (40, y, 560, 54))
        pygame.draw.rect(screen, (90, 80, 40), (40, y, 560, 54), 1)
        art.text(screen, 'CREDITS COLLECTED %s   CLEAR BONUS %s   STAR BONUS %s' % (
            fmt(r['run_credits']), fmt(r['clear_bonus']), fmt(r['star_bonus'])), SCREEN_W // 2, y + 8, (200, 200, 220), 1, 'c')
        if r.get('credit_mult', 1.0) != 1.0:
            art.text(screen, 'HULL BONUS ×%.2f' % r['credit_mult'], SCREEN_W // 2, y + 18, (160, 220, 160), 1, 'c')
        art.text(screen, '+' + fmt(self.shown_credits), SCREEN_W // 2, y + 28, GOLD, 2, 'c')
        # unlocks
        y = 234
        for kind, payload in self.unlocks:
            if self.t < 240:
                break
            pygame.draw.rect(screen, (30, 20, 50), (120, y, 400, 30))
            pygame.draw.rect(screen, (255, 200, 90) if (self.t // 10) % 2 else (200, 120, 255), (120, y, 400, 30), 1)
            if kind == 'hull':
                h = shop.HULL_BY_ID[payload]
                hs = art.hull_sprite(payload)
                screen.blit(pygame.transform.scale(hs, (hs.get_width() * 2, hs.get_height() * 2)), (130, y - 2))
                art.text(screen, 'NEW HULL UNLOCKED: ' + h['name'], 180, y + 6, GOLD)
                art.text(screen, h['desc'], 180, y + 17, (200, 220, 255))
            else:
                screen.blit(art.icon('star', GOLD), (132, y + 10))
                art.text(screen, 'STAR REWARD UNLOCKED', 150, y + 6, GOLD)
                art.text(screen, payload, 150, y + 17, (200, 255, 200))
            y += 36
        if self.t > 90 and (self.t // 20) % 2 == 0:
            art.text(screen, 'PRESS ENTER', SCREEN_W // 2, 344, (255, 220, 120), 1, 'c')


# ====================================================================== victory
class VictoryScene:
    LINES = [
        'THE MOTHERSHIP CORE COLLAPSES.',
        '',
        'ACROSS TEN SECTORS THE ARMADA IS BROKEN.',
        'EARTH ORBIT IS QUIET AGAIN.',
        '',
        'YOUR SHIP LIMPS HOME, SCORCHED AND',
        'BRISTLING WITH SALVAGED GUNS.',
        '',
        'THE SOVEREIGN HULL IS YOURS.',
        'EVERY LEVEL STAYS OPEN FOR STARS AND SCORES.',
        '',
        '',
        'VOID VANGUARD',
        'ALL GRAPHICS AND SOUND GENERATED IN CODE',
        '',
        'THANKS FOR PLAYING!',
    ]

    def __init__(self, app):
        self.app = app
        self.t = 0
        self.bg = Backdrop(9)
        self.app.audio.play_music('title')
        self.app.audio.set_intensity(3)

    def update(self):
        self.t += 1
        self.bg.update(1.2)
        inp = self.app.input
        if inp.confirm and self.t > 120:
            self.app.goto_hangar()

    def draw(self, screen):
        self.bg.draw(screen, 150)
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 10, 150))
        screen.blit(shade, (0, 0))
        y0 = SCREEN_H - self.t * 0.45
        for i, line in enumerate(self.LINES):
            y = y0 + i * 16
            if -10 < y < SCREEN_H:
                col = GOLD if line in ('VOID VANGUARD', 'THANKS FOR PLAYING!') else WHITE
                art.text(screen, line, SCREEN_W // 2, int(y), col, 1, 'c')
        if y0 + len(self.LINES) * 16 < SCREEN_H * 0.6:
            t = art.big_text('VICTORY', 4, (255, 250, 200), (255, 150, 40), (20, 8, 30), (90, 20, 70))
            screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 60))
        if self.t > 120 and (self.t // 25) % 2 == 0:
            art.text(screen, 'PRESS ENTER', SCREEN_W // 2, 344, (255, 220, 120), 1, 'c')
