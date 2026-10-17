"""Chiptune sound: every effect and every song is synthesised here at start-up.

How it stays fast in pure Python: a note is built by repeating one pre-computed
waveform cycle (C-speed array maths) with an NES-style volume envelope that
steps 60 times a second. A whole song renders in a few hundredths of a second.
Songs are split into stems (bass, arpeggio, lead, echo, counter-melody, light
drums, heavy drums). Each stem loops on its own mixer channel, so raising the
music intensity is just fading stems in.
"""
import array
import math
import random
from itertools import zip_longest

import pygame

from config import SAMPLE_RATE

LEVELS = 16
AMP = 5200
STEMS = ('bass', 'arp', 'lead', 'echo', 'counter', 'drums_l', 'drums_h')
# stem volume per intensity level 0..3
MIX = {
    0: dict(bass=0.75, arp=0.55, lead=0.0, echo=0.0, counter=0.35, drums_l=0.45, drums_h=0.0),
    1: dict(bass=0.9, arp=0.7, lead=0.0, echo=0.0, counter=0.45, drums_l=0.8, drums_h=0.0),
    2: dict(bass=1.0, arp=0.55, lead=0.85, echo=0.3, counter=0.0, drums_l=0.0, drums_h=0.85),
    3: dict(bass=1.0, arp=0.7, lead=1.0, echo=0.35, counter=0.6, drums_l=0.0, drums_h=1.0),
}
MUSIC_VOL = 0.55
SFX_VOL = 0.7

SCALES = {
    'minor': [0, 2, 3, 5, 7, 8, 10], 'dorian': [0, 2, 3, 5, 7, 9, 10], 'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'harmonic': [0, 2, 3, 5, 7, 8, 11], 'major': [0, 2, 4, 5, 7, 9, 11], 'mixo': [0, 2, 4, 5, 7, 9, 10],
}

# tempo, root (MIDI), scale, chord progression (scale degrees, 2 bars each), bass style, arp style,
# lead duty, arp duty, lead octave, drum style
SONGS = {
    'title':   dict(bpm=132, root=40, scale='minor', prog=[0, 5, 3, 4], prog_b=[5, 6, 0, 4], bass='drive', arp='updown', duty=0.5, aduty=0.25, oct=0, drums='rock', seed=11),
    'hangar':  dict(bpm=96, root=43, scale='dorian', prog=[0, 3, 0, 4], prog_b=[5, 3, 6, 4], bass='slow', arp='wide', duty=0.25, aduty=0.125, oct=0, drums='half', seed=22),
    1:  dict(bpm=138, root=45, scale='minor', prog=[0, 5, 2, 6], prog_b=[3, 4, 5, 6], bass='drive', arp='up', duty=0.5, aduty=0.25, oct=0, drums='rock', seed=101),
    2:  dict(bpm=128, root=38, scale='dorian', prog=[0, 3, 0, 6], prog_b=[5, 3, 4, 4], bass='bounce', arp='updown', duty=0.25, aduty=0.25, oct=0, drums='shuffle', seed=202),
    3:  dict(bpm=112, root=42, scale='phrygian', prog=[0, 1, 0, 6], prog_b=[5, 1, 3, 1], bass='slow', arp='wide', duty=0.125, aduty=0.125, oct=0, drums='half', seed=303),
    4:  dict(bpm=132, root=47, scale='minor', prog=[0, 6, 5, 4], prog_b=[3, 4, 0, 4], bass='drive', arp='down', duty=0.25, aduty=0.125, oct=0, drums='rock', seed=404),
    5:  dict(bpm=150, root=40, scale='harmonic', prog=[0, 5, 3, 4], prog_b=[0, 3, 5, 4], bass='gallop', arp='up', duty=0.5, aduty=0.25, oct=0, drums='fast', seed=505),
    6:  dict(bpm=124, root=36, scale='minor', prog=[0, 0, 6, 5], prog_b=[3, 3, 4, 4], bass='pulse', arp='updown', duty=0.25, aduty=0.125, oct=0, drums='industrial', seed=606),
    7:  dict(bpm=116, root=43, scale='phrygian', prog=[0, 1, 6, 0], prog_b=[3, 1, 5, 6], bass='slow', arp='wide', duty=0.125, aduty=0.25, oct=0, drums='half', seed=707),
    8:  dict(bpm=140, root=38, scale='harmonic', prog=[0, 5, 1, 4], prog_b=[3, 0, 5, 4], bass='gallop', arp='down', duty=0.5, aduty=0.125, oct=0, drums='tribal', seed=808),
    9:  dict(bpm=158, root=45, scale='dorian', prog=[0, 3, 6, 4], prog_b=[5, 6, 3, 4], bass='drive', arp='up', duty=0.25, aduty=0.25, oct=0, drums='fast', seed=909),
    10: dict(bpm=146, root=37, scale='minor', prog=[0, 5, 6, 4], prog_b=[3, 5, 1, 4], bass='gallop', arp='updown', duty=0.5, aduty=0.25, oct=0, drums='rock', seed=1010),
}


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


class Synth:
    def __init__(self, rate):
        self.rate = rate
        self.seg = max(1, rate // 60)
        self.tables = {}
        self.noise_tabs = {}
        self.silence = {}

    # ------------------------------------------------------------ primitives
    def table(self, wave, period, duty, level):
        """One waveform cycle at one of 16 volume levels (built on first use)."""
        key = (wave, period, duty, level)
        t = self.tables.get(key)
        if t is not None:
            return t
        base = self.tables.get((wave, period, duty))
        if base is None:
            base = []
            for i in range(period):
                ph = i / period
                if wave == 'square':
                    v = 1.0 if ph < duty else -1.0
                elif wave == 'tri':
                    v = round((4 * abs(ph - 0.5) - 1) * 7.5) / 7.5
                elif wave == 'saw':
                    v = round((2 * ph - 1) * 7.5) / 7.5
                else:
                    v = math.sin(ph * math.tau)
                base.append(v)
            self.tables[(wave, period, duty)] = base
        k = AMP * level / (LEVELS - 1)
        t = array.array('h', [int(v * k) for v in base])
        self.tables[key] = t
        return t

    NOISE_LEN = 2048

    def noise_table(self, hold, level):
        hold = min(hold, 40)
        key = (hold, level)
        t = self.noise_tabs.get(key)
        if t is not None:
            return t
        base = self.noise_tabs.get(hold)
        if base is None:
            rnd = random.Random(hold * 7 + 1)
            base = []
            while len(base) < self.NOISE_LEN:
                v = 1.0 if rnd.random() < 0.5 else -1.0
                base.extend([v] * hold)
            base = base[:self.NOISE_LEN]
            self.noise_tabs[hold] = base
        k = AMP * level / (LEVELS - 1)
        t = array.array('h', [int(v * k) for v in base])
        self.noise_tabs[key] = t
        return t

    def zeros(self, n):
        z = self.silence.get(n)
        if z is None:
            z = array.array('h', bytes(2 * n))
            self.silence[n] = z
        return z

    def env(self, nseg, peak, attack=0, decay=4, sustain=0.65, release=3):
        out = []
        for i in range(nseg):
            if i < attack:
                lv = peak * (i + 1) / (attack + 1)
            elif i < attack + decay:
                lv = peak - (peak - peak * sustain) * (i - attack + 1) / decay
            else:
                lv = peak * sustain
            if i >= nseg - release:
                lv *= (nseg - i) / (release + 1.0)
            out.append(max(0, min(LEVELS - 1, int(round(lv)))))
        return out

    def tone(self, wave, freq, n, levels=None, duty=0.5, vib=0.0, slide=1.0, peak=12, **envkw):
        """One note of n samples. slide = frequency multiplier per 1/60 s segment."""
        seg = self.seg
        nseg = max(1, -(-n // seg))
        lv = levels or self.env(nseg, peak, **envkw)
        out = array.array('h')
        pos = 0
        f = freq
        for s in range(nseg):
            ln = min(seg, n - s * seg)
            if ln <= 0:
                break
            ff = f
            if vib and s > 4:
                ff = f * (1 + vib * (1 if (s // 3) % 2 else -1))
            p = max(2, int(round(self.rate / ff)))
            tab = self.table(wave, p, duty, lv[min(s, len(lv) - 1)])
            off = pos % p
            reps = (off + ln) // p + 1
            out.extend((tab * reps)[off:off + ln])
            pos += ln
            f *= slide
        return out

    def noise(self, n, hold=2, levels=None, peak=12, hold_slide=0.0, **envkw):
        seg = self.seg
        nseg = max(1, -(-n // seg))
        lv = levels or self.env(nseg, peak, **envkw)
        out = array.array('h')
        h = float(hold)
        for s in range(nseg):
            ln = min(seg, n - s * seg)
            if ln <= 0:
                break
            tab = self.noise_table(max(1, int(h)), lv[min(s, len(lv) - 1)])
            off = random.randrange(0, self.NOISE_LEN - ln)
            out.extend(tab[off:off + ln])
            h += hold_slide
        return out

    def kick(self, n, peak=14, f0=150.0, f1=42.0):
        out = array.array('h')
        f = f0
        lv = float(peak)
        while len(out) < n:
            p = max(2, int(self.rate / f))
            out.extend(self.table('sine', p, 0.5, max(0, int(lv))))
            f = max(f1, f * 0.9)
            lv *= 0.93
        return out[:n]

    @staticmethod
    def mix(*tracks):
        # each voice peaks at AMP (5200), so a few voices summed never clip 16 bits
        return array.array('h', map(sum, zip_longest(*tracks, fillvalue=0)))

    def seq(self, notes, wave='square', duty=0.5, peak=11, **kw):
        """notes: list of (freq or 0, seconds)."""
        out = array.array('h')
        for f, d in notes:
            n = int(d * self.rate)
            if f <= 0:
                out.extend(self.zeros(n))
            else:
                out.extend(self.tone(wave, f, n, duty=duty, peak=peak, **kw))
        return out


# ====================================================================== sound effects
def build_sfx(sy):
    r = sy.rate
    S = {}

    def secs(x):
        return int(x * r)

    S['shot'] = sy.tone('square', 1500, secs(0.035), duty=0.125, slide=0.8, peak=3, decay=2, sustain=0.3, release=1)
    S['enemy_shot'] = sy.tone('tri', 700, secs(0.06), slide=0.88, peak=7, decay=3, sustain=0.5, release=1)
    S['missile'] = sy.noise(secs(0.12), 1, peak=4, hold_slide=0.4, decay=4, sustain=0.4, release=2)
    S['explode_s'] = sy.noise(secs(0.28), 3, peak=12, hold_slide=0.6, decay=10, sustain=0.2, release=4)
    S['explode_m'] = sy.mix(sy.noise(secs(0.5), 4, peak=13, hold_slide=0.7, decay=18, sustain=0.15, release=6),
                            sy.kick(secs(0.2), 10))
    S['explode_l'] = sy.mix(sy.noise(secs(0.9), 6, peak=14, hold_slide=0.8, decay=40, sustain=0.1, release=10),
                            sy.kick(secs(0.35), 13, 110, 30))
    S['boss_explode'] = sy.mix(sy.noise(secs(1.9), 6, peak=15, hold_slide=0.35, decay=100, sustain=0.05, release=14),
                               sy.kick(secs(0.6), 14, 90, 25))
    S['boss_hit'] = sy.mix(sy.noise(secs(0.5), 3, peak=13, hold_slide=1.2, decay=20, sustain=0.1, release=5),
                           sy.tone('saw', 110, secs(0.5), slide=0.97, peak=10, decay=20, sustain=0.2, release=5))
    S['pop'] = sy.noise(secs(0.07), 2, peak=8, decay=3, sustain=0.3, release=1)
    S['coin'] = sy.seq([(1568, 0.04), (2093, 0.09)], 'square', 0.5, 7, decay=3, sustain=0.5, release=2)
    S['graze'] = sy.tone('square', 2600, secs(0.025), duty=0.125, peak=4, decay=1, sustain=0.5, release=1)
    S['powerup'] = sy.seq([(523, 0.045), (659, 0.045), (784, 0.045), (1047, 0.1)], 'square', 0.5, 10, decay=3,
                          sustain=0.6, release=2)
    S['overdrive'] = sy.mix(sy.tone('saw', 110, secs(0.6), slide=1.035, peak=12, decay=10, sustain=0.6, release=6),
                            sy.noise(secs(0.6), 2, peak=6, decay=20, sustain=0.3, release=6))
    S['combo_up'] = sy.seq([(1319, 0.035), (1661, 0.035), (1976, 0.035), (2637, 0.07)], 'square', 0.25, 7,
                           decay=2, sustain=0.5, release=1)
    S['shield_hit'] = sy.tone('square', 900, secs(0.22), duty=0.125, slide=0.9, peak=11, decay=6, sustain=0.4, release=3)
    S['player_hit'] = sy.mix(sy.noise(secs(0.35), 2, peak=13, hold_slide=0.8, decay=10, sustain=0.2, release=4),
                             sy.tone('square', 220, secs(0.3), duty=0.5, slide=0.93, peak=10, decay=8, sustain=0.3, release=4))
    S['death'] = sy.mix(sy.noise(secs(1.6), 5, peak=15, hold_slide=0.5, decay=70, sustain=0.05, release=12),
                        sy.tone('square', 440, secs(1.2), duty=0.5, slide=0.965, peak=10, decay=40, sustain=0.3, release=10))
    S['bomb'] = sy.mix(sy.noise(secs(1.3), 1, peak=15, hold_slide=0.5, decay=60, sustain=0.05, release=12),
                       sy.tone('saw', 300, secs(1.0), slide=0.95, peak=11, decay=40, sustain=0.2, release=10),
                       sy.kick(secs(0.5), 14, 120, 30))
    S['warning'] = sy.seq([(587, 0.24), (880, 0.24)] * 4, 'square', 0.5, 9, decay=2, sustain=0.9, release=2)
    S['warning_short'] = sy.seq([(698, 0.12), (1047, 0.12), (698, 0.12), (1047, 0.16)], 'square', 0.25, 8,
                                decay=2, sustain=0.9, release=2)
    S['charge'] = sy.tone('square', 220, secs(0.55), duty=0.25, slide=1.045, peak=6, attack=4, decay=4, sustain=0.9, release=3)
    S['laser'] = sy.mix(sy.tone('saw', 180, secs(0.7), vib=0.06, peak=11, decay=6, sustain=0.7, release=10),
                        sy.noise(secs(0.7), 1, peak=5, decay=20, sustain=0.4, release=8))
    S['thunder'] = sy.mix(sy.noise(secs(1.0), 1, peak=15, hold_slide=0.9, decay=40, sustain=0.1, release=10),
                          sy.kick(secs(0.3), 12, 90, 30))
    S['snipe'] = sy.tone('square', 900, secs(0.12), duty=0.125, slide=1.12, peak=8, decay=4, sustain=0.5, release=2)
    S['deflect'] = sy.tone('square', 2200, secs(0.03), duty=0.25, peak=5, decay=1, sustain=0.6, release=1)
    S['ping'] = sy.tone('tri', 2349, secs(0.08), peak=8, decay=3, sustain=0.4, release=2)
    S['flare'] = sy.mix(sy.noise(secs(1.0), 1, peak=14, hold_slide=0.6, attack=8, decay=30, sustain=0.2, release=10),
                        sy.tone('saw', 90, secs(1.0), slide=1.01, peak=8, attack=6, decay=30, sustain=0.4, release=10))
    S['warp'] = sy.tone('square', 300, secs(0.5), duty=0.125, slide=1.06, vib=0.04, peak=8, decay=6, sustain=0.7, release=6)
    S['phase'] = sy.mix(sy.tone('saw', 130, secs(0.8), slide=0.975, vib=0.05, peak=13, decay=20, sustain=0.6, release=8),
                        sy.noise(secs(0.8), 4, peak=8, decay=30, sustain=0.2, release=8))
    S['golden'] = sy.seq([(2093, 0.05), (2637, 0.05), (3136, 0.05), (4186, 0.05), (3136, 0.05), (4186, 0.12)],
                         'square', 0.25, 7, decay=2, sustain=0.6, release=2)
    S['golden_kill'] = sy.seq([(1047, 0.07), (1319, 0.07), (1568, 0.07), (2093, 0.07), (1568, 0.07), (2093, 0.07),
                               (2637, 0.3)], 'square', 0.5, 10, decay=3, sustain=0.6, release=4)
    S['star'] = sy.seq([(1319, 0.06), (1760, 0.06), (2637, 0.18)], 'square', 0.25, 9, decay=3, sustain=0.6, release=4)
    S['menu_move'] = sy.tone('square', 880, secs(0.035), duty=0.25, peak=6, decay=2, sustain=0.5, release=1)
    S['menu_select'] = sy.seq([(660, 0.04), (990, 0.08)], 'square', 0.25, 8, decay=2, sustain=0.6, release=2)
    S['error'] = sy.seq([(196, 0.08), (0, 0.03), (165, 0.12)], 'square', 0.5, 8, decay=2, sustain=0.8, release=2)
    S['buy'] = sy.seq([(1047, 0.04), (1568, 0.04), (2093, 0.1)], 'square', 0.5, 9, decay=2, sustain=0.6, release=2)
    S['launch'] = sy.mix(sy.tone('square', 200, secs(0.7), duty=0.25, slide=1.04, peak=9, decay=10, sustain=0.6, release=8),
                         sy.noise(secs(0.7), 1, peak=7, attack=6, decay=20, sustain=0.3, release=8))
    S['level_clear'] = sy.seq([(523, 0.08), (659, 0.08), (784, 0.08), (1047, 0.2)], 'square', 0.5, 10,
                              decay=3, sustain=0.7, release=3)
    return S


def build_jingles(sy):
    J = {}
    lead = [(784, 0.12), (784, 0.12), (784, 0.12), (1047, 0.36), (988, 0.12), (1047, 0.12), (1175, 0.12), (1568, 0.6)]
    bass = [(196, 0.36), (262, 0.36), (294, 0.36), (392, 0.6)]
    J['clear'] = sy.mix(sy.seq(lead, 'square', 0.5, 11, decay=3, sustain=0.7, release=3),
                        sy.seq(bass, 'tri', 0.5, 13, decay=4, sustain=0.8, release=4))
    lead = [(523, 0.25), (494, 0.25), (466, 0.25), (440, 0.7)]
    bass = [(131, 0.25), (123, 0.25), (117, 0.25), (110, 0.7)]
    J['gameover'] = sy.mix(sy.seq(lead, 'square', 0.25, 10, decay=4, sustain=0.6, release=6),
                           sy.seq(bass, 'tri', 0.5, 13, decay=4, sustain=0.8, release=6))
    return J


# ====================================================================== composer
RHYTHMS = [[4, 2, 2, 4, 4], [2, 2, 2, 2, 4, 4], [6, 2, 4, 4], [3, 3, 2, 4, 4], [8, 4, 4], [2, 2, 4, 2, 2, 4],
           [4, 4, 4, 4], [4, -2, 2, 4, 4], [2, 2, 2, 2, 2, 2, 4], [3, 3, 3, 3, 4]]


def song_spec(key):
    """Resolve a track key to (spec dict, variant)."""
    if key in ('title', 'hangar'):
        return dict(SONGS[key]), 'normal'
    kind, sector = key
    base = dict(SONGS[sector])
    if kind in ('sector', 'frigate'):
        return base, 'normal'
    base['scale'] = 'harmonic' if base['scale'] != 'phrygian' else 'phrygian'
    base['bass'] = 'gallop'
    base['drums'] = 'fast'
    base['seed'] = base['seed'] + 7
    base['prog'] = [0, 5, 4, 0]
    base['prog_b'] = [3, 4, 5, 4]
    if kind == 'boss':
        base['bpm'] = int(base['bpm'] * 1.06) + 6
    elif kind == 'angry':
        base['bpm'] = int(base['bpm'] * 1.14) + 8
        base['root'] += 2
        base['seed'] += 13
        base['duty'] = 0.125
    elif kind == 'rage':
        base['bpm'] = int(base['bpm'] * 1.24) + 10
        base['root'] += 3
        base['seed'] += 29
        base['arp'] = 'up'
    return base, kind


def compose(spec):
    rnd = random.Random(spec['seed'])
    scale = SCALES[spec['scale']]
    root = spec['root']

    def deg(d, base_oct=0):
        o, i = divmod(d, 7)
        return root + 12 * (o + base_oct) + scale[i]

    chords = []
    for b in range(16):
        prog = spec['prog'] if b < 8 or b >= 12 else spec['prog_b']
        chords.append(prog[(b // 2) % 4])
    # ---- bass (one note list of (midi, steps))
    bass = []
    for b in range(16):
        c = chords[b]
        r = deg(c, 0) - 12
        f5 = deg(c + 4, 0) - 12
        st = spec['bass']
        if st == 'drive':
            pat = [(r, 2), (r, 2), (r + 12, 2), (r, 2), (r, 2), (r + 12, 2), (r, 2), (f5, 2)]
        elif st == 'gallop':
            pat = [(r, 2), (r, 1), (r, 1)] * 3 + [(r + 12, 2), (f5, 2)]
        elif st == 'slow':
            pat = [(r, 6), (f5, 2), (r + 12, 4), (f5, 4)]
        elif st == 'bounce':
            pat = [(r, 2), (None, 2), (r + 12, 2), (r, 2), (None, 2), (f5, 2), (r + 12, 2), (r, 2)]
        else:  # pulse
            pat = [(r if i % 2 == 0 else r + 12, 1) for i in range(16)]
        bass.extend(pat)
    # ---- arpeggio
    arp = []
    shapes = {'up': [0, 2, 4, 7], 'down': [7, 4, 2, 0], 'updown': [0, 2, 4, 7, 4, 2], 'wide': [0, 4, 7, 9, 11, 7]}
    shape = shapes[spec['arp']]
    for b in range(16):
        c = chords[b]
        for i in range(16):
            arp.append((deg(c + shape[(b * 16 + i) % len(shape)], 1), 1))
    # ---- lead melody (motif based)
    def make_motif():
        notes = []
        cur = rnd.choice([0, 2, 4])
        for bar in range(2):
            rh = rnd.choice(RHYTHMS)
            pos = 0
            for d in rh:
                if d < 0:
                    notes.append((None, -d))
                    pos += -d
                    continue
                if pos % 8 == 0:
                    cur = min((0, 2, 4, 7), key=lambda t: abs(t - cur)) if rnd.random() < 0.7 else cur
                else:
                    cur += rnd.choice([-2, -1, -1, 1, 1, 2, 0, 3])
                cur = max(-3, min(9, cur))
                notes.append((cur, d))
                pos += d
        return notes

    def vary(m):
        m = list(m)
        for k in range(len(m) - 3, len(m)):
            if 0 <= k < len(m) and m[k][0] is not None and rnd.random() < 0.7:
                m[k] = (max(-3, min(9, m[k][0] + rnd.choice([-2, -1, 1, 2]))), m[k][1])
        return m

    def cadence(m):
        m = list(m)
        total_last = 0
        while m and total_last < 8:
            total_last += m[-1][1]
            m.pop()
        m.append((0, total_last))
        return m

    m1 = make_motif()
    m2 = make_motif()
    blocks = [m1, vary(m1), m1, cadence(vary(m1)), m2, vary(m2), m1, cadence(m1)]
    lead = []
    for bi, blk in enumerate(blocks):
        c = chords[bi * 2]
        for d, steps in blk:
            if d is None:
                lead.append((None, steps))
            else:
                lead.append((deg(c + d, 2 + spec.get('oct', 0)), steps))
    # ---- counter melody: chord third/fifth, long notes
    counter = []
    for b in range(16):
        c = chords[b]
        counter.append((deg(c + 2, 1), 8))
        counter.append((deg(c + 4, 1), 8))
    # ---- drums (4 bar loops): lists of hit names per step
    style = spec['drums']

    def drum_bar(heavy, fill):
        hits = [None] * 16
        if not heavy:
            for i in range(0, 16, 2):
                hits[i] = 'hat'
            hits[0] = 'kick'
            if style != 'half':
                hits[8] = 'kick'
            return hits
        for i in range(16):
            hits[i] = 'hat'
        kicks = {'rock': [0, 6, 8], 'fast': [0, 4, 8, 12], 'shuffle': [0, 3, 8, 11], 'half': [0, 10],
                 'industrial': [0, 3, 6, 8, 11, 14], 'tribal': [0, 2, 7, 8, 10, 15]}.get(style, [0, 8])
        for k in kicks:
            hits[k] = 'kick'
        for sn in ((4, 12) if style != 'half' else (8,)):
            hits[sn] = 'snare'
        if fill:
            for i in range(8, 16):
                hits[i] = 'snare' if i % 2 == 0 or i > 12 else 'tom'
        return hits

    drums_l = []
    drums_h = []
    for b in range(4):
        drums_l.extend(drum_bar(False, False))
        drums_h.extend(drum_bar(True, b == 3))
    return dict(bass=bass, arp=arp, lead=lead, counter=counter, drums_l=drums_l, drums_h=drums_h)


def render_song(sy, spec):
    score = compose(spec)
    step = int(sy.rate * 60.0 / spec['bpm'] / 4)
    total = step * 256

    def voice(notes, wave, duty, peak, **kw):
        out = array.array('h')
        cache = {}
        for m, steps in notes:
            n = step * steps
            if m is None:
                out.extend(sy.zeros(n))
                continue
            key = (m, steps)
            buf = cache.get(key)
            if buf is None:
                buf = sy.tone(wave, midi_freq(m), n, duty=duty, peak=peak, **kw)
                cache[key] = buf
            out.extend(buf)
        return out[:total] if len(out) >= total else out + sy.zeros(total - len(out))

    stems = {}
    stems['bass'] = voice(score['bass'], 'tri', 0.5, 15, decay=2, sustain=0.85, release=1)
    stems['arp'] = voice(score['arp'], 'square', spec['aduty'], 6, decay=2, sustain=0.5, release=1)
    stems['lead'] = voice(score['lead'], 'square', spec['duty'], 11, decay=3, sustain=0.7, release=2, vib=0.012)
    d = step * 3
    lead = stems['lead']
    stems['echo'] = lead[-d:] + lead[:-d]
    stems['counter'] = voice(score['counter'], 'saw', 0.5, 6, attack=4, decay=6, sustain=0.6, release=4)
    hitbuf = {
        'kick': sy.kick(step * 2, 14),
        'snare': sy.mix(sy.noise(step * 2, 1, peak=11, decay=6, sustain=0.1, release=2),
                        sy.tone('tri', 196, step, peak=8, decay=3, sustain=0.2, release=1)),
        'hat': sy.noise(max(1, step // 2), 1, peak=4, decay=1, sustain=0.3, release=1),
        'tom': sy.tone('tri', 150, step, slide=0.92, peak=12, decay=3, sustain=0.3, release=1),
    }

    def drums(hits):
        out = array.array('h')
        i = 0
        while i < len(hits):
            h = hits[i]
            j = i + 1
            while j < len(hits) and hits[j] is None:
                j += 1
            n = step * (j - i)
            if h is None:
                out.extend(sy.zeros(n))
            else:
                buf = hitbuf[h]
                out.extend(buf[:n] if len(buf) >= n else buf + sy.zeros(n - len(buf)))
            i = j
        return out

    stems['drums_l'] = drums(score['drums_l'])
    stems['drums_h'] = drums(score['drums_h'])
    return stems


# ====================================================================== audio manager
class Audio:
    MUSIC_CH = len(STEMS)

    def __init__(self, muted=False):
        self.muted = muted
        self.ok = False
        self.sounds = {}
        self.jingles = {}
        self.last = {}
        self.frame = 0
        self.tracks = {}          # key -> {stem: Sound}
        self.order = []
        self.current = None
        self.bank = 0
        self.bank_key = [None, None]
        self.vol = [dict((s, 0.0) for s in STEMS), dict((s, 0.0) for s in STEMS)]
        self.target_master = [0.0, 0.0]
        self.master = [0.0, 0.0]
        self.intensity = 1
        self.pending = None
        self.paused = False
        try:
            init = pygame.mixer.get_init()
            if not init:
                pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
                init = pygame.mixer.get_init()
            if not init:
                return
            self.rate, self.fmt, self.channels = init
            if self.fmt not in (-16, 16):
                return
            pygame.mixer.set_num_channels(40)
            pygame.mixer.set_reserved(self.MUSIC_CH * 2)
            self.chans = [[pygame.mixer.Channel(b * self.MUSIC_CH + i) for i in range(self.MUSIC_CH)] for b in range(2)]
            self.synth = Synth(self.rate)
            for k, buf in build_sfx(self.synth).items():
                self.sounds[k] = self.make_sound(buf)
            for k, buf in build_jingles(self.synth).items():
                self.jingles[k] = self.make_sound(buf)
            self.ok = True
        except (pygame.error, ValueError, OSError):
            self.ok = False

    # ------------------------------------------------------------ helpers
    def to_bytes(self, buf):
        if self.channels == 2:
            st = array.array('h', bytes(4 * len(buf)))
            st[0::2] = buf
            st[1::2] = buf
            buf = st
        return buf.tobytes()

    def make_sound(self, buf):
        return pygame.mixer.Sound(buffer=self.to_bytes(buf))

    def norm(self, key):
        if isinstance(key, tuple) and key[0] == 'frigate':
            return ('sector', key[1])
        return key

    def prefetch(self, keys):
        """Render songs now (a few hundredths of a second each) so later switches are instant."""
        if not self.ok:
            return
        for k in keys:
            self.ready(self.norm(k))

    def ready(self, key):
        if key in self.tracks:
            return True
        try:
            spec, _ = song_spec(key)
            stems = render_song(self.synth, spec)
            self.tracks[key] = {k: self.make_sound(v) for k, v in stems.items()}
        except (pygame.error, KeyError, ValueError):
            return False
        self.order.append(key)
        # keep memory in check: forget old songs that are not playing
        for old in list(self.order):
            if len(self.order) <= 6:
                break
            if old not in self.bank_key and old != key:
                self.order.remove(old)
                self.tracks.pop(old, None)
        return True

    # ------------------------------------------------------------ public API
    def set_muted(self, m):
        self.muted = m
        if self.ok and m:
            for b in range(2):
                for ch in self.chans[b]:
                    ch.set_volume(0)

    def sfx(self, name, vol=1.0):
        if not self.ok or self.muted:
            return
        s = self.sounds.get(name)
        if s is None:
            return
        gap = 2 if name in ('coin', 'graze', 'pop', 'deflect', 'ping') else 4 if name.startswith('explode') else 6
        if self.frame - self.last.get(name, -99) < gap:
            return
        self.last[name] = self.frame
        ch = s.play()
        if ch is not None:
            ch.set_volume(SFX_VOL * vol * (0.5 if name == 'shot' else 1.0))

    def jingle(self, name):
        if not self.ok or self.muted:
            return
        s = self.jingles.get(name)
        if s is not None:
            ch = s.play()
            if ch is not None:
                ch.set_volume(SFX_VOL)

    def play_music(self, key):
        if not self.ok:
            return
        key = self.norm(key)
        if key == self.current and self.pending is None and self.bank_key[self.bank] == key:
            self.target_master[self.bank] = 1.0
            return
        self.current = key
        self.pending = key

    def _start(self, key):
        old = self.bank
        nb = 1 - old
        for ch in self.chans[nb]:
            ch.stop()
        snd = self.tracks[key]
        for i, s in enumerate(STEMS):
            ch = self.chans[nb][i]
            ch.set_volume(0)
            ch.play(snd[s], loops=-1)
            self.vol[nb][s] = MIX[self.intensity][s]
        self.bank_key[nb] = key
        self.master[nb] = 0.0
        self.target_master[nb] = 1.0
        self.target_master[old] = 0.0
        self.bank = nb

    def stop_music(self, ms=500):
        if not self.ok:
            return
        self.current = None
        self.pending = None
        self.target_master = [0.0, 0.0]

    def pause_music(self, paused):
        if not self.ok:
            return
        self.paused = paused
        for b in range(2):
            for ch in self.chans[b]:
                if paused:
                    ch.pause()
                else:
                    ch.unpause()

    def set_intensity(self, level):
        self.intensity = max(0, min(3, level))

    def update(self):
        self.frame += 1
        if not self.ok:
            return
        if self.pending is not None and self.ready(self.pending):
            key = self.pending
            self.pending = None
            if key == self.current:
                self._start(key)
        mix = MIX[self.intensity]
        for b in range(2):
            m = self.master[b]
            t = self.target_master[b]
            self.master[b] = m + (t - m) * (0.06 if t > m else 0.05)
            if self.master[b] < 0.01 and t == 0.0 and self.bank_key[b] is not None:
                for ch in self.chans[b]:
                    ch.stop()
                self.bank_key[b] = None
            if self.bank_key[b] is None:
                continue
            for i, s in enumerate(STEMS):
                cur = self.vol[b][s]
                cur += (mix[s] - cur) * 0.035
                self.vol[b][s] = cur
                v = 0.0 if self.muted else cur * self.master[b] * MUSIC_VOL
                self.chans[b][i].set_volume(v)
