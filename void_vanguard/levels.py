"""Builds the timeline for any of the 100 levels from level_data.py."""
import random

import level_data as D

FPS = 60
SECTOR_MECH = {2: 'asteroids', 3: 'nebula', 4: 'crystals', 5: 'flares', 6: 'station',
               7: 'gravity', 8: 'hive', 9: 'wormhole'}
HAZARD_MECHS = list(SECTOR_MECH.values())
MECH_LABEL = {
    'formations': 'ENEMY FORMATIONS', 'asteroids': 'ASTEROIDS DROP ORE', 'nebula': 'FOG AND LIGHTNING',
    'crystals': 'CRYSTALS BOUNCE BULLETS', 'flares': 'HIDE FROM SOLAR FLARES', 'station': 'CORRIDORS AND LASER GATES',
    'gravity': 'GRAVITY PULL', 'hive': 'DESTROY THE NESTS', 'wormhole': 'WARP SURGES', 'remix': 'EVERYTHING AT ONCE',
}


def curve(name, level):
    a, b, c = D.DIFFICULTY[name]
    t = ((max(1, min(100, level)) - 1) / 99.0) ** c
    return a + (b - a) * t


def sector_of(level):
    return (level - 1) // 10 + 1


def index_in_sector(level):
    return (level - 1) % 10 + 1


def end_kind(level):
    if level % 10 == 0:
        return 'boss'
    if level % 5 == 0:
        return 'miniboss'
    return 'frigate'


def level_name(level):
    return '%d-%d' % (sector_of(level), index_in_sector(level))


# How much stronger shop upgrades make a typical player by each level
# (measured with tools/balance_run.py + tools/fit_costs.py).
UPGRADE_POWER = [(1, 1.0), (10, 1.5), (25, 2.0), (50, 2.6), (75, 3.2), (100, 3.6)]


def upgrade_power(level):
    pts = UPGRADE_POWER
    for (l0, v0), (l1, v1) in zip(pts, pts[1:]):
        if level <= l1:
            return v0 + (v1 - v0) * (level - l0) / float(l1 - l0)
    return pts[-1][1]


def expected_dps(level):
    """Firepower an end fight is balanced around: typical shop upgrades for this
    point in the game plus a mid-level pickup loadout."""
    base = 22.0 + 16.0 * min(1.0, level / 60.0) + 22.0 * max(0.0, (level - 60) / 40.0)
    return base * upgrade_power(level)


def _weighted(rnd, items):
    total = sum(w for _, w in items)
    r = rnd.uniform(0, total)
    for k, w in items:
        r -= w
        if r <= 0:
            return k
    return items[-1][0]


class Plan:
    pass


CHALLENGES = {
    'nodamage': 'TAKE NO DAMAGE',
    'kills': 'DESTROY %d%% OF ENEMIES',
    'combo': 'REACH A %d CHAIN',
    'graze': 'GRAZE %d BULLETS',
    'bosstime': 'BEAT THE %s IN %dS',
    'nobomb': 'USE NO BOMBS',
    'parts': 'COLLECT %d PARTS',
    'golden': 'CATCH THE GOLDEN SHIP',
}


def make_challenges(level, rnd, has_golden):
    kind = end_kind(level)
    out = []
    a = rnd.choice(['nodamage', 'kills', 'kills'])
    b = rnd.choice(['combo', 'graze', 'bosstime'])
    c_pool = ['nobomb', 'parts']
    if has_golden:
        c_pool += ['golden', 'golden']
    c = rnd.choice(c_pool)
    for cid in (a, b, c):
        if cid == 'kills':
            target = 90 if level <= 10 else 95
            out.append(dict(id=cid, target=target, text=CHALLENGES[cid] % target))
        elif cid == 'combo':
            target = int(15 + level * 0.85)
            out.append(dict(id=cid, target=target, text=CHALLENGES[cid] % target))
        elif cid == 'graze':
            target = int(12 + level * 1.1)
            out.append(dict(id=cid, target=target, text=CHALLENGES[cid] % target))
        elif cid == 'bosstime':
            target = int(D.END_FIGHT_SECONDS[kind] * 0.9)
            name = {'boss': 'BOSS', 'miniboss': 'MINI-BOSS', 'frigate': 'FRIGATE'}[kind]
            out.append(dict(id=cid, target=target, text=CHALLENGES[cid] % (name, target)))
        elif cid == 'parts':
            target = 4 + level // 25
            out.append(dict(id=cid, target=target, text=CHALLENGES[cid] % target))
        else:
            out.append(dict(id=cid, target=1, text=CHALLENGES[cid]))
    return out


def build(level, golden_radar=False):
    level = max(1, min(100, level))
    rnd = random.Random(level * 7919 + 13)
    s = sector_of(level)
    k = index_in_sector(level)
    sec = D.SECTORS[s]
    ov = D.LEVEL_OVERRIDES.get(level, {})
    tune = sec.get('tune', {})
    diff = {n: curve(n, level) * ov.get(n, 1.0) * tune.get(n, 1.0) for n in D.DIFFICULTY}
    boss_hp = tune.get('boss_hp', 1.0) * ov.get('boss_hp', 1.0)

    # ---------------------------------------------------- hazards
    hazards = {}
    mech = sec['mechanic']
    inten = ov.get('intensity', sec['intensity'][k - 1])
    if mech in HAZARD_MECHS and inten > 0:
        hazards[mech] = inten
    earlier = [SECTOR_MECH[i] for i in range(2, min(s, 10))]
    if mech == 'remix':
        pick = rnd.sample(HAZARD_MECHS, 3 if k < 6 else 4)
        if 'station' in pick and 'crystals' in pick:
            pick.remove('crystals')
        for m in pick:
            hazards[m] = round(inten * rnd.uniform(0.75, 1.0), 2)
    elif earlier:
        n_echo = 0 if k < 3 else (1 if k < 7 else 2)
        for m in rnd.sample(earlier, min(n_echo, len(earlier))):
            if m == 'station' and 'crystals' in hazards:
                continue
            hazards[m] = D.ECHO_INTENSITY

    # ---------------------------------------------------- waves
    acts = ov.get('acts', D.ACTS)
    intro = D.INTRO_SECONDS * FPS
    breather = D.BREATHER_SECONDS * FPS
    act_len = int((D.WAVE_SECONDS * FPS - acts * breather) / acts)
    if acts < D.ACTS:
        act_len = int(act_len * 0.9)
    unlocked = {kk: w for kk, w in sec['enemies'].items() if D.ENEMY_UNLOCK.get(kk, 1) <= level}
    patterns = [(p, w) for p, w in sec['patterns'].items() if D.PATTERN_UNLOCK.get(p, 1) <= level]
    if 'station' not in hazards:
        patterns = [(p, w) for p, w in patterns if p != 'turrets']
    if 'hive' not in hazards:
        patterns = [(p, w) for p, w in patterns if p != 'nests']
    elif mech != 'hive':
        patterns.append(('nests', 1))

    intensities = D.ACT_INTENSITY[-acts:]
    events = []
    t = intro
    for a in range(acts):
        ai = intensities[a]
        events.append((t, 'act', dict(index=a, big=(a == acts - 1), length=act_len)))
        end = t + act_len
        tt = t + 30
        last = None
        while tt < end - 100:
            pat = _weighted(rnd, patterns)
            if pat == last and len(patterns) > 1:
                pat = _weighted(rnd, patterns)
            last = pat
            if pat in ('nests', 'turrets'):
                kind = 'nest' if pat == 'nests' else 'turret'
            else:
                kinds = [(kk, unlocked[kk]) for kk in D.PATTERN_KINDS[pat] if kk in unlocked]
                if not kinds:
                    continue
                kind = _weighted(rnd, kinds)
            count = D.PATTERN_COUNT[pat] * diff['density'] * ai * rnd.uniform(0.85, 1.15)
            if pat == 'hover':
                count = min(count, 4)
            elif pat in ('ambush', 'nests'):
                count = min(count, 4 if pat == 'ambush' else 3)
            elif kind == 'heavy':
                count = min(count, 3)
            count = max(1, int(round(count)))
            events.append((tt, 'wave', dict(pattern=pat, kind=kind, count=count,
                                             seed=rnd.randrange(1 << 30), side=rnd.choice((-1, 1)))))
            gap = D.PATTERN_GAP[pat] / (0.72 + 0.28 * diff['density'] * ai)
            tt += int(gap * rnd.uniform(0.85, 1.1))
        events.append((t + int(act_len * rnd.uniform(0.3, 0.7)), 'wave',
                       dict(pattern='single', kind='carrier', count=1, seed=rnd.randrange(1 << 30))))
        t = end
        events.append((t, 'breather', dict(frames=breather)))
        t += breather
    wave_end = t
    events.append((t, 'end', None))

    chance = D.GOLDEN_CHANCE_RADAR if golden_radar else D.GOLDEN_CHANCE
    has_golden = ov.get('golden', rnd.random() < chance)
    if has_golden:
        gt = intro + int((act_len + breather) * rnd.uniform(1.15, max(1.2, acts - 1.4)))
        events.append((gt, 'golden', None))
    events.sort(key=lambda e: e[0])

    p = Plan()
    p.level = level
    p.sector = s
    p.index = k
    p.name = level_name(level)
    p.sector_name = sec['name']
    p.mechanic = mech
    p.mechanic_label = MECH_LABEL.get(mech, '')
    p.diff = diff
    p.hazards = hazards
    p.events = events
    p.wave_end = wave_end
    p.intro = intro
    p.end_kind = end_kind(level)
    p.boss_id = sec['boss'] if p.end_kind == 'boss' else sec['miniboss'] if p.end_kind == 'miniboss' else 'frigate'
    p.has_golden = has_golden
    p.challenges = make_challenges(level, rnd, has_golden)
    p.boss_hp = boss_hp
    p.seed = level * 31 + 7
    return p
