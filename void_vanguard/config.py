"""Global constants: screen layout, player tuning and shared colors.

Level and difficulty numbers live in level_data.py. Shop prices live in shop.py.
"""

TITLE = "VOID VANGUARD"
VERSION = "1.0"

# Internal canvas. The window scales this up with crisp nearest-neighbour pixels.
SCREEN_W, SCREEN_H = 640, 360
PF_W, PF_H = 270, 360                 # playfield (centre column)
PF_X = (SCREEN_W - PF_W) // 2         # left edge of the playfield on screen
PANEL_W = PF_X                        # width of each side panel
FPS = 60

SAMPLE_RATE = 22050
SAVE_NAME = "savegame.json"

# ---------------------------------------------------------------- player tuning
PLAYER_BASE_SPEED = 2.35        # pixels per frame before upgrades
PLAYER_SPEED_PER_LEVEL = 0.12   # added per speed upgrade
PLAYER_HITBOX = 2.2             # radius of the tiny core that actually gets hit
PLAYER_GRAZE = 13               # radius that counts as a graze
INVULN_FRAMES = 90              # mercy invulnerability after a hit
BASE_FIRE_INTERVAL = 7          # frames between main cannon volleys
MIN_FIRE_INTERVAL = 3
BOMB_INVULN = 120
GRAZE_PER_BOMB = 80             # grazes needed to earn a bonus bomb
MAX_BOMBS = 9
MAX_SHIELD = 4

# Combo multiplier tiers: kills needed to reach x1, x2, ... x8
COMBO_TIERS = [0, 5, 12, 22, 35, 52, 75, 105]
COMBO_WINDOW = 130              # frames you have to get the next kill
GRAZE_COMBO_BONUS = 18          # frames a graze adds to the combo timer

# ---------------------------------------------------------------- colours
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
INK = (12, 10, 24)
DARK = (24, 22, 44)
GREY = (120, 124, 150)
LIGHT = (200, 206, 230)
RED = (255, 64, 72)
ORANGE = (255, 150, 40)
YELLOW = (255, 226, 70)
GREEN = (90, 230, 110)
CYAN = (70, 220, 255)
BLUE = (70, 120, 255)
PURPLE = (170, 90, 255)
PINK = (255, 90, 190)
GOLD = (255, 200, 40)
