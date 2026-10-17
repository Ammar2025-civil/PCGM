"""LEVEL DATA - edit the numbers in this file to tweak the game.

Everything here is plain Python numbers, strings, lists and dicts.
Save the file and run main.py again to see your changes.
(If you packaged an .exe, rebuild it after editing.)

Levels are numbered 1..100. Sector = 10 levels.
Every level is generated from this data with a fixed random seed, so the same
level always plays the same way.
"""

# ============================================================== level length
INTRO_SECONDS = 4          # title card + challenges before enemies arrive
WAVE_SECONDS = 120         # length of the enemy-wave section (about 2 minutes)
ACTS = 4                   # tense / relax cycles inside the wave section
BREATHER_SECONDS = 6       # calm gap after each act
WARNING_SECONDS = 3        # the boss WARNING siren

# How long an end fight should last if you have the expected firepower.
# Boss hit points are calculated from this, so it keeps fights fair at every level.
END_FIGHT_SECONDS = {
    'frigate': 38,
    'miniboss': 52,
    'boss': 68,
}

# ============================================================== difficulty curve
# (value at level 1, value at level 100, curve shape)
# curve 1.0 = straight line, above 1.0 = gentle start then steeper, below 1.0 = the opposite
DIFFICULTY = {
    'enemy_hp':     (1.0, 4.6, 1.0),    # multiplies enemy health (boss health comes from END_FIGHT_SECONDS)
    'bullet_speed': (1.0, 1.6, 0.9),     # enemy bullet speed
    'fire_rate':    (0.7, 2.0, 0.95),    # how often enemies shoot
    'density':      (0.8, 1.9, 0.9),     # how many enemies per wave
    'aggression':   (0.0, 1.0, 1.0),     # extra bullets in enemy patterns
    'credits':      (1.0, 9.0, 1.15),    # credit value of everything that drops
}

# Inside one level, each act gets a bit harder. The last act is the "big wave".
ACT_INTENSITY = [0.8, 0.95, 1.05, 1.3]

# ============================================================== enemies
# Level where each enemy type first appears anywhere in the game.
ENEMY_UNLOCK = {
    'dart': 1, 'gunner': 1, 'weaver': 2, 'kamikaze': 4, 'heavy': 6,
    'splitter': 13, 'sniper': 24, 'shielded': 34, 'minelayer': 44, 'turret': 51,
}

# Base number of enemies per wave pattern (multiplied by density and act intensity)
PATTERN_COUNT = {
    'v': 5, 'line': 5, 'column': 5, 'swoop': 7, 'pincer': 6, 'circle': 6, 'snake': 7,
    'wall': 7, 'ambush': 3, 'hover': 2, 'rush': 5, 'rain': 7, 'sine': 5, 'nests': 2, 'turrets': 3,
}
# Roughly how many frames (60 = 1 second) a pattern keeps you busy before the next wave
PATTERN_GAP = {
    'v': 150, 'line': 170, 'column': 140, 'swoop': 260, 'pincer': 200, 'circle': 220, 'snake': 200,
    'wall': 170, 'ambush': 150, 'hover': 260, 'rush': 170, 'rain': 170, 'sine': 170, 'nests': 240,
    'turrets': 200,
}
# Which enemy types fit which patterns
PATTERN_KINDS = {
    'v': ['dart', 'gunner', 'weaver'],
    'line': ['gunner', 'weaver', 'splitter', 'shielded', 'minelayer'],
    'column': ['dart', 'gunner', 'splitter'],
    'swoop': ['dart', 'gunner', 'weaver', 'shielded'],
    'pincer': ['dart', 'gunner', 'weaver'],
    'circle': ['dart', 'weaver', 'gunner'],
    'snake': ['dart', 'weaver'],
    'wall': ['weaver', 'gunner', 'dart'],
    'ambush': ['dart', 'gunner', 'weaver'],
    'hover': ['heavy', 'sniper', 'minelayer', 'shielded'],
    'rush': ['kamikaze'],
    'rain': ['dart', 'kamikaze', 'splitter'],
    'sine': ['weaver', 'gunner', 'sniper'],
    'nests': ['nest'],
    'turrets': ['turret'],
}
PATTERN_UNLOCK = {'ambush': 8, 'hover': 5, 'rush': 4, 'rain': 3, 'nests': 71, 'turrets': 51}

GOLDEN_CHANCE = 0.4         # chance a level has a golden ship (0..1)
GOLDEN_CHANCE_RADAR = 0.75  # chance once the Golden Radar star unlock is owned

# ============================================================== sectors
# mechanic: the sector's new hazard (stays in the mix later at lower strength)
# intensity: hazard strength for levels 1..10 of the sector (0 = off, 1 = full)
# enemies / patterns: weights (higher = more common)
# tune (optional): multipliers on the difficulty curve for this sector only,
#   e.g. tune=dict(density=0.9, fire_rate=0.9) makes a sector a bit easier;
#   boss_hp multiplies the health of that sector's frigates and bosses
SECTORS = {
    1: dict(
        name='EARTH ORBIT', mechanic='formations',
        intensity=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        enemies={'dart': 3, 'gunner': 2, 'weaver': 2, 'kamikaze': 1, 'heavy': 1},
        patterns={'swoop': 4, 'v': 3, 'line': 2, 'column': 2, 'pincer': 2, 'circle': 2,
                  'snake': 1, 'hover': 1, 'rush': 1, 'ambush': 1},
        miniboss='sentinel', boss='aegis',
    ),
    2: dict(
        name='ASTEROID BELT', mechanic='asteroids',
        intensity=[0.35, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.7],
        enemies={'dart': 2, 'gunner': 2, 'weaver': 2, 'kamikaze': 2, 'heavy': 1, 'splitter': 2},
        patterns={'v': 3, 'swoop': 2, 'rain': 3, 'column': 2, 'line': 2, 'snake': 1, 'hover': 1,
                  'rush': 2, 'ambush': 1, 'pincer': 1},
        miniboss='crusher', boss='grinder',
    ),
    3: dict(
        name='PURPLE NEBULA', mechanic='nebula',
        intensity=[0.35, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.7],
        enemies={'dart': 2, 'gunner': 2, 'weaver': 3, 'kamikaze': 1, 'heavy': 1, 'splitter': 1, 'sniper': 2},
        patterns={'sine': 3, 'snake': 2, 'swoop': 2, 'v': 2, 'hover': 2, 'circle': 2, 'line': 1,
                  'ambush': 1, 'rush': 1},
        miniboss='wisp', boss='leviathan',
    ),
    4: dict(
        name='ICE MOON', mechanic='crystals',
        intensity=[0.35, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.6],
        enemies={'dart': 2, 'gunner': 3, 'weaver': 1, 'heavy': 2, 'splitter': 1, 'sniper': 1, 'shielded': 2,
                 'kamikaze': 1},
        patterns={'line': 3, 'hover': 2, 'swoop': 2, 'v': 2, 'wall': 2, 'column': 1, 'sine': 1,
                  'ambush': 1, 'rush': 1},
        miniboss='glacier', boss='cryo', tune=dict(density=0.95),
    ),
    5: dict(
        name='SOLAR FLARE ZONE', mechanic='flares',
        intensity=[0.35, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.6],
        enemies={'dart': 2, 'gunner': 2, 'weaver': 2, 'kamikaze': 2, 'heavy': 1, 'splitter': 1,
                 'sniper': 1, 'shielded': 1, 'minelayer': 2},
        patterns={'rush': 2, 'v': 2, 'swoop': 2, 'hover': 2, 'line': 2, 'rain': 2, 'pincer': 1,
                  'snake': 1, 'ambush': 1},
        miniboss='moth', boss='seraph',
    ),
    6: dict(
        name='DERELICT STATION', mechanic='station',
        intensity=[0.4, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.5],
        enemies={'dart': 2, 'gunner': 2, 'heavy': 1, 'splitter': 1, 'sniper': 1, 'shielded': 2,
                 'minelayer': 1, 'kamikaze': 1},
        patterns={'column': 3, 'v': 2, 'line': 2, 'hover': 2, 'turrets': 2, 'snake': 1, 'ambush': 1,
                  'rush': 1},
        miniboss='secdrone', boss='warden', tune=dict(density=0.9, fire_rate=1.0),
    ),
    7: dict(
        name='BLACK HOLE RIM', mechanic='gravity',
        intensity=[0.35, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.6],
        enemies={'dart': 2, 'gunner': 2, 'weaver': 2, 'kamikaze': 1, 'heavy': 1, 'splitter': 1,
                 'sniper': 2, 'shielded': 1, 'minelayer': 1},
        patterns={'circle': 3, 'swoop': 2, 'sine': 2, 'snake': 2, 'hover': 2, 'v': 1, 'line': 1,
                  'ambush': 1, 'rush': 1},
        miniboss='graviton', boss='horizon', tune=dict(density=1.35, fire_rate=1.45, boss_hp=1.35),
    ),
    8: dict(
        name='ALIEN HIVE', mechanic='hive',
        intensity=[0.4, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.6],
        enemies={'dart': 1, 'gunner': 1, 'weaver': 2, 'kamikaze': 3, 'heavy': 1, 'splitter': 2,
                 'sniper': 1, 'shielded': 1, 'minelayer': 1},
        patterns={'nests': 3, 'rush': 2, 'rain': 2, 'swoop': 2, 'snake': 2, 'v': 1, 'hover': 1,
                  'ambush': 1, 'pincer': 1},
        miniboss='brood', boss='queen', tune=dict(density=1.2, fire_rate=1.35, boss_hp=1.45),
    ),
    9: dict(
        name='WORMHOLE', mechanic='wormhole',
        intensity=[0.4, 0.45, 0.55, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9, 0.6],
        enemies={'dart': 2, 'gunner': 2, 'weaver': 2, 'kamikaze': 2, 'heavy': 1, 'splitter': 1,
                 'sniper': 1, 'shielded': 1, 'minelayer': 1},
        patterns={'snake': 2, 'swoop': 2, 'v': 2, 'circle': 2, 'sine': 2, 'rush': 2, 'hover': 1,
                  'ambush': 1, 'pincer': 1, 'line': 1},
        miniboss='stalker', boss='phantom', tune=dict(density=1.1, fire_rate=1.2),
    ),
    10: dict(
        name='MOTHERSHIP CORE', mechanic='remix',
        intensity=[0.5, 0.55, 0.6, 0.65, 0.7, 0.7, 0.75, 0.8, 0.85, 0.5],
        enemies={'dart': 2, 'gunner': 2, 'weaver': 2, 'kamikaze': 2, 'heavy': 2, 'splitter': 2,
                 'sniper': 2, 'shielded': 2, 'minelayer': 2},
        patterns={'swoop': 2, 'v': 2, 'line': 2, 'hover': 2, 'snake': 2, 'circle': 1, 'rush': 2,
                  'ambush': 2, 'pincer': 2, 'turrets': 1, 'nests': 1, 'sine': 1},
        miniboss='guardian', boss='mothership',
    ),
}

# Earlier mechanics come back at this strength in later sectors ("stays in the mix").
ECHO_INTENSITY = 0.35

# ============================================================== per-level overrides
# Any level can be hand-tuned here. Keys you can use:
#   density, enemy_hp, bullet_speed, fire_rate, aggression, boss_hp  (multipliers)
#   acts (number of acts), golden (True / False), intensity (hazard strength 0..1)
LEVEL_OVERRIDES = {
    1: dict(density=0.6, fire_rate=0.6, acts=3, golden=True),
    2: dict(density=0.8, fire_rate=0.8),
    3: dict(density=0.9),
    # bosses with many or wide hit zones go down faster than the rest
    10: dict(boss_hp=1.5),
    15: dict(boss_hp=1.3),
    25: dict(boss_hp=1.3),
    30: dict(boss_hp=2.0),
    60: dict(boss_hp=1.4),
}
