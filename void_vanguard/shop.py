"""Hangar shop: permanent upgrades, ship hulls and star unlocks.

Prices: cost of the next level = BASE * GROWTH ^ (current level), times COST_SCALE.
"""
from config import PLAYER_BASE_SPEED, PLAYER_SPEED_PER_LEVEL, PLAYER_HITBOX, PLAYER_GRAZE

COST_SCALE = 1.0

UPGRADES = [
    dict(id='hull', name='HULL STRENGTH', max=7, base=120, growth=1.62, desc='+1 HULL POINT'),
    dict(id='damage', name='WEAPON DAMAGE', max=10, base=110, growth=1.52, desc='+11% DAMAGE'),
    dict(id='rate', name='FIRE RATE', max=8, base=140, growth=1.6, desc='SHOOT 6% FASTER'),
    dict(id='speed', name='ENGINE SPEED', max=6, base=90, growth=1.6, desc='FLY FASTER'),
    dict(id='bombs', name='STARTING BOMBS', max=4, base=180, growth=1.9, desc='+1 BOMB EACH LEVEL'),
    dict(id='magnet', name='MAGNET RANGE', max=6, base=80, growth=1.6, desc='PULL CREDITS FROM FURTHER'),
    dict(id='drones', name='DRONE SLOTS', max=3, base=450, growth=2.6, desc='HOLD +1 HELPER DRONE'),
]
UPGRADE_BY_ID = {u['id']: u for u in UPGRADES}

# unlock = number of the sector boss that unlocks the hull (0 = owned from the start)
HULLS = [
    dict(id='falcon', name='FALCON', unlock=0, hp=0, speed=1.0, dmg=1.0, rate=1.0, magnet=1.0,
         desc='BALANCED ALL-ROUNDER'),
    dict(id='bulwark', name='BULWARK', unlock=1, hp=2, speed=0.88, dmg=1.0, rate=1.05, magnet=1.0,
         start={'shield': 1}, desc='+2 HULL, STARTS SHIELDED, SLOW'),
    dict(id='prospector', name='PROSPECTOR', unlock=2, hp=0, speed=1.0, dmg=0.95, rate=1.0, magnet=1.7,
         credit_mult=1.15, desc='HUGE MAGNET, +15% CREDITS'),
    dict(id='wraith', name='WRAITH', unlock=3, hp=-1, speed=1.15, dmg=1.05, rate=1.0, magnet=1.0,
         hitbox=1.4, graze=18, desc='TINY CORE, BIG GRAZE, FRAGILE'),
    dict(id='prism', name='PRISM', unlock=4, hp=0, speed=1.0, dmg=1.0, rate=1.0, magnet=1.0,
         start={'laser': 1}, desc='STARTS WITH A LASER'),
    dict(id='helios', name='HELIOS', unlock=5, hp=0, speed=1.0, dmg=0.95, rate=0.82, magnet=1.0,
         flare_resist=True, desc='RAPID FIRE, FLARE PROOF'),
    dict(id='breacher', name='BREACHER', unlock=6, hp=1, speed=0.92, dmg=1.0, rate=1.0, magnet=1.0,
         start={'wing': 1, 'rear': 1}, desc='STARTS WITH WING AND REAR GUNS'),
    dict(id='singularity', name='SINGULARITY', unlock=7, hp=0, speed=1.0, dmg=1.0, rate=1.0, magnet=1.2,
         start={'missile': 1}, gravity_resist=0.25, desc='MISSILES, IGNORES MOST GRAVITY'),
    dict(id='swarmlord', name='SWARMLORD', unlock=8, hp=0, speed=1.02, dmg=0.95, rate=1.0, magnet=1.0,
         drone_slots=1, start={'drone': 1}, desc='+1 DRONE SLOT, STARTS WITH ONE'),
    dict(id='phase', name='PHASE', unlock=9, hp=0, speed=1.08, dmg=1.0, rate=1.0, magnet=1.0,
         bomb_regen=35 * 60, desc='BOMBS RECHARGE EVERY 35S'),
    dict(id='sovereign', name='SOVEREIGN', unlock=10, hp=1, speed=1.05, dmg=1.15, rate=0.9, magnet=1.2,
         start={'spread': 3}, desc='ELITE: SPREAD 3 FROM THE START'),
    dict(id='starborn', name='STARBORN', unlock='stars', hp=1, speed=1.1, dmg=1.1, rate=0.92, magnet=1.4,
         start={'drone': 1, 'wing': 1}, graze=16, desc='STAR REWARD: DRONE + WING GUNS'),
]
HULL_BY_ID = {h['id']: h for h in HULLS}

STAR_UNLOCKS = [
    (10, 'spread2', 'START WITH SPREAD LV2'),
    (25, 'radar', 'GOLDEN RADAR: MORE GOLD SHIPS'),
    (40, 'drone', 'START WITH A HELPER DRONE'),
    (60, 'bombcap', '+1 BOMB AT THE START'),
    (80, 'partmagnet', 'YOUR MAGNET PULLS PARTS TOO'),
    (100, 'wing', 'START WITH WING GUNS'),
    (130, 'keeper', 'CHAIN KEEPER: 1ST HIT HALVES IT'),
    (160, 'overdrive', 'OVERDRIVE LASTS 50% LONGER'),
    (200, 'starborn', 'UNLOCKS THE STARBORN HULL'),
    (250, 'spread3', 'START WITH SPREAD LV3'),
    (300, 'gold', 'GOLD PAINT FOR EVERY HULL'),
]


def cost(up_id, level):
    u = UPGRADE_BY_ID[up_id]
    if level >= u['max']:
        return None
    c = u['base'] * (u['growth'] ** level) * COST_SCALE
    return int(round(c / 10.0)) * 10


def total_stars(save):
    return sum(bin(v).count('1') for v in save['stars'].values())


def owned_star_unlocks(save):
    n = total_stars(save)
    return {key for need, key, _ in STAR_UNLOCKS if n >= need}


def hull_unlocked(save, hull_id):
    h = HULL_BY_ID[hull_id]
    if h['unlock'] == 'stars':
        return 'starborn' in owned_star_unlocks(save)
    return hull_id in save['hulls']


def compute_stats(save, extra_shield=0):
    hull = HULL_BY_ID.get(save['hull'], HULLS[0])
    up = save['upgrades']
    stars = owned_star_unlocks(save)
    start = dict(hull.get('start', {}))
    if 'spread3' in stars:
        start['spread'] = max(start.get('spread', 1), 3)
    elif 'spread2' in stars:
        start['spread'] = max(start.get('spread', 1), 2)
    if 'drone' in stars:
        start['drone'] = max(start.get('drone', 0), 1)
    if 'wing' in stars:
        start['wing'] = max(start.get('wing', 0), 1)
    stats = dict(
        hull=hull['id'],
        paint='gold' if 'gold' in stars else None,
        hp=max(1, 3 + up['hull'] + hull.get('hp', 0)),
        speed=(PLAYER_BASE_SPEED + PLAYER_SPEED_PER_LEVEL * up['speed']) * hull.get('speed', 1.0),
        dmg=(1.0 + 0.11 * up['damage']) * hull.get('dmg', 1.0),
        rate=(1.0 - 0.06 * up['rate']) * hull.get('rate', 1.0),
        bombs=1 + up['bombs'] + (1 if 'bombcap' in stars else 0),
        magnet=(34 + 13 * up['magnet']) * hull.get('magnet', 1.0),
        drone_slots=1 + up['drones'] + hull.get('drone_slots', 0),
        hitbox=hull.get('hitbox', PLAYER_HITBOX),
        graze=hull.get('graze', PLAYER_GRAZE),
        shield=start.pop('shield', 0) + extra_shield,
        start=start,
        credit_mult=hull.get('credit_mult', 1.0),
        flare_resist=hull.get('flare_resist', False),
        gravity_resist=hull.get('gravity_resist', 1.0),
        bomb_regen=hull.get('bomb_regen', 0),
        overdrive_mult=1.5 if 'overdrive' in stars else 1.0,
    )
    return stats


def game_flags(save):
    stars = owned_star_unlocks(save)
    return dict(golden_radar='radar' in stars, part_magnet='partmagnet' in stars, combo_keeper='keeper' in stars)


def default_stats():
    import save as S
    return compute_stats(S.default_save())
