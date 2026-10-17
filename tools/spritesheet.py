"""Dump a zoomed sheet of every generated sprite to a PNG (for checking the art).

Usage: python tools/spritesheet.py out.png
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'void_vanguard'))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((640, 360))

import art  # noqa: E402


def main(out):
    sheet = pygame.Surface((640, 480))
    sheet.fill((30, 30, 50))
    x, y = 4, 4
    rowh = 0

    def put(s, label=None):
        nonlocal x, y, rowh
        if x + s.get_width() > 636:
            x = 4
            y += rowh + 10
            rowh = 0
        sheet.blit(s, (x, y))
        if label:
            art.text(sheet, label[:6], x, y + s.get_height() + 1, (180, 180, 200))
        x += max(s.get_width(), 30) + 6
        rowh = max(rowh, s.get_height() + 8)

    for h in art.HULL_ART:
        put(art.hull_sprite(h), h)
    put(art.hull_sprite('falcon', 'gold'), 'gold')
    x = 640
    for p in art.PART_ROWS:
        put(art.part_sprite(p), p)
    put(art.drone_sprite(), 'drone')
    x = 640
    for sec in (1, 3, 5, 8):
        for k in art.ENEMY_ROWS:
            put(art.enemy_sprite(k, sec), k)
        x = 640
    put(art.enemy_sprite('nest', 8), 'nest')
    for sz in (4, 7, 11, 16):
        put(art.asteroid_sprite(sz, 3, ore=sz > 6), 'rock')
    put(art.crystal_sprite(14, 30, 2), 'cryst')
    put(art.debris_sprite(22, 14, 5), 'debr')
    x = 640
    for k in art.PICKUP_STYLE:
        put(art.pickup_sprite(k, 1), k)
    for k in ('small', 'big', 'gem', 'ore'):
        put(art.coin_sprite(k), k)
    x = 640
    for r, c in ((2, (255, 90, 160)), (3, (255, 150, 60)), (5, (120, 255, 255)), (8, (255, 240, 120))):
        put(art.orb(r, c))
    put(art.needle(10, (255, 80, 220)))
    for k in ('main', 'main_big', 'spread', 'wing', 'rear', 'drone', 'missile'):
        put(art.player_shot(k))
    for k in art.ICON_ROWS:
        put(art.icon(k, (255, 90, 110)))
    put(art.big_text('VOID', 3, (255, 240, 140), (255, 90, 40), outline2=(80, 20, 60)))
    put(art.text_surface('THE QUICK BROWN FOX 0123456789 ×8 +-%!?'))
    big = pygame.transform.scale(sheet, (sheet.get_width() * 3, sheet.get_height() * 3))
    pygame.image.save(big, out)
    print('saved', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'sheet.png')
