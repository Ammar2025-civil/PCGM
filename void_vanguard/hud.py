"""Side panels, boss health bar, level intro card and menu overlays."""
import pygame

import art
from config import PF_W, PF_X, PANEL_W, SCREEN_W, SCREEN_H, WHITE, GOLD, COMBO_TIERS, COMBO_WINDOW, \
    GRAZE_PER_BOMB

_panel_cache = {}
MULT_COLORS = [(200, 200, 220), (120, 220, 255), (120, 255, 160), (255, 240, 100), (255, 170, 60),
               (255, 90, 90), (255, 90, 220), (255, 255, 255)]
LABEL = (140, 140, 175)


def panel_bg(sector, side):
    key = (sector, side)
    s = _panel_cache.get(key)
    if s is not None:
        return s
    ui = art.SECTOR_STYLE[sector]['ui']
    s = pygame.Surface((PANEL_W, SCREEN_H))
    for y in range(SCREEN_H):
        t = y / SCREEN_H
        s.fill(art.mix((16, 14, 30), (8, 8, 18), t), (0, y, PANEL_W, 1))
    # rivets & grid
    for y in range(0, SCREEN_H, 6):
        for x in range(0, PANEL_W, 6):
            if (x // 6 + y // 6) % 2 == 0:
                s.set_at((x, y), (22, 20, 40))
    edge = PANEL_W - 3 if side == 'l' else 0
    s.fill(art.scale(ui, 0.35), (edge, 0, 3, SCREEN_H))
    s.fill(ui, (edge + (2 if side == 'l' else 0), 0, 1, SCREEN_H))
    _panel_cache[key] = s
    return s


def box(surf, rect, ui, title=None):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, (10, 9, 22), r)
    pygame.draw.rect(surf, art.scale(ui, 0.45), r, 1)
    pygame.draw.line(surf, ui, (r.left + 2, r.top), (r.left + 14, r.top))
    if title:
        art.text(surf, title, r.left + 4, r.top + 3, LABEL)


def bar(surf, x, y, w, h, frac, col, back=(30, 28, 50)):
    surf.fill(back, (x, y, w, h))
    fw = int(w * max(0.0, min(1.0, frac)))
    if fw > 0:
        surf.fill(col, (x, y, fw, h))
        surf.fill(art.mix(col, WHITE, 0.45), (x, y, fw, 1))


def fmt(n):
    return '{:,}'.format(int(n))


def draw_panels(screen, g):
    ui = g.ui_color
    screen.blit(panel_bg(g.sector, 'l'), (0, 0))
    screen.blit(panel_bg(g.sector, 'r'), (PF_X + PF_W, 0))
    p = g.player
    # ------------------------------------------------ left: score / combo / ship status
    x0 = 8
    art.text(screen, 'SCORE', x0, 8, LABEL)
    art.text(screen, fmt(g.score), x0, 18, WHITE, 2)
    best = g.app.best_score(g.level)
    art.text(screen, 'BEST ' + fmt(max(best, g.score)), x0, 36, (110, 110, 150))

    box(screen, (x0 - 2, 50, PANEL_W - 16, 78), ui, 'COMBO')
    m = g.mult
    col = MULT_COLORS[min(m - 1, len(MULT_COLORS) - 1)]
    pulse = 1 if (g.combo_t > COMBO_WINDOW - 8) else 0
    art.text(screen, '×%d' % m, x0 + 4, 64 - pulse, col, 4)
    art.text(screen, '%d CHAIN' % g.combo, x0 + 74, 66, WHITE if g.combo else (90, 90, 120))
    nxt = COMBO_TIERS[m] if m < len(COMBO_TIERS) else None
    art.text(screen, ('NEXT AT %d' % nxt) if nxt else 'MAX', x0 + 74, 78, (110, 110, 150))
    bar(screen, x0 + 4, 100, PANEL_W - 28, 5, g.combo_t / COMBO_WINDOW, col)
    art.text(screen, 'GRAZE %d' % g.stats['grazes'], x0 + 4, 110, (200, 200, 255))
    bar(screen, x0 + 84, 111, PANEL_W - 108, 4, g.graze_meter / GRAZE_PER_BOMB, (255, 120, 120))

    box(screen, (x0 - 2, 134, PANEL_W - 16, 98), ui, 'SHIP')
    art.text(screen, 'HULL', x0 + 4, 150, LABEL)
    for i in range(p.max_hp):
        ic = art.icon('heart', (255, 80, 110) if i < p.hp else (60, 40, 60))
        screen.blit(ic, (x0 + 40 + (i % 10) * 12, 148 + (i // 10) * 10))
    art.text(screen, 'SHIELD', x0 + 4, 172, LABEL)
    shield_n = p.shield if p.overdrive <= 0 else 0
    for i in range(max(shield_n, 1)):
        ic = art.icon('shield', (110, 190, 255) if i < shield_n else (40, 50, 80))
        screen.blit(ic, (x0 + 52 + i * 12, 170))
    if p.overdrive > 0:
        art.text(screen, 'OFF', x0 + 66, 172, (255, 90, 90))
    art.text(screen, 'BOMBS', x0 + 4, 194, LABEL)
    for i in range(p.bombs):
        screen.blit(art.icon('bomb', (255, 120, 90)), (x0 + 46 + i * 11, 192))
    art.text(screen, 'SPACE', x0 + 4, 212, (90, 90, 120))

    y = 240
    for label, t, mx, colr in (('OVERDRIVE', p.overdrive, 1200, (255, 70, 70)), ('BOUNTY', p.bounty, 1200, (200, 110, 255)),
                               ('MAGNET', p.magnet_t, 1500, (255, 220, 60))):
        if t > 0:
            art.text(screen, label, x0, y, colr)
            bar(screen, x0 + 70, y + 1, PANEL_W - 92, 5, t / mx, colr)
            y += 14

    # ------------------------------------------------ right: level / challenges / loadout
    rx = PF_X + PF_W + 10
    rw = PANEL_W - 18
    art.text(screen, 'SECTOR %d' % g.sector, rx, 8, ui)
    art.text(screen, g.plan.sector_name, rx, 18, WHITE)
    art.text(screen, 'LEVEL ' + g.plan.name, rx, 30, LABEL)
    # progress
    total = g.plan.wave_end
    frac = min(1.0, g.wave_frame / max(1, total))
    if g.state not in ('waves',):
        frac = 1.0
    bar(screen, rx, 44, rw - 14, 4, frac, ui)
    for ev in g.plan.events:
        if ev[1] == 'breather':
            screen.fill((60, 60, 90), (rx + int((rw - 14) * ev[0] / total), 42, 1, 8))
    bcol = (255, 70, 70) if g.state in ('warning', 'boss') and (g.frame // 10) % 2 == 0 else (160, 60, 70)
    pygame.draw.rect(screen, bcol, (rx + rw - 10, 41, 9, 9))
    art.text(screen, '!', rx + rw - 7, 42, WHITE, shadow=None)

    box(screen, (rx - 2, 58, rw + 4, 92), ui, 'CHALLENGES')
    for i, ch in enumerate(g.plan.challenges):
        done, failed, prog = g.challenge_status(ch)
        yy = 74 + i * 25
        if done:
            ic = art.icon('star', GOLD)
        elif failed:
            ic = art.icon('star', (70, 40, 50))
        else:
            ic = art.icon('star', (90, 90, 130))
        screen.blit(ic, (rx + 2, yy))
        tcol = (255, 230, 140) if done else ((120, 80, 90) if failed else (210, 210, 230))
        words = ch['text']
        if art.text_width(words) > rw - 16:
            cut = words.rfind(' ', 0, 22)
            art.text(screen, words[:cut], rx + 14, yy, tcol)
            art.text(screen, words[cut + 1:], rx + 14, yy + 9, tcol)
        else:
            art.text(screen, words, rx + 14, yy, tcol)
        if prog and not done and not failed:
            art.text(screen, prog, rx + rw - 2, yy + 9, (130, 130, 170), align='r')
        if failed:
            art.text(screen, 'FAILED', rx + rw - 2, yy + 9, (150, 70, 80), align='r')

    box(screen, (rx - 2, 156, rw + 4, 30), ui, 'RUN CREDITS')
    art.text(screen, fmt(g.run_credits), rx + 4, 170, GOLD, 1)
    art.text(screen, 'BANK ' + fmt(g.app.bank_credits()), rx + rw - 2, 170, (120, 120, 160), align='r')

    box(screen, (rx - 2, 192, rw + 4, 110), ui, 'LOADOUT')
    lo = p.loadout
    rows = [('SPREAD', lo['spread'], 5), ('WING GUNS', lo['wing'], 3), ('MISSILES', lo['missile'], 3),
            ('LASER', lo['laser'], 3), ('REAR GUN', lo['rear'], 3), ('DRONES', len(p.drones), p.drone_slots)]
    for i, (name, lv, mx) in enumerate(rows):
        yy = 207 + i * 15
        art.text(screen, name, rx + 2, yy, WHITE if lv else (80, 80, 110))
        for j in range(mx):
            c = (255, 160, 50) if j < lv else (40, 38, 64)
            screen.fill(c, (rx + 76 + j * 9, yy + 1, 7, 5))
            if j < lv:
                screen.fill((255, 230, 150), (rx + 76 + j * 9, yy + 1, 7, 1))
    art.text(screen, 'P / ESC  PAUSE', rx, 344, (80, 80, 110))
    art.text(screen, 'F11 FULLSCREEN', 8, 344, (80, 80, 110))


def draw_boss_bar(surf, boss):
    x, y, w = 14, 6, PF_W - 28
    art.text(surf, boss.name, PF_W // 2, y, (255, 200, 200), align='c')
    frac = boss.hp_fraction()
    pygame.draw.rect(surf, (10, 8, 20), (x - 1, y + 10, w + 2, 7))
    col = (255, 70, 90) if boss.phase_index < 1 else (255, 140, 40) if boss.phase_index < 2 else (255, 230, 80)
    if boss.invulnerable() and (boss.t // 4) % 2 == 0:
        col = WHITE
    bar(surf, x, y + 11, w, 5, frac, col, (50, 20, 30))
    for th in boss.phase_marks():
        surf.fill(WHITE, (x + int(w * th), y + 10, 1, 7))


def draw_intro_card(surf, g):
    f = g.frame
    end = g.intro_frames + 60
    alpha = 1.0 if f < end - 40 else max(0.0, (end - f) / 40.0)
    if alpha <= 0:
        return
    if f % 2 == 1 and alpha < 1.0:
        return
    ui = g.ui_color
    plan = g.plan
    cy = 64
    t = art.big_text('SECTOR %d' % plan.sector, 2, art.mix(ui, WHITE, 0.6), ui)
    surf.blit(t, (PF_W // 2 - t.get_width() // 2, cy))
    t = art.big_text(plan.sector_name, 2, WHITE, art.mix(ui, WHITE, 0.3))
    surf.blit(t, (PF_W // 2 - t.get_width() // 2, cy + 22))
    art.text(surf, 'LEVEL ' + plan.name, PF_W // 2, cy + 46, (220, 220, 240), align='c')
    if plan.mechanic != 'formations' or plan.level == 1:
        label = plan.mechanic_label if plan.level > 1 else 'ARROWS/WASD MOVE  SPACE BOMB'
        art.text(surf, label, PF_W // 2, cy + 58, (255, 220, 120), align='c')
    pygame.draw.rect(surf, (10, 8, 22), (16, cy + 74, PF_W - 32, 52))
    pygame.draw.rect(surf, art.scale(ui, 0.6), (16, cy + 74, PF_W - 32, 52), 1)
    art.text(surf, 'OPTIONAL CHALLENGES', PF_W // 2, cy + 78, LABEL, align='c')
    for i, ch in enumerate(plan.challenges):
        surf.blit(art.icon('star', GOLD), (24, cy + 90 + i * 11))
        art.text(surf, ch['text'], 36, cy + 90 + i * 11, WHITE)


def draw_menu_overlay(screen, title, options, sel, note=None, color=(255, 220, 120)):
    dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    screen.blit(dim, (0, 0))
    w, h = 240, 50 + len(options) * 18 + (16 if note else 0)
    x, y = SCREEN_W // 2 - w // 2, SCREEN_H // 2 - h // 2
    pygame.draw.rect(screen, (12, 10, 26), (x, y, w, h))
    pygame.draw.rect(screen, color, (x, y, w, h), 1)
    t = art.big_text(title, 2, WHITE, color)
    screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, y + 8))
    for i, o in enumerate(options):
        yy = y + 36 + i * 18
        if i == sel:
            pygame.draw.rect(screen, art.scale(color, 0.35), (x + 20, yy - 3, w - 40, 13))
            art.text(screen, '> ' + o + ' <', SCREEN_W // 2, yy, WHITE, align='c')
        else:
            art.text(screen, o, SCREEN_W // 2, yy, (150, 150, 180), align='c')
    if note:
        art.text(screen, note, SCREEN_W // 2, y + h - 14, (140, 120, 140), align='c')
