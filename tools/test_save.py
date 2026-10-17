"""Save-file robustness tests. Run: python tools/test_save.py"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'void_vanguard'))
d = tempfile.mkdtemp()
path = os.path.join(d, 'savegame.json')
os.environ['VV_SAVE_PATH'] = path

import save  # noqa: E402
import shop  # noqa: E402


def write_raw(text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        check.failed = True


check.failed = False

# 1. missing file
if os.path.exists(path):
    os.remove(path)
data, existed = save.load()
check('missing file -> fresh save', not existed and data == save.default_save())

# 2. empty, garbage, truncated, wrong root type
for label, text in (('empty file', ''), ('garbage', 'not json at all {{{'), ('truncated', '{"credits": 50, "upgr'),
                    ('array root', '[1, 2, 3]'), ('null', 'null'), ('binary', '\x00\x01\x02')):
    write_raw(text)
    data, existed = save.load()
    check(label + ' -> fresh save, no crash', not existed and data['credits'] == 0)
    check(label + ' -> broken file kept aside', os.path.exists(os.path.join(d, 'savegame.broken.json')))

# 3. wrong types / out of range values are repaired, good values kept
raw = dict(started=True, credits='lots', level_unlocked=999, selected=-5,
           upgrades={'hull': 99, 'damage': '3', 'rate': None, 'speed': 2.7, 'bogus': 5},
           hulls='falcon', hull='spaceship', stars={'1': 7, 'abc': 3, '500': 1, '2': 'x'},
           best={'1': 12345}, deaths=[], muted='yes')
write_raw(json.dumps(raw))
data, existed = save.load()
check('wrong types -> loads', existed)
check('credits repaired', data['credits'] == 0)
check('level clamped', data['level_unlocked'] == 100 and data['selected'] == 1)
check('upgrades clamped', data['upgrades']['hull'] == 7 and data['upgrades']['damage'] == 3
      and data['upgrades']['rate'] == 0 and data['upgrades']['speed'] == 2 and 'bogus' not in data['upgrades'])
check('bad hull -> falcon', data['hull'] == 'falcon' and data['hulls'] == ['falcon'])
check('stars filtered', data['stars'] == {'1': 7})
check('best kept', data['best'] == {'1': 12345})
check('stats computable', shop.compute_stats(data)['hp'] == 10)

# 4. partial save (old/missing keys) fills in defaults
write_raw(json.dumps({'started': True, 'credits': 777}))
data, existed = save.load()
check('partial save keeps credits', existed and data['credits'] == 777 and data['upgrades']['hull'] == 0)

# 5. atomic write round trip, no temp file left behind
data['credits'] = 4242
check('write ok', save.write(data))
data2, existed = save.load()
check('round trip', existed and data2['credits'] == 4242)
check('no temp file left', not os.path.exists(path + '.tmp'))

# 6. adaptive shield rule lives in main.App.start_level: 3 deaths -> +1, 6 -> +2
st0 = shop.compute_stats(data, 0)
st1 = shop.compute_stats(data, 1)
check('extra shield applied', st1['shield'] == st0['shield'] + 1)

print('ALL SAVE TESTS PASSED' if not check.failed else 'SOME SAVE TESTS FAILED')
sys.exit(1 if check.failed else 0)
