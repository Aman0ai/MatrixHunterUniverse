"""
games/assassin.py
=================
Matrix Assassin — stealth infiltration game.

Matrix / Linear-Algebra integration
────────────────────────────────────
• Reflection matrix  → guard patrol paths are mirrors of each other
• Rotation matrix    → vision-cone sweep angle computed with 2×2 rotation
• Translation matrix → camera / map scroll offset
• Guards on mirrored patrol routes created by reflecting waypoint lists
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
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE,
)
from animation import ParticleSystem, ScreenShake
from ui import (
    HealthBar, ScoreDisplay, FPSCounter, FloatingTextManager,
    MessageQueue, draw_text, draw_glow_text, ProgressBar,
    LivesDisplay, VignetteOverlay,
)
from games.common import (
    BasePlayer, Tile, Camera,
    mat_rotation, mat_reflection_y, mat_reflection_x,
    mat_transform, rotate_point,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Tile / Room helpers
# ─────────────────────────────────────────────────────────────────────────────

TILE_SIZE = 48

def _wall(tx: int, ty: int, tw: int = 1, th: int = 1) -> Tile:
    """Helper: build a Tile from tile-grid coordinates."""
    return Tile(tx * TILE_SIZE, ty * TILE_SIZE, tw * TILE_SIZE, th * TILE_SIZE)


def _rect(tx: int, ty: int, tw: int = 1, th: int = 1) -> pygame.Rect:
    return pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, tw * TILE_SIZE, th * TILE_SIZE)


# ─────────────────────────────────────────────────────────────────────────────
#  Key & Door
# ─────────────────────────────────────────────────────────────────────────────

class Key:
    SIZE = 14

    def __init__(self, x: float, y: float, key_id: int) -> None:
        self.x, self.y  = x, y
        self.key_id     = key_id
        self.collected  = False
        self._bob       = 0.0

    def update(self, dt: float) -> None:
        self._bob += dt * 3.0

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        if self.collected:
            return
        px = int(self.x) - offset[0]
        py = int(self.y + math.sin(self._bob) * 4) - offset[1]
        pygame.draw.circle(surface, GOLD, (px, py), self.SIZE)
        pygame.draw.circle(surface, WHITE, (px, py), self.SIZE, 2)
        draw_text(surface, str(self.key_id), px, py, FONT_SMALL, BLACK,
                  bold=True, anchor="center")


class Door:
    def __init__(self, x: int, y: int, w: int, h: int, key_id: int, color: Tuple[int,int,int] = MATRIX_GREEN) -> None:
        self.rect    = pygame.Rect(x, y, w, h)
        self.key_id  = key_id
        self.locked  = True
        self.color   = color

    def unlock(self) -> None:
        self.locked = False

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        col = NEON_RED if self.locked else self.color
        r   = pygame.Rect(self.rect.x - offset[0], self.rect.y - offset[1],
                          self.rect.width, self.rect.height)
        pygame.draw.rect(surface, col, r, border_radius=4)
        pygame.draw.rect(surface, WHITE, r, 2, border_radius=4)
        lbl = "🔒" if self.locked else "✓"
        draw_text(surface, lbl, r.centerx, r.centery, FONT_SMALL,
                  WHITE, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Exit
# ─────────────────────────────────────────────────────────────────────────────

class Exit:
    SIZE = 30

    def __init__(self, x: float, y: float, color: Tuple[int,int,int] = MATRIX_GREEN) -> None:
        self.rect  = pygame.Rect(int(x) - self.SIZE, int(y) - self.SIZE,
                                 self.SIZE * 2, self.SIZE * 2)
        self._anim = 0.0
        self.color = color

    def update(self, dt: float) -> None:
        self._anim += dt

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        px = self.rect.centerx - offset[0]
        py = self.rect.centery - offset[1]
        r  = int(self.SIZE + 3 * math.sin(self._anim * 3))
        pygame.draw.circle(surface, self.color, (px, py), r)
        pygame.draw.circle(surface, WHITE,        (px, py), r, 2)
        draw_text(surface, "EXIT", px, py, FONT_SMALL, BLACK, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  HealingZone (Data Cache)
# ─────────────────────────────────────────────────────────────────────────────

class HealingZone:
    SIZE = 24

    def __init__(self, x: float, y: float) -> None:
        self.rect = pygame.Rect(int(x) - self.SIZE, int(y) - self.SIZE,
                                self.SIZE * 2, self.SIZE * 2)
        self._anim = 0.0

    def update(self, dt: float) -> None:
        self._anim += dt

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        px = self.rect.centerx - offset[0]
        py = self.rect.centery - offset[1]
        
        # Pulse cyan
        pulse = abs(math.sin(self._anim * 4))
        r = int(self.SIZE + 4 * pulse)
        
        pygame.draw.circle(surface, NEON_CYAN, (px, py), r, 2)
        pygame.draw.circle(surface, (0, 100, 100, 100), (px, py), self.SIZE)
        draw_text(surface, "+", px, py, FONT_LARGE, NEON_CYAN, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Guard (enemy)
# ─────────────────────────────────────────────────────────────────────────────

class Guard:
    """
    Patrol guard with vision cone.

    The patrol route of every other guard is computed by reflecting the
    waypoints of the first guard across the Y-axis — demonstrating the
    reflection matrix in gameplay AI.
    """

    def __init__(
        self,
        waypoints: List[Tuple[float,float]],
        mirror: bool = False,
        gtype: str = "normal",
    ) -> None:
        """
        waypoints : list of (x,y) world positions the guard walks between.
        mirror    : if True, reflect the waypoints using the reflection matrix.
        gtype     : "novice" | "normal" | "camera" | "alert" | "elite"
        """
        self.gtype = gtype

        # Base stats
        self.VISION_RANGE = 180.0
        self.VISION_HALF  = math.radians(40)
        self.PATROL_SPEED = 70.0
        self.CHASE_SPEED  = 130.0
        self.ALERT_STEPS  = 3

        if gtype == "novice":
            self.VISION_RANGE = 150.0
            self.VISION_HALF = math.radians(30)
            self.PATROL_SPEED = 50.0
            self.CHASE_SPEED = 100.0
        elif gtype == "camera":
            self.VISION_RANGE = 220.0
            self.VISION_HALF = math.radians(20)
            self.PATROL_SPEED = 0.0 # Cameras don't move
            self.CHASE_SPEED = 0.0
        elif gtype == "alert":
            self.VISION_RANGE = 220.0
            self.VISION_HALF = math.radians(50)
            self.PATROL_SPEED = 100.0
            self.CHASE_SPEED = 160.0
        elif gtype == "elite":
            self.VISION_RANGE = 250.0
            self.VISION_HALF = math.radians(60)
            self.PATROL_SPEED = 120.0
            self.CHASE_SPEED = 200.0

        if mirror:
            # ── Reflection matrix integration ──────────────────────
            # Reflect all waypoints across the vertical centre line
            mid_x = SCREEN_WIDTH * 1.5   # midpoint of the map
            ref   = mat_reflection_y()   # y-axis reflection
            reflected = []
            for wx, wy in waypoints:
                # translate to origin, reflect, translate back
                lx, ly = wx - mid_x, wy
                rx, ry = mat_transform(ref, (lx, ly))
                reflected.append((rx + mid_x, ry))
            waypoints = reflected

        self._waypoints = waypoints
        self._wp_idx    = 0
        self.x, self.y  = waypoints[0]
        self.angle      = 0.0          # facing direction (rad)
        self.state      = "patrol"     # patrol | alert | chase | return
        self._alert_t   = 0.0
        self._chase_t   = 0.0
        self._scan_dir  = 1
        self._scan_t    = 0.0
        self._hit_flash = 0.0
        self.alive      = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 12, int(self.y) - 12, 24, 24)

    @property
    def center(self) -> Tuple[float,float]:
        return (self.x, self.y)

    def can_see(self, tx: float, ty: float, obstacles: List[pygame.Rect]) -> bool:
        """True if target (tx, ty) is inside the vision cone."""
        dx, dy  = tx - self.x, ty - self.y
        dist    = math.hypot(dx, dy)
        if dist > self.VISION_RANGE:
            return False

        # Angle to target
        angle_to = math.atan2(dy, dx)

        # ── Rotation matrix: compute angular difference ──
        # Rotate the target vector by -self.angle, then check x > 0 and |y| small
        rel = mat_transform(mat_rotation(-self.angle), (dx, dy))
        rel_angle = math.atan2(rel[1], rel[0])

        if abs(rel_angle) > self.VISION_HALF:
            return False

        # Line-of-sight check (simple ray-vs-rect)
        for obs in obstacles:
            if obs.clipline((int(self.x), int(self.y)), (int(tx), int(ty))):
                return False
        return True

    def update(self, dt: float, player_pos: Tuple[float,float],
               player_crouch: bool, obstacles: List[pygame.Rect],
               alarm_active: bool) -> str:
        """
        Update guard AI.
        Returns: "" | "spotted" | "alarm"
        """
        self._hit_flash = max(0.0, self._hit_flash - dt)
        px, py  = player_pos
        detect  = self.can_see(px, py, obstacles)
        if player_crouch:
            detect = detect and math.hypot(px - self.x, py - self.y) < self.VISION_RANGE * 0.5

        result = ""

        if self.state == "patrol":
            if self.gtype == "camera":
                self.angle += 1.5 * dt
            else:
                # Walk toward current waypoint
                wx, wy = self._waypoints[self._wp_idx]
                dx, dy = wx - self.x, wy - self.y
                d = math.hypot(dx, dy)
                if d < 8:
                    self._wp_idx = (self._wp_idx + 1) % len(self._waypoints)
                else:
                    spd = self.PATROL_SPEED
                    self.x += (dx / d) * spd * dt
                    self.y += (dy / d) * spd * dt
                    self.angle = math.atan2(dy, dx)

                # Slow scanning sweep (rotation matrix applied to facing angle)
                self._scan_t += dt
                if self._scan_t > 1.8:
                    self._scan_t = 0.0
                    self._scan_dir *= -1
                self.angle += self._scan_dir * 0.4 * dt

            if detect:
                self.state    = "alert"
                self._alert_t = self.ALERT_STEPS
                result        = "spotted"

        elif self.state == "alert":
            # Face the player
            dx, dy = px - self.x, py - self.y
            self.angle = math.atan2(dy, dx)
            if detect:
                self._alert_t -= dt
                if self._alert_t <= 0:
                    self.state = "chase"
                    result     = "alarm"
            else:
                self._alert_t += dt * 0.5
                if self._alert_t >= self.ALERT_STEPS:
                    self.state = "patrol"

        elif self.state == "chase":
            dx, dy = px - self.x, py - self.y
            d = math.hypot(dx, dy) or 1
            self.x += (dx/d) * self.CHASE_SPEED * dt
            self.y += (dy/d) * self.CHASE_SPEED * dt
            self.angle = math.atan2(dy, dx)
            if not alarm_active:
                self.state = "patrol"

        return result

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        cx = int(self.x) - offset[0]
        cy = int(self.y) - offset[1]

        # ── Vision cone (drawn with rotation matrix for edge points) ──
        cone_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        n_rays    = 12
        cone_pts  = [(cx, cy)]
        for i in range(n_rays + 1):
            frac  = i / n_rays
            ray_a = self.angle - self.VISION_HALF + frac * 2 * self.VISION_HALF
            # Rotate base vector (VISION_RANGE, 0) by ray_a
            rx, ry = mat_transform(mat_rotation(ray_a), (self.VISION_RANGE, 0))
            cone_pts.append((cx + int(rx), cy + int(ry)))

        if self.state == "chase":
            cone_col = (255, 30, 30, 60)
        elif self.state == "alert":
            cone_col = (255, 200, 0, 60)
        else:
            cone_col = (255, 255, 255, 25)

        if len(cone_pts) >= 3:
            pygame.draw.polygon(cone_surf, cone_col, cone_pts)
        surface.blit(cone_surf, (0, 0))

        # Guard body
        body_col = {
            "patrol": (60, 100, 200),
            "alert":  (220, 180, 0),
            "chase":  (220, 40,  40),
            "return": (60, 100, 200),
        }.get(self.state, (60, 100, 200))
        
        if self._hit_flash > 0:
            body_col = WHITE

        if self.gtype == "camera":
            pygame.draw.rect(surface, (40, 40, 40), (cx - 10, cy - 10, 20, 20))
            pygame.draw.rect(surface, NEON_RED if self.state == "alert" else NEON_CYAN, (cx - 4, cy - 4, 8, 8))
        else:
            pygame.draw.circle(surface, body_col, (cx, cy), 12)
            pygame.draw.circle(surface, WHITE,    (cx, cy), 12, 2)

            # Facing line
            ex = cx + int(math.cos(self.angle) * 18)
            ey = cy + int(math.sin(self.angle) * 18)
            pygame.draw.line(surface, WHITE, (cx, cy), (ex, ey), 2)

        # Alert indicator
        if self.state == "alert":
            pct = 1.0 - max(0, self._alert_t) / self.ALERT_STEPS
            draw_text(surface, "?!", cx, cy - 22, FONT_SMALL, NEON_YELLOW,
                      bold=True, anchor="center")
        elif self.state == "chase":
            draw_text(surface, "!", cx, cy - 22, FONT_SMALL, NEON_RED,
                      bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Assassin Player
# ─────────────────────────────────────────────────────────────────────────────

class AssassinPlayer(BasePlayer):
    WALK_SPEED   = 150.0
    CROUCH_SPEED = 75.0
    SIZE_NORMAL  = (22, 30)
    SIZE_CROUCH  = (22, 16)

    STEALTH_KILL_RANGE = 40.0   # px — must be this close, behind the guard

    def __init__(self, x: float, y: float) -> None:
        super().__init__(x, y, 22, 30, max_hp=1.0)   # 1 hit = dead in stealth
        self.lives       = LIVES
        self.crouch      = False
        self._has_keys: set[int] = set()
        self._anim_t     = 0.0
        self._step_t     = 0.0

    def has_key(self, key_id: int) -> bool:
        return key_id in self._has_keys

    def collect_key(self, key_id: int) -> None:
        self._has_keys.add(key_id)

    def try_stealth_kill(self, guard) -> bool:
        """
        Attempt a stealth kill on *guard*.
        Succeeds if:
          1. Player is within STEALTH_KILL_RANGE
          2. Player is roughly BEHIND the guard (> 90° from guard's facing)
          3. Guard is NOT in 'chase' state
        Returns True on success.
        """
        gx, gy = guard.center
        px, py = self.x + self.width/2, self.y + self.height/2
        dist   = math.hypot(px - gx, py - gy)
        if dist > self.STEALTH_KILL_RANGE:
            return False
        if guard.state == 'chase':
            return False
        if guard.gtype == 'camera':
            return False
        # Dot product: player relative to guard vs guard facing direction
        # If player is BEHIND the guard, dot product with facing < 0
        fwd_x = math.cos(guard.angle)
        fwd_y = math.sin(guard.angle)
        to_px = px - gx
        to_py = py - gy
        dot   = fwd_x * to_px + fwd_y * to_py
        if dot > 0:   # player is in front — cannot stealth kill
            return False
        return True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LCTRL, pygame.K_c):
                self.crouch = True
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_LCTRL, pygame.K_c):
                self.crouch = False

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper,
               obstacles: List[pygame.Rect],
               doors: List[Door]) -> str:
        """Return "" or "footstep"."""
        self.update_invincible(dt)
        speed = self.CROUCH_SPEED if self.crouch else self.WALK_SPEED
        w, h  = self.SIZE_CROUCH if self.crouch else self.SIZE_NORMAL
        self.width, self.height = w, h

        dx, dy = 0.0, 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        mag = math.hypot(dx, dy)
        moving = mag > 0
        if moving:
            dx, dy = dx/mag, dy/mag

        self.vx = dx * speed
        self.vy = dy * speed

        self._anim_t += dt
        if moving:
            self._step_t += dt

        # ── X movement + collision ──
        self.x += self.vx * dt
        for obs in obstacles:
            if self.rect.colliderect(obs):
                if self.vx > 0: self.x = obs.left - self.width
                elif self.vx < 0: self.x = obs.right
        # Door collision
        for door in doors:
            if door.locked and self.rect.colliderect(door.rect):
                if self.vx > 0: self.x = door.rect.left - self.width
                elif self.vx < 0: self.x = door.rect.right

        # ── Y movement + collision ──
        self.y += self.vy * dt
        for obs in obstacles:
            if self.rect.colliderect(obs):
                if self.vy > 0: self.y = obs.top - self.height
                elif self.vy < 0: self.y = obs.bottom
        for door in doors:
            if door.locked and self.rect.colliderect(door.rect):
                if self.vy > 0: self.y = door.rect.top - self.height
                elif self.vy < 0: self.y = door.rect.bottom

        # Footstep sound trigger every 0.45s while walking
        if self._step_t > 0.45 and not self.crouch:
            self._step_t = 0.0
            return "footstep"
        return ""

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        if self.invincible_t > 0 and int(self.invincible_t * 10) % 2:
            return
        cx = int(self.x) - offset[0] + self.width  // 2
        cy = int(self.y) - offset[1] + self.height // 2
        h  = self.height // 2

        # Body
        body_col = MATRIX_GREEN
        pygame.draw.ellipse(surface, body_col,
                            (cx - 11, cy - h, 22, h * 2))
        pygame.draw.ellipse(surface, WHITE,
                            (cx - 11, cy - h, 22, h * 2), 2)

        # Head
        pygame.draw.circle(surface, NEON_CYAN, (cx, cy - h - 8), 9)
        pygame.draw.circle(surface, WHITE,     (cx, cy - h - 8), 9, 1)

        # Crouch indicator
        if self.crouch:
            pygame.draw.line(surface, NEON_YELLOW,
                             (cx - 14, cy + h - 2), (cx + 14, cy + h - 2), 2)

    def draw_hud(self, surface: pygame.Surface) -> None:
        # Keys collected
        draw_text(surface, "KEYS:", 10, SCREEN_HEIGHT - 50, FONT_SMALL, GOLD)
        for i, kid in enumerate(sorted(self._has_keys)):
            pygame.draw.circle(surface, GOLD, (80 + i * 22, SCREEN_HEIGHT - 42), 9)
            draw_text(surface, str(kid), 80 + i * 22, SCREEN_HEIGHT - 42,
                      FONT_SMALL, BLACK, bold=True, anchor="center")
        draw_text(surface, "[C] Crouch  [E] Interact/Stealth Kill",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18, FONT_SMALL,
                  DARK_GRAY, anchor="midbottom")


# ─────────────────────────────────────────────────────────────────────────────
#  Level definitions
# ─────────────────────────────────────────────────────────────────────────────

# Map is defined in tile coordinates (TILE_SIZE = 48 px)
# '#' = wall, ' ' = open, 'P' = player start, 'E' = exit,
# 'K' = key, 'D' = door, 'G' = guard

LEVEL_MAPS = [
    # Level 1 — Simple Corridor (2-point patrols)
    dict(
        tiles=[
            _wall(0,0,20,1), _wall(0,10,20,1),
            _wall(0,0,1,11), _wall(19,0,1,11),
            _wall(6,1,2,6), _wall(13,4,2,6),
        ],
        player=(2*TILE_SIZE, 5*TILE_SIZE),
        exit  =(17*TILE_SIZE, 5*TILE_SIZE),
        keys  =[(4*TILE_SIZE, 8*TILE_SIZE, 1)],
        doors=[pygame.Rect(13*TILE_SIZE, 1*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*3)],
        door_keys=[1],
        guard_waypoints=[
            [(9*TILE_SIZE, 2*TILE_SIZE), (9*TILE_SIZE, 8*TILE_SIZE)],
        ],
        guard_mirrors=[False],
        heals=[]
    ),
    # Level 2 — Open Rooms (2-point patrols)
    dict(
        tiles=[
            _wall(0,0,20,1), _wall(0,16,20,1),
            _wall(0,0,1,17), _wall(19,0,1,17),
            _wall(9,0,2,6), _wall(9,10,2,6),
        ],
        player=(2*TILE_SIZE, 2*TILE_SIZE),
        exit  =(17*TILE_SIZE, 14*TILE_SIZE),
        keys  =[(2*TILE_SIZE, 14*TILE_SIZE, 1)],
        doors=[pygame.Rect(9*TILE_SIZE, 6*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*4)],
        door_keys=[1],
        guard_waypoints=[
            [(4*TILE_SIZE, 4*TILE_SIZE), (4*TILE_SIZE, 12*TILE_SIZE)],
            [(14*TILE_SIZE, 4*TILE_SIZE), (14*TILE_SIZE, 12*TILE_SIZE)],
        ],
        guard_mirrors=[False, False],
        heals=[]
    ),
    # Level 3 — Simple Maze (2-point patrols)
    dict(
        tiles=[
            _wall(0,0,20,1), _wall(0,14,20,1),
            _wall(0,0,1,15), _wall(19,0,1,15),
            _wall(4,4,12,2), _wall(4,8,12,2),
        ],
        player=(2*TILE_SIZE, 2*TILE_SIZE),
        exit  =(17*TILE_SIZE, 12*TILE_SIZE),
        keys  =[(9*TILE_SIZE, 6*TILE_SIZE, 1)],
        doors=[pygame.Rect(16*TILE_SIZE, 10*TILE_SIZE, TILE_SIZE*3, TILE_SIZE*2)],
        door_keys=[1],
        guard_waypoints=[
            [(2*TILE_SIZE, 6*TILE_SIZE), (17*TILE_SIZE, 6*TILE_SIZE)],
            [(17*TILE_SIZE, 10*TILE_SIZE), (2*TILE_SIZE, 10*TILE_SIZE)],
        ],
        guard_mirrors=[False, False],
        heals=[]
    ),
    # Level 4 — Grid Maze (3-point patrols)
    dict(
        tiles=[
            _wall(0,0,22,1), _wall(0,22,22,1),
            _wall(0,0,1,23), _wall(21,0,1,23),
            _wall(5,5,4,4), _wall(13,5,4,4),
            _wall(5,13,4,4), _wall(13,13,4,4),
        ],
        player=(2*TILE_SIZE, 2*TILE_SIZE),
        exit  =(19*TILE_SIZE, 19*TILE_SIZE),
        keys  =[(11*TILE_SIZE, 2*TILE_SIZE, 1), (2*TILE_SIZE, 11*TILE_SIZE, 2)],
        doors=[
            pygame.Rect(9*TILE_SIZE, 5*TILE_SIZE, TILE_SIZE*4, TILE_SIZE*2),
            pygame.Rect(9*TILE_SIZE, 15*TILE_SIZE, TILE_SIZE*4, TILE_SIZE*2),
        ],
        door_keys=[1, 2],
        guard_waypoints=[
            [(3*TILE_SIZE, 3*TILE_SIZE), (9*TILE_SIZE, 3*TILE_SIZE), (9*TILE_SIZE, 9*TILE_SIZE)],
            [(19*TILE_SIZE, 3*TILE_SIZE), (13*TILE_SIZE, 3*TILE_SIZE), (13*TILE_SIZE, 9*TILE_SIZE)],
            [(3*TILE_SIZE, 19*TILE_SIZE), (9*TILE_SIZE, 19*TILE_SIZE), (9*TILE_SIZE, 13*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False],
        heals=[]
    ),
    # Level 5 — H-Shaped Maze (3-point patrols)
    dict(
        tiles=[
            _wall(0,0,24,1), _wall(0,20,24,1),
            _wall(0,0,1,21), _wall(23,0,1,21),
            _wall(6,1,2,8), _wall(6,13,2,8),
            _wall(16,1,2,8), _wall(16,13,2,8),
            _wall(6,9,12,2),
        ],
        player=(3*TILE_SIZE, 10*TILE_SIZE),
        exit  =(20*TILE_SIZE, 10*TILE_SIZE),
        keys  =[(3*TILE_SIZE, 3*TILE_SIZE, 1), (3*TILE_SIZE, 17*TILE_SIZE, 2)],
        doors=[
            pygame.Rect(16*TILE_SIZE, 9*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*4),
        ],
        door_keys=[1, 2],
        guard_waypoints=[
            [(11*TILE_SIZE, 4*TILE_SIZE), (11*TILE_SIZE, 7*TILE_SIZE), (14*TILE_SIZE, 7*TILE_SIZE)],
            [(11*TILE_SIZE, 16*TILE_SIZE), (11*TILE_SIZE, 13*TILE_SIZE), (14*TILE_SIZE, 13*TILE_SIZE)],
            [(20*TILE_SIZE, 4*TILE_SIZE), (20*TILE_SIZE, 16*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False],
        heals=[]
    ),
    # Level 6 — Cross Maze (3-point patrols)
    dict(
        tiles=[
            _wall(0,0,24,1), _wall(0,24,24,1),
            _wall(0,0,1,25), _wall(23,0,1,25),
            _wall(0,0,8,8), _wall(16,0,8,8),
            _wall(0,16,8,8), _wall(16,16,8,8),
        ],
        player=(12*TILE_SIZE, 22*TILE_SIZE),
        exit  =(12*TILE_SIZE, 2*TILE_SIZE),
        keys  =[(2*TILE_SIZE, 12*TILE_SIZE, 1), (22*TILE_SIZE, 12*TILE_SIZE, 2)],
        doors=[
            pygame.Rect(9*TILE_SIZE, 8*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*2),
            pygame.Rect(13*TILE_SIZE, 8*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*2),
        ],
        door_keys=[1, 2],
        guard_waypoints=[
            [(10*TILE_SIZE, 10*TILE_SIZE), (10*TILE_SIZE, 14*TILE_SIZE), (14*TILE_SIZE, 14*TILE_SIZE), (14*TILE_SIZE, 10*TILE_SIZE)],
            [(4*TILE_SIZE, 9*TILE_SIZE), (6*TILE_SIZE, 9*TILE_SIZE), (6*TILE_SIZE, 15*TILE_SIZE)],
            [(20*TILE_SIZE, 9*TILE_SIZE), (18*TILE_SIZE, 9*TILE_SIZE), (18*TILE_SIZE, 15*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False],
        heals=[]
    ),
    # Level 7 — Spiral Maze (4-point patrols)
    dict(
        tiles=[
            _wall(0,0,22,1), _wall(0,22,22,1),
            _wall(0,0,1,23), _wall(21,0,1,23),
            _wall(4,4,14,2), _wall(4,4,2,14),
            _wall(4,18,18,2), _wall(18,8,2,12),
            _wall(8,8,12,2), _wall(8,8,2,8),
            _wall(8,14,8,2), _wall(14,10,2,6),
        ],
        player=(2*TILE_SIZE, 2*TILE_SIZE),
        exit  =(11*TILE_SIZE, 11*TILE_SIZE),
        keys  =[(19*TILE_SIZE, 5*TILE_SIZE, 1), (2*TILE_SIZE, 20*TILE_SIZE, 2)],
        doors=[
            pygame.Rect(14*TILE_SIZE, 12*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*2),
            pygame.Rect(11*TILE_SIZE, 14*TILE_SIZE, TILE_SIZE*3, TILE_SIZE*2),
        ],
        door_keys=[1, 2],
        guard_waypoints=[
            [(10*TILE_SIZE, 2*TILE_SIZE), (19*TILE_SIZE, 2*TILE_SIZE), (19*TILE_SIZE, 6*TILE_SIZE)],
            [(6*TILE_SIZE, 6*TILE_SIZE), (6*TILE_SIZE, 16*TILE_SIZE), (16*TILE_SIZE, 16*TILE_SIZE)],
            [(16*TILE_SIZE, 6*TILE_SIZE), (10*TILE_SIZE, 6*TILE_SIZE), (10*TILE_SIZE, 12*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False],
        heals=[]
    ),
    # Level 8 — Key-Lock Maze (4-point patrols)
    dict(
        tiles=[
            _wall(0,0,26,1), _wall(0,20,26,1),
            _wall(0,0,1,21), _wall(25,0,1,21),
            _wall(6,1,2,14), _wall(18,6,2,14),
            _wall(6,6,8,2), _wall(12,12,8,2),
        ],
        player=(2*TILE_SIZE, 2*TILE_SIZE),
        exit  =(23*TILE_SIZE, 18*TILE_SIZE),
        keys  =[(2*TILE_SIZE, 18*TILE_SIZE, 1), (23*TILE_SIZE, 2*TILE_SIZE, 2), (10*TILE_SIZE, 9*TILE_SIZE, 3)],
        doors=[
            pygame.Rect(6*TILE_SIZE, 15*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*5),
            pygame.Rect(18*TILE_SIZE, 1*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*5),
            pygame.Rect(14*TILE_SIZE, 6*TILE_SIZE, TILE_SIZE*4, TILE_SIZE*2),
        ],
        door_keys=[1, 2, 3],
        guard_waypoints=[
            [(9*TILE_SIZE, 3*TILE_SIZE), (15*TILE_SIZE, 3*TILE_SIZE), (15*TILE_SIZE, 5*TILE_SIZE), (9*TILE_SIZE, 5*TILE_SIZE)],
            [(9*TILE_SIZE, 15*TILE_SIZE), (15*TILE_SIZE, 15*TILE_SIZE), (15*TILE_SIZE, 17*TILE_SIZE), (9*TILE_SIZE, 17*TILE_SIZE)],
            [(22*TILE_SIZE, 6*TILE_SIZE), (22*TILE_SIZE, 12*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False],
        heals=[]
    ),
    # Level 9 — Dead-End Trap Maze (4-point patrols)
    dict(
        tiles=[
            _wall(0,0,28,1), _wall(0,20,28,1),
            _wall(0,0,1,21), _wall(27,0,1,21),
            _wall(4,4,8,2), _wall(16,4,8,2),
            _wall(4,14,8,2), _wall(16,14,8,2),
            _wall(13,0,2,8), _wall(13,12,2,8),
        ],
        player=(2*TILE_SIZE, 10*TILE_SIZE),
        exit  =(25*TILE_SIZE, 10*TILE_SIZE),
        keys  =[(25*TILE_SIZE, 2*TILE_SIZE, 1), (25*TILE_SIZE, 18*TILE_SIZE, 2)],
        doors=[
            pygame.Rect(13*TILE_SIZE, 8*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*4),
        ],
        door_keys=[1, 2],
        guard_waypoints=[
            [(7*TILE_SIZE, 7*TILE_SIZE), (11*TILE_SIZE, 7*TILE_SIZE), (11*TILE_SIZE, 13*TILE_SIZE), (7*TILE_SIZE, 13*TILE_SIZE)],
            [(17*TILE_SIZE, 7*TILE_SIZE), (21*TILE_SIZE, 7*TILE_SIZE), (21*TILE_SIZE, 13*TILE_SIZE), (17*TILE_SIZE, 13*TILE_SIZE)],
            [(2*TILE_SIZE, 4*TILE_SIZE), (2*TILE_SIZE, 16*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False],
        heals=[]
    ),
    # Level 10 — Security Facility (Overlapping patrols)
    dict(
        tiles=[
            _wall(0,0,30,1), _wall(0,24,30,1),
            _wall(0,0,1,25), _wall(29,0,1,25),
            _wall(5,5,6,6), _wall(19,5,6,6),
            _wall(5,13,6,6), _wall(19,13,6,6),
        ],
        player=(2*TILE_SIZE, 12*TILE_SIZE),
        exit  =(27*TILE_SIZE, 12*TILE_SIZE),
        keys  =[(14*TILE_SIZE, 2*TILE_SIZE, 1), (14*TILE_SIZE, 22*TILE_SIZE, 2)],
        doors=[
            pygame.Rect(11*TILE_SIZE, 11*TILE_SIZE, TILE_SIZE*8, TILE_SIZE*2),
        ],
        door_keys=[1, 2],
        guard_waypoints=[
            [(4*TILE_SIZE, 4*TILE_SIZE), (25*TILE_SIZE, 4*TILE_SIZE), (25*TILE_SIZE, 12*TILE_SIZE)],
            [(4*TILE_SIZE, 20*TILE_SIZE), (25*TILE_SIZE, 20*TILE_SIZE), (25*TILE_SIZE, 12*TILE_SIZE)],
            [(15*TILE_SIZE, 4*TILE_SIZE), (15*TILE_SIZE, 20*TILE_SIZE)],
            [(12*TILE_SIZE, 8*TILE_SIZE), (17*TILE_SIZE, 8*TILE_SIZE), (17*TILE_SIZE, 16*TILE_SIZE), (12*TILE_SIZE, 16*TILE_SIZE)],
        ],
        guard_mirrors=[False, False, False, False],
        heals=[]
    ),
    # Level 11 — The Vault (Boss Level design)
    dict(
        tiles=[
            _wall(0,0,32,1), _wall(0,24,32,1),
            _wall(0,0,1,25), _wall(31,0,1,25),
            _wall(10,8,12,2), _wall(10,14,12,2),
            _wall(10,8,2,8), _wall(20,8,2,8),
            _wall(4,4,4,4), _wall(24,4,4,4),
            _wall(4,16,4,4), _wall(24,16,4,4),
        ],
        player=(2*TILE_SIZE, 12*TILE_SIZE),
        exit  =(15*TILE_SIZE, 11*TILE_SIZE),
        keys  =[(2*TILE_SIZE, 2*TILE_SIZE, 1), (29*TILE_SIZE, 2*TILE_SIZE, 2), (2*TILE_SIZE, 22*TILE_SIZE, 3), (29*TILE_SIZE, 22*TILE_SIZE, 4)],
        doors=[
            pygame.Rect(12*TILE_SIZE, 10*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*4),
            pygame.Rect(18*TILE_SIZE, 10*TILE_SIZE, TILE_SIZE*2, TILE_SIZE*4),
        ],
        door_keys=[1, 2, 3, 4],
        guard_waypoints=[
            [(6*TILE_SIZE, 2*TILE_SIZE), (25*TILE_SIZE, 2*TILE_SIZE), (25*TILE_SIZE, 9*TILE_SIZE), (6*TILE_SIZE, 9*TILE_SIZE)],
            [(6*TILE_SIZE, 22*TILE_SIZE), (25*TILE_SIZE, 22*TILE_SIZE), (25*TILE_SIZE, 15*TILE_SIZE), (6*TILE_SIZE, 15*TILE_SIZE)],
            [(16*TILE_SIZE, 3*TILE_SIZE), (16*TILE_SIZE, 7*TILE_SIZE), (2*TILE_SIZE, 7*TILE_SIZE)],
            [(16*TILE_SIZE, 21*TILE_SIZE), (16*TILE_SIZE, 17*TILE_SIZE), (29*TILE_SIZE, 17*TILE_SIZE)],
            [(15*TILE_SIZE, 10*TILE_SIZE), (16*TILE_SIZE, 10*TILE_SIZE), (16*TILE_SIZE, 14*TILE_SIZE), (15*TILE_SIZE, 14*TILE_SIZE)],
        ],
        guard_mirrors=[False]*5,
        heals=[]
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
#  AssassinGame
# ─────────────────────────────────────────────────────────────────────────────

class AssassinGame:
    """Stealth game with 3 levels, keys, locked doors, guards and alarm."""

    def __init__(self, screen: pygame.Surface, sound, settings, save_mgr, level: int = 1) -> None:
        self._screen   = screen
        self._sound    = sound
        self._settings = settings
        self._save     = save_mgr
        from config import GameID, LEVEL_THEMES
        self._game_id  = GameID.ASSASSIN
        self._level    = level
        self._theme_col= LEVEL_THEMES.get(level, MATRIX_GREEN)

        # We have 3 levels, so wrap around for level 4 and 5
        self._level_idx  = (level - 1) % len(LEVEL_MAPS)
        self._result     = None
        self._score      = 0
        self._alarm      = False
        self._alarm_t    = 0.0
        self._alarm_blink= 0.0

        self._particles  = ParticleSystem(300)
        self._shake      = ScreenShake()
        self._msgs       = MessageQueue(10, 80)
        self._fps_cnt    = FPSCounter(10, 10)
        self._score_disp = ScoreDisplay(SCREEN_WIDTH - 10, 10, anchor="topright")
        self._lives_disp = LivesDisplay(SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT - 65,
                                        max_lives=LIVES)
        self._vignette   = VignetteOverlay(SCREEN_WIDTH, SCREEN_HEIGHT)
        self._stealth_kills = 0
        self._floats     = FloatingTextManager()

        self._load_level(self._level_idx)
        self._sound.play_music("music_assassin")
        self._msgs.push(f"LEVEL {self._level} — Collect the key and reach the EXIT!", NEON_CYAN, 4.0)
        self._msgs.push("[C] Hold to crouch (reduces detection)", GOLD, 4.0)

    def _load_level(self, idx: int) -> None:
        from config import LEVEL_THEMES
        theme = LEVEL_THEMES.get(self._level, MATRIX_GREEN)

        data              = LEVEL_MAPS[idx]
        self._tiles       = data["tiles"]
        self._obs_rects   = [t.rect for t in self._tiles]

        px, py            = data["player"]
        self._player      = AssassinPlayer(float(px), float(py))
        self._player.settings = self._settings

        ex, ey            = data["exit"]
        self._exit        = Exit(float(ex), float(ey), color=theme)

        self._keys: List[Key] = [
            Key(float(kx), float(ky), kid)
            for kx, ky, kid in data["keys"]
        ]
        self._doors: List[Door] = [
            Door(dr.x, dr.y, dr.width, dr.height, dk, color=theme)
            for dr, dk in zip(data["doors"], data["door_keys"])
        ]

        self._guards: List[Guard] = []
        for i, wp in enumerate(data["guard_waypoints"]):
            gt = "normal"
            if self._level == 1: gt = "novice"
            elif self._level >= 2 and self._level <= 5: gt = "alert"
            elif self._level >= 6 and self._level <= 9: gt = "camera" if i % 2 == 0 else "elite"
            elif self._level >= 10: gt = "elite"
            self._guards.append(Guard(wp, mirror=data["guard_mirrors"][i], gtype=gt))

        self._heals: List[HealingZone] = []
        if "heals" in data:
            for hx, hy in data["heals"]:
                self._heals.append(HealingZone(hx, hy))

        self._camera     = Camera(
            max(t.rect.right for t in self._tiles) + 50,
            max(t.rect.bottom for t in self._tiles) + 50,
        )
        self._alarm      = False
        self._alarm_t    = 0.0

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "pause"
        # Interact with doors & Stealth Kills
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            stealth_killed = False
            for guard in self._guards[:]:
                if self._player.try_stealth_kill(guard):
                    guard.hp = 0
                    guard.state = "dead"
                    self._guards.remove(guard)
                    gx, gy = guard.center
                    self._particles.emit_burst(gx, gy, 15, NEON_RED, 120, glow=True)
                    self._sound.play("explosion")
                    self._shake.shake(6, 0.2)
                    pts = 300 * (3 if self._level == 6 else 1)
                    self._msgs.push(f"STEALTH KILL +{pts}", NEON_PURPLE)
                    self._score += pts
                    self._stealth_kills += 1
                    self._floats.add(f"+{pts}", gx, gy, NEON_PURPLE)
                    stealth_killed = True
                    break

            if not stealth_killed:
                for door in self._doors:
                    if not door.locked:
                        continue
                    expand = self._player.rect.inflate(20, 20)
                    if expand.colliderect(door.rect) and self._player.has_key(door.key_id):
                        door.unlock()
                        self._sound.play("door_open")
                        self._msgs.push("Door unlocked!", MATRIX_GREEN)
        self._player.handle_event(event)
        return None

    def update(self, dt: float) -> Optional[str]:
        if self._result:
            return self._result

        keys = pygame.key.get_pressed()

        # Player movement
        sfx = self._player.update(dt, keys, self._obs_rects, self._doors)
        if sfx == "footstep":
            self._sound.play("footstep")

        self._camera.follow(self._player.rect, dt)

        # Key collection
        for key in self._keys:
            if not key.collected:
                key.update(dt)
                if self._player.rect.inflate(10,10).colliderect(
                        pygame.Rect(key.x-14, key.y-14, 28, 28)):
                    key.collected = True
                    self._player.collect_key(key.key_id)
                    self._sound.play("key_pickup")
                    self._particles.emit_ring(key.x, key.y, 16, GOLD)
                    self._msgs.push(f"Key {key.key_id} collected!", GOLD)
                    pts = 200 * (3 if self._level == 6 else 1)
                    self._score += pts
                    self._floats.add(f"+{pts}", key.x, key.y, GOLD)

        self._exit.update(dt)

        # Healing zones
        for hz in self._heals[:]:
            hz.update(dt)
            if self._player.rect.colliderect(hz.rect) and self._player.hp < self._player.max_hp:
                self._player.hp = min(self._player.max_hp, self._player.hp + 20)
                self._sound.play("powerup")
                self._msgs.push("DATA CACHE: Health Restored", NEON_CYAN)
                self._heals.remove(hz)
                self._particles.emit_ring(hz.rect.centerx, hz.rect.centery, 24, NEON_CYAN)

        # Guard updates
        for guard in self._guards:
            res = guard.update(dt, self._player.center, self._player.crouch,
                               self._obs_rects, self._alarm)
            if res == "spotted":
                self._sound.play("spotted")
                self._msgs.push("Guard suspicious!", NEON_YELLOW)
            elif res == "alarm":
                if not self._alarm:
                    self._alarm = True
                    self._alarm_t = 15.0
                    self._sound.play("alarm")
                    self._shake.shake(10, 0.5)
                    self._msgs.push("⚠ ALARM TRIGGERED!", NEON_RED, 3.0)

            # Guard catches player
            if guard.state == "chase" and guard.rect.colliderect(self._player.rect):
                self._player.alive = False

        # Alarm countdown
        if self._alarm:
            self._alarm_t    -= dt
            self._alarm_blink += dt
            if self._alarm_t <= 0:
                self._alarm = False
                self._sound.play("alarm_off")
                self._msgs.push("Alarm deactivated.", NEON_CYAN)

        # Particles
        self._particles.update(dt)
        self._floats.update(dt)
        self._msgs.update(dt)
        self._shake.update(dt)
        self._lives_disp.update(dt)
        self._vignette.update(dt)
        self._score_disp.set(self._score)
        self._score_disp.update(dt)

        # Exit check
        if self._exit.rect.colliderect(self._player.rect):
            self._score += 500 * (3 if self._level == 6 else 1)
            self._sound.play("victory")
            self._save.add_score(self._game_id, self._score)
            self._result = "win"
            return self._result

        # Player death -> Respawn logic
        if not self._player.alive:
            self._sound.play("death")
            self._player.lives -= 1
            self._lives_disp.set_lives(self._player.lives)
            if self._player.lives <= 0:
                self._result = "dead"
            else:
                self._load_level(self._level_idx)
                self._msgs.push(f"Lives remaining: {self._player.lives}", NEON_RED, 2.0)
                self._shake.shake(15, 0.6)
                self._player.alive = True
                
        return None

    def draw(self, clock: pygame.time.Clock) -> None:
        ox, oy   = self._shake.offset
        cam_off  = self._camera.offset

        self._screen.fill((8, 10, 18))

        # World surface
        world = pygame.Surface((SCREEN_WIDTH + 60, SCREEN_HEIGHT + 60))
        world.fill((8, 10, 18))

        # Floor grid
        for gx in range(0, 1200, TILE_SIZE):
            for gy in range(0, 900, TILE_SIZE):
                r = pygame.Rect(gx - cam_off[0] + ox, gy - cam_off[1] + oy, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self._screen, (12, 15, 25), r, 1)

        # Tiles
        for tile in self._tiles:
            tile.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))

        # Doors
        for door in self._doors:
            door.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))

        # Keys
        for key in self._keys:
            key.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))

        # Exit
        self._exit.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))
        
        # Healing zones
        for hz in self._heals:
            hz.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))

        # Guards
        for guard in self._guards:
            guard.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))

        # Player
        self._player.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))

        # Particles / floats
        self._particles.draw(self._screen, (cam_off[0] - ox, cam_off[1] - oy))
        self._floats.draw(self._screen,    (cam_off[0] - ox, cam_off[1] - oy))

        # ── HUD ──────────────────────────────────────────────────
        hp_ratio = 1.0 if not self._alarm else 0.25 # Vignette pulse intense during alarm
        self._vignette.draw(self._screen, hp_ratio)
        self._score_disp.draw(self._screen)
        self._lives_disp.draw(self._screen)

        if self._settings.show_fps:
            self._fps_cnt.update(clock)
            self._fps_cnt.draw(self._screen)

        # Level indicator
        lvl_txt = "THE ARCHITECT" if self._level == 6 else f"LEVEL {self._level}"
        col = GOLD if self._level == 6 else self._theme_col
        draw_text(self._screen, lvl_txt,
                  SCREEN_WIDTH // 2, 10, FONT_MEDIUM, col,
                  bold=True, anchor="midtop")
                  
        # Stealth Kills tracker
        draw_text(self._screen, f"Stealth Kills: {self._stealth_kills}",
                  SCREEN_WIDTH // 2, 35, FONT_SMALL, NEON_PURPLE, anchor="midtop")

        # Alarm overlay
        if self._alarm:
            if int(self._alarm_blink * 2) % 2 == 0:
                ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                ov.fill((200, 0, 0, 40))
                self._screen.blit(ov, (0, 0))
            draw_glow_text(self._screen, "⚠ ALARM ⚠",
                           SCREEN_WIDTH // 2, 65, FONT_LARGE, NEON_RED, glow_radius=6)
            draw_text(self._screen, f"Alarm: {int(self._alarm_t)}s",
                      SCREEN_WIDTH // 2, 105, FONT_SMALL, NEON_RED, anchor="midtop")

        self._msgs.draw(self._screen)
        self._player.draw_hud(self._screen)
