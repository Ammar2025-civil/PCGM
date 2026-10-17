"""Chiptune sound effects and music (placeholder: silent until the synth is added)."""


class Audio:
    def __init__(self, muted=False):
        self.muted = muted

    def set_muted(self, m):
        self.muted = m

    def sfx(self, name, vol=1.0):
        pass

    def play_music(self, track):
        pass

    def stop_music(self, ms=0):
        pass

    def pause_music(self, paused):
        pass

    def set_intensity(self, level):
        pass

    def jingle(self, name):
        pass

    def update(self):
        pass
