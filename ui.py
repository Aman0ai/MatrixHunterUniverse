"""
ui.py
=====
Reusable HUD widgets: HealthBar, TimerDisplay, ScoreDisplay,
FPSCounter, ProgressBar, MessageQueue, and a generic Button class.
"""

from __future__ import annotations

import math
import time
from typing import Callable, List, Optional, Tuple

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_XLARGE,
    WHITE, BLACK, MATRIX_GREEN, NEON_RED, NEON_CYAN,
    NEON_ORANGE, GOLD, DARK_PANEL, DARK_GRAY, MID_GRAY,
    GRAY, ACCENT, ACCENT2, NEON_YELLOW,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Font cache
# ─────────────────────────────────────────────────────────────────────────────

_font_cache: dict[int, pygame.font.Font] = {}

def get_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        # Try a nice system mono font, fall back to default
        for name in ("Consolas", "Courier New", "Courier", "monospace"):
            try:
                f = pygame.font.SysFont(name, size, bold=False)
                _font_cache[size] = f
                break
            except Exception:
                pass
        else:
            _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


def get_bold_font(size: int) -> pygame.font.Font:
    key = -size
    if key not in _font_cache:
        for name in ("Consolas", "Courier New", "Courier", "monospace"):
            try:
                f = pygame.font.SysFont(name, size, bold=True)
                _font_cache[key] = f
                break
            except Exception:
                pass
        else:
            _font_cache[key] = pygame.font.Font(None, size)
    return _font_cache[key]


def draw_text(
    surface: pygame.Surface,
    text: str,
    x: int, y: int,
    size: int = FONT_MEDIUM,
    colour: Tuple[int,int,int] = WHITE,
    bold: bool = False,
    alpha: int = 255,
    anchor: str = "topleft",
) -> pygame.Rect:
    """Render anti-aliased text at (x,y) with chosen anchor point."""
    font = get_bold_font(size) if bold else get_font(size)
    surf = font.render(text, True, colour)
    if alpha < 255:
        surf.set_alpha(alpha)
    rect = surf.get_rect()
    setattr(rect, anchor, (x, y))
    surface.blit(surf, rect)
    return rect


def draw_glow_text(
    surface: pygame.Surface,
    text: str,
    x: int, y: int,
    size: int = FONT_XLARGE,
    colour: Tuple[int,int,int] = MATRIX_GREEN,
    glow_radius: int = 4,
    anchor: str = "center",
) -> None:
    """Draw text with a soft neon-glow halo."""
    font = get_bold_font(size)
    glow_col = tuple(min(255, int(c * 0.4)) for c in colour)
    for dx in range(-glow_radius, glow_radius + 1, 2):
        for dy in range(-glow_radius, glow_radius + 1, 2):
            if dx == 0 and dy == 0:
                continue
            g = font.render(text, True, glow_col)  # type: ignore[arg-type]
            r = g.get_rect()
            setattr(r, anchor, (x + dx, y + dy))
            g.set_alpha(80)
            surface.blit(g, r)
    main = font.render(text, True, colour)
    r = main.get_rect()
    setattr(r, anchor, (x, y))
    surface.blit(main, r)


# ─────────────────────────────────────────────────────────────────────────────
#  HealthBar
# ─────────────────────────────────────────────────────────────────────────────

class HealthBar:
    """
    Animated health bar with gradient colour shift (green→orange→red)
    and a small pulse animation when low HP.
    """

    def __init__(
        self,
        x: int, y: int,
        width: int = 200, height: int = 18,
        max_hp: float = 100.0,
        label: str = "HP",
        colour_full:  Tuple[int,int,int] = MATRIX_GREEN,
        colour_empty: Tuple[int,int,int] = NEON_RED,
    ) -> None:
        self.rect   = pygame.Rect(x, y, width, height)
        self.max_hp = max_hp
        self.hp     = max_hp
        self._label = label
        self._cf    = colour_full
        self._ce    = colour_empty
        self._pulse = 0.0

    def set_hp(self, hp: float) -> None:
        self.hp = max(0.0, min(self.max_hp, hp))

    def update(self, dt: float) -> None:
        self._pulse += dt * 6.0

    def draw(self, surface: pygame.Surface) -> None:
        ratio = self.hp / self.max_hp if self.max_hp > 0 else 0.0

        # Colour interpolation
        r = int(self._cf[0] + (self._ce[0] - self._cf[0]) * (1.0 - ratio))
        g = int(self._cf[1] + (self._ce[1] - self._cf[1]) * (1.0 - ratio))
        b = int(self._cf[2] + (self._ce[2] - self._cf[2]) * (1.0 - ratio))
        colour = (r, g, b)

        if ratio < 0.25:
            pulse = abs(math.sin(self._pulse)) * 0.3
            colour = (min(255, r + int(80 * pulse)), g, b)

        # Draw segmented bar
        segments = 10
        gap = 2
        seg_w = (self.rect.width - (segments - 1) * gap) / segments
        
        # Backing panel
        pygame.draw.rect(surface, (20, 20, 25, 200), (self.rect.x - 4, self.rect.y - 18, self.rect.width + 8, self.rect.height + 22), border_radius=4)
        
        for i in range(segments):
            sx = self.rect.x + i * (seg_w + gap)
            sy = self.rect.y
            s_rect = pygame.Rect(sx, sy, int(seg_w), self.rect.height)
            
            seg_ratio = (i + 1) / segments
            if ratio >= seg_ratio or (ratio > 0 and i == 0):
                pygame.draw.rect(surface, colour, s_rect, border_radius=2)
            else:
                pygame.draw.rect(surface, (40, 40, 40), s_rect, border_radius=2)

        # Label + value
        label = f"{self._label}: {int(self.hp)}/{int(self.max_hp)}"
        draw_text(surface, label, self.rect.x, self.rect.y - 16, FONT_SMALL, WHITE)


# ─────────────────────────────────────────────────────────────────────────────
#  TimerDisplay
# ─────────────────────────────────────────────────────────────────────────────

class TimerDisplay:
    """Count-up or countdown timer rendered in MM:SS format."""

    def __init__(
        self,
        x: int, y: int,
        countdown: bool = False,
        duration:  float = 60.0,
        size: int = FONT_MEDIUM,
        colour: Tuple[int,int,int] = NEON_CYAN,
        anchor: str = "topright",
    ) -> None:
        self._x        = x
        self._y        = y
        self._countdown = countdown
        self._duration  = duration
        self._elapsed   = 0.0
        self._running   = True
        self._size      = size
        self._colour    = colour
        self._anchor    = anchor

    def reset(self) -> None:
        self._elapsed = 0.0
        self._running = True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> None:
        if self._running:
            self._elapsed += dt

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def remaining(self) -> float:
        return max(0.0, self._duration - self._elapsed)

    @property
    def expired(self) -> bool:
        return self._countdown and self._elapsed >= self._duration

    def _format(self, seconds: float) -> str:
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"

    def draw(self, surface: pygame.Surface) -> None:
        val = self.remaining if self._countdown else self._elapsed
        col = self._colour
        if self._countdown and val < 10:
            col = NEON_RED
        draw_text(surface, self._format(val), self._x, self._y,
                  self._size, col, bold=True, anchor=self._anchor)


# ─────────────────────────────────────────────────────────────────────────────
#  ScoreDisplay
# ─────────────────────────────────────────────────────────────────────────────

class ScoreDisplay:
    """Animated score counter that pops when the score changes."""

    def __init__(
        self,
        x: int, y: int,
        size: int = FONT_MEDIUM,
        colour: Tuple[int,int,int] = GOLD,
        prefix: str = "SCORE",
        anchor: str = "topright",
    ) -> None:
        self._x      = x
        self._y      = y
        self._size   = size
        self._colour = colour
        self._prefix = prefix
        self._anchor = anchor
        self._score  = 0
        self._disp   = 0.0   # smooth displayed value
        self._pop    = 0.0   # pop scale animation timer

    def add(self, points: int) -> None:
        self._score += points
        self._pop    = 0.3

    def set(self, score: int) -> None:
        self._score = score

    @property
    def value(self) -> int:
        return self._score

    def update(self, dt: float) -> None:
        # Smooth scroll displayed value toward actual score
        diff = self._score - self._disp
        self._disp += diff * min(1.0, dt * 8)
        if abs(diff) < 1:
            self._disp = float(self._score)
        if self._pop > 0:
            self._pop -= dt

    def draw(self, surface: pygame.Surface) -> None:
        scale = 1.0 + max(0, self._pop) * 0.5
        size  = int(self._size * scale)
        text  = f"{self._prefix}: {int(self._disp):,}"
        draw_glow_text(surface, text, self._x, self._y, size, self._colour, glow_radius=3, anchor=self._anchor)


# ─────────────────────────────────────────────────────────────────────────────
#  FPSCounter
# ─────────────────────────────────────────────────────────────────────────────

class FPSCounter:
    """Small FPS readout in the corner (only drawn when enabled)."""

    def __init__(self, x: int = 10, y: int = 10) -> None:
        self._x, self._y = x, y
        self._fps        = 0.0
        self._timer      = 0.0

    def update(self, clock: pygame.time.Clock) -> None:
        self._fps = clock.get_fps()

    def draw(self, surface: pygame.Surface) -> None:
        col = MATRIX_GREEN if self._fps >= 55 else (NEON_ORANGE if self._fps >= 30 else NEON_RED)
        draw_text(surface, f"FPS: {int(self._fps)}", self._x, self._y, FONT_SMALL, col)


# ─────────────────────────────────────────────────────────────────────────────
#  ProgressBar
# ─────────────────────────────────────────────────────────────────────────────

class ProgressBar:
    """Generic horizontal progress bar (loading, boss-HP, wave-progress, etc.)."""

    def __init__(
        self,
        x: int, y: int,
        width: int, height: int = 12,
        colour: Tuple[int,int,int] = NEON_CYAN,
        bg_colour: Tuple[int,int,int] = DARK_GRAY,
        label: str = "",
    ) -> None:
        self.rect       = pygame.Rect(x, y, width, height)
        self._colour    = colour
        self._bg        = bg_colour
        self._label     = label
        self.progress   = 0.0   # 0.0 … 1.0

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self._bg, self.rect, border_radius=6)
        fill_w = int(self.rect.width * min(1.0, max(0.0, self.progress)))
        if fill_w > 0:
            fill = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
            pygame.draw.rect(surface, self._colour, fill, border_radius=6)
        pygame.draw.rect(surface, MID_GRAY, self.rect, 1, border_radius=6)
        if self._label:
            draw_text(surface, self._label, self.rect.centerx, self.rect.y - 18,
                      FONT_SMALL, WHITE, anchor="midbottom")


# ─────────────────────────────────────────────────────────────────────────────
#  FloatingText
# ─────────────────────────────────────────────────────────────────────────────

class FloatingText:
    """Temporary floating text that rises and fades (damage numbers, pickups)."""

    def __init__(
        self,
        text: str,
        x: float, y: float,
        colour: Tuple[int,int,int] = GOLD,
        size: int = FONT_MEDIUM,
        duration: float = 1.0,
        rise_speed: float = 40.0,
    ) -> None:
        self._text      = text
        self._x         = x
        self._y         = y
        self._colour    = colour
        self._size      = size
        self._duration  = duration
        self._elapsed   = 0.0
        self._rise      = rise_speed
        self.alive      = True

    def update(self, dt: float) -> None:
        self._elapsed += dt
        self._y       -= self._rise * dt
        if self._elapsed >= self._duration:
            self.alive = False

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        alpha = int(255 * max(0, 1.0 - self._elapsed / self._duration))
        draw_text(
            surface, self._text,
            int(self._x - offset[0]), int(self._y - offset[1]),
            self._size, self._colour, bold=True, alpha=alpha, anchor="center",
        )


class FloatingTextManager:
    """Pool of FloatingText instances."""

    def __init__(self) -> None:
        self._items: List[FloatingText] = []

    def add(self, text: str, x: float, y: float,
            colour: Tuple[int,int,int] = GOLD,
            size: int = FONT_MEDIUM, duration: float = 1.0) -> None:
        self._items.append(FloatingText(text, x, y, colour, size, duration))

    def update(self, dt: float) -> None:
        for item in self._items:
            item.update(dt)
        self._items = [i for i in self._items if i.alive]

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        for item in self._items:
            item.draw(surface, offset)


# ─────────────────────────────────────────────────────────────────────────────
#  Button
# ─────────────────────────────────────────────────────────────────────────────

class Button:
    """
    Stylised rectangular button with hover glow and click callback.
    Supports optional icon character prefix.
    """

    def __init__(
        self,
        x: int, y: int,
        width: int, height: int,
        label: str,
        callback: Callable[[], None],
        colour: Tuple[int,int,int]    = MATRIX_GREEN,
        text_colour: Tuple[int,int,int] = BLACK,
        font_size: int = FONT_MEDIUM,
        icon: str = "",
        anchor: str = "topleft",
    ) -> None:
        self._rect      = pygame.Rect(0, 0, width, height)
        setattr(self._rect, anchor, (x, y))
        self._label     = label
        self._callback  = callback
        self._colour    = colour
        self._text_col  = text_colour
        self._font_size = font_size
        self._icon      = icon
        self._hovered   = False
        self._pressed   = False
        self._anim      = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return self._rect

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self._rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._rect.collidepoint(event.pos):
                self._pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self._rect.collidepoint(event.pos):
                self._pressed = False
                self._callback()
                return True
            self._pressed = False
        return False

    def update(self, dt: float) -> None:
        target = 1.0 if self._hovered else 0.0
        self._anim += (target - self._anim) * min(1.0, dt * 12)

    def draw(self, surface: pygame.Surface) -> None:
        glow  = self._anim
        scale = 1.0 + glow * 0.04
        w = int(self._rect.width  * scale)
        h = int(self._rect.height * scale)
        x = self._rect.centerx - w // 2
        y = self._rect.centery - h // 2
        r = pygame.Rect(x, y, w, h)

        # Intense glow halo
        if glow > 0.01:
            halo = pygame.Surface((w + 30, h + 30), pygame.SRCALPHA)
            col_a = tuple(int(c * 0.8) for c in self._colour)
            pygame.draw.rect(halo, (*col_a, int(glow * 150)),  # type: ignore[arg-type]
                             (0, 0, w+30, h+30), border_radius=12)
            surface.blit(halo, (x - 15, y - 15), special_flags=pygame.BLEND_RGBA_ADD)

        # Transparent / Semi-dark body
        bg = (10, 10, 15, int(180 + glow * 50))
        body = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(body, bg, (0, 0, w, h), border_radius=6)
        
        # Cyberpunk neon border
        border_col = tuple(min(255, int(c + glow * 100)) for c in self._colour)
        pygame.draw.rect(body, border_col, (0, 0, w, h), width=max(2, int(2 + glow * 2)), border_radius=6)
        
        surface.blit(body, (x, y))

        # Label
        prefix = f"{self._icon}  " if self._icon else ""
        text = prefix + self._label
        tc = WHITE if glow < 0.5 else tuple(min(255, int(c + 150)) for c in self._colour)
        draw_text(surface, text, r.centerx, r.centery, self._font_size, tc, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Tooltip / message overlay
# ─────────────────────────────────────────────────────────────────────────────

class MessageQueue:
    """Screen-edge notifications that stack and auto-expire."""

    def __init__(self, x: int = 20, y_start: int = 120, max_messages: int = 5) -> None:
        self._x         = x
        self._y_start   = y_start
        self._max       = max_messages
        self._messages: List[dict] = []   # {text, colour, elapsed, duration}

    def push(self, text: str, colour: Tuple[int,int,int] = WHITE, duration: float = 2.5) -> None:
        self._messages.append({"text": text, "colour": colour,
                                "elapsed": 0.0, "duration": duration})
        if len(self._messages) > self._max:
            self._messages.pop(0)

    def update(self, dt: float) -> None:
        for m in self._messages:
            m["elapsed"] += dt
        self._messages = [m for m in self._messages if m["elapsed"] < m["duration"]]


    def draw(self, surface: pygame.Surface) -> None:
        y = self._y_start
        for m in self._messages:
            ratio = m["elapsed"] / m["duration"]
            alpha = int(255 * (1.0 - max(0, ratio - 0.7) / 0.3))
            draw_text(surface, m["text"], self._x, y, FONT_SMALL, m["colour"], alpha=alpha)
            y += 22


# ─────────────────────────────────────────────────────────────────────────────
#  ComboTracker  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class ComboTracker:
    """
    Tracks consecutive kills within a time window and computes a score
    multiplier.  Call register_kill() on each kill; query .multiplier for
    the current bonus.  The combo resets after COMBO_TIMEOUT seconds of
    inactivity.
    """

    def __init__(self, timeout: float = 2.0, max_multi: int = 16) -> None:
        self._timeout  = timeout
        self._max      = max_multi
        self._count    = 0          # consecutive kills
        self._timer    = 0.0        # time since last kill
        self._anim     = 0.0        # display pop animation
        self._display  = 0          # displayed combo count

    def register_kill(self) -> int:
        """Call after each kill.  Returns the multiplier that should be applied."""
        self._count  += 1
        self._timer   = 0.0
        self._anim    = 0.5
        return self.multiplier

    def reset(self) -> None:
        self._count = 0
        self._timer = 0.0

    @property
    def multiplier(self) -> int:
        """Score multiplier: 1× up to max, doubling every 4 kills."""
        if self._count <= 1:
            return 1
        tiers = [1, 1, 2, 2, 3, 3, 4, 4, 6, 6, 8, 8, 12, 12, 16, 16]
        idx   = min(self._count, len(tiers) - 1)
        return min(tiers[idx], self._max)

    @property
    def count(self) -> int:
        return self._count

    def update(self, dt: float) -> None:
        self._anim = max(0.0, self._anim - dt * 3)
        if self._count > 0:
            self._timer += dt
            if self._timer >= self._timeout:
                self.reset()
        self._display = self._count

    def draw(self, surface: pygame.Surface,
             x: int = 10, y: int = 80) -> None:
        """Render combo counter only when active (count ≥ 2)."""
        if self._count < 2:
            return
        pop   = 1.0 + self._anim * 0.6
        size  = int(FONT_LARGE * pop)
        multi = self.multiplier

        # Background pill
        label = f"×{multi} COMBO  {self._count} kills"
        font  = get_bold_font(size)
        tw    = font.size(label)[0]
        pill  = pygame.Surface((tw + 20, size + 8), pygame.SRCALPHA)
        pygame.draw.rect(pill, (0, 0, 0, 140),
                         (0, 0, tw + 20, size + 8), border_radius=8)
        surface.blit(pill, (x - 10, y - 4))

        # Colour shifts: green → yellow → orange → red with combo depth
        ratio  = min(1.0, self._count / 12)
        r      = int(50 + 205 * ratio)
        g      = int(255 * (1.0 - ratio * 0.7))
        colour = (r, g, 30)
        draw_glow_text(surface, label, x + tw // 2, y, size, colour,  # type: ignore[arg-type]
                       glow_radius=3, anchor="midleft")

        # Timer bar underneath
        bar_w  = tw
        remain = max(0.0, 1.0 - self._timer / self._timeout)
        pygame.draw.rect(surface, DARK_GRAY, (x, y + size + 4, bar_w, 4))
        pygame.draw.rect(surface, colour, (x, y + size + 4, int(bar_w * remain), 4))  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
#  LivesDisplay  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class LivesDisplay:
    """
    Renders heart icons representing remaining lives.
    Call set_lives() when a life is lost.
    """

    def __init__(
        self,
        x: int, y: int,
        max_lives: int = 3,
        icon_size: int = 22,
        colour: Tuple[int,int,int] = NEON_RED,
        anchor: str = "topleft",
    ) -> None:
        self._x          = x
        self._y          = y
        self._max        = max_lives
        self._lives      = max_lives
        self._size       = icon_size
        self._colour     = colour
        self._anchor     = anchor
        self._lose_anim: List[float] = []   # per-life lose animation timers

    def set_lives(self, lives: int) -> None:
        if lives < self._lives:
            self._lose_anim.insert(0, 0.5)
        self._lives = max(0, lives)

    def update(self, dt: float) -> None:
        self._lose_anim = [max(0.0, t - dt * 2) for t in self._lose_anim]

    def _draw_heart(self, surface: pygame.Surface, cx: int, cy: int,
                    size: int, filled: bool, alpha: int = 255) -> None:
        """Draw a simple heart shape using circles + polygon."""
        col = self._colour if filled else DARK_GRAY
        s   = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        r   = size // 2
        # Two circles (top bumps)
        pygame.draw.circle(s, (*col, alpha), (r,     r), r)
        pygame.draw.circle(s, (*col, alpha), (size + r//2 - 1, r), r)
        # Bottom triangle
        pts = [(0, r), (size * 2, r), (size, size * 2 - 2)]
        pygame.draw.polygon(s, (*col, alpha), pts)
        surface.blit(s, (cx - size, cy - r), special_flags=pygame.BLEND_RGBA_ADD)

    def draw(self, surface: pygame.Surface) -> None:
        gap = self._size + 6
        for i in range(self._max):
            filled = i < self._lives
            # Shake lost life slightly
            shake  = 0
            if not filled and i < len(self._lose_anim) and self._lose_anim[i] > 0:
                shake = int(self._lose_anim[i] * 5)
            cx = self._x + i * gap + self._size
            cy = self._y + shake
            self._draw_heart(surface, cx, cy, self._size // 2, filled)

        draw_text(surface, "LIVES", self._x, self._y + self._size + 2,
                  FONT_SMALL, GRAY)


# ─────────────────────────────────────────────────────────────────────────────
#  VignetteOverlay  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class VignetteOverlay:
    """
    Draws a dark-corner vignette that turns red and pulses when HP is low.
    Always-on with a subtle dark vignette; intensifies below 30 % HP.
    """

    def __init__(
        self,
        width: int,
        height: int,
    ) -> None:
        self._w    = width
        self._h    = height
        self._base = self._make_vignette(width, height, (0, 0, 0), 100)
        self._red  = self._make_vignette(width, height, (200, 0, 0), 180)
        self._t    = 0.0

    @staticmethod
    def _make_vignette(w: int, h: int,
                       colour: Tuple[int,int,int], max_alpha: int) -> pygame.Surface:
        # Generate at 1/16th resolution to prevent heavy CPU blocking on Android
        # which causes ANR/crash due to SDL event queue overflow during the block.
        sw, sh = max(1, w // 16), max(1, h // 16)
        surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        cx, cy = sw / 2, sh / 2
        for y in range(sh):
            for x in range(sw):
                dx = (x - cx) / cx
                dy = (y - cy) / cy
                dist = math.hypot(dx, dy)
                a    = max(0, int(max_alpha * (dist - 0.5) / 0.5))
                a    = min(max_alpha, a)
                if a > 0:
                    surf.set_at((x, y), (*colour, a))
        return pygame.transform.smoothscale(surf, (w, h))

    def update(self, dt: float) -> None:
        self._t += dt * 5

    def draw(self, surface: pygame.Surface, hp_ratio: float) -> None:
        """Draw vignette. hp_ratio = current_hp / max_hp in [0, 1]."""
        # Base dark corners always visible
        surface.blit(self._base, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Red pulse below 30 %
        if hp_ratio < 0.30:
            intensity = (0.30 - hp_ratio) / 0.30           # 0→1
            pulse     = 0.5 + 0.5 * math.sin(self._t)      # 0→1
            alpha     = int(255 * intensity * pulse * 0.75)
            red       = self._red.copy()
            red.set_alpha(alpha)
            surface.blit(red, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


# ─────────────────────────────────────────────────────────────────────────────
#  SceneTransition  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class SceneTransition:
    """
    Fade-to-black overlay for smooth scene switches.
    Usage:
        transition.start_out()   # fade OUT (black appears)
        # ... when done == True, switch scene ...
        transition.start_in()    # fade IN (black disappears)
    """

    def __init__(self, duration: float = 0.4) -> None:
        self._alpha    = 0.0
        self._dir      = 0          # +1 fade to black, -1 fade to clear
        self._duration = duration
        self._surf     = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._surf.fill(BLACK)
        self.done      = False

    def start_out(self) -> None:
        """Begin fade to black."""
        self._alpha = 0.0
        self._dir   = 1
        self.done   = False

    def start_in(self) -> None:
        """Begin fade from black."""
        self._alpha = 255.0
        self._dir   = -1
        self.done   = False

    def update(self, dt: float) -> None:
        if self._dir == 0:
            return
        speed = 255.0 / self._duration
        self._alpha += self._dir * speed * dt
        if self._dir == 1 and self._alpha >= 255:
            self._alpha = 255
            self.done   = True
            self._dir   = 0
        elif self._dir == -1 and self._alpha <= 0:
            self._alpha = 0
            self.done   = True
            self._dir   = 0

    @property
    def active(self) -> bool:
        return self._dir != 0 or self._alpha > 0

    def draw(self, surface: pygame.Surface) -> None:
        if self._alpha > 0:
            self._surf.set_alpha(int(self._alpha))
            surface.blit(self._surf, (0, 0))


# ─────────────────────────────────────────────────────────────────────────────
#  CRTOverlay  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

class CRTOverlay:
    """
    Simulates a CRT screen with horizontal scanlines and a vignette effect.
    """
    def __init__(self, width: int, height: int) -> None:
        self._w = width
        self._h = height
        
        # Pre-render scanlines for performance
        self._scanlines = pygame.Surface((width, height), pygame.SRCALPHA)
        for y in range(0, height, 4):
            pygame.draw.line(self._scanlines, (0, 0, 0, 80), (0, y), (width, y), 2)
            
        # Moving scanline (bright bar)
        self._bar_y = 0.0
        
        # Pre-render vignette (dark corners)
        self._vignette = pygame.Surface((width, height), pygame.SRCALPHA)
        center = (width // 2, height // 2)
        max_dist = math.sqrt(center[0]**2 + center[1]**2)
        
        for y in range(0, height, 8):
            for x in range(0, width, 8):
                dist = math.sqrt((x - center[0])**2 + (y - center[1])**2)
                alpha = int(200 * (dist / max_dist)**2)
                if alpha > 0:
                    alpha = min(255, alpha)
                    pygame.draw.rect(self._vignette, (0, 0, 0, alpha), (x, y, 8, 8))
                    
    def update(self, dt: float) -> None:
        self._bar_y += dt * 100.0
        if self._bar_y > self._h:
            self._bar_y = -50.0

    def draw(self, surface: pygame.Surface) -> None:
        # Draw static scanlines
        surface.blit(self._scanlines, (0, 0))
        
        # Draw moving bright bar
        bar = pygame.Surface((self._w, 20), pygame.SRCALPHA)
        bar.fill((255, 255, 255, 10))
        surface.blit(bar, (0, int(self._bar_y)))
        
        # Draw vignette
        surface.blit(self._vignette, (0, 0))


# ─────────────────────────────────────────────────────────────────────────────
#  Achievement Toast Manager
# ─────────────────────────────────────────────────────────────────────────────

class AchievementToastManager:
    """Displays pop-up notifications for unlocked achievements."""
    def __init__(self) -> None:
        self._toasts: list[dict] = []
        self._current = None
        self._timer = 0.0

    def update(self, dt: float) -> None:
        import achievements
        for ach in achievements.get_pending_toasts():
            self._toasts.append(ach)

        if self._current is None and self._toasts:
            self._current = self._toasts.pop(0)
            self._timer = 4.0

        if self._current:
            self._timer -= dt
            if self._timer <= 0:
                self._current = None

    def draw(self, surface: pygame.Surface) -> None:
        if not self._current:
            return
            
        tw, th = 380, 80
        tx = SCREEN_WIDTH // 2 - tw // 2
        
        # Slide animation
        ty = 20
        if self._timer > 3.5:
            ty = int(20 - (self._timer - 3.5) * 2 * 100)
        elif self._timer < 0.5:
            ty = int(20 - (0.5 - self._timer) * 2 * 100)
            
        rect = pygame.Rect(tx, ty, tw, th)
        
        # Background
        pygame.draw.rect(surface, (20, 20, 25), rect, border_radius=8)
        pygame.draw.rect(surface, GOLD, rect, 2, border_radius=8)
        
        # Text
        draw_text(surface, "🏆 ACHIEVEMENT UNLOCKED 🏆", tx + tw//2, ty + 10, FONT_SMALL, GOLD, anchor="midtop")
        draw_glow_text(surface, self._current["title"], tx + tw//2, ty + 35, FONT_MEDIUM, WHITE, glow_radius=4)
        draw_text(surface, self._current["desc"], tx + tw//2, ty + 60, FONT_SMALL, NEON_CYAN, anchor="midtop")
        draw_text(surface, f"+{self._current['reward']} Coins", tx + tw - 10, ty + 10, FONT_SMALL, GOLD, anchor="topright")


