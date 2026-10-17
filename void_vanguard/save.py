"""Auto-save. Writes savegame.json next to the game after every level and purchase.

If the file is missing or broken, the game simply starts fresh (a broken file is
kept as savegame.broken.json so nothing is silently destroyed).
"""
import json
import os
import sys

from config import SAVE_NAME

SAVE_VERSION = 1
UP_IDS = ('hull', 'damage', 'rate', 'speed', 'bombs', 'magnet', 'drones')
UP_MAX = {'hull': 8, 'damage': 20, 'rate': 15, 'speed': 8, 'bombs': 4, 'magnet': 8, 'drones': 3}
HULL_IDS = ('falcon', 'bulwark', 'prospector', 'wraith', 'prism', 'helios', 'breacher', 'singularity',
            'swarmlord', 'phase', 'sovereign', 'starborn')


def default_save():
    return dict(
        version=SAVE_VERSION,
        started=False,
        level_unlocked=1,
        selected=1,
        credits=0,
        upgrades={k: 0 for k in UP_IDS},
        hulls=['falcon'],
        hull='falcon',
        stars={},
        best={},
        deaths={},
        muted=False,
        total_kills=0,
        golden=0,
        complete=False,
        seen_unlocks=[],
    )


def game_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _writable(d):
    try:
        test = os.path.join(d, '.vv_write_test')
        with open(test, 'w') as f:
            f.write('ok')
        os.remove(test)
        return True
    except OSError:
        return False


_path = None


def save_path():
    global _path
    if _path is None and os.environ.get('VV_SAVE_PATH'):
        _path = os.environ['VV_SAVE_PATH']
    if _path is None:
        d = game_dir()
        if not _writable(d):
            base = os.environ.get('APPDATA') or os.path.expanduser('~')
            d = os.path.join(base, 'VoidVanguard')
            try:
                os.makedirs(d, exist_ok=True)
            except OSError:
                pass
        _path = os.path.join(d, SAVE_NAME)
    return _path


def _int(v, lo, hi, default):
    try:
        if isinstance(v, bool):
            return default
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _level_map(v, lo, hi):
    out = {}
    if isinstance(v, dict):
        for k, val in v.items():
            lv = _int(k, -10 ** 9, 10 ** 9, None)
            if lv is None or not 1 <= lv <= 100:
                continue
            iv = _int(val, lo, hi, None)
            if iv is not None:
                out[str(lv)] = iv
    return out


def validate(raw):
    """Merge whatever is in the file onto defaults, fixing every field's type and range."""
    d = default_save()
    if not isinstance(raw, dict):
        raise ValueError('save is not an object')
    d['started'] = bool(raw.get('started', False))
    d['level_unlocked'] = _int(raw.get('level_unlocked'), 1, 100, 1)
    d['selected'] = _int(raw.get('selected'), 1, d['level_unlocked'], d['level_unlocked'])
    d['credits'] = _int(raw.get('credits'), 0, 10 ** 12, 0)
    ups = raw.get('upgrades')
    if isinstance(ups, dict):
        for k in UP_IDS:
            d['upgrades'][k] = _int(ups.get(k), 0, UP_MAX[k], 0)
    hulls = raw.get('hulls')
    if isinstance(hulls, list):
        d['hulls'] = [h for h in HULL_IDS if h in hulls] or ['falcon']
    if 'falcon' not in d['hulls']:
        d['hulls'].insert(0, 'falcon')
    hull = raw.get('hull')
    d['hull'] = hull if hull in HULL_IDS else 'falcon'
    d['stars'] = _level_map(raw.get('stars'), 0, 7)
    d['best'] = _level_map(raw.get('best'), 0, 10 ** 12)
    d['deaths'] = _level_map(raw.get('deaths'), 0, 10 ** 6)
    d['muted'] = bool(raw.get('muted', False))
    d['total_kills'] = _int(raw.get('total_kills'), 0, 10 ** 12, 0)
    d['golden'] = _int(raw.get('golden'), 0, 10 ** 9, 0)
    d['complete'] = bool(raw.get('complete', False))
    seen = raw.get('seen_unlocks')
    if isinstance(seen, list):
        d['seen_unlocks'] = [str(s) for s in seen if isinstance(s, str)][:64]
    return d


def load():
    """Returns (save_dict, existed). Never raises."""
    path = save_path()
    if not os.path.exists(path):
        return default_save(), False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        data = validate(raw)
        return data, bool(data['started'])
    except Exception:
        try:
            broken = os.path.join(os.path.dirname(path), 'savegame.broken.json')
            os.replace(path, broken)
        except OSError:
            pass
        return default_save(), False


def write(data):
    """Atomic write: temp file then rename, so a crash never leaves half a save."""
    path = save_path()
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1, sort_keys=True)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False


def delete():
    path = save_path()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
