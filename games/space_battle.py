"""
games/space_battle.py
=====================
Matrix Space Battle — 2D scrolling space shooter.

Matrix / Linear-Algebra integration
────────────────────────────────────
• Rotation matrix   → ship orientation and aimed bullet direction
• Scale matrix      → power-up hitbox expansion + pulse ring effect
• grid_formation()  → enemy waves positioned via rotation-transformed grids
• v_formation()     → V-shape enemy groups
• Boss multi-phase with rotated bullet fans
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, LIVES,
    BLACK, WHITE, DARK_BG, DARK_GRAY, MATRIX_GREEN,
    NEON_RED, NEON_CYAN, NEON_ORANGE, NEON_YELLOW, NEON_PURPLE, GOLD,
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_XLARGE,
)
from animation import ParticleSystem, ScreenShake, Starfield
from ui import (
    HealthBar, ScoreDisplay, FPSCounter, FloatingTextManager,
    MessageQueue, draw_text, draw_glow_text, ProgressBar,
    ComboTracker, LivesDisplay, VignetteOverlay,
)
from games.common import (
    Bullet, BaseEnemy, Camera,
    mat_rotation, mat_scale, mat_transform,
    grid_formation, v_formation,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Spaceship (player)
# ─────────────────────────────────────────────────────────────────────────────

class Spaceship:
    """
    Player-controlled spaceship.
    Movement uses rotation matrix to transform thrust into world velocity.
    """

    MAX_SPEED     = 380.0
    ACCEL         = 600.0
    FRICTION      = 0.85
    SHOOT_COOL    = 0.12
    BOMB_COOL     = 8.0
    MAX_HP        = 120.0

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y  = x, y
        self.vx = self.vy = 0.0
        self.angle       = -math.pi / 2   # pointing upward
        self.hp          = self.MAX_HP
        self.max_hp      = self.MAX_HP
        self.score       = 0
        self.alive       = True
        self.lives       = LIVES

        self._shoot_t    = 0.0
        self._bomb_t     = 0.0
        self._shield     = 0.0   # shield timer
        self._rapid      = 0.0   # rapid-fire timer
        self._bomb_count = 2
        self.bullets: List[Bullet] = []

        self._inv_t      = 0.0

        # Baked ship polygon (pointing right)
        self._poly_base  = [
            (20, 0), (-14, 12), (-8, 0), (-14, -12),
        ]

    def respawn(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.angle     = -math.pi / 2
        self.hp        = self.MAX_HP
        self.alive     = True
        self._shield   = 0.0
        self._rapid    = 0.0
        self._inv_t    = 2.0
        self.bullets.clear()

    # ── transform polygon ─────────────────────────────────────────

    def _transformed_poly(self, cx: int, cy: int) -> List[Tuple[int,int]]:
        rot = mat_rotation(self.angle)
        pts = []
        for px, py in self._poly_base:
            rx, ry = mat_transform(rot, (px, py))
            pts.append((cx + int(rx), cy + int(ry)))
        return pts

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 18, int(self.y) - 18, 36, 36)

    @property
    def center(self) -> Tuple[float,float]:
        return (self.x, self.y)

    def take_damage(self, amount: float) -> bool:
        if self._shield > 0 or self._inv_t > 0:
            return False
        self.hp  -= amount
        self._inv_t = 0.6
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
        return True

    def heal(self, amount: float) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def apply_powerup(self, kind: str) -> None:
        if kind == "shield":
            self._shield = 8.0
        elif kind == "rapid":
            self._rapid  = 6.0
        elif kind == "hp":
            self.heal(40)
        elif kind == "bomb":
            self._bomb_count += 1

    # ── update ────────────────────────────────────────────────────

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper) -> bool:
        """Returns True if a bomb was dropped this frame."""
        self._inv_t  = max(0, self._inv_t  - dt)
        self._shield = max(0, self._shield - dt)
        self._rapid  = max(0, self._rapid  - dt)
        self._shoot_t= max(0, self._shoot_t- dt)
        self._bomb_t = max(0, self._bomb_t - dt)

        # Rotation
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.angle -= 3.0 * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.angle += 3.0 * dt

        # Thrust — rotation matrix applied to forward vector (1, 0)
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            fwd = mat_transform(mat_rotation(self.angle), (self.ACCEL, 0.0))
            self.vx += fwd[0] * dt
            self.vy += fwd[1] * dt

        # Brake
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.vx *= (1.0 - 3.0 * dt)
            self.vy *= (1.0 - 3.0 * dt)

        # Speed cap
        spd = math.hypot(self.vx, self.vy)
        if spd > self.MAX_SPEED:
            self.vx = self.vx / spd * self.MAX_SPEED
            self.vy = self.vy / spd * self.MAX_SPEED

        # Friction
        self.vx *= (self.FRICTION ** dt)
        self.vy *= (self.FRICTION ** dt)

        self.x += self.vx * dt
        self.y += self.vy * dt

        # Screen wrap
        self.x = self.x % SCREEN_WIDTH
        self.y = self.y % SCREEN_HEIGHT

        # Shoot
        cool = self.SHOOT_COOL * (0.4 if self._rapid > 0 else 1.0)
        if (keys[pygame.K_SPACE] or keys[pygame.K_z]) and self._shoot_t <= 0:
            self._shoot_t = cool
            self._fire()

        # Bomb
        bomb_dropped = False
        if keys[pygame.K_x] and self._bomb_t <= 0 and self._bomb_count > 0:
            self._bomb_t      = self.BOMB_COOL
            self._bomb_count -= 1
            bomb_dropped      = True

        # Bullet update
        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

        return bomb_dropped

    def _fire(self) -> None:
        cx, cy = self.center
        # Main forward bullet
        self.bullets.append(
            Bullet(cx, cy, self.angle, 620, 25, NEON_CYAN, 5, owner="player", lifetime=1.5)
        )
        # Side guns when rapid
        if self._rapid > 0:
            for offset in (-0.2, 0.2):
                self.bullets.append(
                    Bullet(cx, cy, self.angle + offset, 600, 15, NEON_YELLOW, 4, owner="player", lifetime=1.2)
                )

    # ── draw ──────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        if self._inv_t > 0 and int(self._inv_t * 10) % 2:
            return
        cx, cy = int(self.x), int(self.y)
        pts = self._transformed_poly(cx, cy)

        # Shield ring (scale matrix pulse)
        if self._shield > 0:
            pulse = 1.0 + 0.12 * math.sin(pygame.time.get_ticks() * 0.01)
            sr    = int(26 * pulse)
            shld  = pygame.Surface((sr*2+4, sr*2+4), pygame.SRCALPHA)
            pygame.draw.circle(shld, (0, 150, 255, 80), (sr+2, sr+2), sr)
            pygame.draw.circle(shld, (0, 200, 255, 180), (sr+2, sr+2), sr, 2)
            surface.blit(shld, (cx - sr - 2, cy - sr - 2),
                         special_flags=pygame.BLEND_RGBA_ADD)

        # Engine trail
        trail_angle = self.angle + math.pi
        trx = cx + int(math.cos(trail_angle) * 14)
        try_ = cy + int(math.sin(trail_angle) * 14)
        pygame.draw.circle(surface, NEON_ORANGE, (trx, try_), 5)
        pygame.draw.circle(surface, NEON_YELLOW, (trx, try_), 2)

        # Ship body
        from games.common import AvatarRenderer
        drawn = False
        if hasattr(self, "settings"):
            drawn = AvatarRenderer.draw_avatar(surface, cx, cy, 26, 26, self.settings, NEON_CYAN, self.angle - math.pi/2)
            
        if not drawn:
            pygame.draw.polygon(surface, NEON_CYAN, pts)
            pygame.draw.polygon(surface, WHITE, pts, 2)

        # Rapid glow
        if self._rapid > 0:
            glow = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 255, 0, 50), (20, 20), 18)
            surface.blit(glow, (cx - 20, cy - 20),
                         special_flags=pygame.BLEND_RGBA_ADD)

    def draw_hud(self, surface: pygame.Surface) -> None:
        draw_text(surface, f"BOMBS: {'◉' * self._bomb_count}",
                  10, SCREEN_HEIGHT - 38, FONT_SMALL, NEON_ORANGE)
        if self._shield > 0:
            draw_text(surface, f"SHIELD: {self._shield:.1f}s",
                      10, SCREEN_HEIGHT - 60, FONT_SMALL, NEON_CYAN)
        if self._rapid > 0:
            draw_text(surface, f"RAPID: {self._rapid:.1f}s",
                      160, SCREEN_HEIGHT - 60, FONT_SMALL, NEON_YELLOW)
        draw_text(surface,
                  "[Arrows/WASD] Steer  [Space/Z] Fire  [X] Bomb",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18,
                  FONT_SMALL, DARK_GRAY, anchor="midbottom")


# ─────────────────────────────────────────────────────────────────────────────
#  Enemies
# ─────────────────────────────────────────────────────────────────────────────

class SpaceEnemy:
    """Standard enemy fighter. Moves toward the player and fires."""

    SIZE       = 18
    SHOOT_COOL = 2.2

    def __init__(self, x: float, y: float, hp: float = 30.0,
                 speed: float = 80.0, score: int = 100) -> None:
        self.x, self.y  = x, y
        self.vx = self.vy = 0.0
        self.hp          = hp
        self.max_hp      = hp
        self.speed       = speed
        self.score_value = score
        self.alive       = True
        self._shoot_t    = random.uniform(0, self.SHOOT_COOL)
        self._hit_flash  = 0.0
        self.bullets: List[Bullet] = []
        self._angle      = math.pi / 2  # facing down initially
        self.colour      = NEON_RED

    @property
    def rect(self) -> pygame.Rect:
        s = self.SIZE
        return pygame.Rect(int(self.x) - s, int(self.y) - s, s*2, s*2)

    @property
    def center(self) -> Tuple[float,float]:
        return (self.x, self.y)

    def take_damage(self, amount: float) -> bool:
        self.hp -= amount
        self._hit_flash = 0.15
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            return True
        return False

    def update(self, dt: float, player_pos: Tuple[float,float]) -> None:
        self._hit_flash = max(0.0, self._hit_flash - dt)
        px, py  = player_pos
        dx, dy  = px - self.x, py - self.y
        d       = math.hypot(dx, dy) or 1
        self._angle = math.atan2(dy, dx)

        self.x += (dx/d) * self.speed * dt * 0.4
        self.y += (dy/d) * self.speed * dt * 0.4

        self._shoot_t -= dt
        if self._shoot_t <= 0:
            self._shoot_t = self.SHOOT_COOL
            self.bullets.append(
                Bullet(self.x, self.y, self._angle, 200, 12,
                       NEON_RED, 5, owner="enemy", lifetime=2.0)
            )
        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.x), int(self.y)
        # Triangle shape pointing toward player
        rot = mat_rotation(self._angle)
        pts_base = [(self.SIZE, 0), (-self.SIZE, self.SIZE*0.7), (-self.SIZE, -self.SIZE*0.7)]
        pts = [(cx + int(mat_transform(rot, p)[0]),
                cy + int(mat_transform(rot, p)[1])) for p in pts_base]
        
        col = WHITE if self._hit_flash > 0 else NEON_RED
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, WHITE, pts, 2)
        # HP bar
        bw = self.SIZE * 2
        pygame.draw.rect(surface, (60,0,0), (cx - self.SIZE, cy - self.SIZE - 8, bw, 4))
        fill = int(bw * self.hp / self.max_hp)
        pygame.draw.rect(surface, (200,50,50), (cx - self.SIZE, cy - self.SIZE - 8, fill, 4))


class HeavyEnemy(SpaceEnemy):
    """Bigger, slower enemy that fires burst shots."""

    SIZE       = 26
    SHOOT_COOL = 1.8

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, hp=80.0, speed=50.0, score=250)
        self._burst_left = 0
        self.colour      = NEON_ORANGE

    def update(self, dt: float, player_pos: Tuple[float,float]) -> None:
        super().update(dt, player_pos)
        # Override shoot with burst
        if self._burst_left > 0:
            if not hasattr(self, "_burst_t"):
                self._burst_t = 0.0
            self._burst_t -= dt
            if self._burst_t <= 0:
                self._burst_t     = 0.18
                self._burst_left -= 1
                angle = self._angle + random.uniform(-0.15, 0.15)
                self.bullets.append(
                    Bullet(self.x, self.y, angle, 230, 10,
                           NEON_ORANGE, 5, owner="enemy", lifetime=2.0)
                )
        elif random.random() < 0.01:
            self._burst_left = 4

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.x), int(self.y)
        pygame.draw.rect(surface, NEON_ORANGE,
                         (cx - self.SIZE, cy - self.SIZE, self.SIZE*2, self.SIZE*2),
                         border_radius=6)
        pygame.draw.rect(surface, WHITE,
                         (cx - self.SIZE, cy - self.SIZE, self.SIZE*2, self.SIZE*2),
                         2, border_radius=6)
        bw = self.SIZE * 2
        pygame.draw.rect(surface, (60,0,0), (cx - self.SIZE, cy - self.SIZE - 8, bw, 4))
        fill = int(bw * self.hp / self.max_hp)
        pygame.draw.rect(surface, (200,120,0), (cx - self.SIZE, cy - self.SIZE - 8, fill, 4))


# ─────────────────────────────────────────────────────────────────────────────
#  PowerUp
# ─────────────────────────────────────────────────────────────────────────────

class PowerUp:
    """Collectible power-up with a scale-matrix pulsing ring on collect."""

    KINDS = ["shield", "rapid", "hp", "bomb"]
    COLS  = {
        "shield": NEON_CYAN,
        "rapid":  NEON_YELLOW,
        "hp":     MATRIX_GREEN,
        "bomb":   NEON_ORANGE,
    }
    ICONS = {"shield": "S", "rapid": "R", "hp": "+", "bomb": "B"}

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y  = x, y
        self.kind       = random.choice(self.KINDS)
        self.colour     = self.COLS[self.kind]
        self.alive      = True
        self._anim      = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 14, int(self.y) - 14, 28, 28)

    def update(self, dt: float) -> None:
        self._anim += dt * 3

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.x), int(self.y)
        # Scale-matrix pulse ring
        pulse  = 1.0 + 0.15 * math.sin(self._anim)
        r      = int(14 * pulse)
        pygame.draw.circle(surface, self.colour, (cx, cy), r)
        pygame.draw.circle(surface, WHITE,       (cx, cy), r, 2)
        draw_text(surface, self.ICONS[self.kind], cx, cy,
                  FONT_SMALL, BLACK, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Space Boss
# ─────────────────────────────────────────────────────────────────────────────

class SpaceBoss:
    """
    Multi-phase space boss.
    Bullet patterns use the rotation matrix to create fans and spirals.
    """

    MAX_HP  = 800.0
    SIZE    = 50

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y  = x, y
        self.vx = self.vy = 0.0
        self.hp          = self.MAX_HP
        self.max_hp      = self.MAX_HP
        self.alive       = True
        self._phase      = 0
        self._shoot_t    = 0.0
        self._spiral_a   = 0.0
        self._move_t     = 0.0
        self._target_x   = float(x)
        self._hit_flash  = 0.0
        self.bullets: List[Bullet] = []

    @property
    def rect(self) -> pygame.Rect:
        s = self.SIZE
        return pygame.Rect(int(self.x) - s, int(self.y) - s, s*2, s*2)

    @property
    def center(self) -> Tuple[float,float]:
        return (self.x, self.y)

    def take_damage(self, amount: float) -> bool:
        self.hp -= amount
        self._hit_flash = 0.1
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            return True
        return False

    def update(self, dt: float, player_pos: Tuple[float,float]) -> None:
        self._hit_flash = max(0.0, self._hit_flash - dt)
        ratio = self.hp / self.max_hp
        if ratio > 0.66:
            self._phase = 0
        elif ratio > 0.33:
            self._phase = 1
        else:
            self._phase = 2

        # Side-to-side movement
        self._move_t += dt
        target_x = SCREEN_WIDTH * (0.3 + 0.4 * math.sin(self._move_t * 0.5))
        dx = target_x - self.x
        self.x += dx * min(1.0, dt * 1.5)
        self.y = max(80, self.y + (150 - self.y) * min(1.0, dt * 1.0))

        # ── Rotation-matrix bullet fans ──
        self._shoot_t -= dt
        self._spiral_a += (1.0 + self._phase) * dt

        shoot_rate = [1.0, 0.65, 0.4][self._phase]
        fan_count  = [5,   8,    12][self._phase]

        if self._shoot_t <= 0:
            self._shoot_t = shoot_rate
            cx, cy = self.center
            # Fan pattern: rotate base angle by i * (π / fan_count)
            for i in range(fan_count):
                angle = self._spiral_a + (math.pi * 2 / fan_count) * i
                self.bullets.append(
                    Bullet(cx, cy, angle, 200 + self._phase * 40,
                           20, NEON_PURPLE, 6, owner="enemy", lifetime=3.0)
                )
            # Phase 2: homing burst
            if self._phase >= 2:
                px, py = player_pos
                ah = math.atan2(py - cy, px - cx)
                for off in (-0.15, 0, 0.15):
                    self.bullets.append(
                        Bullet(cx, cy, ah + off, 280, 25, NEON_RED, 7,
                               owner="enemy", lifetime=3.0)
                    )

        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.x), int(self.y)
        t = pygame.time.get_ticks() * 0.003
        r = int(self.SIZE + 5 * math.sin(t))

        # Core
        phase_cols = [NEON_CYAN, NEON_ORANGE, NEON_RED]
        col = WHITE if self._hit_flash > 0 else phase_cols[self._phase]
        
        pygame.draw.circle(surface, NEON_PURPLE, (cx, cy), r)
        pygame.draw.circle(surface, col, (cx, cy), r, 4)
        pygame.draw.circle(surface, WHITE, (cx, cy), r, 2)

        # Rotating ring (scale + rotation matrix)
        ring_r = int((r + 22) * (1.0 + 0.05 * math.sin(t * 2)))
        for i in range(8):
            ang   = t * 2 + i * math.pi / 4
            dx    = int(math.cos(ang) * ring_r)
            dy    = int(math.sin(ang) * ring_r)
            pygame.draw.circle(surface, phase_cols[self._phase], (cx+dx, cy+dy), 5)

        # HP bar
        bw = self.SIZE * 3
        by = cy - self.SIZE - 15
        pygame.draw.rect(surface, DARK_GRAY, (cx - bw//2, by, bw, 8))
        fill = int(bw * self.hp / self.max_hp)
        pygame.draw.rect(surface, NEON_PURPLE, (cx - bw//2, by, fill, 8))
        pygame.draw.rect(surface, WHITE, (cx - bw//2, by, bw, 8), 1)

    def draw_hud_bar(self, surface: pygame.Surface) -> None:
        bw, bh = 500, 20
        bx = SCREEN_WIDTH // 2 - bw // 2
        by = 10
        pygame.draw.rect(surface, DARK_GRAY, (bx, by, bw, bh), border_radius=6)
        fill = int(bw * max(0, self.hp / self.max_hp))
        pygame.draw.rect(surface, NEON_PURPLE, (bx, by, fill, bh), border_radius=6)
        pygame.draw.rect(surface, WHITE, (bx, by, bw, bh), 2, border_radius=6)
        draw_text(surface, f"BOSS: {int(self.hp)} / {int(self.max_hp)}",
                  SCREEN_WIDTH // 2, by + bh + 4, FONT_SMALL, NEON_PURPLE,
                  bold=True, anchor="midtop")


# ─────────────────────────────────────────────────────────────────────────────
#  Wave builder
# ─────────────────────────────────────────────────────────────────────────────

WAVES = [
    dict(count=4,  heavy=0, boss=False, formation="grid",   angle=0.0),
    dict(count=6,  heavy=1, boss=False, formation="v",      angle=0.0),
    dict(count=8,  heavy=2, boss=False, formation="grid",   angle=0.3),
    dict(count=6,  heavy=3, boss=False, formation="v",      angle=-0.3),
    dict(count=0,  heavy=0, boss=True,  formation="single", angle=0.0),
]


def _build_wave(w: dict) -> Tuple[List[SpaceEnemy|HeavyEnemy], Optional[SpaceBoss]]:
    enemies: List[SpaceEnemy | HeavyEnemy] = []
    boss: Optional[SpaceBoss]              = None

    if w["boss"]:
        boss = SpaceBoss(SCREEN_WIDTH // 2, -80)
        return enemies, boss

    origin = (SCREEN_WIDTH // 2, -100)

    if w["formation"] == "grid":
        n    = w["count"]
        cols = max(2, n // 2)
        rows = max(1, (n + cols - 1) // cols)
        pts  = grid_formation(origin, rows, cols, 80, w["angle"])
    else:
        pts = v_formation(origin, w["count"], 80, w["angle"])

    for (ex, ey) in pts[:w["count"]]:
        enemies.append(SpaceEnemy(ex, ey))
    for _ in range(w["heavy"]):
        hx = random.uniform(100, SCREEN_WIDTH - 100)
        enemies.append(HeavyEnemy(hx, -60))

    return enemies, boss


# ─────────────────────────────────────────────────────────────────────────────
#  HealthOrb
# ─────────────────────────────────────────────────────────────────────────────

class HealthOrb:
    SIZE = 12

    def __init__(self, x: float, y: float) -> None:
        self.rect = pygame.Rect(int(x) - self.SIZE, int(y) - self.SIZE,
                                self.SIZE * 2, self.SIZE * 2)
        self.x = x
        self.y = y
        self.vy = 80.0
        self._anim = 0.0

    def update(self, dt: float) -> None:
        self._anim += dt * 5.0
        self.y += self.vy * dt
        self.rect.centery = int(self.y)

    def draw(self, surface: pygame.Surface) -> None:
        px = int(self.x)
        py = int(self.y + math.sin(self._anim) * 3)
        
        pygame.draw.circle(surface, NEON_CYAN, (px, py), self.SIZE)
        pygame.draw.circle(surface, WHITE, (px, py), self.SIZE, 2)
        draw_text(surface, "+", px, py, FONT_SMALL, BLACK, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Hazards (Asteroids & Lasers)
# ─────────────────────────────────────────────────────────────────────────────

class Asteroid:
    def __init__(self, x: float, y: float, size: int, speed: float) -> None:
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.angle = random.uniform(0, math.pi * 2)
        self.rot_speed = random.uniform(-2.0, 2.0)
        self.rect = pygame.Rect(int(x) - size, int(y) - size, size * 2, size * 2)
        self.alive = True

        # Generate random jagged polygon for asteroid shape
        self.pts = []
        for i in range(8):
            a = i * (math.pi / 4)
            r = size * random.uniform(0.7, 1.1)
            self.pts.append((math.cos(a)*r, math.sin(a)*r))

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        self.angle += self.rot_speed * dt
        self.rect.centery = int(self.y)
        if self.y > SCREEN_HEIGHT + self.size:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        rot_pts = []
        c, s = math.cos(self.angle), math.sin(self.angle)
        for (px, py) in self.pts:
            rx = px * c - py * s
            ry = px * s + py * c
            rot_pts.append((int(self.x + rx), int(self.y + ry)))
        pygame.draw.polygon(surface, (100, 100, 100), rot_pts)
        pygame.draw.polygon(surface, (150, 150, 150), rot_pts, 2)


class LaserBarrier:
    def __init__(self, y: float) -> None:
        self.y = y
        self.timer = 0.0
        self.active = False
        self.alive = True
        self.cycle_time = 3.0 # 1.5s warning, 1.5s active
        self.rect = pygame.Rect(0, int(y) - 10, SCREEN_WIDTH, 20)

    def update(self, dt: float) -> None:
        self.timer += dt
        if self.timer > self.cycle_time:
            self.timer = 0.0
        self.active = self.timer > 1.5

        # Moves slowly down
        self.y += 20 * dt
        self.rect.y = int(self.y) - 10
        if self.y > SCREEN_HEIGHT + 20:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        if self.active:
            pygame.draw.rect(surface, NEON_RED, self.rect)
            pygame.draw.rect(surface, WHITE, (self.rect.x, self.rect.centery - 2, SCREEN_WIDTH, 4))
        else:
            # Warning lines
            if int(self.timer * 10) % 2 == 0:
                pygame.draw.line(surface, NEON_RED, (0, self.y), (SCREEN_WIDTH, self.y), 1)

# ─────────────────────────────────────────────────────────────────────────────
#  SpaceBattleGame
# ─────────────────────────────────────────────────────────────────────────────

class SpaceBattleGame:
    """2D space shooter game."""

    def __init__(self, screen: pygame.Surface, sound, settings, save_mgr, level: int = 1) -> None:
        self._screen   = screen
        self._sound    = sound
        self._settings = settings
        self._save     = save_mgr
        from config import GameID, LEVEL_THEMES
        self._game_id  = GameID.SPACE
        self._level    = level
        self._theme_col= LEVEL_THEMES.get(level, MATRIX_GREEN)

        if level <= 4:
            self._waves = [dict(count=6+(level*2), heavy=level, boss=False, formation="grid", angle=0.0)]
        elif level <= 8:
            self._waves = [dict(count=8+(level*2), heavy=level, boss=False, formation="v", angle=0.3)]
        elif level <= 10:
            self._waves = [dict(count=12, heavy=6, boss=False, formation="grid", angle=0.0), dict(count=12, heavy=6, boss=False, formation="v", angle=0.5)]
        else: # level 11 (The Architect)
            self._waves = [dict(count=0, heavy=0, boss=True, formation="single", angle=0.0), dict(count=0, heavy=0, boss=True, formation="single", angle=0.0), dict(count=0, heavy=0, boss=True, formation="single", angle=0.0)]

        self._player    = Spaceship(SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.7)
        self._player.settings = self._settings
        self._starfield = Starfield(SCREEN_WIDTH, SCREEN_HEIGHT, 250)
        self._particles = ParticleSystem(600)
        self._shake     = ScreenShake()
        self._orbs: List[HealthOrb] = []
        self._floats    = FloatingTextManager()
        self._msgs      = MessageQueue(10, 80)
        self._hp_bar    = HealthBar(10, 50, 200, 18, self._player.max_hp)
        self._score_disp= ScoreDisplay(SCREEN_WIDTH - 10, 10, anchor="topright")
        self._fps_cnt   = FPSCounter(10, 10)
        self._combo     = ComboTracker()
        self._lives_disp= LivesDisplay(SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT - 65, max_lives=LIVES)
        self._vignette  = VignetteOverlay(SCREEN_WIDTH, SCREEN_HEIGHT)

        self._wave_idx    = 0
        self._enemies: List[SpaceEnemy | HeavyEnemy] = []
        self._powerups: List[PowerUp] = []
        self._asteroids: List[Asteroid] = []
        self._lasers: List[LaserBarrier] = []
        self._boss: Optional[SpaceBoss] = None
        self._result  = None
        self._wave_intro_t = 2.0

        self._start_wave()
        self._sound.play_music("music_space")
        self._msgs.push("WAVE 1 — Destroy all enemies!", NEON_CYAN, 2.5)

    def _start_wave(self) -> None:
        enemies, boss = _build_wave(self._waves[self._wave_idx])
        self._enemies = enemies
        self._boss    = boss
        if boss:
            self._sound.play("boss_roar")
            self._msgs.push("⚠ BOSS INCOMING!", NEON_RED, 3.0)

    def _wave_clear(self) -> bool:
        if self._boss:
            return not self._boss.alive
        return len(self._enemies) == 0

    # ── interface ─────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "pause"
        return None

    def update(self, dt: float) -> Optional[str]:
        if self._result:
            return self._result

        keys = pygame.key.get_pressed()

        # Wave intro delay
        if self._wave_intro_t > 0:
            self._wave_intro_t -= dt
            self._starfield.update(dt * 3.0 if self._level >= 4 else dt)
            return None

        # Player
        bomb_dropped = self._player.update(dt, keys)
        if bomb_dropped:
            self._sound.play("big_explosion")
            cx, cy = self._player.center
            # Bomb kills all on-screen enemies
            for e in self._enemies[:]:
                e.take_damage(9999)
                ex, ey = e.center
                self._particles.emit_burst(ex, ey, 30, NEON_ORANGE, 200, glow=True)
                self._shake.shake(15, 0.6)
                self._sound.play("explosion")
            if self._boss and self._boss.alive:
                self._boss.take_damage(150)
            self._enemies = [e for e in self._enemies if e.alive]

        # Starfield
        self._starfield.update(dt * 3.0 if self._level >= 4 else dt)

        # Particles / misc
        self._particles.update(dt)
        self._floats.update(dt)
        self._msgs.update(dt)
        self._shake.update(dt)
        self._combo.update(dt)
        self._lives_disp.update(dt)
        self._vignette.update(dt)
        self._hp_bar.set_hp(self._player.hp)
        self._hp_bar.update(dt)
        self._score_disp.set(self._player.score)
        self._score_disp.update(dt)

        # Powerup spawning
        if random.random() < 0.003:
            px = random.uniform(50, SCREEN_WIDTH - 50)
            self._powerups.append(PowerUp(px, -20))

        # Update powerups
        for pu in self._powerups[:]:
            pu.update(dt)
            pu.y += 60 * dt
            if pu.rect.colliderect(self._player.rect):
                self._player.apply_powerup(pu.kind)
                self._particles.emit_ring(pu.x, pu.y, 20, pu.colour, speed=80)
                self._sound.play("powerup")
                self._floats.add(pu.kind.upper(), pu.x, pu.y, pu.colour)
                pu.alive = False
            if pu.y > SCREEN_HEIGHT + 40:
                pu.alive = False
        self._powerups = [p for p in self._powerups if p.alive]

        # Hazard spawning based on level
        if self._level >= 2: # Asteroids
            asteroid_chance = 0.005 + (0.005 * self._level) # Scales with level
            if random.random() < asteroid_chance:
                sz = random.randint(15, 35)
                spd = random.randint(100, 300)
                px = random.uniform(50, SCREEN_WIDTH - 50)
                self._asteroids.append(Asteroid(px, -40, sz, spd))
                
        if self._level >= 3: # Laser Barriers
            laser_chance = 0.001 * (self._level - 2)
            if random.random() < laser_chance and len(self._lasers) == 0:
                self._lasers.append(LaserBarrier(-20))

        # Update Asteroids
        for ast in self._asteroids[:]:
            ast.update(dt)
            if ast.rect.colliderect(self._player.rect):
                if self._player.take_damage(20):
                    self._shake.shake(8, 0.3)
                    self._sound.play("player_hit")
                self._particles.emit_burst(ast.x, ast.y, 20, (150, 150, 150), 100)
                ast.alive = False
            # Check player bullet vs asteroid
            for pb in self._player.bullets:
                if pb.alive and pb.rect.colliderect(ast.rect):
                    pb.alive = False
                    self._particles.emit_sparks(pb.x, pb.y, 5, NEON_CYAN, pb._angle + math.pi)
        self._asteroids = [a for a in self._asteroids if a.alive]

        # Update Lasers
        for laser in self._lasers[:]:
            laser.update(dt)
            if laser.active and laser.rect.colliderect(self._player.rect):
                if self._player.take_damage(40 * dt): # Continuous damage
                    self._shake.shake(4, 0.1)
        self._lasers = [l for l in self._lasers if l.alive]

        # Update enemies
        for enemy in self._enemies[:]:
            enemy.update(dt, self._player.center)

            # Enemy bullets → player
            for eb in enemy.bullets[:]:
                if eb.rect.colliderect(self._player.rect):
                    if self._player.take_damage(eb.damage):
                        self._shake.shake(6, 0.25)
                        self._sound.play("player_hit")
                    eb.alive = False

            # Remove off-screen enemies
            if enemy.y > SCREEN_HEIGHT + 60:
                enemy.alive = False

        # Player bullets → enemies
        for pb in self._player.bullets[:]:
            if not pb.alive:
                continue
            for enemy in self._enemies[:]:
                if not enemy.alive: continue
                if pb.rect.colliderect(enemy.rect):
                    killed = enemy.take_damage(pb.damage)
                    pb.alive = False
                    ex, ey = enemy.center
                    self._particles.emit_sparks(ex, ey, 8, NEON_CYAN, pb._angle + math.pi)
                    self._floats.add(f"-{int(pb.damage)}", ex, ey, NEON_RED, duration=0.6)
                    if killed:
                        multi = self._combo.register_kill()
                        
                        import achievements
                        achievements.check_achievement(self._save, "first_blood", True)
                        achievements.check_achievement(self._save, "combo_10", multi >= 10)
                        achievements.check_achievement(self._save, "combo_20", multi >= 20)
                        
                        pts   = enemy.score_value * multi * (3 if self._level == 6 else 1)
                        self._player.score += pts
                        self._particles.emit_burst(ex, ey, 30, enemy.colour, 140, glow=True)
                        self._shake.shake(5, 0.15)
                        self._sound.play("explosion")
                        self._floats.add(f"+{pts}", ex, ey - 20, GOLD)
                        if multi > 1:
                            self._floats.add(f"×{multi}!", ex + 20, ey - 35, NEON_YELLOW, duration=1.2)
                        if random.random() < 0.25:
                            self._powerups.append(PowerUp(ex, ey))
                        elif random.random() < 0.15: # 15% chance if no powerup
                            self._orbs.append(HealthOrb(ex, ey))
                    break

            if not pb.alive: continue
            # Player bullet → boss
            if self._boss and self._boss.alive:
                if pb.rect.colliderect(self._boss.rect):
                    killed = self._boss.take_damage(pb.damage)
                    pb.alive = False
                    bx, by = self._boss.center
                    self._particles.emit_sparks(bx, by, 10, NEON_CYAN, math.pi/2)
                    self._floats.add(f"-{int(pb.damage)}", bx, by, NEON_RED, duration=0.6)
                    if killed:
                        multi = self._combo.register_kill()
                        
                        import achievements
                        achievements.check_achievement(self._save, "boss_killer", True)
                        
                        pts = 5000 * multi * (3 if self._level == 6 else 1)
                        self._player.score += pts
                        self._particles.emit_burst(bx, by, 60, NEON_PURPLE, 200, glow=True)
                        self._shake.shake(20, 1.0)
                        self._sound.play("big_explosion")
                        self._msgs.push("BOSS DESTROYED!", GOLD, 3.0)
                        if multi > 1:
                            self._floats.add(f"×{multi} COMBO!", bx, by - 50, GOLD)

        # ── HealthOrbs ───────────────────────────────────────────
        for orb in self._orbs[:]:
            orb.update(dt)
            if orb.rect.colliderect(self._player.rect):
                self._player.hp = min(self._player.max_hp, self._player.hp + 20)
                self._sound.play("powerup")
                self._floats.add("+20 HP", orb.x, orb.y, NEON_CYAN)
                self._particles.emit_ring(orb.x, orb.y, 16, NEON_CYAN)
                self._orbs.remove(orb)
            elif orb.y > SCREEN_HEIGHT + 40:
                self._orbs.remove(orb)

        self._enemies = [e for e in self._enemies if e.alive]

        # Boss update + boss bullets → player
        if self._boss and self._boss.alive:
            self._boss.update(dt, self._player.center)
            for bb in self._boss.bullets[:]:
                if bb.rect.colliderect(self._player.rect):
                    if self._player.take_damage(bb.damage):
                        self._shake.shake(8, 0.3)
                        self._sound.play("player_hit")
                    bb.alive = False

        # Player death
        if not self._player.alive:
            self._sound.play("death")
            self._player.lives -= 1
            self._lives_disp.set_lives(self._player.lives)
            self._combo.reset()
            if self._player.lives <= 0:
                self._result = "dead"
                return None
            else:
                self._player.respawn(SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.7)
                self._shake.shake(15, 0.6)
                self._msgs.push(f"Lives remaining: {self._player.lives}", NEON_RED, 2.0)
                # Keep going with new life

        # Wave clear
        if self._wave_clear():
            self._wave_idx += 1
            if self._wave_idx >= len(self._waves):
                self._save.add_score(self._game_id, self._player.score)
                self._sound.play("victory")
                self._result = "win"
            else:
                self._start_wave()
                self._wave_intro_t = 2.5
                self._sound.play("level_up")
                self._msgs.push(f"WAVE {self._wave_idx + 1}!", NEON_CYAN, 2.0)

        return None

    def draw(self, clock: pygame.time.Clock) -> None:
        ox, oy = self._shake.offset

        self._screen.fill(DARK_BG)
        self._starfield.draw(self._screen)

        # Wave intro banner
        if self._wave_intro_t > 0:
            draw_glow_text(self._screen,
                           f"WAVE {self._wave_idx + 1}",
                           SCREEN_WIDTH // 2 + ox, SCREEN_HEIGHT // 2 + oy,
                           FONT_XLARGE, NEON_CYAN, glow_radius=8)
            return

        # Draw offset with shake
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        # Powerups
        for pu in self._powerups:
            pu.draw(surf)

        # Enemies
        for enemy in self._enemies:
            enemy.draw(surf)
            for b in enemy.bullets:
                b.draw(surf)

        # Boss
        if self._boss and self._boss.alive:
            self._boss.draw(surf)
            for b in self._boss.bullets:
                b.draw(surf)

        # Draw HealthOrbs
        for orb in self._orbs:
            orb.draw(surf)

        # Hazards
        for ast in self._asteroids:
            ast.draw(surf)
        for laser in self._lasers:
            laser.draw(surf)

        # Player
        self._player.draw(surf)
        for b in self._player.bullets:
            b.draw(surf)

        # Particles
        self._particles.draw(surf)
        self._floats.draw(surf)

        self._screen.blit(surf, (ox, oy))

        # HUD
        hp_ratio = self._player.hp / self._player.max_hp
        self._vignette.draw(self._screen, hp_ratio)
        self._hp_bar.draw(self._screen)
        self._score_disp.draw(self._screen)
        self._combo.draw(self._screen, 10, 80)
        self._lives_disp.draw(self._screen)
        if self._settings.show_fps:
            self._fps_cnt.update(clock)
            self._fps_cnt.draw(self._screen)

        lvl_txt = "THE ARCHITECT" if self._level == 6 else f"LEVEL {self._level}"
        col = GOLD if self._level == 6 else self._theme_col
        draw_text(self._screen, f"{lvl_txt} - WAVE {self._wave_idx + 1} / {len(self._waves)}",
                  SCREEN_WIDTH // 2, 10, FONT_MEDIUM, col,
                  bold=True, anchor="midtop")

        if self._boss and self._boss.alive:
            self._boss.draw_hud_bar(self._screen)

        self._msgs.draw(self._screen)
        self._player.draw_hud(self._screen)
