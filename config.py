"""
config.py
=========
Global configuration constants for Matrix Hunter Universe.
Colours, screen dimensions, game states, paths, physics constants.
"""

from __future__ import annotations

import os
from enum import Enum, auto
from typing import Tuple

# ──────────────────────────── Display ────────────────────────────
SCREEN_WIDTH: int  = 1280
SCREEN_HEIGHT: int = 720
FPS: int           = 60
TITLE: str         = "Matrix Hunter Universe"
VERSION: str       = "1.0.0"

# ──────────────────────────── File Paths ─────────────────────────
import sys as _sys
_ANDROID_DIR = os.environ.get('ANDROID_PRIVATE', None) \
            or os.environ.get('ANDROID_ARGUMENT', None) \
            or os.path.dirname(os.path.abspath(__file__))

BASE_DIR: str       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR: str       = os.path.join(_ANDROID_DIR, "data")
ASSETS_DIR: str     = os.path.join(BASE_DIR, "assets")
HIGHSCORES_FILE: str = os.path.join(DATA_DIR, "highscores.json")
SETTINGS_FILE: str  = os.path.join(DATA_DIR, "settings.json")
SAVE_FILE: str      = os.path.join(DATA_DIR, "save.json")

# ──────────────────────────── Colour Palette ─────────────────────
BLACK          : Tuple[int,int,int] = (  0,   0,   0)
WHITE          : Tuple[int,int,int] = (255, 255, 255)
MATRIX_GREEN   : Tuple[int,int,int] = (  0, 255,  70)
MATRIX_DIM     : Tuple[int,int,int] = (  0, 160,  40)
MATRIX_DARK    : Tuple[int,int,int] = (  0,  60,  20)
NEON_CYAN      : Tuple[int,int,int] = (  0, 255, 255)
NEON_PURPLE    : Tuple[int,int,int] = (180,   0, 255)
NEON_ORANGE    : Tuple[int,int,int] = (255, 140,   0)
NEON_RED       : Tuple[int,int,int] = (255,  30,  50)
NEON_BLUE      : Tuple[int,int,int] = ( 30, 100, 255)
NEON_YELLOW    : Tuple[int,int,int] = (255, 255,   0)
NEON_PINK      : Tuple[int,int,int] = (255,  20, 147)
GOLD           : Tuple[int,int,int] = (255, 215,   0)
DARK_BG        : Tuple[int,int,int] = (  5,   5,  15)
DARK_PANEL     : Tuple[int,int,int] = ( 10,  15,  30)
GRAY           : Tuple[int,int,int] = (128, 128, 128)
DARK_GRAY      : Tuple[int,int,int] = ( 40,  40,  50)
MID_GRAY       : Tuple[int,int,int] = ( 80,  80,  90)
TRANSPARENT    : Tuple[int,int,int,int] = (0, 0, 0, 0)

LEVEL_THEMES = {
    1: MATRIX_GREEN,
    2: NEON_CYAN,
    3: NEON_PURPLE,
    4: NEON_ORANGE,
    5: NEON_RED,
    6: GOLD,
    7: NEON_BLUE,
    8: NEON_PINK,
    9: NEON_YELLOW,
    10: WHITE,
    11: MATRIX_DARK
}

# Alias used by UI widgets
ACCENT = MATRIX_GREEN
ACCENT2 = NEON_CYAN

# ──────────────────────────── Game States ────────────────────────
class GameState(Enum):
    LOADING      = auto()
    MAIN_MENU    = auto()
    GAME_SELECT  = auto()
    LEVEL_SELECT = auto()
    PLAYING      = auto()
    PAUSED       = auto()
    SETTINGS    = auto()
    HIGH_SCORES = auto()
    GAME_OVER   = auto()
    GAME_WIN    = auto()
    AVATAR_SELECT = auto()
    SHOP        = auto()
    ACHIEVEMENTS = auto()

# ──────────────────────────── Game IDs ───────────────────────────
class GameID(Enum):
    SNIPER      = "Matrix Sniper"
    ASSASSIN    = "Matrix Assassin"
    SPACE       = "Matrix Space Battle"
    RUNNER      = "Matrix Runner"

# Map GameID → description shown on selection screen
GAME_DESCRIPTIONS: dict[GameID, str] = {
    GameID.SNIPER:   "Top-down shooter — use rotation\nmatrices to curve your bullets!",
    GameID.ASSASSIN: "Stealth infiltration — mirror\npatrols with reflection matrices!",
    GameID.SPACE:    "Space shooter — matrix formations\nand power-up scaling effects!",
    GameID.RUNNER:   "Endless runner — shear matrices\nadd wild speed-blur warping!",
}

# Map GameID → neon accent colour for its card
GAME_COLOURS: dict[GameID, Tuple[int,int,int]] = {
    GameID.SNIPER:   NEON_RED,
    GameID.ASSASSIN: NEON_CYAN,
    GameID.SPACE:    NEON_PURPLE,
    GameID.RUNNER:   NEON_ORANGE,
}

# ──────────────────────────── Font Sizes ─────────────────────────
FONT_TINY   : int = 14
FONT_SMALL  : int = 18
FONT_MEDIUM : int = 24
FONT_LARGE  : int = 36
FONT_XLARGE : int = 54
FONT_TITLE  : int = 72

# ──────────────────────────── Physics ────────────────────────────
GRAVITY: float = 900.0   # pixels / second²

# ──────────────────────────── Gameplay Tuning ─────────────────────
LIVES: int          = 3      # lives per game session
COMBO_TIMEOUT: float = 2.0  # seconds of no-kill before combo resets
COMBO_MAX: int       = 16   # max combo multiplier cap

# ──────────────────────────── Touch / Mobile ──────────────────────
import pygame as _pg
# Auto-detect Android: sys.getandroidapilevel only exists inside python-for-android.
# On desktop this attribute is absent → TOUCH_ENABLED = False (keyboard + mouse).
# On Android it is always present → TOUCH_ENABLED = True (virtual joystick shown).
import sys as _sys
TOUCH_ENABLED: bool = hasattr(_sys, 'getandroidapilevel')

# ──────────────────────────── Difficulty Presets ─────────────────
class Difficulty(Enum):
    EASY   = "Easy"
    NORMAL = "Normal"
    HARD   = "Hard"

# Enemy speed / health multiplier per difficulty
DIFFICULTY_MULTIPLIER: dict[str, float] = {
    Difficulty.EASY.value:   0.65,
    Difficulty.NORMAL.value: 1.00,
    Difficulty.HARD.value:   1.45,
}
