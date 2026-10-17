"""Sector mechanics (asteroids, fog, lightning, crystals, flares, corridors,
gravity, nests, wormhole warps). Filled in by the hazard systems below."""
from config import PF_W


class HazardManager:
    def __init__(self, game, hazards):
        self.game = game
        self.hazards = dict(hazards)
        self.systems = []

    def bounds_at(self, y):
        return 0, PF_W

    def corridor_at(self, y):
        return 0, PF_W

    def update(self):
        for s in self.systems:
            s.update()

    def affect_bullets(self):
        pass

    def on_act(self, index, length):
        pass

    def on_breather(self, frames):
        pass

    def end_fight(self):
        pass

    def asteroid_destroyed(self, e):
        pass

    def draw_back(self, surf):
        pass

    def draw_mid(self, surf):
        pass

    def draw_front(self, surf):
        pass
