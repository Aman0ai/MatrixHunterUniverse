"""
sound_manager.py
================
Audio playback using pre-generated static WAV files.
Numpy dependency has been permanently removed for Android compatibility.
Falls back to silent stubs when files are unavailable or mixer init fails.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

import pygame


class _SilentSound:
    """Stub used when sound generation is unavailable."""
    def play(self, loops: int = 0) -> None:  pass
    def stop(self) -> None:                  pass
    def set_volume(self, v: float) -> None:  pass


# ── SoundManager ─────────────────────────────────────────────────────────────

class SoundManager:
    """
    Generates and caches all game sound effects and music tracks.
    All sounds are loaded from pre-generated .ogg files in assets/sounds/.
    """

    # Channel allocation
    _CH_SFX   = 0
    _CH_MUSIC = 7   # channel used for looped music simulation

    def __init__(self) -> None:
        self._sounds:      Dict[str, pygame.mixer.Sound | _SilentSound] = {}
        self._music_sound: Optional[pygame.mixer.Sound] = None
        self._music_ch:    Optional[pygame.mixer.Channel] = None
        self._sfx_vol:     float = 0.8
        self._music_vol:   float = 0.5
        self._muted:       bool  = False

        if not pygame.mixer.get_init():
            return

        pygame.mixer.set_num_channels(16)
        self._build_all()

    # ── build library ──────────────────────────────────────────────

    def _store(self, name: str) -> None:
        try:
            _BASE = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(_BASE, "assets", "sounds", f"{name}.ogg")
            if os.path.exists(filepath):
                sound = pygame.mixer.Sound(filepath)
                self._sounds[name] = sound
            else:
                print(f"Warning: Sound asset {filepath} not found.")
                self._sounds[name] = _SilentSound()
        except Exception as e:
            print(f"Warning: Failed to load sound {name}: {e}")
            self._sounds[name] = _SilentSound()

    def _build_all(self) -> None:
        """Load every SFX and music cue."""
        sound_names = [
            "menu_click", "menu_hover", "menu_back",
            "pistol", "rifle", "shotgun", "sniper_shot", "reload", "empty_gun",
            "footstep", "key_pickup", "door_open", "alarm", "alarm_off", "stealth", "spotted",
            "laser", "laser2", "explosion", "big_explosion", "powerup", "shield_hit", "warp",
            "jump", "land", "slide", "coin", "crash", "speed_up",
            "hit", "player_hit", "death", "boss_roar", "level_up", "game_over", "victory",
            "music_menu", "music_sniper", "music_assassin", "music_space", "music_runner"
        ]
        for name in sound_names:
            self._store(name)

    # ── playback API ──────────────────────────────────────────────

    def play(self, name: str, loops: int = 0) -> None:
        """Play a named sound effect once (or looped)."""
        if self._muted:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        if isinstance(snd, _SilentSound):
            return
        snd.set_volume(self._sfx_vol)
        ch = pygame.mixer.find_channel(True)
        if ch:
            ch.play(snd, loops=loops)

    def play_music(self, name: str) -> None:
        """Start looping background music track (replaces current)."""
        self.stop_music()
        snd = self._sounds.get(name)
        if snd is None or isinstance(snd, _SilentSound) or self._muted:
            return
        ch = pygame.mixer.Channel(self._CH_MUSIC)
        snd.set_volume(self._music_vol)
        ch.play(snd, loops=-1)
        self._music_ch = ch

    def stop_music(self) -> None:
        if self._music_ch:
            self._music_ch.stop()
            self._music_ch = None

    def set_sfx_volume(self, v: float) -> None:
        self._sfx_vol = max(0.0, min(1.0, v))

    def set_music_volume(self, v: float) -> None:
        self._music_vol = max(0.0, min(1.0, v))
        if self._music_ch and self._music_ch.get_busy():
            snd = self._music_ch.get_sound()
            if snd:
                snd.set_volume(self._music_vol)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        if muted:
            self.stop_music()
