"""
games/sniper.py  (v2 — improved)
=================================
Matrix Sniper — top-down shooter.

Improvements added
──────────────────
• Lives system (3 lives — respawn on death)
• Combo multiplier (ComboTracker from ui.py)
• 6th weapon: Ricochet — bullets bounce off walls using reflection matrix
• Muzzle flash on every shot
• Enemy hit-flash (brief white glow when damaged)
• Low-HP vignette (VignetteOverlay)
• Heart-icon lives display (LivesDisplay)

Matrix / Linear-Algebra integration
────────────────────────────────────
• Rotation matrix  → curveball bullet trajectory
• Scale matrix     → scope-zoom magnification
• Reflection matrix→ ricochet wall bounce direction
• Boss bullet spiral built with rotation matrix increments
• Enemy AI step rotated via rotation matrix for unpredictable movement
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, LIVES,
    BLACK, WHITE, DARK_BG, DARK_PANEL, DARK_GRAY, MATRIX_GREEN,
    NEON_RED, NEON_CYAN, NEON_ORANGE, NEON_YELLOW, NEON_PURPLE, GOLD,
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_XLARGE,
)
from animation import ParticleSystem, ScreenShake
from ui import (
    HealthBar, ScoreDisplay, FPSCounter, FloatingTextManager,
    MessageQueue, draw_text, draw_glow_text, ProgressBar,
    ComboTracker, LivesDisplay, VignetteOverlay,
)
from games.common import (
    BasePlayer, BaseEnemy, Bullet, Tile, Camera,
    mat_rotation, mat_scale, mat_transform, mat_reflection_line,
    rotate_point, grid_formation, v_formation,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Weapon definitions
# ─────────────────────────────────────────────────────────────────────────────

WEAPONS = {
    "pistol":    dict(damage=20,  speed=500, cool=0.35, ammo=12, reload=1.2,
                      colour=NEON_CYAN,   radius=5,  spread=0.05, burst=1,
                      curve=0.0,  bounces=0, label="Pistol"),
    "rifle":     dict(damage=35,  speed=650, cool=0.12, ammo=25, reload=1.8,
                      colour=NEON_ORANGE, radius=4,  spread=0.03, burst=1,
                      curve=0.0,  bounces=0, label="Assault Rifle"),
    "shotgun":   dict(damage=18,  speed=400, cool=0.65, ammo=8,  reload=2.0,
                      colour=NEON_YELLOW, radius=4,  spread=0.25, burst=5,
                      curve=0.0,  bounces=0, label="Shotgun"),
    "sniper":    dict(damage=80,  speed=900, cool=1.20, ammo=5,  reload=2.5,
                      colour=NEON_PURPLE, radius=3,  spread=0.00, burst=1,
                      curve=0.0,  bounces=0, label="Sniper Rifle"),
    "curveball": dict(damage=25,  speed=380, cool=0.40, ammo=10, reload=1.5,
                      colour=MATRIX_GREEN,radius=5,  spread=0.02, burst=1,
                      curve=1.8,  bounces=0, label="Curveball [MATRIX]"),
    "ricochet":  dict(damage=30,  speed=500, cool=0.45, ammo=8,  reload=1.8,
                      colour=NEON_YELLOW, radius=5,  spread=0.01, burst=1,
                      curve=0.0,  bounces=2, label="Ricochet [REFLECT]"),  # <-- reflection matrix
}
WEAPON_ORDER = ["pistol", "rifle", "shotgun", "sniper", "curveball", "ricochet"]

PLAYER_SPAWN = (MAP_W := 2000) // 2, (MAP_H := 1600) // 2


# ─────────────────────────────────────────────────────────────────────────────
#  Ricochet bullet  (extends Bullet — adds wall-bounce via reflection matrix)
# ─────────────────────────────────────────────────────────────────────────────

class RicochetBullet(Bullet):
    """
    A bullet that bounces off axis-aligned walls using the reflection matrix.

    When the bullet hits a wall:
      - horizontal wall → reflect velocity across X-axis  (vy → -vy)
      - vertical wall   → reflect velocity across Y-axis  (vx → -vx)

    This is equivalent to applying the 2×2 reflection matrices:
        Rx = [[1, 0], [0, -1]]   (horizontal wall)
        Ry = [[-1, 0], [0, 1]]   (vertical wall)
    """

    def __init__(self, x: float, y: float, angle: float, speed: float,
                 damage: float, colour: Tuple[int,int,int], radius: int,
                 max_bounces: int = 2) -> None:
        super().__init__(x, y, angle, speed, damage, colour, radius,
                         curve_rate=0.0, owner="player")
        self._bounces_left = max_bounces
        self._bounce_positions: List[Tuple[float,float]] = []

    def bounce_off_walls(self, obstacles: List[pygame.Rect]) -> bool:
        """
        Check wall collision and reflect velocity using reflection matrix.
        Returns True if a bounce occurred.
        """
        if self._bounces_left <= 0:
            return False

        bx = self.x + self.radius
        by = self.y + self.radius

        for obs in obstacles:
            if self.rect.colliderect(obs):
                # Determine which face was hit
                dx_left  = abs(bx - obs.left)
                dx_right = abs(bx - obs.right)
                dy_top   = abs(by - obs.top)
                dy_bot   = abs(by - obs.bottom)
                min_d    = min(dx_left, dx_right, dy_top, dy_bot)

                if min_d in (dx_left, dx_right):
                    # Hit vertical wall — apply Y-axis reflection: Ry
                    # Ry = [[-1, 0], [0, 1]]  →  vx → -vx
                    self.vx = -self.vx
                else:
                    # Hit horizontal wall — apply X-axis reflection: Rx
                    # Rx = [[1, 0], [0, -1]]  →  vy → -vy
                    self.vy = -self.vy

                self._bounces_left -= 1
                self._bounce_positions.append((bx, by))
                # Step away from wall to prevent double-bounce
                self.x += self.vx * 0.016
                self.y += self.vy * 0.016
                return True
        return False

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        # Draw bounce markers
        for bpx, bpy in self._bounce_positions:
            px = int(bpx) - offset[0]
            py = int(bpy) - offset[1]
            pygame.draw.circle(surface, self.colour, (px, py), 3)
            pygame.draw.circle(surface, WHITE, (px, py), 5, 1)
        super().draw(surface, offset)


# ─────────────────────────────────────────────────────────────────────────────
#  SniperPlayer
# ─────────────────────────────────────────────────────────────────────────────

class SniperPlayer(BasePlayer):
    SPEED = 200.0

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, 28, 28, max_hp=120.0, colour=MATRIX_GREEN)
        self.lives          = LIVES
        self._weapon_idx    = 0
        self._weapon_key    = WEAPON_ORDER[0]
        self._cooldown      = 0.0
        self._ammo          = WEAPONS[self._weapon_key]["ammo"]
        self._reloading     = 0.0
        self._reload_dur    = 0.0
        self.angle          = 0.0
        self._scope_zoom    = False
        self._zoom_t        = 0.0
        self._muzzle_t      = 0.0   # muzzle flash timer
        self.bullets: List[Bullet] = []

    def respawn(self, x: float, y: float) -> None:
        """Reset player to spawn with full HP (one life consumed)."""
        self.x, self.y = x, y
        self.hp         = self.max_hp
        self.alive      = True
        self.vx = self.vy = 0.0
        self.invincible_t = 2.0     # brief grace period
        self.bullets.clear()

    # ── input ─────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r and self._reloading == 0:
                self._start_reload()
            elif event.key == pygame.K_q:
                self._prev_weapon()
            elif event.key == pygame.K_e:
                self._next_weapon()
            elif event.key == pygame.K_z:
                self._scope_zoom = not self._scope_zoom

    def _next_weapon(self) -> None:
        self._weapon_idx = (self._weapon_idx + 1) % len(WEAPON_ORDER)
        self._switch_weapon()

    def _prev_weapon(self) -> None:
        self._weapon_idx = (self._weapon_idx - 1) % len(WEAPON_ORDER)
        self._switch_weapon()

    def _switch_weapon(self) -> None:
        self._weapon_key = WEAPON_ORDER[self._weapon_idx]
        self._ammo       = WEAPONS[self._weapon_key]["ammo"]
        self._reloading  = 0.0

    def _start_reload(self) -> None:
        self._reload_dur = WEAPONS[self._weapon_key]["reload"]
        self._reloading  = self._reload_dur

    # ── update ────────────────────────────────────────────────────

    def update(self, dt: float, keys, world_mouse: Tuple[float, float],
               mouse_buttons, obstacles: List[pygame.Rect],
               move_joy: Tuple[float, float] = (0.0, 0.0),
               aim_joy: Tuple[float, float] = (0.0, 0.0),
               dash_btn: bool = False, shoot_btn: bool = False) -> None:
        self.update_invincible(dt)
        self._muzzle_t = max(0.0, self._muzzle_t - dt)

        # Dash logic
        if getattr(self, '_dash_t', 0.0) > 0:
            self._dash_t -= dt
            speed_mult = 3.0
        else:
            speed_mult = 1.0
            if (keys[pygame.K_LSHIFT] or dash_btn) and getattr(self, '_dash_cooldown', 0.0) <= 0:
                self._dash_t = 0.2
                self._dash_cooldown = 1.0
                speed_mult = 3.0
        
        self._dash_cooldown = max(0.0, getattr(self, '_dash_cooldown', 0.0) - dt)

        dx, dy = move_joy
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        mag = math.hypot(dx, dy)
        if mag > 0 and mag > 1.0:
            dx, dy = dx/mag, dy/mag
        self.vx = dx * self.SPEED * speed_mult
        self.vy = dy * self.SPEED * speed_mult

        self.x += self.vx * dt
        for obs in obstacles:
            if self.rect.colliderect(obs):
                if self.vx > 0: self.x = obs.left - self.width
                if self.vx < 0: self.x = obs.right
        self.y += self.vy * dt
        for obs in obstacles:
            if self.rect.colliderect(obs):
                if self.vy > 0: self.y = obs.top - self.height
                if self.vy < 0: self.y = obs.bottom

        cx, cy = self.center
        
        # Aim logic
        if aim_joy[0] != 0.0 or aim_joy[1] != 0.0:
            self.angle = math.atan2(aim_joy[1], aim_joy[0])
            if shoot_btn and getattr(self, '_cooldown', 0) <= 0 and self._reloading == 0:
                self._shoot()
        else:
            mx, my = world_mouse
            self.angle = math.atan2(my - cy, mx - cx)
            if (mouse_buttons[0] or shoot_btn) and getattr(self, '_cooldown', 0) <= 0 and self._reloading == 0:
                self._shoot()

        if self._reloading > 0:
            self._reloading -= dt
            if self._reloading <= 0:
                self._reloading = 0.0
                self._ammo      = WEAPONS[self._weapon_key]["ammo"]

        if self._cooldown > 0:
            self._cooldown -= dt

        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

    def _shoot(self) -> None:
        w = WEAPONS[self._weapon_key]
        if self._ammo <= 0:
            self._start_reload()
            return
        self._cooldown  = w["cool"]
        self._ammo     -= 1
        self._muzzle_t  = 0.08   # flash duration
        cx, cy = self.center
        for _ in range(w["burst"]):
            spread = random.uniform(-w["spread"], w["spread"])
            angle  = self.angle + spread
            if w["bounces"] > 0:
                # Ricochet weapon — use RicochetBullet
                b = RicochetBullet(cx, cy, angle, w["speed"], w["damage"],
                                   w["colour"], w["radius"], w["bounces"])
            else:
                b = Bullet(cx, cy, angle, w["speed"], w["damage"],
                           w["colour"], w["radius"], w["curve"])
            self.bullets.append(b)

    # ── draw ──────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        if self.invincible_t > 0 and int(self.invincible_t * 10) % 2:
            return
        cx = int(self.x) - offset[0] + self.width  // 2
        cy = int(self.y) - offset[1] + self.height // 2

        from games.common import AvatarRenderer
        drawn = False
        if hasattr(self, "settings"):
            drawn = AvatarRenderer.draw_avatar(surface, cx, cy, 28, 28, self.settings, MATRIX_GREEN, self.angle)
            
        if not drawn:
            pygame.draw.circle(surface, MATRIX_GREEN, (cx, cy), 14)
            pygame.draw.circle(surface, WHITE,        (cx, cy), 14, 2)

        ex = cx + math.cos(self.angle) * 22
        ey = cy + math.sin(self.angle) * 22
        pygame.draw.line(surface, NEON_CYAN, (cx, cy), (int(ex), int(ey)), 3)
        pygame.draw.circle(surface, WEAPONS[self._weapon_key]["colour"],
                           (int(ex), int(ey)), 4)

        # Muzzle flash
        if self._muzzle_t > 0:
            mx_ = int(ex + math.cos(self.angle) * 8)
            my_ = int(ey + math.sin(self.angle) * 8)
            flash_r = int(10 * (self._muzzle_t / 0.08))
            flash = pygame.Surface((flash_r*2+4, flash_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(flash, (255, 255, 180, 200), (flash_r+2, flash_r+2), flash_r)
            surface.blit(flash, (mx_ - flash_r - 2, my_ - flash_r - 2),
                         special_flags=pygame.BLEND_RGBA_ADD)

    def draw_hud(self, surface: pygame.Surface) -> None:
        w = WEAPONS[self._weapon_key]
        draw_text(surface, f"[Q/E] {w['label']}", 10, SCREEN_HEIGHT - 60,
                  FONT_SMALL, NEON_CYAN)
        ammo_col = NEON_RED if self._ammo == 0 else GOLD
        draw_text(surface, f"AMMO: {self._ammo}/{w['ammo']}", 10, SCREEN_HEIGHT - 38,
                  FONT_SMALL, ammo_col)
        if self._reloading > 0:
            prog = 1.0 - self._reloading / self._reload_dur
            bar  = pygame.Rect(10, SCREEN_HEIGHT - 20, int(200 * prog), 10)
            pygame.draw.rect(surface, DARK_GRAY, (10, SCREEN_HEIGHT - 20, 200, 10))
            pygame.draw.rect(surface, NEON_ORANGE, bar)
            draw_text(surface, "RELOADING...", 220, SCREEN_HEIGHT - 22,
                      FONT_SMALL, NEON_ORANGE)
        if self._scope_zoom:
            draw_text(surface, "[Z] SCOPE ON", 10, SCREEN_HEIGHT - 80,
                      FONT_SMALL, NEON_YELLOW)
        draw_text(surface,
                  "[WASD] Move  [Mouse] Aim/Shoot  [Q/E] Weapon  [R] Reload  [Z] Scope",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18, FONT_SMALL, DARK_GRAY,
                  anchor="midbottom")


# ─────────────────────────────────────────────────────────────────────────────
#  Enemy types
# ─────────────────────────────────────────────────────────────────────────────

class SniperEnemy(BaseEnemy):
    DETECTION_RANGE = 280.0
    ATTACK_RANGE    = 200.0
    SHOOT_COOL      = 1.8

    def __init__(self, x: float, y: float, hp: float = 40.0,
                 speed: float = 90.0) -> None:
        super().__init__(x, y, 26, 26, hp, speed, score_value=100, colour=NEON_RED)
        offset_x = random.choice([-1, 1]) * random.randint(60, 150)
        offset_y = random.choice([-1, 1]) * random.randint(60, 150)
        self._waypoints  = [(x, y), (x + offset_x, y + offset_y)]
        self._wp_idx     = 0
        self._shoot_cool = self.SHOOT_COOL
        self._hit_flash  = 0.0   # white flash when damaged
        self.bullets: List[Bullet] = []

    def take_damage(self, amount: float) -> bool:
        self._hit_flash = 0.15
        return super().take_damage(amount)

    def update(self, dt: float, player: SniperPlayer,
               obstacles: List[pygame.Rect]) -> None:
        self._hit_flash = max(0.0, self._hit_flash - dt)
        if self.update_stun(dt):
            return

        cx, cy = self.center
        px, py = player.center
        dist   = math.hypot(px - cx, py - cy)

        if dist < self.DETECTION_RANGE:
            self.state = self.CHASE if dist > self.ATTACK_RANGE else self.ATTACK
        else:
            self.state = self.PATROL

        if self.state == self.PATROL:
            wx, wy = self._waypoints[self._wp_idx]
            dx, dy = wx - cx, wy - cy
            d = math.hypot(dx, dy)
            if d < 8:
                self._wp_idx = 1 - self._wp_idx
            else:
                self.vx = dx / d * self.speed
                self.vy = dy / d * self.speed

        elif self.state == self.CHASE:
            dx, dy = px - cx, py - cy
            d = math.hypot(dx, dy) or 1
            angle_offset = math.sin(pygame.time.get_ticks() * 0.002) * 0.3
            rdx, rdy = mat_transform(mat_rotation(angle_offset), (dx/d, dy/d))
            self.vx = rdx * self.speed
            self.vy = rdy * self.speed

        elif self.state == self.ATTACK:
            self.vx, self.vy = 0.0, 0.0
            self._shoot_cool -= dt
            if self._shoot_cool <= 0:
                self._shoot_cool = self.SHOOT_COOL
                angle = math.atan2(py - cy, px - cx)
                self.bullets.append(
                    Bullet(cx, cy, angle, 260, 12, NEON_RED, 5, owner="enemy")
                )

        self.x += self.vx * dt
        for obs in obstacles:
            if self.rect.colliderect(obs):
                self.vx = -self.vx * 0.5
                self.x  += self.vx * dt
        self.y += self.vy * dt
        for obs in obstacles:
            if self.rect.colliderect(obs):
                self.vy = -self.vy * 0.5
                self.y  += self.vy * dt

        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        cx = int(self.x) - offset[0] + self.width  // 2
        cy = int(self.y) - offset[1] + self.height // 2

        # Hit flash
        col = WHITE if self._hit_flash > 0 else NEON_RED
        pygame.draw.circle(surface, col, (cx, cy), 13)
        pygame.draw.circle(surface, WHITE, (cx, cy), 13, 2)

        col_map = {self.PATROL: DARK_GRAY, self.CHASE: NEON_ORANGE, self.ATTACK: NEON_RED}
        pygame.draw.circle(surface, col_map.get(self.state, DARK_GRAY), (cx, cy), 5)
        self.draw_hp_bar(surface, offset)


class FastEnemy(BaseEnemy):
    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, 20, 20, hp=20.0, speed=180.0,
                         score_value=150, colour=NEON_ORANGE)
        self._hit_flash = 0.0

    def take_damage(self, amount: float) -> bool:
        self._hit_flash = 0.12
        return super().take_damage(amount)

    def update(self, dt: float, player: SniperPlayer,
               obstacles: List[pygame.Rect]) -> None:
        self._hit_flash = max(0.0, self._hit_flash - dt)
        if self.update_stun(dt):
            return
        cx, cy = self.center
        px, py = player.center
        dx, dy = px - cx, py - cy
        d = math.hypot(dx, dy) or 1
        self.vx = dx / d * self.speed
        self.vy = dy / d * self.speed
        self.move(dt)
        self.bullets = []   # type: ignore[assignment]

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        cx = int(self.x) - offset[0] + self.width  // 2
        cy = int(self.y) - offset[1] + self.height // 2
        col = WHITE if self._hit_flash > 0 else NEON_ORANGE
        pts = [(cx, cy-12), (cx+12, cy), (cx, cy+12), (cx-12, cy)]
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, WHITE, pts, 2)
        self.draw_hp_bar(surface, offset)


# ─────────────────────────────────────────────────────────────────────────────
#  Boss
# ─────────────────────────────────────────────────────────────────────────────

class SniperBoss(BaseEnemy):
    PHASES = [
        dict(hp_threshold=0.66, speed=55,  shoot_rate=0.8,  spiral_n=4,  spiral_speed=0.8),
        dict(hp_threshold=0.33, speed=80,  shoot_rate=0.5,  spiral_n=8,  spiral_speed=1.4),
        dict(hp_threshold=0.00, speed=110, shoot_rate=0.3,  spiral_n=12, spiral_speed=2.0),
    ]

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, 56, 56, hp=600.0, speed=55.0,
                         score_value=5000, colour=NEON_PURPLE)
        self._phase        = 0
        self._shoot_timer  = 0.0
        self._spiral_angle = 0.0
        self._hit_flash    = 0.0
        self.bullets: List[Bullet] = []

    def take_damage(self, amount: float) -> bool:
        self._hit_flash = 0.1
        return super().take_damage(amount)

    @property
    def phase_data(self) -> dict:
        return self.PHASES[self._phase]

    def update(self, dt: float, player: SniperPlayer,
               obstacles: List[pygame.Rect]) -> None:
        self._hit_flash = max(0.0, self._hit_flash - dt)
        ratio = self.hp / self.max_hp
        for i, ph in enumerate(self.PHASES):
            if ratio > ph["hp_threshold"]:
                if self._phase != i:
                    self._phase = i
                    self.speed  = ph["speed"]
                break

        cx, cy = self.center
        px, py = player.center
        angle_to_player = math.atan2(py - cy, px - cx)
        orbit_dist = 250.0
        target_x = px - math.cos(angle_to_player) * orbit_dist
        target_y = py - math.sin(angle_to_player) * orbit_dist
        dx = target_x - cx
        dy = target_y - cy
        d  = math.hypot(dx, dy) or 1
        self.vx = dx / d * self.speed
        self.vy = dy / d * self.speed
        self.move(dt)

        ph = self.phase_data
        self._shoot_timer  += dt
        self._spiral_angle += ph["spiral_speed"] * dt

        if self._shoot_timer >= ph["shoot_rate"]:
            self._shoot_timer = 0.0
            n = ph["spiral_n"]
            for i in range(n):
                base_angle = self._spiral_angle + (2 * math.pi / n) * i
                self.bullets.append(
                    Bullet(cx, cy, base_angle, 220, 15, NEON_PURPLE, 6, owner="enemy")
                )
            if self._phase >= 1:
                angle_home = math.atan2(py - cy, px - cx)
                self.bullets.append(
                    Bullet(cx, cy, angle_home, 280, 18, NEON_RED, 7, owner="enemy")
                )

        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if b.alive]

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        cx = int(self.x) - offset[0] + self.width  // 2
        cy = int(self.y) - offset[1] + self.height // 2
        t  = pygame.time.get_ticks() * 0.003
        r  = int(28 + 4 * math.sin(t))

        col = WHITE if self._hit_flash > 0 else NEON_PURPLE
        pygame.draw.circle(surface, col,  (cx, cy), r)
        pygame.draw.circle(surface, WHITE, (cx, cy), r, 3)

        phase_colours = [NEON_CYAN, NEON_ORANGE, NEON_RED]
        pygame.draw.circle(surface, phase_colours[self._phase], (cx, cy), 10)
        draw_text(surface, f"BOSS P{self._phase+1}",
                  cx - 24, cy - r - 20, FONT_SMALL, NEON_PURPLE, bold=True)
        self.draw_hp_bar(surface, offset)

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
#  HealthOrb
# ─────────────────────────────────────────────────────────────────────────────

class HealthOrb:
    SIZE = 12

    def __init__(self, x: float, y: float) -> None:
        self.rect = pygame.Rect(int(x) - self.SIZE, int(y) - self.SIZE,
                                self.SIZE * 2, self.SIZE * 2)
        self.x = x
        self.y = y
        self._anim = 0.0

    def update(self, dt: float) -> None:
        self._anim += dt * 5.0

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        px = int(self.x) - offset[0]
        py = int(self.y + math.sin(self._anim) * 3) - offset[1]
        
        pygame.draw.circle(surface, NEON_CYAN, (px, py), self.SIZE)
        pygame.draw.circle(surface, WHITE, (px, py), self.SIZE, 2)
        draw_text(surface, "+", px, py, FONT_SMALL, BLACK, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Level layout
# ─────────────────────────────────────────────────────────────────────────────

def _build_level_tiles(level: int = 1) -> List[Tile]:
    tiles: List[Tile] = []
    margin = 40
    # Outer walls
    tiles.append(Tile(0, 0, MAP_W, margin))
    tiles.append(Tile(0, MAP_H - margin, MAP_W, margin))
    tiles.append(Tile(0, 0, margin, MAP_H))
    tiles.append(Tile(MAP_W - margin, 0, margin, MAP_H))
    
    if level == 1:
        # Open Arena: just 4 corner blocks
        tiles.append(Tile(200, 200, 200, 200))
        tiles.append(Tile(MAP_W-400, 200, 200, 200))
        tiles.append(Tile(200, MAP_H-400, 200, 200))
        tiles.append(Tile(MAP_W-400, MAP_H-400, 200, 200))
    elif level == 2:
        # Sparse Cover: random scattered boxes (original logic)
        random.seed(42)
        for _ in range(30):
            bx = random.randint(2, 9) * 200 + random.randint(-30, 30)
            by = random.randint(2, 7) * 200 + random.randint(-30, 30)
            bw = random.randint(60, 140)
            bh = random.randint(60, 140)
            bx = max(60, min(MAP_W - 60 - bw, bx))
            by = max(60, min(MAP_H - 60 - bh, by))
            tiles.append(Tile(bx, by, bw, bh))
        random.seed()
    elif level == 3:
        # Cross Labyrinth: Big central cross and corners
        cx, cy = MAP_W // 2, MAP_H // 2
        tiles.append(Tile(cx - 100, cy - 600, 200, 400)) # Top
        tiles.append(Tile(cx - 100, cy + 200, 200, 400)) # Bottom
        tiles.append(Tile(cx - 600, cy - 100, 400, 200)) # Left
        tiles.append(Tile(cx + 200, cy - 100, 400, 200)) # Right
    elif level == 4:
        # City Grid: Dense square blocks
        for gx in range(300, MAP_W - 300, 350):
            for gy in range(300, MAP_H - 300, 350):
                tiles.append(Tile(gx, gy, 150, 150))
    elif level == 5:
        # Concentric Rings / Forts
        cx, cy = MAP_W // 2, MAP_H // 2
        tiles.append(Tile(cx - 200, cy - 200, 400, 100))
        tiles.append(Tile(cx - 200, cy + 100, 400, 100))
        tiles.append(Tile(cx - 200, cy - 100, 100, 200))
        tiles.append(Tile(cx + 100, cy - 100, 100, 200))
        for gx in [cx - 600, cx + 400]:
            for gy in [cy - 600, cy + 400]:
                tiles.append(Tile(gx, gy, 200, 200))
    elif level == 6:
        # Vertical Corridors
        for gx in range(200, MAP_W - 200, 400):
            tiles.append(Tile(gx, 150, 100, MAP_H - 300))
    elif level == 7:
        # Horizontal Barriers
        for gy in range(200, MAP_H - 200, 300):
            tiles.append(Tile(150, gy, MAP_W - 300, 100))
    elif level == 8:
        # Checkered Cover
        for gx in range(200, MAP_W - 100, 250):
            for gy in range(200, MAP_H - 100, 250):
                if (gx + gy) % 2 == 0:
                    tiles.append(Tile(gx, gy, 150, 150))
    elif level == 9:
        # Diagonal Blocks
        for i in range(1, 6):
            tiles.append(Tile(i * 300, i * 200, 150, 150))
            tiles.append(Tile(MAP_W - i * 300 - 150, i * 200, 150, 150))
    elif level == 10:
        # The Narrow Cross (Walls blocking corners, leaving a cross open)
        cx, cy = MAP_W // 2, MAP_H // 2
        tiles.append(Tile(100, 100, cx - 150, cy - 150)) # Top Left chunk
        tiles.append(Tile(cx + 150, 100, cx - 250, cy - 150)) # Top Right chunk
        tiles.append(Tile(100, cy + 150, cx - 150, cy - 250)) # Bot Left
        tiles.append(Tile(cx + 150, cy + 150, cx - 250, cy - 250)) # Bot right
    else: # Level 11 (The Architect)
        # Arena: Massive central pillar and 4 corner pillars
        cx, cy = MAP_W // 2, MAP_H // 2
        tiles.append(Tile(cx - 300, cy - 300, 600, 600))
        tiles.append(Tile(150, 150, 100, 100))
        tiles.append(Tile(MAP_W - 250, 150, 100, 100))
        tiles.append(Tile(150, MAP_H - 250, 100, 100))
        tiles.append(Tile(MAP_W - 250, MAP_H - 250, 100, 100))
        
    return tiles


def _spawn_positions(tiles: List[Tile], count: int) -> List[Tuple[float, float]]:
    positions: List[Tuple[float,float]] = []
    obstacle_rects = [t.rect for t in tiles]
    attempts = 0
    while len(positions) < count and attempts < 2000:
        attempts += 1
        px = random.randint(100, MAP_W - 100)
        py = random.randint(100, MAP_H - 100)
        test = pygame.Rect(px - 20, py - 20, 40, 40)
        if not any(test.colliderect(r) for r in obstacle_rects):
            positions.append((float(px), float(py)))
    return positions


# ─────────────────────────────────────────────────────────────────────────────
#  SniperGame
# ─────────────────────────────────────────────────────────────────────────────

class SniperGame:
    WAVES = [
        dict(enemies=4,  fast=0,  boss=False),
        dict(enemies=6,  fast=2,  boss=False),
        dict(enemies=8,  fast=3,  boss=False),
        dict(enemies=10, fast=4,  boss=True),
    ]

    def __init__(self, screen: pygame.Surface, sound, settings, save_mgr, level: int = 1) -> None:
        self._screen   = screen
        self._sound    = sound
        self._settings = settings
        self._save     = save_mgr
        from config import GameID, LEVEL_THEMES
        self._game_id  = GameID.SNIPER
        self._level    = level
        self._theme_col= LEVEL_THEMES.get(level, MATRIX_GREEN)
        
        # V2 Mapping
        self.WAVES = []
        if level == 1:
            self.WAVES = [dict(enemies=4, fast=0, boss=False)]
        elif level == 2:
            self.WAVES = [dict(enemies=6, fast=0, boss=False)]
        elif level == 3:
            self.WAVES = [dict(enemies=8, fast=0, boss=False)]
        elif level == 4:
            self.WAVES = [dict(enemies=8, fast=2, boss=False)]
        elif level == 5:
            self.WAVES = [dict(enemies=10, fast=4, boss=False)]
        elif level == 6:
            self.WAVES = [dict(enemies=12, fast=6, boss=False)]
        elif level == 7:
            self.WAVES = [dict(enemies=14, fast=8, boss=False)]
        elif level == 8:
            self.WAVES = [dict(enemies=20, fast=5, boss=False), dict(enemies=25, fast=5, boss=False)]
        elif level == 9:
            self.WAVES = [dict(enemies=25, fast=10, boss=False), dict(enemies=30, fast=10, boss=False)]
        elif level == 10:
            self.WAVES = [dict(enemies=30, fast=15, boss=False), dict(enemies=20, fast=10, boss=True)]
        else: # level 11 (The Architect)
            self.WAVES = [dict(enemies=0, fast=0, boss=True), dict(enemies=0, fast=0, boss=True), dict(enemies=0, fast=0, boss=True), dict(enemies=0, fast=0, boss=True), dict(enemies=0, fast=0, boss=True)]

        self._tiles       = _build_level_tiles(self._level)
        self._obs_rects   = [t.rect for t in self._tiles]
        spawn_pts         = _spawn_positions(self._tiles, 60)
        self._spawn_pts   = spawn_pts

        self._player      = SniperPlayer(MAP_W // 2, MAP_H // 2)
        self._player.settings = self._settings
        self._camera      = Camera(MAP_W, MAP_H)
        self._world_surf  = pygame.Surface((MAP_W, MAP_H))

        # Systems
        self._particles   = ParticleSystem(600)
        self._shake       = ScreenShake()
        self._orbs: List[HealthOrb] = []
        self._floats      = FloatingTextManager()
        self._msgs        = MessageQueue(10, 80)
        self._hp_bar      = HealthBar(10, 50, 200, 18, self._player.max_hp)
        self._score_disp  = ScoreDisplay(SCREEN_WIDTH - 10, 10, anchor="topright")
        self._fps_cnt     = FPSCounter(10, 10)
        self._combo       = ComboTracker()
        self._lives_disp  = LivesDisplay(SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT - 65,
                                         max_lives=LIVES)
        self._vignette    = VignetteOverlay(SCREEN_WIDTH, SCREEN_HEIGHT)

        from games.common import VirtualJoystick, TouchButton
        from config import NEON_CYAN, NEON_RED
        
        self._joy_move = VirtualJoystick(120, SCREEN_HEIGHT - 120, 70, NEON_CYAN)
        self._joy_aim = VirtualJoystick(SCREEN_WIDTH - 120, SCREEN_HEIGHT - 120, 70, NEON_RED)
        self._btn_dash = TouchButton(SCREEN_WIDTH - 250, SCREEN_HEIGHT - 100, 40, "Dash", NEON_CYAN)

        self._wave        = 0
        self._enemies: List[SniperEnemy | FastEnemy] = []
        self._boss: Optional[SniperBoss]             = None
        self._boss_alive  = False
        self._result      = None

        self._start_wave()
        self._sound.play_music("music_sniper")
        self._msgs.push("WAVE 1 — Eliminate all enemies!", NEON_CYAN)
        self._msgs.push("[Ricochet] = NEW weapon that REFLECTS off walls!", NEON_YELLOW, 4.0)

    # ── wave management ───────────────────────────────────────────

    def _start_wave(self) -> None:
        w = self.WAVES[self._wave]
        positions = self._spawn_pts[:]
        random.shuffle(positions)
        idx = 0
        for _ in range(w["enemies"]):
            if idx < len(positions):
                ex, ey = positions[idx]; idx += 1
                self._enemies.append(SniperEnemy(ex, ey))
        for _ in range(w["fast"]):
            if idx < len(positions):
                ex, ey = positions[idx]; idx += 1
                self._enemies.append(FastEnemy(ex, ey))
        if w["boss"]:
            self._boss = SniperBoss(MAP_W // 2, MAP_H // 4)
            self._boss_alive = True
            self._sound.play("boss_roar")
            self._msgs.push("⚠ BOSS INCOMING!", NEON_RED, 3.0)

    def _wave_clear(self) -> bool:
        regular_clear = len(self._enemies) == 0
        if self.WAVES[self._wave]["boss"]:
            return regular_clear and (self._boss is None or not self._boss.alive)
        return regular_clear

    def _respawn_player(self) -> None:
        """Consume a life and respawn player at center."""
        self._player.lives -= 1
        self._lives_disp.set_lives(self._player.lives)
        if self._player.lives <= 0:
            self._result = "dead"
            return
        self._player.respawn(MAP_W // 2, MAP_H // 2)
        self._shake.shake(15, 0.6)
        self._sound.play("death")
        self._msgs.push(f"Lives remaining: {self._player.lives}", NEON_RED, 2.0)

    # ── interface ─────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "pause"
            
        self._joy_move.handle_event(event)
        self._joy_aim.handle_event(event)
        self._btn_dash.handle_event(event)
        self._player.handle_event(event)
        return None

    def update(self, dt: float) -> Optional[str]:
        if self._result:
            return self._result

        keys = pygame.key.get_pressed()
        mpos = pygame.mouse.get_pos()
        mb   = pygame.mouse.get_pressed()
        wx   = mpos[0] + self._camera.x
        wy   = mpos[1] + self._camera.y
        
        self._btn_dash.update()
        move_dir = (self._joy_move.dir_x, self._joy_move.dir_y)
        aim_dir = (self._joy_aim.dir_x, self._joy_aim.dir_y)
        shoot = (self._joy_aim.dir_x != 0 or self._joy_aim.dir_y != 0)

        self._player.update(dt, keys, (wx, wy), mb, self._obs_rects, move_joy=move_dir, aim_joy=aim_dir, dash_btn=self._btn_dash.is_pressed, shoot_btn=shoot)
        self._camera.follow(self._player.rect, dt)
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

        # ── player bullets → world ───────────────────────────────
        for bullet in self._player.bullets[:]:
            if not bullet.alive:
                continue

            # Ricochet bounce before wall kill
            if isinstance(bullet, RicochetBullet):
                bullet.bounce_off_walls(self._obs_rects)
            else:
                for obs in self._obs_rects:
                    if bullet.rect.colliderect(obs):
                        bullet.alive = False
                        bx, by = bullet.center
                        self._particles.emit_sparks(bx, by, 5, NEON_CYAN,
                                                    bullet._angle + math.pi)
                        break

            if not bullet.alive:
                continue

            # Boss hit
            if self._boss and self._boss.alive:
                if bullet.rect.colliderect(self._boss.rect):
                    killed = self._boss.take_damage(bullet.damage)
                    bullet.alive = False
                    bx, by = self._boss.center
                    self._particles.emit_burst(bx, by, 10, NEON_PURPLE, 100)
                    self._floats.add(f"-{int(bullet.damage)}", bx, by - 20, NEON_RED)
                    if killed:
                        multi = self._combo.register_kill()
                        pts = self._boss.score_value * multi * (3 if self._level == 6 else 1)
                        self._player.score += pts
                        self._particles.emit_burst(bx, by, 60, NEON_PURPLE, 200, glow=True)
                        self._shake.shake(20, 1.0)
                        self._sound.play("big_explosion")
                        self._msgs.push("BOSS DEFEATED!", GOLD, 3.0)
                        if multi > 1:
                            self._floats.add(f"×{multi} COMBO!", bx, by - 50, GOLD)

            # Enemy hit
            for enemy in self._enemies[:]:
                if not enemy.alive or not bullet.alive:
                    continue
                if bullet.rect.colliderect(enemy.rect):
                    killed = enemy.take_damage(bullet.damage)
                    bullet.alive = False
                    ex, ey = enemy.center
                    self._particles.emit_sparks(ex, ey, 6, NEON_RED,
                                                bullet._angle + math.pi, speed=150)
                    self._floats.add(f"-{int(bullet.damage)}", ex, ey - 20, NEON_RED)
                    if killed:
                        multi = self._combo.register_kill()
                        pts   = enemy.score_value * multi * (3 if self._level == 6 else 1)
                        self._player.score += pts
                        self._particles.emit_burst(ex, ey, 25, enemy.colour, 120, glow=True)
                        self._shake.shake(5, 0.15)
                        self._sound.play("explosion")
                        self._floats.add(f"+{pts}", ex, ey - 35, GOLD)
                        if multi > 1:
                            self._floats.add(f"×{multi}!", ex + 20, ey - 50,
                                             NEON_YELLOW, duration=1.2)
                        
                        # 15% chance to drop a HealthOrb
                        if random.random() < 0.15:
                            self._orbs.append(HealthOrb(ex, ey))
                    else:
                        self._sound.play("hit")
                    break

        # ── HealthOrbs ───────────────────────────────────────────
        for orb in self._orbs[:]:
            orb.update(dt)
            if orb.rect.colliderect(self._player.rect):
                self._player.hp = min(self._player.max_hp, self._player.hp + 20)
                self._sound.play("powerup")
                self._floats.add("+20 HP", orb.x, orb.y, NEON_CYAN)
                self._particles.emit_ring(orb.x, orb.y, 16, NEON_CYAN)
                self._orbs.remove(orb)

        # ── update enemies ───────────────────────────────────────
        for enemy in self._enemies[:]:
            if isinstance(enemy, FastEnemy):
                enemy.update(dt, self._player, self._obs_rects)
                if not enemy.alive:
                    continue
                if enemy.rect.colliderect(self._player.rect):
                    if self._player.take_damage(25):
                        self._shake.shake(8, 0.3)
                        self._sound.play("player_hit")
            else:
                enemy.update(dt, self._player, self._obs_rects)
                for eb in enemy.bullets[:]:
                    if not eb.alive: continue
                    for obs in self._obs_rects:
                        if eb.rect.colliderect(obs):
                            eb.alive = False
                            break
                    if eb.alive and eb.rect.colliderect(self._player.rect):
                        if self._player.take_damage(eb.damage):
                            self._shake.shake(6, 0.25)
                            self._sound.play("player_hit")
                        eb.alive = False
        self._enemies = [e for e in self._enemies if e.alive]

        # ── boss update ──────────────────────────────────────────
        if self._boss and self._boss.alive:
            self._boss.update(dt, self._player, self._obs_rects)
            for eb in self._boss.bullets[:]:
                if not eb.alive: continue
                for obs in self._obs_rects:
                    if eb.rect.colliderect(obs):
                        eb.alive = False
                        break
                if eb.alive and eb.rect.colliderect(self._player.rect):
                    if self._player.take_damage(eb.damage):
                        self._shake.shake(8, 0.3)
                        self._sound.play("player_hit")
                    eb.alive = False

        # ── player death ─────────────────────────────────────────
        if not self._player.alive:
            self._combo.reset()
            self._respawn_player()
            return None

        # ── wave clear ───────────────────────────────────────────
        if self._wave_clear():
            self._wave += 1
            if self._wave >= len(self.WAVES):
                self._sound.play("victory")
                self._result = "win"
                self._save.add_score(self._game_id, self._player.score)
            else:
                self._start_wave()
                self._sound.play("level_up")
                self._msgs.push(f"WAVE {self._wave + 1} BEGINS!", NEON_CYAN, 2.5)

        return None

    def draw(self, clock: pygame.time.Clock) -> None:
        ox, oy  = self._shake.offset
        self._world_surf.fill((12, 14, 22))
        cam_off = self._camera.offset

        # Grid
        grid_col = (18, 22, 35)
        gs = 80
        for gx in range(0, MAP_W, gs):
            pygame.draw.line(self._world_surf, grid_col, (gx, 0), (gx, MAP_H))
        for gy in range(0, MAP_H, gs):
            pygame.draw.line(self._world_surf, grid_col, (0, gy), (MAP_W, gy))

        for tile in self._tiles:
            tile.draw(self._world_surf)

        for b in self._player.bullets:
            b.draw(self._world_surf)
        for enemy in self._enemies:
            if hasattr(enemy, "bullets"):
                for b in enemy.bullets:    # type: ignore
                    b.draw(self._world_surf)
        if self._boss and self._boss.alive:
            for b in self._boss.bullets:
                b.draw(self._world_surf)

        for enemy in self._enemies:
            enemy.draw(self._world_surf)
        if self._boss and self._boss.alive:
            self._boss.draw(self._world_surf)
        
        # Draw HealthOrbs
        for orb in self._orbs:
            orb.draw(self._world_surf)
            
        self._player.draw(self._world_surf)

        self._particles.draw(self._world_surf)
        self._floats.draw(self._world_surf)

        self._screen.blit(self._world_surf,
                          (-int(cam_off[0]) + ox, -int(cam_off[1]) + oy))

        # ── HUD ──────────────────────────────────────────────────
        hp_ratio = self._player.hp / self._player.max_hp
        self._vignette.draw(self._screen, hp_ratio)
        self._hp_bar.draw(self._screen)
        self._score_disp.draw(self._screen)
        self._combo.draw(self._screen, 10, 80)
        self._lives_disp.draw(self._screen)

        if self._settings.show_fps:
            self._fps_cnt.update(clock)
            self._fps_cnt.draw(self._screen)

        self._joy_move.draw(self._screen)
        self._joy_aim.draw(self._screen)
        self._btn_dash.draw(self._screen)

        lvl_txt = "THE ARCHITECT" if self._level == 6 else f"LEVEL {self._level}"
        col = GOLD if self._level == 6 else self._theme_col
        draw_text(self._screen, f"{lvl_txt} - WAVE {self._wave + 1}/{len(self.WAVES)}",
                  SCREEN_WIDTH // 2, 10, FONT_MEDIUM, col,
                  bold=True, anchor="midtop")
        draw_text(self._screen, f"Enemies: {len(self._enemies)}",
                  SCREEN_WIDTH // 2, 36, FONT_SMALL, WHITE, anchor="midtop")

        if self._boss and self._boss.alive:
            self._boss.draw_hud_bar(self._screen)

        self._msgs.draw(self._screen)
        self._player.draw_hud(self._screen)

        # Crosshair
        mx, my = pygame.mouse.get_pos()
        size = 12
        pygame.draw.line(self._screen, NEON_CYAN, (mx - size, my), (mx + size, my), 1)
        pygame.draw.line(self._screen, NEON_CYAN, (mx, my - size), (mx, my + size), 1)
        pygame.draw.circle(self._screen, NEON_CYAN, (mx, my), size, 1)
