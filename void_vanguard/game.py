"""One level being played: the update loop, collisions, scoring, combo, graze,
challenges, end fight and the level state machine."""
import math
import random

import pygame

import art
import backgrounds
import bosses
import bullets as B
import enemies as E
import hazards
import hud
import levels
import pickups as P
from config import (PF_W, PF_H, PF_X, WHITE, COMBO_TIERS, COMBO_WINDOW,
                    GRAZE_COMBO_BONUS, GRAZE_PER_BOMB, BOMB_INVULN, MAX_BOMBS, GOLD)
from effects import Effects
from player import Player

EXPLOSION_SIZE = {'mini': 's', 'larva': 's', 'heavy': 'l', 'minelayer': 'l', 'nest': 'l', 'golden': 'l',
                  'carrier': 'l', 'splitter': 'l', 'shielded': 'l'}


class GameScene:
    def __init__(self, app, level, stats, flags=None):
        self.app = app
        flags = flags or {}
        self.flags = flags
        self.level = level
        self.plan = levels.build(level, flags.get('golden_radar', False))
        self.sector = self.plan.sector
        self.diff = dict(self.plan.diff)
        self.bullet_colors = art.SECTOR_STYLE[self.sector]['bullets']
        self.ui_color = art.SECTOR_STYLE[self.sector]['ui']
        self.fx = Effects()
        self.rnd = random.Random(self.plan.seed)
        self.frame = 0
        self.wave_frame = 0
        self.ev_i = 0
        self.state = 'waves'
        self.state_t = 0
        self.scroll_base = 0.55
        self.scroll = self.scroll_base
        self.scroll_mult = 1.0
        self.gravity_x = 0.0
        self.mirror_x = False
        self.allow_enemy_fire = True
        self.fire_mult = 1.0
        self.enemies = []
        self.ebullets = []
        self.pbullets = []
        self.pickups = []
        self.telegraphs = []
        self.beams = []
        self.scheduled = []
        self.banners = []
        self.boss = None
        self.boss_t = 0
        self.player = Player(self, stats)
        self.part_magnet = flags.get('part_magnet', False)
        self.combo_keeper = flags.get('combo_keeper', False)
        self.keeper_used = False
        self.bg = backgrounds.make(self.sector, level)
        self.hazards = hazards.HazardManager(self, self.plan.hazards)
        # scoring
        self.score = 0
        self.combo = 0
        self.combo_t = 0
        self.mult = 1
        self.graze_meter = 0
        self.run_credits = 0
        self.part_pity = 0
        self.stats = dict(kills=0, escaped=0, damage=0, bombs=0, parts=0, grazes=0, best_combo=0,
                          max_mult=1, golden=False, boss_time=0, ore=0)
        self.challenge_fail = set()
        self.timescale = 1.0
        self.time_acc = 0.0
        self.paused = False
        self.menu_sel = 0
        self.over_t = 0
        self.result = None
        self.music_level = -1
        self.last_graze_sfx = 0
        self.intro_frames = self.plan.intro
        self.pf = pygame.Surface((PF_W, PF_H))
        self.app.audio.play_music(('sector', self.sector))
        self.set_music(1)
        if self.plan.end_kind != 'frigate':
            self.app.audio.prefetch([('boss', self.sector), ('angry', self.sector), ('rage', self.sector)])

    # ================================================================ services
    def sfx(self, name, vol=1.0):
        self.app.audio.sfx(name, vol)

    def schedule(self, delay, fn):
        self.scheduled.append([self.frame + delay, fn])

    def add_enemy(self, e):
        self.enemies.append(e)
        return e

    def count_kind(self, kind):
        return sum(1 for e in self.enemies if e.kind == kind and e.alive)

    def popup_player(self, text, color=WHITE):
        self.fx.popup(self.player.x, self.player.y - 24, text, color, 60)

    def popup_world(self, x, y, text, color=WHITE):
        self.fx.popup(x, y, text, color, 50)

    def banner(self, text, color=WHITE, frames=90, sc=2):
        self.banners.append([text, color, frames, frames, sc])

    def telegraph_line(self, x, y, x2, y2, frames, color=(255, 60, 60), follow=None, width=1):
        a = math.atan2(y2 - y, x2 - x)
        self.telegraphs.append(dict(kind='line', x=x, y=y, a=a, len=460, life=frames, max=frames,
                                    color=color, follow=follow, w=width))
        return a

    def telegraph_angle(self, x, y, a, frames, color=(255, 60, 60), follow=None, width=1, length=460):
        self.telegraphs.append(dict(kind='line', x=x, y=y, a=a, len=length, life=frames, max=frames,
                                    color=color, follow=follow, w=width))

    def telegraph_circle(self, x, y, r, frames, color=(255, 60, 60)):
        self.telegraphs.append(dict(kind='circle', x=x, y=y, r=r, life=frames, max=frames, color=color))

    def telegraph_rect(self, rect, frames, color=(255, 60, 60)):
        self.telegraphs.append(dict(kind='rect', rect=pygame.Rect(rect), life=frames, max=frames, color=color))

    def warn_marker(self, x, y, frames):
        self.telegraphs.append(dict(kind='arrow', x=x, y=y, life=frames, max=frames, color=(255, 80, 80)))

    def beam(self, x, y, a, frames, width=8, color=(255, 80, 120), length=480, owner=None, dmg=1):
        b = dict(x=x, y=y, a=a, len=length, life=frames, max=frames, w=width, color=color, owner=owner, dmg=dmg)
        self.beams.append(b)
        return b

    def play_bounds(self):
        return self.hazards.bounds_at(self.player.y)

    def nearest_target(self, x, y, maxd=None):
        """Closest thing worth shooting (asteroids only if nothing else is around)."""
        lim = maxd * maxd if maxd else 1e12
        best, bd = None, lim
        rock, rd = None, lim
        for e in self.targets():
            if not e.alive or e.y < -4:
                continue
            d = (e.x - x) ** 2 + (e.y - y) ** 2
            if e.kind == 'asteroid':
                if d < rd:
                    rock, rd = e, d
            elif d < bd:
                best, bd = e, d
        return best or rock

    def targets(self):
        t = [e for e in self.enemies if e.alive]
        if self.boss is not None and self.boss.alive:
            t.extend(self.boss.targets())
        return t

    def mine_burst(self, b):
        n = 8 + int(self.diff['aggression'] * 4)
        B.ring(self, b.x, b.y, n, 1.4, random.uniform(0, 1), 's', 0)
        self.fx.explosion(b.x, b.y, 's')
        self.sfx('pop')

    def set_music(self, level):
        if level != self.music_level:
            self.music_level = level
            self.app.audio.set_intensity(level)

    # ================================================================ scoring
    def add_combo(self, n=1):
        self.combo += n
        self.combo_t = COMBO_WINDOW
        self.stats['best_combo'] = max(self.stats['best_combo'], self.combo)
        m = 1
        for i, need in enumerate(COMBO_TIERS):
            if self.combo >= need:
                m = i + 1
        if m > self.mult:
            self.mult = m
            self.stats['max_mult'] = max(self.stats['max_mult'], m)
            self.fx.popup(self.player.x, self.player.y - 30, '×%d!' % m, (255, 230, 90), 50, 2)
            self.sfx('combo_up')

    def break_combo(self, hit=False):
        if self.combo >= 10:
            self.fx.popup(PF_W / 2, 90, '%d CHAIN' % self.combo, (200, 200, 255), 60)
        if hit and self.combo_keeper and not self.keeper_used and self.combo > 0:
            self.keeper_used = True
            self.combo //= 2
            self.combo_t = COMBO_WINDOW
            m = 1
            for i, need in enumerate(COMBO_TIERS):
                if self.combo >= need:
                    m = i + 1
            self.mult = m
            return
        self.combo = 0
        self.combo_t = 0
        self.mult = 1

    def add_score(self, pts):
        self.score += int(pts)

    def gain_credits(self, amount):
        self.run_credits += int(amount)

    def on_graze(self, b):
        self.stats['grazes'] += 1
        self.graze_meter += 1
        self.add_score(25 * self.mult)
        if self.combo > 0:
            self.combo_t = min(COMBO_WINDOW, self.combo_t + GRAZE_COMBO_BONUS)
        p = self.player
        mx, my = (b.x + p.x) / 2, (b.y + p.y) / 2
        self.fx.sparks(mx, my, 3, (255, 255, 255), 1.8, 8)
        if self.frame - self.last_graze_sfx > 3:
            self.last_graze_sfx = self.frame
            self.sfx('graze')
        if self.graze_meter >= GRAZE_PER_BOMB:
            self.graze_meter = 0
            if p.bombs < MAX_BOMBS:
                p.bombs += 1
                self.popup_player('GRAZE BOMB +1', (255, 140, 140))
                self.sfx('powerup')

    def kill_enemy(self, e):
        size = EXPLOSION_SIZE.get(e.kind, 'm')
        if e.kind == 'asteroid':
            size = 's' if e.size < 6 else 'm' if e.size < 11 else 'l'
        self.fx.explosion(e.x, e.y, size, e.spr)
        self.sfx('explode_' + ('s' if size == 's' else 'm' if size == 'm' else 'l'))
        if e.counts:
            self.stats['kills'] += 1
        if e.kind != 'asteroid':
            self.add_combo()
        self.add_score(e.score * self.mult)
        if e.score >= 500 or self.mult >= 3:
            self.fx.popup(e.x, e.y - 6, str(e.score * self.mult), (255, 240, 170) if self.mult < 4 else GOLD, 30)
        p = self.player
        cmult = self.diff['credits'] * (1 + 0.08 * (self.mult - 1)) * (2 if p.bounty > 0 else 1)
        if e.kind == 'asteroid':
            self.hazards.asteroid_destroyed(e)
            if e.ore:
                P.scatter_coins(self, e.x, e.y, (2 + e.size * 0.9) * cmult, 1.8, ore=True)
            return
        if e.credits:
            P.scatter_coins(self, e.x, e.y, e.credits * cmult)
        if e.kind == 'golden':
            self.stats['golden'] = True
            P.scatter_coins(self, e.x, e.y, 140 * cmult, 3.2)
            P.drop_part(self, e.x, e.y, weights=P.RARE_WEIGHTS)
            self.banner('GOLDEN BONUS!', GOLD, 80)
            self.fx.freeze(8)
            self.sfx('golden_kill')
            return
        if e.kind == 'carrier':
            P.drop_part(self, e.x, e.y)
            self.part_pity = 0
            return
        if e.kind == 'splitter':
            for i in range(3):
                a = math.pi / 2 + (i - 1) * 0.7
                self.add_enemy(E.Enemy(self, 'mini', e.x, e.y, E.make_drift(math.cos(a) * 1.4, math.sin(a) * 1.4 + 0.6)))
        if e.kind == 'kamikaze' and self.diff['aggression'] > 0.55:
            B.ring(self, e.x, e.y, 6, 1.1, random.uniform(0, 1), 's', 1)
        chance = 0.03 + (0.04 if e.kind in ('heavy', 'nest', 'minelayer') else 0)
        if self.part_pity > 25 * 60 and e.counts:
            chance = 1.0
        if random.random() < chance:
            P.drop_part(self, e.x, e.y)
            self.part_pity = 0

    def collect_pickup(self, pk):
        p = self.player
        if pk.part:
            text = p.collect(pk.kind)
            self.stats['parts'] += 1
            if text is None:
                bonus = 15 * self.diff['credits']
                self.gain_credits(bonus)
                self.add_score(1000)
                self.popup_player('MAX! +%d' % int(bonus), (255, 220, 120))
                self.sfx('coin')
            else:
                col = art.PICKUP_STYLE[pk.kind][1]
                self.popup_player(text, art.mix(col, WHITE, 0.3))
                self.fx.ring(p.x, p.y, 6, 1.4, 16, col, 2)
                self.fx.sparks(p.x, p.y, 12, col, 2.5)
                self.sfx('overdrive' if pk.kind == 'overdrive' else 'powerup')
                if pk.kind == 'overdrive':
                    self.fx.screen_flash(8, (255, 60, 60))
                    self.banner('OVERDRIVE!', (255, 70, 70), 60)
                elif pk.kind == 'bounty':
                    self.banner('BOUNTY BEACON', (200, 120, 255), 60)
            self.add_score(200)
        else:
            amount = pk.value
            if pk.kind == 'ore':
                self.stats['ore'] += amount
            self.gain_credits(amount)
            self.add_score(10 * amount)
            self.sfx('coin', 0.6)

    # ================================================================ player events
    def on_player_hit(self, shield):
        self.stats['damage'] += 1
        self.challenge_fail.add('nodamage')
        self.break_combo(hit=True)

    def on_player_death(self):
        p = self.player
        self.fx.explosion(p.x, p.y, 'xl', p.sprite())
        self.fx.freeze(10)
        self.fx.screen_flash(18, (255, 255, 255))
        self.sfx('death')
        self.state = 'dead'
        self.state_t = 0
        self.timescale = 0.35
        self.app.audio.stop_music(800)
        self.app.record_death(self.level)

    def detonate_bomb(self, x, y):
        p = self.player
        p.invuln = max(p.invuln, BOMB_INVULN)
        self.stats['bombs'] += 1
        self.challenge_fail.add('nobomb')
        self.fx.bomb_wave(x, y)
        self.sfx('bomb')
        cleared = 0
        for b in self.ebullets:
            if cleared < 120 and cleared % 2 == 0:
                self.fx.particle(b.x, b.y, 0, -0.6, 18, 2, (255, 240, 170), 'sq', 0.95)
            cleared += 1
        self.ebullets.clear()
        for bm in self.beams:
            bm['life'] = min(bm['life'], 2)
        if cleared:
            self.add_score(cleared * 10)
            self.fx.popup(x, y - 34, 'CLEAR +%d' % (cleared * 10), (255, 240, 170), 50)
        dmg = 30 * self.diff['enemy_hp']
        for e in list(self.enemies):
            if e.alive and -10 < e.y < PF_H + 10:
                e.damage(dmg, 'bomb')
        if self.boss is not None and self.boss.alive:
            self.boss.bomb_hit(levels.expected_dps(self.level) * 2.2)

    # ================================================================ main loop
    def update(self):
        inp = self.app.input
        if self.result is not None:
            return
        if self.state == 'over':
            self.update_over(inp)
            self.fx.update()
            return
        if inp.pause and self.state not in ('dead', 'outro'):
            self.paused = not self.paused
            self.menu_sel = 0
            self.sfx('menu_select')
            self.app.audio.pause_music(self.paused)
            return
        if self.paused:
            self.update_pause(inp)
            return
        if self.fx.hitstop > 0:
            self.fx.hitstop -= 1
            return
        self.time_acc += self.timescale
        while self.time_acc >= 1.0:
            self.time_acc -= 1.0
            self.step(inp)
            inp = self.app.idle_input

    def pause_options(self):
        d = self.app.data
        return ['RESUME', 'MUSIC VOLUME %d%%' % (d['music_vol'] * 10), 'EFFECTS VOLUME %d%%' % (d['sfx_vol'] * 10),
                'RETRY LEVEL', 'QUIT TO HANGAR']

    def update_pause(self, inp):
        opts = 5
        if inp.up:
            self.menu_sel = (self.menu_sel - 1) % opts
            self.sfx('menu_move')
        if inp.down:
            self.menu_sel = (self.menu_sel + 1) % opts
            self.sfx('menu_move')
        if self.menu_sel in (1, 2) and (inp.left or inp.right):
            self.app.change_volume('music_vol' if self.menu_sel == 1 else 'sfx_vol', -1 if inp.left else 1)
            return
        if inp.confirm:
            if self.menu_sel == 0:
                self.sfx('menu_select')
                self.paused = False
                self.app.audio.pause_music(False)
            elif self.menu_sel in (1, 2):
                key = 'music_vol' if self.menu_sel == 1 else 'sfx_vol'
                self.app.change_volume(key, 1 if self.app.data[key] < 10 else -10)
            elif self.menu_sel == 3:
                self.sfx('menu_select')
                self.app.audio.pause_music(False)
                self.app.retry_level()
            else:
                self.sfx('menu_select')
                self.app.audio.pause_music(False)
                self.app.goto_hangar()
        if inp.back:
            self.paused = False
            self.app.audio.pause_music(False)

    def update_over(self, inp):
        self.over_t += 1
        if self.over_t < 30:
            return
        if inp.up or inp.down:
            self.menu_sel = 1 - self.menu_sel
            self.sfx('menu_move')
        if inp.confirm:
            self.sfx('menu_select')
            if self.menu_sel == 0:
                self.app.retry_level()
            else:
                self.app.goto_hangar()

    def step(self, inp):
        self.frame += 1
        self.state_t += 1
        p = self.player
        # scheduled spawns
        if self.scheduled:
            due = [s for s in self.scheduled if s[0] <= self.frame]
            if due:
                self.scheduled = [s for s in self.scheduled if s[0] > self.frame]
                for s in due:
                    s[1]()
        self.update_state()
        self.bg.update(self.scroll)
        self.hazards.update()
        if self.state == 'outro':
            p.y -= min(7.0, 0.5 + self.state_t * 0.06)
            p.flicker += 1
        else:
            p.update(inp)
        for e in self.enemies:
            if e.alive:
                e.update()
        if self.boss is not None:
            self.boss.update()
        removed = [e for e in self.enemies if not e.alive]
        if removed:
            for e in removed:
                if e.escaped and e.counts and e.entered:
                    self.stats['escaped'] += 1
            self.enemies = [e for e in self.enemies if e.alive]
        B.update_player_bullets(self)
        B.update_enemy_bullets(self)
        self.hazards.affect_bullets()
        self.update_beams()
        if p.alive and self.state not in ('outro', 'clear'):
            self.collide()
        else:
            self.collide_player_bullets()
        for pk in self.pickups:
            pk.update(self)
            if p.alive and abs(pk.x - p.x) < 16 and abs(pk.y - p.y) < 16:
                pk.alive = False
                self.collect_pickup(pk)
        self.pickups = [pk for pk in self.pickups if pk.alive]
        if self.combo_t > 0:
            self.combo_t -= 1
            if self.combo_t == 0:
                self.break_combo()
        self.part_pity += 1
        for t in self.telegraphs:
            t['life'] -= 1
        self.telegraphs = [t for t in self.telegraphs if t['life'] > 0]
        for bn in self.banners:
            bn[2] -= 1
        self.banners = [bn for bn in self.banners if bn[2] > 0]
        self.fx.update()

    def update_state(self):
        st = self.state
        plan = self.plan
        if st == 'waves':
            self.wave_frame += 1
            ev = plan.events
            while self.ev_i < len(ev) and ev[self.ev_i][0] <= self.wave_frame:
                self.handle_event(ev[self.ev_i])
                self.ev_i += 1
        elif st == 'clearing':
            alive = [e for e in self.enemies if e.counts and e.alive]
            if not alive or self.state_t > 6 * 60:
                self.state = 'warning'
                self.state_t = 0
                self.hazards.end_fight()
                kind = plan.end_kind
                txt = {'boss': 'WARNING', 'miniboss': 'WARNING', 'frigate': 'INCOMING'}[kind]
                self.banner(txt, (255, 60, 60), 170, 3)
                self.sfx('warning')
                self.app.audio.stop_music(600)
                self.set_music(3)
        elif st == 'warning':
            if self.state_t >= 170:
                self.state = 'boss'
                self.state_t = 0
                self.boss = bosses.create(self, plan.boss_id)
                self.boss_t = 0
                if plan.end_kind != 'frigate':
                    self.banner(self.boss.name, (255, 200, 200), 120, 1)
                self.app.audio.play_music(('boss', self.sector) if plan.end_kind != 'frigate'
                                          else ('frigate', self.sector))
        elif st == 'boss':
            if self.boss is not None and self.boss.fighting:
                self.boss_t += 1
        elif st == 'clear':
            if self.state_t >= 70:
                self.timescale = 1.0
                if self.state_t >= 120:
                    self.state = 'outro'
                    self.state_t = 0
                    self.sfx('level_clear')
                    self.app.audio.jingle('clear')
                    self.banner('LEVEL CLEAR', (120, 255, 160), 160, 3)
                    for pk in self.pickups:
                        pk.pulled = True
        elif st == 'outro':
            for e in self.enemies:
                if e.alive:
                    e.damage(1e9, 'bomb')
            self.ebullets.clear()
            if self.state_t >= 170:
                self.finish()
        elif st == 'dead':
            if self.state_t >= 70:
                self.timescale = 1.0
            if self.state_t >= 110:
                self.state = 'over'
                self.menu_sel = 0
                self.over_t = 0
                self.app.audio.jingle('gameover')

    def handle_event(self, ev):
        _, kind, data = ev
        if kind == 'wave':
            E.spawn_wave(self, data)
        elif kind == 'act':
            self.hazards.on_act(data['index'], data['length'])
            self.set_music(3 if data['big'] else 2)
            self.allow_enemy_fire = True
            if data['big']:
                self.banner('BIG WAVE!', (255, 200, 80), 90)
        elif kind == 'breather':
            self.hazards.on_breather(data['frames'])
            self.set_music(1)
        elif kind == 'golden':
            E.spawn_golden(self)
        elif kind == 'end':
            self.state = 'clearing'
            self.state_t = 0

    def boss_defeated(self, boss):
        self.hazards.shutdown()
        if not self.player.alive:
            return          # you went down first: the death stands
        self.stats['boss_time'] = self.boss_t
        self.player.safe = True
        self.state = 'clear'
        self.state_t = 0
        self.timescale = 0.3
        self.ebullets.clear()
        self.beams.clear()
        self.telegraphs.clear()
        self.app.audio.stop_music(500)
        P.scatter_coins(self, boss.x, boss.y, boss.reward_credits() * self.diff['credits'], 3.5)
        if boss.kind != 'frigate':
            P.drop_part(self, boss.x, boss.y + 10, weights=P.RARE_WEIGHTS)
        self.add_score(boss.score_value() * self.mult)
        self.add_combo(5)

    # ================================================================ collisions
    def collide_player_bullets(self):
        targets = self.targets()
        if not targets:
            return
        fx = self.fx
        for b in self.pbullets:
            if not b.alive:
                continue
            bx, by = b.x, b.y
            for e in targets:
                if not e.alive:
                    continue
                if abs(bx - e.x) < (b.w + e.w) * 0.5 and abs(by - e.y) < (b.h + e.h) * 0.5:
                    if b.kind == 'missile':
                        kind = 'missile'
                        fx.explosion(bx, by, 's')
                    elif b.vy > 0:
                        kind = 'rear'
                    else:
                        kind = 'shot'
                    e.damage(b.dmg, kind)
                    fx.hit_spark(bx, by - 2)
                    b.alive = False
                    break
        p = self.player
        if p.alive and p.laser_on:
            r = p.laser_rect()
            dmg = p.laser_damage()
            cx = r.centerx
            for e in targets:
                if e.alive and abs(e.x - cx) < (r.width + e.w) * 0.5 and e.y - e.h / 2 < r.bottom:
                    e.damage(dmg, 'laser')
                    if self.frame % 5 == 0:
                        fx.sparks(cx, e.y + e.h / 2, 2, (150, 240, 255), 2, 8)

    def collide(self):
        self.collide_player_bullets()
        p = self.player
        hr = p.hitbox
        gr = p.graze_r
        px, py = p.x, p.y
        for b in self.ebullets:
            if not b.alive or b.delay > 0:
                continue
            dx = b.x - px
            dy = b.y - py
            lim = gr + b.r
            if dx > lim or dx < -lim or dy > lim or dy < -lim:
                continue
            d2 = dx * dx + dy * dy
            hit_r = hr + b.r * 0.75
            if d2 < hit_r * hit_r:
                if p.hit(b.dmg):
                    b.alive = False
                    if not p.alive:
                        return
            elif not b.grazed and d2 < lim * lim and p.invuln <= 0:
                b.grazed = True
                self.on_graze(b)
        for bm in self.beams:
            if bm['life'] > bm['max'] - 6:
                continue  # beams warm up for a few frames before they hurt
            if self.point_in_beam(px, py, bm, hr):
                p.hit(bm['dmg'])
                if not p.alive:
                    return
        for e in self.enemies:
            if not e.alive or e.ground:
                continue
            if abs(e.x - px) < e.w * 0.38 + 2 and abs(e.y - py) < e.h * 0.38 + 2:
                if p.hit(1):
                    e.damage(1e9 if e.contact else e.maxhp * 0.35, 'ram')
                    if not p.alive:
                        return
        if self.boss is not None and self.boss.alive and self.boss.touches(px, py):
            p.hit(1)

    def point_in_beam(self, px, py, bm, pad):
        ca, sa = math.cos(bm['a']), math.sin(bm['a'])
        dx, dy = px - bm['x'], py - bm['y']
        along = dx * ca + dy * sa
        if along < 0 or along > bm['len']:
            return False
        perp = abs(-dx * sa + dy * ca)
        return perp < bm['w'] / 2 + pad

    def update_beams(self):
        for bm in self.beams:
            o = bm.get('owner')
            if o is not None and 'follow' in bm:
                bm['x'], bm['y'] = o.beam_origin(bm['follow'])
            if 'spin' in bm:
                bm['a'] += bm['spin']
            bm['life'] -= 1
        self.beams = [bm for bm in self.beams if bm['life'] > 0]

    # ================================================================ finish
    def kill_pct(self):
        total = self.stats['kills'] + self.stats['escaped']
        return 100.0 if total == 0 else 100.0 * self.stats['kills'] / total

    def challenge_status(self, ch):
        """Returns (done, failed, progress_text)."""
        cid = ch['id']
        st = self.stats
        finished = self.state in ('outro', 'clear') or self.result is not None
        if cid == 'nodamage':
            failed = 'nodamage' in self.challenge_fail
            return (finished and not failed), failed, ''
        if cid == 'nobomb':
            failed = 'nobomb' in self.challenge_fail
            return (finished and not failed), failed, ''
        if cid == 'kills':
            pct = self.kill_pct()
            return (finished and pct >= ch['target']), False, '%d%%' % int(pct)
        if cid == 'combo':
            return st['best_combo'] >= ch['target'], False, '%d/%d' % (min(st['best_combo'], ch['target']), ch['target'])
        if cid == 'graze':
            return st['grazes'] >= ch['target'], False, '%d/%d' % (min(st['grazes'], ch['target']), ch['target'])
        if cid == 'parts':
            return st['parts'] >= ch['target'], False, '%d/%d' % (min(st['parts'], ch['target']), ch['target'])
        if cid == 'golden':
            return st['golden'], False, ''
        if cid == 'bosstime':
            secs = self.boss_t / 60.0
            failed = secs > ch['target']
            done = finished and not failed and self.boss_t > 0
            return done, failed, ('%dS' % int(secs)) if self.boss is not None else ''
        return False, False, ''

    def finish(self):
        stars = 0
        done_list = []
        for i, ch in enumerate(self.plan.challenges):
            done, failed, _ = self.challenge_status(ch)
            if done and not failed:
                stars |= (1 << i)
            done_list.append(bool(done and not failed))
        dmult = self.diff['credits']
        clear_bonus = int(40 * dmult)
        star_bonus = int(25 * dmult * sum(done_list))
        self.result = dict(
            level=self.level, score=self.score, kills=self.stats['kills'],
            kill_pct=self.kill_pct(), best_combo=self.stats['best_combo'], max_mult=self.stats['max_mult'],
            grazes=self.stats['grazes'], damage=self.stats['damage'], bombs=self.stats['bombs'],
            parts=self.stats['parts'], golden=self.stats['golden'], boss_time=self.stats['boss_time'],
            run_credits=self.run_credits, clear_bonus=clear_bonus, star_bonus=star_bonus,
            challenges=[dict(c) for c in self.plan.challenges], challenge_done=done_list, stars=stars,
            end_kind=self.plan.end_kind,
        )
        self.app.level_complete(self.result)

    # ================================================================ drawing
    def draw(self, screen):
        pf = self.pf
        self.bg.draw(pf, self.frame)
        self.hazards.draw_back(pf)
        for pk in self.pickups:
            pk.draw(pf, self.frame)
        for e in self.enemies:
            if e.ground:
                e.draw(pf)
        if self.boss is not None:
            self.boss.draw(pf)
        for e in self.enemies:
            if not e.ground:
                e.draw(pf)
        self.hazards.draw_mid(pf)
        B.draw_player_bullets(pf, self.pbullets)
        self.player.draw(pf)
        self.fx.draw(pf)
        self.draw_beams(pf)
        B.draw_enemy_bullets(pf, self.ebullets)
        self.hazards.draw_front(pf)
        self.draw_telegraphs(pf)
        self.fx.draw_flash(pf)
        out = pygame.transform.flip(pf, True, False) if self.mirror_x else pf
        # text overlays go on after the mirror flip so they always read correctly
        self.fx.draw_popups(out, self.mirror_x)
        if self.boss is not None and self.boss.alive and self.state == 'boss':
            hud.draw_boss_bar(out, self.boss)
        self.draw_banners(out)
        if self.frame < self.intro_frames + 60 and self.state == 'waves':
            hud.draw_intro_card(out, self)
        p = self.player
        if p.alive and p.hp == 1 and p.shield == 0 and (self.frame // 20) % 2 == 0:
            for i, c in enumerate(((200, 20, 40), (120, 10, 30))):
                pygame.draw.rect(out, c, (i, i, PF_W - i * 2, PF_H - i * 2), 1)
        ox, oy = self.fx.offset()
        screen.fill((0, 0, 0))
        screen.blit(out, (PF_X + ox, oy))
        hud.draw_panels(screen, self)
        if self.paused:
            hud.draw_menu_overlay(screen, 'PAUSED', self.pause_options(), self.menu_sel,
                                  'RUN CREDITS ARE LOST IF YOU QUIT OR RETRY')
        elif self.state == 'over':
            hud.draw_menu_overlay(screen, 'SHIP DESTROYED', ['RETRY', 'HANGAR'], self.menu_sel,
                                  'CREDITS FROM THIS RUN WERE LOST', (255, 80, 80))

    def draw_beams(self, surf):
        for bm in self.beams:
            ca, sa = math.cos(bm['a']), math.sin(bm['a'])
            x2 = bm['x'] + ca * bm['len']
            y2 = bm['y'] + sa * bm['len']
            warm = bm['life'] > bm['max'] - 6
            frac = bm['life'] / bm['max']
            w = bm['w'] if not warm else max(1, bm['w'] // 4)
            if frac < 0.15:
                w = max(1, int(w * frac / 0.15))
            p1 = (int(bm['x']), int(bm['y']))
            p2 = (int(x2), int(y2))
            pygame.draw.line(surf, art.scale(bm['color'], 0.6), p1, p2, w + 4)
            pygame.draw.line(surf, bm['color'], p1, p2, w + 1)
            pygame.draw.line(surf, WHITE, p1, p2, max(1, w // 2))
            pygame.draw.circle(surf, WHITE, p1, w // 2 + 3)

    def draw_telegraphs(self, surf):
        f = self.frame
        for t in self.telegraphs:
            frac = t['life'] / t['max']
            blink = (f // (2 if frac < 0.35 else 4)) % 2 == 0
            if not blink:
                continue
            col = t['color']
            if t['kind'] == 'line':
                o = t.get('follow')
                if o is not None and o.alive:
                    t['x'], t['y'] = o.x, o.y
                x2 = t['x'] + math.cos(t['a']) * t['len']
                y2 = t['y'] + math.sin(t['a']) * t['len']
                w = t.get('w', 1) + (1 if frac < 0.35 else 0)
                pygame.draw.line(surf, col, (int(t['x']), int(t['y'])), (int(x2), int(y2)), w)
            elif t['kind'] == 'circle':
                r = int(t['r'])
                pygame.draw.circle(surf, col, (int(t['x']), int(t['y'])), r, 1)
                inner = int(r * (1 - frac))
                if inner > 1:
                    pygame.draw.circle(surf, col, (int(t['x']), int(t['y'])), inner, 1)
            elif t['kind'] == 'rect':
                pygame.draw.rect(surf, col, t['rect'], 1)
                r = t['rect']
                for i in range(r.left, r.right, 8):
                    pygame.draw.line(surf, col, (i, r.top), (min(r.right, i + 4), r.top + 4))
            elif t['kind'] == 'arrow':
                x, y = int(t['x']), int(t['y'])
                pygame.draw.polygon(surf, col, [(x, y - 7), (x - 5, y), (x + 5, y)])
                art.text(surf, '!', x - 1, y - 6, WHITE, 1, shadow=None)

    def draw_banners(self, surf):
        y = 120
        for text, color, life, mx, sc in self.banners:
            t = mx - life
            slide = min(1.0, t / 10.0)
            if life < 12:
                slide = life / 12.0
            ts = art.big_text(text, sc, art.mix(color, WHITE, 0.5), color)
            w = ts.get_width()
            x = PF_W / 2 - w / 2 + (1 - slide) * (PF_W if (t // 1) % 2 == 0 else -PF_W) * 0.3
            if text in ('WARNING', 'INCOMING') and (life // 8) % 2 == 0:
                pygame.draw.rect(surf, (120, 0, 20), (0, y - 4, PF_W, ts.get_height() + 8))
                pygame.draw.line(surf, (255, 60, 60), (0, y - 4), (PF_W, y - 4))
                pygame.draw.line(surf, (255, 60, 60), (0, y + ts.get_height() + 3), (PF_W, y + ts.get_height() + 3))
            surf.blit(ts, (int(x), y))
            y += ts.get_height() + 6
