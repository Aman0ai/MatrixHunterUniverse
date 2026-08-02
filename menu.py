"""
menu.py
=======
All menu and overlay screens:
  • LoadingScreen   — animated progress bar
  • MainMenu        — matrix rain + pulsing title + nav buttons
  • GameSelectScreen— 4 neon game cards
  • PauseMenu       — semi-transparent overlay
  • SettingsScreen  — sliders + toggles
  • HighScoreScreen — top-score table
  • GameOverScreen  — result card
"""

from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Tuple

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TITLE, VERSION,
    BLACK, WHITE, DARK_BG, DARK_PANEL, DARK_GRAY, MID_GRAY,
    MATRIX_GREEN, MATRIX_DIM, NEON_CYAN, NEON_RED, NEON_ORANGE,
    NEON_YELLOW, NEON_PURPLE, GOLD, MATRIX_DARK,
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_XLARGE, FONT_TITLE,
    GameID, GAME_DESCRIPTIONS, GAME_COLOURS, LEVEL_THEMES,
)
from animation import MatrixRain
from ui import Button, draw_text, draw_glow_text, get_bold_font, ProgressBar


# ─────────────────────────────────────────────────────────────────────────────
#  Utility: draw a rounded panel with optional glow border
# ─────────────────────────────────────────────────────────────────────────────

def _draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    bg: Tuple[int,int,int] = DARK_PANEL,
    border: Tuple[int,int,int] = MATRIX_GREEN,
    radius: int = 12,
    alpha: int = 220,
) -> None:
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*bg, alpha), (0, 0, rect.width, rect.height), border_radius=radius)
    pygame.draw.rect(panel, (*border, 255), (0, 0, rect.width, rect.height), 2, border_radius=radius)
    surface.blit(panel, (rect.x, rect.y))


# ─────────────────────────────────────────────────────────────────────────────
#  Slider widget (for settings)
# ─────────────────────────────────────────────────────────────────────────────

class Slider:
    def __init__(
        self,
        x: int, y: int, width: int,
        label: str,
        value: float = 0.5,
        min_v: float = 0.0,
        max_v: float = 1.0,
        colour: Tuple[int,int,int] = MATRIX_GREEN,
    ) -> None:
        self._track  = pygame.Rect(x, y + 14, width, 8)
        self._label  = label
        self.value   = value
        self._min    = min_v
        self._max    = max_v
        self._col    = colour
        self._drag   = False

    @property
    def _handle_x(self) -> int:
        ratio = (self.value - self._min) / max(1e-6, self._max - self._min)
        return int(self._track.x + ratio * self._track.width)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hx = self._handle_x
            handle_r = pygame.Rect(hx - 10, self._track.y - 6, 20, 20)
            if handle_r.collidepoint(event.pos) or self._track.collidepoint(event.pos):
                self._drag = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self._drag = False
        elif event.type == pygame.MOUSEMOTION and self._drag:
            rx = event.pos[0] - self._track.x
            ratio = max(0.0, min(1.0, rx / max(1, self._track.width)))
            self.value = self._min + ratio * (self._max - self._min)
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        # Track
        pygame.draw.rect(surface, DARK_GRAY, self._track, border_radius=4)
        # Fill
        fill_w = self._handle_x - self._track.x
        if fill_w > 0:
            pygame.draw.rect(surface, self._col,
                             (self._track.x, self._track.y, fill_w, 8), border_radius=4)
        # Handle
        hx = self._handle_x
        pygame.draw.circle(surface, self._col,     (hx, self._track.centery), 10)
        pygame.draw.circle(surface, WHITE,          (hx, self._track.centery), 10, 2)
        # Label
        draw_text(surface, self._label, self._track.x, self._track.y - 18,
                  FONT_SMALL, WHITE)
        draw_text(surface, f"{self.value:.0%}" if self._max == 1.0 else f"{self.value:.1f}",
                  self._track.right, self._track.y - 18, FONT_SMALL,
                  self._col, anchor="topright")


# ─────────────────────────────────────────────────────────────────────────────
#  LoadingScreen
# ─────────────────────────────────────────────────────────────────────────────

class LoadingScreen:
    """Full-screen loading screen with matrix rain and progress bar."""

    DURATION = 2.5   # seconds

    def __init__(self) -> None:
        self._rain    = MatrixRain()
        self._elapsed = 0.0
        self._bar     = ProgressBar(SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2 + 60,
                                    400, 16, MATRIX_GREEN, label="LOADING…")
        self._done    = False
        self._chars   = "INITIALIZING MATRIX HUNTER UNIVERSE v1.0"
        self._shown   = 0
        self._char_t  = 0.0

    @property
    def done(self) -> bool:
        return self._done

    def update(self, dt: float) -> None:
        self._elapsed   += dt
        self._bar.progress = min(1.0, self._elapsed / self.DURATION)
        self._char_t    += dt
        if self._char_t > 0.04 and self._shown < len(self._chars):
            self._shown   += 1
            self._char_t  = 0.0
        self._rain.update(dt)
        if self._elapsed >= self.DURATION:
            self._done = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)
        draw_glow_text(surface, TITLE,
                       SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 60,
                       FONT_XLARGE, MATRIX_GREEN, glow_radius=10)
        draw_text(surface, self._chars[:self._shown],
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20,
                  FONT_SMALL, NEON_CYAN, anchor="midtop")
        self._bar.draw(surface)
        draw_text(surface, f"v{VERSION}",
                  SCREEN_WIDTH - 10, SCREEN_HEIGHT - 18,
                  FONT_SMALL, DARK_GRAY, anchor="bottomright")


# ─────────────────────────────────────────────────────────────────────────────
#  MainMenu
# ─────────────────────────────────────────────────────────────────────────────

class MainMenu:
    """Animated main menu with matrix rain, glowing title and navigation."""

    def __init__(self, on_play: Callable, on_avatar: Callable, on_scores: Callable,
                 on_shop: Callable, on_achievements: Callable,
                 on_settings: Callable, on_quit: Callable) -> None:
        self._rain  = MatrixRain()
        self._time  = 0.0
        self._alpha_in = 0.0   # fade in

        cy = SCREEN_HEIGHT // 2 + 20
        bw, bh, gap = 260, 48, 10
        bw2 = 126
        cx = SCREEN_WIDTH // 2

        self._buttons = [
            Button(cx, cy - gap, bw, bh, "PLAY", on_play, MATRIX_GREEN, BLACK, FONT_LARGE, "▶", "center"),
            # Row 1
            Button(cx - 67, cy + bh, bw2, bh, "AVATAR", on_avatar, GOLD, BLACK, FONT_MEDIUM, "👤", "center"),
            Button(cx + 67, cy + bh, bw2, bh, "SHOP", on_shop, NEON_PURPLE, BLACK, FONT_MEDIUM, "🛒", "center"),
            # Row 2
            Button(cx - 67, cy + bh*2 + gap, bw2, bh, "SCORES", on_scores, NEON_CYAN, BLACK, FONT_MEDIUM, "🏆", "center"),
            Button(cx + 67, cy + bh*2 + gap, bw2, bh, "AWARDS", on_achievements, NEON_YELLOW, BLACK, FONT_MEDIUM, "🏅", "center"),
            # Row 3
            Button(cx - 67, cy + bh*3 + gap*2, bw2, bh, "SETTINGS", on_settings, NEON_ORANGE, BLACK, FONT_MEDIUM, "⚙", "center"),
            Button(cx + 67, cy + bh*3 + gap*2, bw2, bh, "QUIT", on_quit, NEON_RED, BLACK, FONT_MEDIUM, "✕", "center"),
        ]

        # Floating matrix symbols around title
        self._floaters: List[dict] = [
            {
                "char": random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(0, SCREEN_HEIGHT * 0.45),
                "vy": random.uniform(10, 30),
                "alpha": random.randint(40, 120),
                "col": random.choice([MATRIX_GREEN, NEON_CYAN, NEON_PURPLE]),
                "size": random.choice([FONT_SMALL, FONT_MEDIUM]),
            }
            for _ in range(18)
        ]

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        for btn in self._buttons:
            if btn.handle_event(event):
                sound.play("menu_click")
            elif event.type == pygame.MOUSEMOTION and btn.rect.collidepoint(event.pos):
                sound.play("menu_hover")

    def update(self, dt: float) -> None:
        self._rain.update(dt)
        self._time       += dt
        self._alpha_in    = min(1.0, self._alpha_in + dt * 1.5)
        for btn in self._buttons:
            btn.update(dt)
        for f in self._floaters:
            f["y"] += f["vy"] * dt
            if f["y"] > SCREEN_HEIGHT * 0.5:
                f["y"]    = -20
                f["char"] = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)

        # Floating chars
        font_sm = get_bold_font(FONT_SMALL)
        for f in self._floaters:
            txt = font_sm.render(f["char"], True, f["col"])
            txt.set_alpha(f["alpha"])
            surface.blit(txt, (int(f["x"]), int(f["y"])))

        # Title glow
        pulse = int(10 + 4 * math.sin(self._time * 2))
        draw_glow_text(surface, "MATRIX HUNTER",
                       SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 - 20,
                       FONT_TITLE, MATRIX_GREEN, glow_radius=pulse)
        draw_glow_text(surface, "UNIVERSE",
                       SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 + 66,
                       FONT_XLARGE, NEON_CYAN, glow_radius=6)

        # Subtitle
        draw_text(surface, "4 MINI-GAMES  ·  MATRIX MECHANICS  ·  ENDLESS ACTION",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 + 118,
                  FONT_SMALL, NEON_PURPLE, anchor="midtop")

        # Separator line
        lx = SCREEN_WIDTH // 2
        pygame.draw.line(surface, MATRIX_GREEN, (lx - 200, SCREEN_HEIGHT // 2 + 6),
                         (lx + 200, SCREEN_HEIGHT // 2 + 6), 1)

        # Buttons
        alpha_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for btn in self._buttons:
            btn.draw(alpha_surf)
        alpha_surf.set_alpha(int(255 * self._alpha_in))
        surface.blit(alpha_surf, (0, 0))

        # Version
        draw_text(surface, f"v{VERSION}", SCREEN_WIDTH - 10, SCREEN_HEIGHT - 18,
                  FONT_SMALL, DARK_GRAY, anchor="bottomright")


# ─────────────────────────────────────────────────────────────────────────────
#  GameSelectScreen
# ─────────────────────────────────────────────────────────────────────────────

class GameSelectScreen:
    """4 neon game-selection cards with hover animation and back button."""

    CARD_W = 260
    CARD_H = 320
    GAP    = 28

    def __init__(
        self,
        on_select: Callable[[GameID], None],
        on_back:   Callable,
        save_mgr,
    ) -> None:
        self._on_select = on_select
        self._save      = save_mgr
        self._time      = 0.0
        self._hovered   = -1

        total_w = len(GameID) * self.CARD_W + (len(GameID)-1) * self.GAP
        start_x = (SCREEN_WIDTH - total_w) // 2
        cy = SCREEN_HEIGHT // 2 - self.CARD_H // 2 + 20

        self._cards: List[dict] = []
        for i, gid in enumerate(GameID):
            cx = start_x + i * (self.CARD_W + self.GAP)
            self._cards.append({
                "gid":   gid,
                "rect":  pygame.Rect(cx, cy, self.CARD_W, self.CARD_H),
                "hover": 0.0,
                "col":   GAME_COLOURS[gid],
                "label": gid.value,
                "desc":  GAME_DESCRIPTIONS[gid],
                "best":  save_mgr.get_best_score(gid),
            })

        self._back_btn = Button(
            SCREEN_WIDTH // 2, SCREEN_HEIGHT - 36,
            160, 40, "BACK", on_back,
            DARK_GRAY, WHITE, FONT_SMALL, "◀", "center"
        )
        self._rain = MatrixRain()

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = -1
            for i, card in enumerate(self._cards):
                if card["rect"].collidepoint(event.pos):
                    self._hovered = i
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for card in self._cards:
                if card["rect"].collidepoint(event.pos):
                    sound.play("menu_click")
                    self._on_select(card["gid"])
                    return
        self._back_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._rain.update(dt)
        self._time += dt
        for i, card in enumerate(self._cards):
            target = 1.0 if i == self._hovered else 0.0
            card["hover"] += (target - card["hover"]) * min(1.0, dt * 10)
        self._back_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)

        draw_glow_text(surface, "SELECT GAME",
                       SCREEN_WIDTH // 2, 28,
                       FONT_XLARGE, MATRIX_GREEN, glow_radius=8)

        for card in self._cards:
            h = card["hover"]
            col = card["col"]
            rect: pygame.Rect = card["rect"]

            # Hover lift
            lift  = int(h * 14)
            r     = pygame.Rect(rect.x, rect.y - lift, rect.width, rect.height)

            # Card shadow
            shadow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
            pygame.draw.rect(shadow, (*col, int(30 + h*80)),
                             (10, 10, rect.width, rect.height), border_radius=14)
            surface.blit(shadow, (r.x - 10, r.y + 10))

            # Panel
            _draw_panel(surface, r, DARK_PANEL, col, alpha=int(200 + h*55))

            # Game icon (large letter + number)
            icon_char = card["gid"].name[0]
            draw_glow_text(surface, icon_char,
                           r.centerx, r.y + 55,
                           FONT_XLARGE, col, glow_radius=6)

            # Title
            draw_text(surface, card["label"], r.centerx, r.y + 105,
                      FONT_MEDIUM, WHITE, bold=True, anchor="midtop")

            # Description (word-wrapped manually)
            lines = card["desc"].split("\n")
            for li, line in enumerate(lines):
                draw_text(surface, line, r.centerx, r.y + 138 + li * 20,
                          FONT_SMALL, col, anchor="midtop")

            # Best score
            best = card["best"]
            draw_text(surface, f"BEST: {best:,}", r.centerx, r.bottom - 38,
                      FONT_SMALL, GOLD, anchor="midtop")

            # Play hint
            if h > 0.1:
                draw_glow_text(surface, "▶ PLAY",
                               r.centerx, r.bottom - 18,
                               FONT_MEDIUM, col, glow_radius=4, anchor="midbottom")

        self._back_btn.draw(surface)


# ─────────────────────────────────────────────────────────────────────────────
#  LevelSelectScreen
# ─────────────────────────────────────────────────────────────────────────────

class LevelSelectScreen:
    """Select a level (1-5) for the chosen game."""

    def __init__(
        self,
        game_id: GameID,
        on_select: Callable[[int], None],
        on_back: Callable,
        save_mgr,
    ) -> None:
        self._game_id   = game_id
        self._on_select = on_select
        self._on_back   = on_back
        self._save      = save_mgr
        
        self._unlocked_level = self._save.get_unlocked_level(game_id)
        self._hovered = -1
        
        cy_row1 = SCREEN_HEIGHT // 2 - 90
        bw, bh, gap = 120, 120, 20
        total_w_row1 = 6 * bw + 5 * gap
        start_x_row1 = (SCREEN_WIDTH - total_w_row1) // 2

        cy_row2 = SCREEN_HEIGHT // 2 + 50
        total_w_row2 = 5 * bw + 4 * gap
        start_x_row2 = (SCREEN_WIDTH - total_w_row2) // 2

        self._cards = []
        for i in range(1, 12):
            if i <= 6:
                cx = start_x_row1 + (i - 1) * (bw + gap)
                cy = cy_row1
            else:
                cx = start_x_row2 + (i - 7) * (bw + gap)
                cy = cy_row2
                
            self._cards.append({
                "level": i,
                "rect": pygame.Rect(cx, cy, bw, bh),
                "unlocked": i <= self._unlocked_level,
                "hover": 0.0
            })

        self._back_btn = Button(
            SCREEN_WIDTH // 2, SCREEN_HEIGHT - 36,
            160, 40, "BACK", on_back,
            DARK_GRAY, WHITE, FONT_SMALL, "◀", "center"
        )
        self._rain = MatrixRain()

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = -1
            for i, card in enumerate(self._cards):
                if card["rect"].collidepoint(event.pos):
                    self._hovered = i
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for card in self._cards:
                if card["rect"].collidepoint(event.pos) and card["unlocked"]:
                    sound.play("menu_click")
                    self._on_select(card["level"])
                    return
        self._back_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._rain.update(dt)
        for i, card in enumerate(self._cards):
            target = 1.0 if (i == self._hovered and card["unlocked"]) else 0.0
            card["hover"] += (target - card["hover"]) * min(1.0, dt * 10)
        self._back_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)

        draw_glow_text(surface, f"{self._game_id.value.upper()} - LEVELS",
                       SCREEN_WIDTH // 2, 80,
                       FONT_LARGE, GAME_COLOURS[self._game_id], glow_radius=8)

        # Draw connecting data-link paths
        for i in range(len(self._cards) - 1):
            c1 = self._cards[i]
            c2 = self._cards[i + 1]
            r1 = c1["rect"]
            r2 = c2["rect"]
            p1 = (r1.centerx, r1.centery)
            p2 = (r2.centerx, r2.centery)
            
            if c2["unlocked"]:
                col = LEVEL_THEMES[c2["level"]]
                pygame.draw.line(surface, col, p1, p2, 4)
                pygame.draw.circle(surface, col, p1, 6)
                pygame.draw.circle(surface, col, p2, 6)
            else:
                pygame.draw.line(surface, DARK_GRAY, p1, p2, 2)

        pulse = abs(math.sin(pygame.time.get_ticks() / 300.0))

        for card in self._cards:
            h = card["hover"]
            rect: pygame.Rect = card["rect"]
            is_unlocked = card["unlocked"]
            lvl = card["level"]
            
            lift = int(h * 10)
            r = pygame.Rect(rect.x, rect.y - lift, rect.width, rect.height)
            
            col = LEVEL_THEMES[lvl] if is_unlocked else MID_GRAY
            bg  = DARK_PANEL if is_unlocked else (30, 30, 30)
            
            _draw_panel(surface, r, bg, col, alpha=200 if is_unlocked else 100)
            
            # Pulse the active level
            if is_unlocked and lvl == self._unlocked_level:
                glow_col = tuple(int(c * pulse) for c in col)
                pygame.draw.rect(surface, glow_col, r, 3, border_radius=12)
            
            if lvl == 11:
                draw_text(surface, "XI", r.centerx, r.centery - 16, FONT_XLARGE, MATRIX_DARK if is_unlocked else col, anchor="center")
                draw_text(surface, "ARCHITECT", r.centerx, r.centery + 10, FONT_SMALL, MATRIX_DARK if is_unlocked else col, anchor="center")
            else:
                draw_text(surface, str(lvl), r.centerx, r.centery - 10, FONT_XLARGE, col, anchor="center")
                
            if not is_unlocked:
                draw_text(surface, "LOCKED", r.centerx, r.bottom - 20, FONT_SMALL, NEON_RED, anchor="center")
            elif lvl < self._unlocked_level:
                draw_text(surface, "CLEARED", r.centerx, r.bottom - 20, FONT_SMALL, MATRIX_GREEN, anchor="center")
                
        self._back_btn.draw(surface)


# ─────────────────────────────────────────────────────────────────────────────
#  PauseMenu
# ─────────────────────────────────────────────────────────────────────────────

class PauseMenu:
    """Semi-transparent overlay with resume, settings, and quit options."""

    def __init__(
        self,
        on_resume: Callable,
        on_settings: Callable,
        on_quit: Callable,
    ) -> None:
        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2 - 40
        bw, bh, gap = 220, 48, 14

        self._buttons = [
            Button(cx, cy,             bw, bh, "RESUME",   on_resume,
                   MATRIX_GREEN, BLACK, FONT_LARGE, "▶", "center"),
            Button(cx, cy + bh+gap,    bw, bh, "SETTINGS", on_settings,
                   NEON_CYAN,    BLACK, FONT_MEDIUM, "⚙", "center"),
            Button(cx, cy+(bh+gap)*2,  bw, bh, "QUIT GAME",on_quit,
                   NEON_RED,     BLACK, FONT_MEDIUM, "✕", "center"),
        ]
        self._overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, 160))

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        for btn in self._buttons:
            if btn.handle_event(event):
                sound.play("menu_click")

    def update(self, dt: float) -> None:
        for btn in self._buttons:
            btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._overlay, (0, 0))
        pw, ph = 300, 300
        panel = pygame.Rect(SCREEN_WIDTH//2 - pw//2,
                            SCREEN_HEIGHT//2 - ph//2, pw, ph)
        _draw_panel(surface, panel, DARK_PANEL, MATRIX_GREEN, alpha=230)
        draw_glow_text(surface, "PAUSED",
                       SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 130,
                       FONT_XLARGE, MATRIX_GREEN, glow_radius=8)
        for btn in self._buttons:
            btn.draw(surface)


# ─────────────────────────────────────────────────────────────────────────────
#  SettingsScreen
# ─────────────────────────────────────────────────────────────────────────────

class SettingsScreen:
    """Full settings page with volume sliders, difficulty, fullscreen toggle."""

    RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)]

    def __init__(self, settings, on_back: Callable, sound) -> None:
        self._settings  = settings
        self._on_back   = on_back
        self._sound     = sound

        cx  = SCREEN_WIDTH  // 2
        col = 240   # left column x
        row = 200   # starting y

        self._sliders = [
            Slider(col, row,       400, "Master Volume", settings.master_volume, colour=MATRIX_GREEN),
            Slider(col, row + 80,  400, "Music Volume",  settings.music_volume,  colour=NEON_CYAN),
            Slider(col, row + 160, 400, "SFX Volume",    settings.sfx_volume,    colour=NEON_ORANGE),
        ]

        bw, bh = 200, 44
        self._buttons = [
            Button(col,       row + 270, bw, bh, f"Difficulty: {settings.difficulty}",
                   self._toggle_diff, NEON_ORANGE, BLACK, FONT_SMALL),
            Button(col + 220, row + 270, bw, bh, f"Fullscreen: {'ON' if settings.fullscreen else 'OFF'}",
                   self._toggle_fs,   NEON_CYAN,   BLACK, FONT_SMALL),
            Button(col,       row + 330, bw, bh, f"FPS Counter: {'ON' if settings.show_fps else 'OFF'}",
                   self._toggle_fps,  MATRIX_GREEN, BLACK, FONT_SMALL),
            Button(col + 220, row + 330, bw, bh, f"Screen Shake: {'ON' if settings.screen_shake else 'OFF'}",
                   self._toggle_shake,NEON_PURPLE, BLACK, FONT_SMALL),
            Button(col,       row + 390, bw, bh, f"Resolution: {settings.resolution[0]}×{settings.resolution[1]}",
                   self._cycle_res,  NEON_YELLOW, BLACK, FONT_SMALL),
            Button(cx,        row + 460, 180, 48, "BACK",
                   self._save_and_back, DARK_GRAY, WHITE, FONT_MEDIUM, anchor="center"),
        ]

    def _toggle_diff(self) -> None:
        self._settings.cycle_difficulty()
        self._buttons[0]._label = f"Difficulty: {self._settings.difficulty}"
        self._sound.play("menu_click")

    def _toggle_fs(self) -> None:
        self._settings.fullscreen = not self._settings.fullscreen
        self._buttons[1]._label = f"Fullscreen: {'ON' if self._settings.fullscreen else 'OFF'}"
        self._sound.play("menu_click")

    def _toggle_fps(self) -> None:
        self._settings.show_fps = not self._settings.show_fps
        self._buttons[2]._label = f"FPS Counter: {'ON' if self._settings.show_fps else 'OFF'}"
        self._sound.play("menu_click")

    def _toggle_shake(self) -> None:
        self._settings.screen_shake = not self._settings.screen_shake
        self._buttons[3]._label = f"Screen Shake: {'ON' if self._settings.screen_shake else 'OFF'}"
        self._sound.play("menu_click")

    def _cycle_res(self) -> None:
        self._settings.cycle_resolution(self.RESOLUTIONS)
        self._buttons[4]._label = f"Resolution: {self._settings.resolution[0]}×{self._settings.resolution[1]}"
        self._sound.play("menu_click")

    def _save_and_back(self) -> None:
        # Flush slider values into settings
        self._settings.master_volume = self._sliders[0].value
        self._settings.music_volume  = self._sliders[1].value
        self._settings.sfx_volume    = self._sliders[2].value
        self._settings.save()
        self._sound.set_sfx_volume(self._settings.effective_sfx)
        self._sound.set_music_volume(self._settings.effective_music)
        self._sound.play("menu_back")
        self._on_back()

    def handle_event(self, event: pygame.event.Event) -> None:
        for s in self._sliders:
            s.handle_event(event)
        for btn in self._buttons:
            btn.handle_event(event)

    def update(self, dt: float) -> None:
        for btn in self._buttons:
            btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(DARK_BG)
        draw_glow_text(surface, "SETTINGS",
                       SCREEN_WIDTH // 2, 40,
                       FONT_XLARGE, MATRIX_GREEN, glow_radius=8)

        for s in self._sliders:
            s.draw(surface)
        for btn in self._buttons:
            btn.draw(surface)

        # Section labels
        draw_text(surface, "AUDIO", 240, 170, FONT_MEDIUM, NEON_CYAN, bold=True)
        draw_text(surface, "GAME",  240, 350, FONT_MEDIUM, NEON_CYAN, bold=True)


# ─────────────────────────────────────────────────────────────────────────────
#  HighScoreScreen
# ─────────────────────────────────────────────────────────────────────────────

class HighScoreScreen:
    """Top-score table for all 4 games."""

    def __init__(self, save_mgr, on_back: Callable) -> None:
        self._save     = save_mgr
        self._mode = "LOCAL"
        self._back_btn = Button(
            SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40,
            160, 40, "BACK", on_back,
            DARK_GRAY, WHITE, FONT_SMALL, "◀", "center"
        )
        self._toggle_btn = Button(
            SCREEN_WIDTH // 2, 75,
            160, 36, "MODE: LOCAL", self._toggle_mode,
            MATRIX_GREEN, BLACK, FONT_SMALL, "🌐", "center"
        )
        self._time = 0.0

    def _toggle_mode(self):
        if self._mode == "LOCAL":
            self._mode = "GLOBAL"
            self._toggle_btn._label = "MODE: GLOBAL"
            self._toggle_btn._colour = NEON_CYAN
        else:
            self._mode = "LOCAL"
            self._toggle_btn._label = "MODE: LOCAL"
            self._toggle_btn._colour = MATRIX_GREEN

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        if self._back_btn.handle_event(event):
            sound.play("menu_back")
        if self._toggle_btn.handle_event(event):
            sound.play("menu_click")

    def update(self, dt: float) -> None:
        self._time += dt
        self._back_btn.update(dt)
        self._toggle_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(DARK_BG)
        draw_glow_text(surface, "HIGH SCORES",
                       SCREEN_WIDTH // 2, 30,
                       FONT_XLARGE, GOLD, glow_radius=8)

        self._toggle_btn.draw(surface)

        col_w = SCREEN_WIDTH // len(list(GameID))
        for gi, gid in enumerate(GameID):
            x  = gi * col_w + col_w // 2
            col = GAME_COLOURS[gid]

            draw_glow_text(surface, gid.value.replace("Matrix ", ""),
                           x, 120, FONT_LARGE, col, glow_radius=4)
            pygame.draw.line(surface, col, (x - col_w//2 + 20, 160),
                             (x + col_w//2 - 20, 160), 1)

            if self._mode == "LOCAL":
                scores = self._save.get_top_scores(gid, 5)
                if not scores:
                    draw_text(surface, "No scores yet", x, 175, FONT_SMALL,
                              DARK_GRAY, anchor="midtop")
                for rank, sc in enumerate(scores, 1):
                    rank_col = GOLD if rank == 1 else (WHITE if rank <= 3 else DARK_GRAY)
                    draw_text(surface, f"#{rank}  {sc:,}", x, 165 + rank * 30,
                              FONT_MEDIUM, rank_col, bold=(rank == 1), anchor="midtop")
            else:
                scores = self._save.get_global_scores(gid, 5)
                for rank, (name, sc) in enumerate(scores, 1):
                    rank_col = GOLD if name == "You" else (WHITE if rank <= 3 else DARK_GRAY)
                    txt = f"#{rank} {name} - {sc:,}"
                    draw_text(surface, txt, x, 165 + rank * 30,
                              FONT_SMALL, rank_col, bold=(name == "You"), anchor="midtop")

        self._back_btn.draw(surface)


# ─────────────────────────────────────────────────────────────────────────────
#  GameOverScreen  /  VictoryScreen
# ─────────────────────────────────────────────────────────────────────────────

class ResultScreen:
    """Shared screen shown after win or lose."""

    def __init__(
        self,
        won: bool,
        score: int,
        game_id: GameID,
        best_score: int,
        on_retry: Callable,
        on_menu: Callable,
        on_next: Optional[Callable] = None,
    ) -> None:
        self._won   = won
        self._score = score
        self._best  = best_score
        self._gid   = game_id
        self._time  = 0.0
        cx          = SCREEN_WIDTH // 2

        bw, bh = 220, 50
        
        self._buttons = []
        if won and on_next:
            self._buttons = [
                Button(cx - bw - 16, SCREEN_HEIGHT // 2 + 120, bw, bh,
                       "NEXT LEVEL", on_next, NEON_CYAN, BLACK, FONT_MEDIUM, anchor="topleft"),
                Button(cx + 16,      SCREEN_HEIGHT // 2 + 120, bw, bh,
                       "MAIN MENU",  on_menu,  DARK_GRAY, WHITE, FONT_MEDIUM, anchor="topleft"),
            ]
        else:
            self._buttons = [
                Button(cx - bw - 16, SCREEN_HEIGHT // 2 + 120, bw, bh,
                       "PLAY AGAIN", on_retry, MATRIX_GREEN if won else NEON_RED, BLACK, FONT_MEDIUM, anchor="topleft"),
                Button(cx + 16,      SCREEN_HEIGHT // 2 + 120, bw, bh,
                       "MAIN MENU",  on_menu,  DARK_GRAY, WHITE, FONT_MEDIUM, anchor="topleft"),
            ]

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        for btn in self._buttons:
            if btn.handle_event(event):
                sound.play("menu_click")

    def update(self, dt: float) -> None:
        self._time += dt
        for btn in self._buttons:
            btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 190))
        surface.blit(ov, (0, 0))

        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        pw, ph = 600, 340
        panel = pygame.Rect(cx - pw//2, cy - ph//2, pw, ph)
        border_col = MATRIX_GREEN if self._won else NEON_RED
        _draw_panel(surface, panel, DARK_PANEL, border_col, alpha=230)

        # Headline
        if self._won:
            draw_glow_text(surface, "MISSION COMPLETE!",
                           cx, cy - 120, FONT_XLARGE, MATRIX_GREEN, glow_radius=10)
        else:
            draw_glow_text(surface, "GAME OVER",
                           cx, cy - 120, FONT_XLARGE, NEON_RED, glow_radius=10)

        # Game name
        draw_text(surface, self._gid.value, cx, cy - 65,
                  FONT_MEDIUM, GAME_COLOURS[self._gid], anchor="midtop")

        # Score
        draw_text(surface, f"SCORE", cx, cy - 20, FONT_SMALL, DARK_GRAY, anchor="midtop")
        draw_glow_text(surface, f"{self._score:,}", cx, cy,
                       FONT_XLARGE, GOLD, glow_radius=4, anchor="center")

        # Best
        new_best = self._score >= self._best and self._best > 0 or (self._best == 0 and self._score > 0)
        best_col = NEON_YELLOW if new_best else DARK_GRAY
        best_txt = f"NEW BEST!" if new_best else f"Best: {self._best:,}"
        draw_text(surface, best_txt, cx, cy + 50, FONT_MEDIUM, best_col, anchor="midtop")

        for btn in self._buttons:
            btn.draw(surface)

# ─────────────────────────────────────────────────────────────────────────────
#  AvatarSelectScreen
# ─────────────────────────────────────────────────────────────────────────────

class AvatarSelectScreen:
    """Screen to select between different avatar shapes and images."""

    def __init__(self, settings, on_back: Callable, sound) -> None:
        self._settings = settings
        self._on_back  = on_back
        self._sound    = sound
        self._time     = 0.0
        self._rain     = MatrixRain()
        
        cx = SCREEN_WIDTH // 2
        cy = 180
        bw, bh, gap = 300, 50, 15

        self.options = [
            ("Default Vector", "shape", "default"),
            ("Square Shape", "shape", "square"),
            ("Circle Shape", "shape", "circle"),
            ("Triangle Shape", "shape", "triangle"),
            ("Image: Cyber Punk", "image", "assets/avatar1.png"),
            ("Image: Neon Ninja", "image", "assets/avatar2.png")
        ]

        self._buttons = []
        for i, (label, atype, avalue) in enumerate(self.options):
            b = Button(cx, cy + i * (bh + gap), bw, bh, label,
                       lambda idx=i: self._select_avatar(idx),
                       NEON_CYAN, BLACK, FONT_SMALL, anchor="center")
            self._buttons.append(b)
            
        self._back_btn = Button(
            cx, SCREEN_HEIGHT - 60, 160, 48, "BACK",
            self._save_and_back, DARK_GRAY, WHITE, FONT_MEDIUM, anchor="center"
        )
        
        self._update_button_colors()

    def _update_button_colors(self):
        curr_type = self._settings.avatar_type
        curr_val = self._settings.avatar_value
        for i, (label, atype, avalue) in enumerate(self.options):
            if atype == curr_type and avalue == curr_val:
                self._buttons[i]._col = GOLD
            else:
                self._buttons[i]._col = NEON_CYAN

    def _select_avatar(self, idx: int) -> None:
        _, atype, avalue = self.options[idx]
        self._settings.avatar_type = atype
        self._settings.avatar_value = avalue
        self._sound.play("menu_click")
        self._update_button_colors()

    def _save_and_back(self) -> None:
        self._settings.save()
        self._sound.play("menu_back")
        self._on_back()

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        for btn in self._buttons:
            if btn.handle_event(event):
                sound.play("menu_click")
        self._back_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._time += dt
        self._rain.update(dt)
        for btn in self._buttons:
            btn.update(dt)
        self._back_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)
        
        draw_glow_text(surface, "SELECT AVATAR",
                       SCREEN_WIDTH // 2, 80,
                       FONT_XLARGE, GOLD, glow_radius=8)

        for btn in self._buttons:
            btn.draw(surface)
            
        # Draw a small preview if it's an image
        curr_type = self._settings.avatar_type
        curr_val = self._settings.avatar_value
        preview_x = SCREEN_WIDTH // 2 + 250
        preview_y = 180
        
        draw_text(surface, "PREVIEW", preview_x, preview_y - 30, FONT_MEDIUM, GOLD, anchor="center")
        
        from games.common import AvatarRenderer
        # Draw the avatar at 100x100
        drawn = AvatarRenderer.draw_avatar(surface, preview_x, preview_y + 80, 100, 100, self._settings, MATRIX_GREEN)
        if not drawn:
            draw_text(surface, "?", preview_x, preview_y + 80, FONT_XLARGE, MATRIX_GREEN, anchor="center")
            
        self._back_btn.draw(surface)


# ─────────────────────────────────────────────────────────────────────────────
#  ShopScreen
# ─────────────────────────────────────────────────────────────────────────────

class ShopScreen:
    def __init__(self, save_mgr, sound, on_back: Callable) -> None:
        self._save = save_mgr
        self._sound = sound
        self._on_back = on_back
        self._rain = MatrixRain()
        self._time = 0.0
        self._buttons = []
        
        self.items = [
            {"id": "cyan_bullets", "title": "Cyan Bullets", "desc": "Cosmetic override", "cost": 300},
            {"id": "max_health_plus", "title": "Max Health +50", "desc": "Start with 150 HP", "cost": 1000},
            {"id": "starting_combo", "title": "Combo Initiate", "desc": "Start with 2x Combo", "cost": 500},
        ]
        
        self._back_btn = Button(
            SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60, 160, 48, "BACK",
            self._save_and_back, DARK_GRAY, WHITE, FONT_MEDIUM, anchor="center"
        )
        self._refresh_buttons()

    def _refresh_buttons(self):
        self._buttons.clear()
        cx = SCREEN_WIDTH // 2
        cy = 200
        unlocked = self._save.get_unlocked_items()
        
        for i, item in enumerate(self.items):
            is_unlocked = item["id"] in unlocked
            col = DARK_GRAY if is_unlocked else NEON_PURPLE
            text = "UNLOCKED" if is_unlocked else f"BUY ({item['cost']})"
            
            b = Button(cx + 180, cy + i * 70, 140, 40, text,
                       lambda idx=i: self._buy_item(idx),
                       col, WHITE if not is_unlocked else BLACK, FONT_SMALL, anchor="center")
            self._buttons.append(b)

    def _buy_item(self, idx: int) -> None:
        item = self.items[idx]
        if item["id"] in self._save.get_unlocked_items():
            self._sound.play("menu_error")
            return
            
        if self._save.spend_coins(item["cost"]):
            self._save.unlock_item(item["id"])
            self._sound.play("powerup")
            self._refresh_buttons()
        else:
            self._sound.play("menu_error")

    def _save_and_back(self) -> None:
        self._sound.play("menu_back")
        self._on_back()

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        for btn in self._buttons:
            if btn.handle_event(event):
                sound.play("menu_click")
        self._back_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._time += dt
        self._rain.update(dt)
        for btn in self._buttons:
            btn.update(dt)
        self._back_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)
        
        draw_glow_text(surface, "HACKER SHOP", SCREEN_WIDTH // 2, 80, FONT_XLARGE, NEON_PURPLE, glow_radius=8)
        
        coins = self._save.get_coins()
        draw_text(surface, f"YOUR COINS: {coins:,}", SCREEN_WIDTH // 2, 130, FONT_MEDIUM, GOLD, anchor="center")
        
        cx = SCREEN_WIDTH // 2
        cy = 200
        
        for i, item in enumerate(self.items):
            iy = cy + i * 70
            draw_text(surface, item["title"], cx - 250, iy - 10, FONT_MEDIUM, WHITE, anchor="midleft")
            draw_text(surface, item["desc"], cx - 250, iy + 15, FONT_SMALL, NEON_CYAN, anchor="midleft")
            
        for btn in self._buttons:
            btn.draw(surface)
            
        self._back_btn.draw(surface)


# ─────────────────────────────────────────────────────────────────────────────
#  AchievementsScreen
# ─────────────────────────────────────────────────────────────────────────────

class AchievementsScreen:
    def __init__(self, save_mgr, sound, on_back: Callable) -> None:
        self._save = save_mgr
        self._sound = sound
        self._on_back = on_back
        self._rain = MatrixRain()
        self._time = 0.0
        
        self._back_btn = Button(
            SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60, 160, 48, "BACK",
            self._save_and_back, DARK_GRAY, WHITE, FONT_MEDIUM, anchor="center"
        )

    def _save_and_back(self) -> None:
        self._sound.play("menu_back")
        self._on_back()

    def handle_event(self, event: pygame.event.Event, sound) -> None:
        self._back_btn.handle_event(event)

    def update(self, dt: float) -> None:
        self._time += dt
        self._rain.update(dt)
        self._back_btn.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        self._rain.draw(surface)
        
        draw_glow_text(surface, "ACHIEVEMENTS", SCREEN_WIDTH // 2, 80, FONT_XLARGE, NEON_YELLOW, glow_radius=8)
        
        cx = SCREEN_WIDTH // 2
        cy = 160
        unlocked = self._save.get_unlocked_achievements()
        
        import achievements
        for i, (ach_id, ach) in enumerate(achievements.ACHIEVEMENTS_DB.items()):
            iy = cy + i * 70
            is_unlocked = ach_id in unlocked
            
            icon = "🏆" if is_unlocked else "🔒"
            col = GOLD if is_unlocked else DARK_GRAY
            title = ach["title"] if is_unlocked else "???"
            desc = ach["desc"] if is_unlocked else "Locked achievement"
            
            draw_text(surface, icon, cx - 220, iy, FONT_LARGE, col, anchor="center")
            draw_text(surface, title, cx - 180, iy - 10, FONT_MEDIUM, col, anchor="midleft")
            draw_text(surface, desc, cx - 180, iy + 15, FONT_SMALL, col if is_unlocked else (50,50,50), anchor="midleft")
            if is_unlocked:
                draw_text(surface, f"Reward: {ach['reward']}", cx + 220, iy, FONT_SMALL, MATRIX_GREEN if is_unlocked else DARK_GRAY, anchor="midright")
            
        self._back_btn.draw(surface)
