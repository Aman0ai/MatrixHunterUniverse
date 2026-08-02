"""
games/common.py
===============
Shared utilities used by all four mini-games:

• Matrix math helpers (rotation, scale, shear, reflection, translation)
• BaseEntity – positioned rectangular object with velocity
• Camera     – world-to-screen offset tracking
• Bullet     – generic projectile
• BasePlayer – movement skeleton
• BaseEnemy  – AI skeleton
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT, GRAVITY, NEON_CYAN, FONT_MEDIUM
from ui import draw_text


# ─────────────────────────────────────────────────────────────────────────────
#  Matrix Math  (core Linear-Algebra integration)
# ─────────────────────────────────────────────────────────────────────────────

# All matrices are stored as flat 4-tuples (a, b, c, d) representing
#   | a  b |
#   | c  d |

Matrix2x2 = Tuple[float, float, float, float]
Vec2       = Tuple[float, float]


def mat_rotation(angle_rad: float) -> Matrix2x2:
    """2×2 rotation matrix for *angle_rad* (counter-clockwise)."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return (c, -s, s, c)


def mat_scale(sx: float, sy: float) -> Matrix2x2:
    """2×2 uniform / non-uniform scale matrix."""
    return (sx, 0.0, 0.0, sy)


def mat_reflection_x() -> Matrix2x2:
    """Reflect across the X-axis  (y → −y)."""
    return (1.0, 0.0, 0.0, -1.0)


def mat_reflection_y() -> Matrix2x2:
    """Reflect across the Y-axis  (x → −x)."""
    return (-1.0, 0.0, 0.0, 1.0)


def mat_reflection_line(angle_rad: float) -> Matrix2x2:
    """Reflect across an arbitrary line through the origin."""
    c2 = math.cos(2 * angle_rad)
    s2 = math.sin(2 * angle_rad)
    return (c2, s2, s2, -c2)


def mat_shear(shx: float, shy: float = 0.0) -> Matrix2x2:
    """2×2 shear matrix — used for speed-blur in Runner."""
    return (1.0, shx, shy, 1.0)


def mat_mul(m1: Matrix2x2, m2: Matrix2x2) -> Matrix2x2:
    """Multiply two 2×2 matrices."""
    a1,b1,c1,d1 = m1
    a2,b2,c2,d2 = m2
    return (
        a1*a2 + b1*c2,  a1*b2 + b1*d2,
        c1*a2 + d1*c2,  c1*b2 + d1*d2,
    )


def mat_transform(m: Matrix2x2, v: Vec2) -> Vec2:
    """Apply 2×2 matrix to a 2-D vector."""
    a, b, c, d = m
    x, y = v
    return (a*x + b*y, c*x + d*y)


def rotate_point(x: float, y: float, angle_rad: float,
                 cx: float = 0.0, cy: float = 0.0) -> Vec2:
    """Rotate point (x,y) around centre (cx,cy)."""
    tx, ty = x - cx, y - cy
    rx, ry = mat_transform(mat_rotation(angle_rad), (tx, ty))
    return (rx + cx, ry + cy)


def scale_point(x: float, y: float, sx: float, sy: float,
                cx: float = 0.0, cy: float = 0.0) -> Vec2:
    """Scale point relative to a centre."""
    return ((x - cx) * sx + cx, (y - cy) * sy + cy)


def transform_formation(
    points: List[Vec2],
    matrix: Matrix2x2,
    origin: Vec2 = (0.0, 0.0),
) -> List[Vec2]:
    """Apply a 2×2 matrix to a list of offset vectors, then translate by origin."""
    ox, oy = origin
    return [(mat_transform(matrix, p)[0] + ox,
             mat_transform(matrix, p)[1] + oy)
            for p in points]


# ─────────────────────────────────────────────────────────────────────────────
#  Camera
# ─────────────────────────────────────────────────────────────────────────────

class Camera:
    """
    Follows a target rectangle smoothly.
    Call apply() to convert a world Rect → screen Rect.
    """

    def __init__(self, map_w: int = 0, map_h: int = 0,
                 deadzone: int = 60) -> None:
        self.x: float = 0.0
        self.y: float = 0.0
        self._map_w   = map_w if map_w > 0 else SCREEN_WIDTH
        self._map_h   = map_h if map_h > 0 else SCREEN_HEIGHT
        self._dead    = deadzone
        self._smoothing = 6.0   # higher = snappier

    def follow(self, target: pygame.Rect, dt: float) -> None:
        """Smooth-chase the centre of *target*."""
        ideal_x = target.centerx - SCREEN_WIDTH  // 2
        ideal_y = target.centery - SCREEN_HEIGHT // 2
        ideal_x = max(0, min(ideal_x, self._map_w - SCREEN_WIDTH))
        ideal_y = max(0, min(ideal_y, self._map_h - SCREEN_HEIGHT))
        t = min(1.0, dt * self._smoothing)
        self.x += (ideal_x - self.x) * t
        self.y += (ideal_y - self.y) * t

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        """Return the screen-space version of a world rect."""
        return pygame.Rect(rect.x - int(self.x), rect.y - int(self.y),
                           rect.width, rect.height)

    @property
    def offset(self) -> Tuple[int, int]:
        return (int(self.x), int(self.y))


# ─────────────────────────────────────────────────────────────────────────────
#  BaseEntity
# ─────────────────────────────────────────────────────────────────────────────

class BaseEntity:
    """Positioned game object with velocity, rect and alive flag."""

    def __init__(
        self,
        x: float, y: float,
        w: int, h: int,
        colour: Tuple[int,int,int] = (255, 255, 255),
    ) -> None:
        self.x, self.y   = x, y
        self.vx: float   = 0.0
        self.vy: float   = 0.0
        self.width       = w
        self.height      = h
        self.colour      = colour
        self.alive       = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def move(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        r = pygame.Rect(int(self.x) - offset[0], int(self.y) - offset[1],
                        self.width, self.height)
        pygame.draw.rect(surface, self.colour, r, border_radius=4)


# ─────────────────────────────────────────────────────────────────────────────
#  Bullet
# ─────────────────────────────────────────────────────────────────────────────

class Bullet(BaseEntity):
    """
    Generic projectile.

    The velocity is derived by applying a rotation matrix to a base
    direction vector — this is the core Linear Algebra integration
    for projectile direction.

    curve_rate  — angular velocity (rad/s) applied each frame via
                  rotation matrix, producing curved trajectories.
    """

    def __init__(
        self,
        x: float, y: float,
        angle: float,         # direction in radians
        speed: float,
        damage: float,
        colour: Tuple[int,int,int],
        radius: int = 4,
        curve_rate: float = 0.0,   # rad/s rotation of velocity vector
        owner: str = "player",     # "player" or "enemy"
        lifetime: float = 3.0,
    ) -> None:
        super().__init__(x - radius, y - radius, radius * 2, radius * 2, colour)
        self._angle      = angle
        self._speed      = speed
        self.damage      = damage
        self.radius      = radius
        self.curve_rate  = curve_rate
        self.owner       = owner
        self._lifetime   = lifetime
        # Initial velocity via rotation matrix on base vector (speed, 0)
        self.vx, self.vy = mat_transform(mat_rotation(angle), (speed, 0.0))
        self._trail: List[Tuple[float,float]] = []

    def update(self, dt: float) -> None:
        if not self.alive:
            return
        self._lifetime -= dt
        if self._lifetime <= 0:
            self.alive = False
            return

        # Store trail positions (last 5 frames)
        self._trail.append((self.x + self.radius, self.y + self.radius))
        if len(self._trail) > 5:
            self._trail.pop(0)

        # Apply rotation matrix to velocity vector (curved trajectory)
        if abs(self.curve_rate) > 0:
            vx, vy = mat_transform(mat_rotation(self.curve_rate * dt),
                                   (self.vx, self.vy))
            self.vx, self.vy = vx, vy
            # Re-normalise speed
            spd = math.hypot(self.vx, self.vy)
            if spd > 0:
                self.vx = self.vx / spd * self._speed
                self.vy = self.vy / spd * self._speed

        self.move(dt)

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        cx = int(self.x + self.radius) - offset[0]
        cy = int(self.y + self.radius) - offset[1]
        # Draw trail
        for i, (tx, ty) in enumerate(self._trail):
            alpha_r = int(self.radius * (i / max(1, len(self._trail))) * 0.7)
            if alpha_r > 0:
                tc = tuple(int(c * i / len(self._trail)) for c in self.colour)
                pygame.draw.circle(surface, tc,  # type: ignore[arg-type]
                                   (int(tx) - offset[0], int(ty) - offset[1]),
                                   alpha_r)
        pygame.draw.circle(surface, self.colour, (cx, cy), self.radius)
        # Bright core
        core = tuple(min(255, c + 80) for c in self.colour)
        pygame.draw.circle(surface, core, (cx, cy), max(1, self.radius - 2))  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
#  BasePlayer
# ─────────────────────────────────────────────────────────────────────────────

class BasePlayer(BaseEntity):
    """Shared player skeleton — health, invincibility frames, basic draw."""

    def __init__(
        self,
        x: float, y: float, w: int, h: int,
        max_hp: float = 100.0,
        colour: Tuple[int,int,int] = (0, 255, 70),
    ) -> None:
        super().__init__(x, y, w, h, colour)
        self.max_hp         = max_hp
        self.hp             = max_hp
        self.invincible_t   = 0.0   # seconds of invincibility remaining
        self.inv_duration   = 0.8
        self.score          = 0

    def take_damage(self, amount: float) -> bool:
        """Apply damage; returns True if damage was actually applied."""
        if self.invincible_t > 0:
            return False
        self.hp -= amount
        self.invincible_t = self.inv_duration
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
        return True

    def heal(self, amount: float) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def update_invincible(self, dt: float) -> None:
        if self.invincible_t > 0:
            self.invincible_t -= dt

    @property
    def is_invincible(self) -> bool:
        return self.invincible_t > 0

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0, 0)) -> None:
        # Flash when invincible
        if self.invincible_t > 0 and int(self.invincible_t * 10) % 2:
            return
        super().draw(surface, offset)


# ─────────────────────────────────────────────────────────────────────────────
#  BaseEnemy
# ─────────────────────────────────────────────────────────────────────────────

class BaseEnemy(BaseEntity):
    """Base enemy with HP, patrol/chase state machine, and drawing."""

    # AI states
    PATROL = "patrol"
    CHASE  = "chase"
    ATTACK = "attack"
    STUNNED= "stunned"

    def __init__(
        self,
        x: float, y: float, w: int, h: int,
        hp: float,
        speed: float,
        score_value: int,
        colour: Tuple[int,int,int] = (255, 50, 50),
    ) -> None:
        super().__init__(x, y, w, h, colour)
        self.hp            = hp
        self.max_hp        = hp
        self.speed         = speed
        self.score_value   = score_value
        self.state         = self.PATROL
        self._state_timer  = 0.0
        self._stun_time    = 0.0

    def take_damage(self, amount: float) -> bool:
        self.hp -= amount
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            return True
        return False

    def stun(self, duration: float = 0.5) -> None:
        self.state    = self.STUNNED
        self._stun_time = duration

    def update_stun(self, dt: float) -> bool:
        """Returns True while still stunned."""
        if self.state == self.STUNNED:
            self._stun_time -= dt
            if self._stun_time <= 0:
                self.state = self.PATROL
            return True
        return False

    def draw_hp_bar(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        bw = self.width
        bh = 4
        bx = int(self.x) - offset[0]
        by = int(self.y) - offset[1] - 8
        pygame.draw.rect(surface, (60, 0, 0),    (bx, by, bw, bh))
        fill = int(bw * max(0, self.hp / self.max_hp))
        pygame.draw.rect(surface, (220, 50, 50), (bx, by, fill, bh))

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        super().draw(surface, offset)
        self.draw_hp_bar(surface, offset)


# ─────────────────────────────────────────────────────────────────────────────
#  Simple wall / platform tile
# ─────────────────────────────────────────────────────────────────────────────

class Tile:
    """Solid rectangular tile used in Sniper and Assassin maps."""

    def __init__(
        self,
        x: int, y: int, w: int, h: int,
        colour: Tuple[int,int,int] = (50, 55, 70),
    ) -> None:
        self.rect   = pygame.Rect(x, y, w, h)
        self.colour = colour

    def draw(self, surface: pygame.Surface, offset: Tuple[int,int] = (0,0)) -> None:
        r = pygame.Rect(self.rect.x - offset[0], self.rect.y - offset[1],
                        self.rect.width, self.rect.height)
        pygame.draw.rect(surface, self.colour, r)
        pygame.draw.rect(surface, (80, 85, 100), r, 1)


# ─────────────────────────────────────────────────────────────────────────────
#  Wave / Formation helpers
# ─────────────────────────────────────────────────────────────────────────────

def grid_formation(
    origin: Vec2,
    rows: int, cols: int,
    spacing: int = 80,
    angle: float = 0.0,
) -> List[Vec2]:
    """
    Generate a rectangular grid of positions, then rotate the whole
    formation using a 2×2 rotation matrix.
    This demonstrates matrix-based enemy formations.
    """
    points: List[Vec2] = []
    rot = mat_rotation(angle)
    cx  = (cols - 1) * spacing / 2
    cy  = (rows - 1) * spacing / 2
    for r in range(rows):
        for c in range(cols):
            local = (c * spacing - cx, r * spacing - cy)
            rx, ry = mat_transform(rot, local)
            points.append((origin[0] + rx, origin[1] + ry))
    return points


def v_formation(
    origin: Vec2,
    count: int,
    spacing: int = 70,
    angle: float = 0.0,
) -> List[Vec2]:
    """V-shape formation, optionally rotated."""
    points: List[Vec2] = []
    rot = mat_rotation(angle)
    half = count // 2
    for i in range(count):
        offset_x = (i - half) * spacing
        offset_y = abs(i - half) * spacing // 2
        rx, ry   = mat_transform(rot, (offset_x, offset_y))
        points.append((origin[0] + rx, origin[1] + ry))
    return points


# ─────────────────────────────────────────────────────────────────────────────
#  AvatarRenderer
# ─────────────────────────────────────────────────────────────────────────────

class AvatarRenderer:
    """Helper for rendering custom avatars (shapes or images)"""
    _cache = {}

    @classmethod
    def load_image(cls, path: str) -> Optional[pygame.Surface]:
        import os
        if not path or not os.path.exists(path):
            return None
        if path not in cls._cache:
            try:
                img = pygame.image.load(path).convert_alpha()
                cls._cache[path] = img
            except Exception:
                return None
        return cls._cache[path]

    @classmethod
    def draw_avatar(cls, surface: pygame.Surface, x: float, y: float, w: int, h: int, 
                    settings, default_colour: Tuple[int,int,int], angle: float = 0.0) -> bool:
        """
        Draws the avatar at center (x, y) with bounding box (w, h).
        Returns True if a custom avatar was drawn, False if caller should draw default.
        """
        atype = getattr(settings, "avatar_type", "shape")
        avalue = getattr(settings, "avatar_value", "default")
        
        if atype == "shape" and avalue == "default":
            return False  
            
        cx, cy = int(x), int(y)
        
        if atype == "image":
            img = cls.load_image(avalue)
            if img:
                scaled = pygame.transform.smoothscale(img, (w, h))
                if angle != 0.0:
                    scaled = pygame.transform.rotate(scaled, math.degrees(-angle))
                r = scaled.get_rect(center=(cx, cy))
                surface.blit(scaled, r)
                return True
            return False
            
        if atype == "shape":
            if avalue == "square":
                r = pygame.Rect(cx - w//2, cy - h//2, w, h)
                pygame.draw.rect(surface, default_colour, r, border_radius=4)
                pygame.draw.rect(surface, (255,255,255), r, 2, border_radius=4)
                return True
            elif avalue == "circle":
                pygame.draw.circle(surface, default_colour, (cx, cy), w//2)
                pygame.draw.circle(surface, (255,255,255), (cx, cy), w//2, 2)
                return True
            elif avalue == "triangle":
                pts = [(cx, cy - h//2), (cx - w//2, cy + h//2), (cx + w//2, cy + h//2)]
                if angle != 0.0:
                    rot = mat_rotation(angle)
                    rot_pts = []
                    for px, py in pts:
                        rx, ry = mat_transform(rot, (px - cx, py - cy))
                        rot_pts.append((cx + rx, cy + ry))
                    pts = rot_pts
                pygame.draw.polygon(surface, default_colour, pts)
                pygame.draw.polygon(surface, (255,255,255), pts, 2)
                return True
                
        return False

# ─────────────────────────────────────────────────────────────────────────────
#  Mobile Touch Controls
# ─────────────────────────────────────────────────────────────────────────────

class VirtualJoystick:
    """On-screen virtual joystick supporting multi-touch and mouse fallback."""
    def __init__(self, x: float, y: float, radius: int = 60, color: Tuple[int,int,int] = NEON_CYAN):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.stick_x = x
        self.stick_y = y
        self.active_finger = None
        self.dir_x = 0.0
        self.dir_y = 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.FINGERDOWN:
            if self.active_finger is None:
                fx = event.x * SCREEN_WIDTH
                fy = event.y * SCREEN_HEIGHT
                if math.hypot(fx - self.x, fy - self.y) < self.radius * 2.0:
                    self.active_finger = event.finger_id
                    self._update_stick(fx, fy)
        elif event.type == pygame.FINGERMOTION:
            if self.active_finger == event.finger_id:
                fx = event.x * SCREEN_WIDTH
                fy = event.y * SCREEN_HEIGHT
                self._update_stick(fx, fy)
        elif event.type == pygame.FINGERUP:
            if self.active_finger == event.finger_id:
                self.active_finger = None
                self.stick_x, self.stick_y = self.x, self.y
                self.dir_x, self.dir_y = 0.0, 0.0
                
        # Fallback for mouse testing
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', 1) == 1:
            if self.active_finger is None:
                mx, my = event.pos
                if math.hypot(mx - self.x, my - self.y) < self.radius * 2.0:
                    self.active_finger = "mouse"
                    self._update_stick(mx, my)
        elif event.type == pygame.MOUSEMOTION:
            if self.active_finger == "mouse":
                mx, my = event.pos
                self._update_stick(mx, my)
        elif event.type == pygame.MOUSEBUTTONUP and getattr(event, 'button', 1) == 1:
            if self.active_finger == "mouse":
                self.active_finger = None
                self.stick_x, self.stick_y = self.x, self.y
                self.dir_x, self.dir_y = 0.0, 0.0

    def _update_stick(self, tx: float, ty: float) -> None:
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist > self.radius:
            dx = (dx / dist) * self.radius
            dy = (dy / dist) * self.radius
        self.stick_x = self.x + dx
        self.stick_y = self.y + dy
        # Normalize strictly up to 1.0
        self.dir_x = dx / self.radius
        self.dir_y = dy / self.radius

    def draw(self, surface: pygame.Surface) -> None:
        # Base circle
        pygame.draw.circle(surface, (40, 40, 40), (int(self.x), int(self.y)), self.radius, 2)
        # Inner stick
        pygame.draw.circle(surface, self.color, (int(self.stick_x), int(self.stick_y)), self.radius // 2)

class TouchButton:
    """On-screen button supporting multi-touch and mouse fallback."""
    def __init__(self, x: float, y: float, radius: int = 30, text: str = "", color: Tuple[int,int,int] = NEON_CYAN):
        self.x = x
        self.y = y
        self.radius = radius
        self.text = text
        self.color = color
        self.is_pressed = False
        self.just_pressed = False
        self.active_finger = None

    def update(self) -> None:
        self.just_pressed = False  # Reset per frame

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.FINGERDOWN:
            fx = event.x * SCREEN_WIDTH
            fy = event.y * SCREEN_HEIGHT
            if math.hypot(fx - self.x, fy - self.y) < self.radius * 1.5:
                self.active_finger = event.finger_id
                self.is_pressed = True
                self.just_pressed = True
        elif event.type == pygame.FINGERUP:
            if self.active_finger == event.finger_id:
                self.active_finger = None
                self.is_pressed = False
                
        # Mouse fallback
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, 'button', 1) == 1:
            mx, my = event.pos
            if math.hypot(mx - self.x, my - self.y) < self.radius * 1.5:
                self.active_finger = "mouse"
                self.is_pressed = True
                self.just_pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and getattr(event, 'button', 1) == 1:
            if self.active_finger == "mouse":
                self.active_finger = None
                self.is_pressed = False

    def draw(self, surface: pygame.Surface) -> None:
        col = (255, 255, 255) if self.is_pressed else self.color
        if self.is_pressed:
            pygame.draw.circle(surface, (col[0]//2, col[1]//2, col[2]//2), (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, col, (int(self.x), int(self.y)), self.radius, 2)
        if self.text:
            draw_text(surface, self.text, self.x, self.y, FONT_MEDIUM, col, anchor="center")

