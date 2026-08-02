"""
games/runner.py
===============
Matrix Runner — Endless runner.

Matrix / Linear-Algebra integration
────────────────────────────────────
• Shear matrix      → background layers skew as speed increases (speed-warp effect)
• Translation matrix→ multi-layer parallax scrolling (each layer offset separately)
• Scale matrix      → coin magnet power-up expands collect radius
• Rotation matrix   → animated character limb swing displayed as tilted rectangles
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, GRAVITY, LIVES,
    BLACK, WHITE, DARK_BG, DARK_GRAY, MATRIX_GREEN,
    NEON_RED, NEON_CYAN, NEON_ORANGE, NEON_YELLOW, NEON_PURPLE, GOLD,
    FONT_SMALL, FONT_MEDIUM, FONT_LARGE, FONT_XLARGE,
)
from animation import ParticleSystem, ScreenShake
from ui import (
    ScoreDisplay, FPSCounter, FloatingTextManager,
    MessageQueue, draw_text, draw_glow_text, ProgressBar,
    LivesDisplay, VignetteOverlay,
)
from games.common import mat_shear, mat_transform, mat_rotation


# ─────────────────────────────────────────────────────────────────────────────
#  Ground / platform constants
# ─────────────────────────────────────────────────────────────────────────────

GROUND_Y      = SCREEN_HEIGHT - 110
PLAYER_X      = 140
RUN_ANIM_FPS  = 16.0

# Environment themes (background colour tuples)
THEMES = [
    # (sky, mid, far, ground top, ground body, name)
    ((5, 5, 20),    (10, 15, 40),  (20, 30, 60),  (30, 180, 90),  (20, 100, 50),  "Cyber City"),
    ((20, 5, 5),    (40, 10, 15),  (60, 20, 25),  (200, 60,  30), (120, 30, 15),  "Lava Zone"),
    ((5, 15, 30),   (5,  25, 55),  (10, 40, 80),  (50, 150, 200), (20, 80, 140),  "Ice World"),
    ((10, 0,  20),  (20, 5,  40),  (35, 10, 60),  (120, 0, 200),  (60, 0, 120),   "Matrix Void"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Parallax Layer  (Translation + Shear matrices)
# ─────────────────────────────────────────────────────────────────────────────

class ParallaxLayer:
    """
    Scrolling background strip.
    The horizontal offset is computed with a translation matrix factor (depth),
    and a shear matrix is applied at high speeds to create a motion-blur warp.
    """

    def __init__(
        self,
        y: int, height: int,
        colour: Tuple[int,int,int],
        scroll_factor: float,
        detail_cols: List[Tuple[int,int,int]],
        detail_count: int = 12,
    ) -> None:
        self.y              = y
        self.height         = height
        self.colour         = colour
        self._factor        = scroll_factor
        self._offset        = 0.0
        self._details: List[Tuple[int,int,int,int,int]] = []   # x,y,w,h, col_idx
        # Populate random detail rectangles (buildings, trees, etc.)
        for _ in range(detail_count):
            dx = random.randint(0, SCREEN_WIDTH * 2)
            dw = random.randint(20, 70)
            dh = random.randint(20, int(height * 0.8))
            ci = random.randrange(len(detail_cols))
            self._details.append((dx, y - dh + height, dw, dh, ci))
        self._detail_cols   = detail_cols
        self._total_w       = SCREEN_WIDTH * 2

    def update(self, dt: float, speed: float) -> None:
        # Translation matrix: offset += speed * factor * dt
        self._offset = (self._offset + speed * self._factor * dt) % self._total_w

    def draw(self, surface: pygame.Surface, speed: float) -> None:
        # Background strip
        pygame.draw.rect(surface, self.colour, (0, self.y, SCREEN_WIDTH, self.height))

        # ── Shear matrix speed-warp ──────────────────────────────
        # Shear the bounding Y coords slightly based on current speed
        shear_x = min(0.06, speed / 8000)   # max shear at very high speed
        mat = mat_shear(shear_x)

        for (bx, by, bw, bh, ci) in self._details:
            # Apply translation
            sx = int((bx - self._offset) % self._total_w)
            if sx > SCREEN_WIDTH + bw:
                sx -= self._total_w

            # Apply shear to top-left corner of the detail rectangle
            sx2, sy2 = mat_transform(mat, (float(sx), float(by)))
            sx2 = int(sx2)

            if -bw < sx2 < SCREEN_WIDTH + bw:
                pygame.draw.rect(surface, self._detail_cols[ci],
                                 (sx2, int(sy2), bw, bh))


# ─────────────────────────────────────────────────────────────────────────────
#  Obstacle
# ─────────────────────────────────────────────────────────────────────────────

class Obstacle:
    """Single obstacle the player must jump or slide under."""

    def __init__(self, x: float, kind: str = "tall") -> None:
        self.alive = True
        self.kind  = kind

        if kind == "tall":
            # Must jump over
            self.rect = pygame.Rect(int(x), GROUND_Y - 50, 32, 50)
            self.colour = NEON_RED
        elif kind == "low":
            # Must slide under (top part only blocks if standing)
            self.rect = pygame.Rect(int(x), GROUND_Y - 26, 80, 26)
            self.colour = NEON_ORANGE
        elif kind == "double":
            self.rect = pygame.Rect(int(x), GROUND_Y - 70, 28, 70)
            self.colour = NEON_PURPLE
        elif kind == "moving":
            self.rect = pygame.Rect(int(x), GROUND_Y - 90, 30, 90)
            self.colour = NEON_CYAN
            self._move_dir = 1
            self._move_range = 60
            self._origin_y = float(self.rect.y)
        elif kind == "laser":
            # Must slide under
            self.rect = pygame.Rect(int(x), GROUND_Y - 120, 10, 85) # High gate
            self.colour = NEON_RED
        elif kind == "gap":
            # Must jump over
            self.rect = pygame.Rect(int(x), GROUND_Y - 10, 100, 20) # Floor trap
            self.colour = MATRIX_GREEN

    def update(self, dt: float, speed: float) -> None:
        self.rect.x -= int(speed * dt)
        if self.kind == "moving":
            self.rect.y = int(self._origin_y + math.sin(pygame.time.get_ticks() * 0.003) * self._move_range)
        if self.rect.right < 0:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        if self.kind == "gap":
            pygame.draw.rect(surface, (10, 10, 15), self.rect)
            pygame.draw.line(surface, self.colour, (self.rect.x, self.rect.y), (self.rect.right, self.rect.y), 2)
            pygame.draw.line(surface, self.colour, (self.rect.x, self.rect.bottom), (self.rect.right, self.rect.bottom), 2)
        elif self.kind == "laser":
            pygame.draw.rect(surface, self.colour, self.rect)
            # Inner white beam
            pygame.draw.rect(surface, WHITE, (self.rect.centerx - 1, self.rect.y, 2, self.rect.height))
        else:
            pygame.draw.rect(surface, self.colour, self.rect, border_radius=5)
            pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=5)


# ─────────────────────────────────────────────────────────────────────────────
#  Coin
# ─────────────────────────────────────────────────────────────────────────────

class Coin:
    RADIUS = 10

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.alive     = True
        self._anim     = 0.0

    def update(self, dt: float, speed: float) -> None:
        self.x     -= speed * dt
        self._anim += dt * 5
        if self.x < -20:
            self.alive = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - self.RADIUS, int(self.y) - self.RADIUS,
                           self.RADIUS * 2, self.RADIUS * 2)

    def draw(self, surface: pygame.Surface) -> None:
        r     = self.RADIUS
        cy    = int(self.y + math.sin(self._anim) * 3)
        pulse = int(r * (1.0 + 0.12 * math.sin(self._anim * 2)))
        pygame.draw.circle(surface, GOLD, (int(self.x), cy), pulse)
        pygame.draw.circle(surface, WHITE, (int(self.x), cy), pulse, 2)
        draw_text(surface, "$", int(self.x), cy, FONT_SMALL, BLACK,
                  bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  Runner Player
# ─────────────────────────────────────────────────────────────────────────────

class RunnerPlayer:
    """
    The runner character.
    Limb swing animation uses the rotation matrix to draw tilted limb rectangles.
    Jump mechanics include double-jump.
    """

    WIDTH   = 24
    HEIGHT  = 50
    JUMP_V  = -560.0
    MAX_FALL= 600.0

    def __init__(self) -> None:
        self.x        = float(PLAYER_X)
        self.y        = float(GROUND_Y - self.HEIGHT)
        self.vy       = 0.0
        self.alive    = True
        self.lives    = LIVES
        self._on_ground = False
        self._jumps   = 0    # jumps used (max 2)
        self._slide   = False
        self._slide_t = 0.0
        self.invincible_t = 0.0
        self.magnet   = False
        self.magnet_t = 0.0
        self._anim_t  = 0.0

    @property
    def rect(self) -> pygame.Rect:
        h = 28 if self._slide else self.HEIGHT
        return pygame.Rect(int(self.x), int(self.y), self.WIDTH, h)

    @property
    def center(self) -> Tuple[float,float]:
        return (self.x + self.WIDTH / 2, self.y + self.HEIGHT / 2)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                self._jump()
            if event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_LCTRL):
                self._start_slide()

    def _jump(self) -> None:
        if self._jumps < 2:
            self.vy     = self.JUMP_V
            self._slide = False
            self._jumps += 1
            self._on_ground = False

    def _start_slide(self) -> None:
        if self._on_ground:
            self._slide   = True
            self._slide_t = 0.45

    def update(self, dt: float) -> None:
        self.invincible_t = max(0, self.invincible_t - dt)
        self.magnet_t     = max(0, self.magnet_t - dt)
        self.magnet       = self.magnet_t > 0

        if self._slide_t > 0:
            self._slide_t -= dt
            if self._slide_t <= 0:
                self._slide = False

        # Gravity
        self.vy = min(self.vy + GRAVITY * dt, self.MAX_FALL)
        self.y += self.vy * dt

        # Ground collision
        ground = GROUND_Y - (28 if self._slide else self.HEIGHT)
        if self.y >= ground:
            self.y          = float(ground)
            self.vy         = 0.0
            self._on_ground = True
            self._jumps     = 0
        else:
            self._on_ground = False

        self._anim_t += dt * RUN_ANIM_FPS

    def take_damage(self) -> bool:
        if self.invincible_t > 0:
            return False
        self.lives -= 1
        self.invincible_t = 1.5
        if self.lives <= 0:
            self.alive = False
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if self.invincible_t > 0 and int(self.invincible_t * 8) % 2:
            return

        cx = int(self.x) + self.WIDTH // 2
        cy = int(self.y) + self.HEIGHT // 2
        h  = 28 if self._slide else self.HEIGHT

        # ── Rotation-matrix limb animation ──────────────────────
        # Leg swing angle oscillates with run cycle
        if self._on_ground and not self._slide:
            swing = math.sin(self._anim_t * 0.3) * 0.5  # radians
        else:
            swing = 0.0

        rot_f = mat_rotation(swing)
        rot_b = mat_rotation(-swing)

        # Legs (two rectangles rotated by ±swing)
        leg_len = 18
        for rot, side in [(rot_f, -1), (rot_b, 1)]:
            base_x, base_y = side * 5, 10   # offset from centre
            tip_x, tip_y   = mat_transform(rot, (0.0, float(leg_len)))
            leg_pts = [
                (cx + base_x - 3, cy + base_y),
                (cx + base_x + 3, cy + base_y),
                (cx + int(tip_x) + 3, cy + int(tip_y)),
                (cx + int(tip_x) - 3, cy + int(tip_y)),
            ]
            pygame.draw.polygon(surface, MATRIX_GREEN, leg_pts)

        # Arms
        arm_angle = -swing * 1.2
        for rot, side in [(mat_rotation(arm_angle), -1),
                          (mat_rotation(-arm_angle), 1)]:
            ax, ay = mat_transform(rot, (0.0, 14.0))
            arm_pts = [
                (cx + side*6 - 2, cy - 6),
                (cx + side*6 + 2, cy - 6),
                (cx + side*6 + int(ax) + 2, cy - 6 + int(ay)),
                (cx + side*6 + int(ax) - 2, cy - 6 + int(ay)),
            ]
            pygame.draw.polygon(surface, NEON_CYAN, arm_pts)

        # Body & Head
        from games.common import AvatarRenderer
        drawn = False
        if hasattr(self, "settings"):
            drawn = AvatarRenderer.draw_avatar(surface, cx, cy, 26, h, self.settings, MATRIX_GREEN, 0.0)

        if not drawn:
            pygame.draw.rect(surface, MATRIX_GREEN,
                             (cx - 11, cy - h//2 + 8, 22, h - 16),
                             border_radius=6)
            
            # Head
            head_y = cy - h//2 - 5
            pygame.draw.circle(surface, NEON_CYAN, (cx, head_y), 11)
            pygame.draw.circle(surface, WHITE,     (cx, head_y), 11, 2)

        # Magnet aura
        if self.magnet:
            mag_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(mag_surf, (255, 215, 0, 40), (30, 30), 30)
            surface.blit(mag_surf, (cx - 30, cy - 30))


# ─────────────────────────────────────────────────────────────────────────────
#  PowerUp item
# ─────────────────────────────────────────────────────────────────────────────

class RunnerPowerUp:
    KINDS = ["magnet", "shield", "slow"]
    COLS  = {"magnet": GOLD, "shield": NEON_CYAN, "slow": NEON_PURPLE}
    ICONS = {"magnet": "M", "shield": "S", "slow": "~"}

    def __init__(self, x: float) -> None:
        self.x     = x
        self.y     = float(GROUND_Y - 100 - random.randint(0, 60))
        self.kind  = random.choice(self.KINDS)
        self.col   = self.COLS[self.kind]
        self.alive = True
        self._t    = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 14, int(self.y) - 14, 28, 28)

    def update(self, dt: float, speed: float) -> None:
        self.x -= speed * dt
        self._t += dt * 3
        if self.x < -30:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = int(self.x), int(self.y)
        r = int(14 + 2 * math.sin(self._t))
        pygame.draw.circle(surface, self.col, (cx, cy), r)
        pygame.draw.circle(surface, WHITE, (cx, cy), r, 2)
        draw_text(surface, self.ICONS[self.kind], cx, cy, FONT_SMALL,
                  BLACK, bold=True, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
#  RunnerGame
# ─────────────────────────────────────────────────────────────────────────────

class RunnerGame:
    """Endless runner game with increasing speed and theme rotation."""

    INITIAL_SPEED = 280.0
    MAX_SPEED     = 780.0
    ACCEL         = 8.0   # px/s per second

    def __init__(self, screen: pygame.Surface, sound, settings, save_mgr, level: int = 1) -> None:
        self._screen    = screen
        self._sound     = sound
        self._settings  = settings
        self._save      = save_mgr
        from config import GameID
        self._game_id   = GameID.RUNNER

        self._player    = RunnerPlayer()
        self._player.settings = self._settings
        self._level     = level
        
        from config import LEVEL_THEMES
        self._theme_col = LEVEL_THEMES.get(level, MATRIX_GREEN)
        
        if level <= 3:
            self._target_dist = 1000.0
            self.INITIAL_SPEED = 300.0
            self.MAX_SPEED = 600.0
            self.ACCEL = 5.0
        elif level <= 6:
            self._target_dist = 2000.0
            self.INITIAL_SPEED = 500.0
            self.MAX_SPEED = 1000.0
            self.ACCEL = 20.0
        elif level <= 9:
            self._target_dist = 3000.0
            self.INITIAL_SPEED = 700.0
            self.MAX_SPEED = 1200.0
            self.ACCEL = 10.0
        else:
            self._target_dist = 4000.0
            self.INITIAL_SPEED = 1000.0
            self.MAX_SPEED = 1800.0
            self.ACCEL = 15.0
            
        self._speed     = self.INITIAL_SPEED
        self._dist      = 0.0          # metres scrolled
        self._score     = 0
        self._coins     = 0
        self._result    = None

        # Obstacle / coin timing
        self._obs_t     = 1.5
        self._coin_t    = 0.8
        self._pu_t      = 10.0
        self._obstacles: List[Obstacle] = []
        self._coins_list: List[Coin]    = []
        self._powerups: List[RunnerPowerUp] = []

        # Theme
        self._theme_idx = 0
        self._theme_dist= 0.0
        self._theme_dur = 800.0   # metres per theme

        # Parallax layers (3 depths)
        self._layers: List[ParallaxLayer] = []
        self._build_layers()

        # Systems
        self._particles  = ParticleSystem(400)
        self._shake      = ScreenShake()
        self._floats     = FloatingTextManager()
        self._msgs       = MessageQueue(10, 80)
        self._score_disp = ScoreDisplay(SCREEN_WIDTH - 10, 10, anchor="topright")
        self._fps_cnt    = FPSCounter(10, 10)
        self._lives_disp = LivesDisplay(SCREEN_WIDTH // 2 - 60, 40, max_lives=LIVES)
        self._vignette   = VignetteOverlay(SCREEN_WIDTH, SCREEN_HEIGHT)

        self._speed_bar  = ProgressBar(SCREEN_WIDTH // 2 - 100, 15, 200, 10, NEON_ORANGE,
                                       label="SPEED")

        # Slow-motion power-up
        self._slow_t  = 0.0

        self._sound.play_music("music_runner")
        self._msgs.push("MATRIX RUNNER — Jump [Space] | Slide [Ctrl/Down]",
                        NEON_CYAN, 4.0)

    def _build_layers(self) -> None:
        t       = THEMES[self._theme_idx]
        sky, mid, far, gtop, gbody, name = t
        self._sky_col    = sky
        self._gtop_col   = gtop
        self._gbody_col  = gbody
        self._theme_name = name

        # Far layer (slowest, most shear)
        self._layers = [
            ParallaxLayer(80,  200, far,  0.15, [mid, sky],       8),
            ParallaxLayer(200, 180, mid,  0.35, [far, (80,80,80)], 10),
            ParallaxLayer(330, 100, far,  0.60, [mid, mid],       14),
        ]

    def _next_theme(self) -> None:
        self._theme_idx = (self._theme_idx + 1) % len(THEMES)
        self._build_layers()
        self._msgs.push(f"Entering: {THEMES[self._theme_idx][5]}",
                        NEON_YELLOW, 2.5)

    # ── interface ─────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "pause"
        self._player.handle_event(event)
        return None

    def update(self, dt: float) -> Optional[str]:
        if self._result:
            return self._result

        keys = pygame.key.get_pressed()
        # Also allow key-held jump for smooth response
        if keys[pygame.K_SPACE] or keys[pygame.K_UP]:
            pass  # handled via events for single-press

        # Slow-mo power-up
        if self._slow_t > 0:
            self._slow_t -= dt
            dt *= 0.45

        # Speed
        self._speed = min(self.MAX_SPEED, self._speed + self.ACCEL * dt)
        self._dist += self._speed * dt / 100.0   # in "metres"
        
        # Check Win Condition
        if self._dist >= self._target_dist:
            self._save.add_score(self._game_id, self._score)
            self._sound.play("victory")
            self._result = "win"
            return self._result

        self._theme_dist += self._speed * dt / 100.0

        if self._theme_dist > self._theme_dur:
            self._theme_dist = 0.0
            self._next_theme()

        # Update score
        base_score = int(self._dist * 10) + self._coins * 50
        self._score = base_score * 3 if self._level == 6 else base_score

        # Parallax layers
        for layer in self._layers:
            layer.update(dt, self._speed)

        # Player
        self._player.update(dt)

        # Spawn obstacles
        self._obs_t -= dt
        if self._obs_t <= 0:
            min_gap = max(0.6, 1.6 - self._speed / 800)
            self._obs_t = random.uniform(min_gap, min_gap + 0.8)
            choices = ["tall", "tall", "low", "double"]
            if self._level >= 2: choices.append("moving")
            if self._level >= 3: choices.append("laser")
            if self._level >= 4: choices.append("gap")
            kind = random.choice(choices)
            self._obstacles.append(Obstacle(SCREEN_WIDTH + 50, kind))

        # Spawn coins
        self._coin_t -= dt
        if self._coin_t <= 0:
            self._coin_t = random.uniform(0.4, 1.0)
            base_y = GROUND_Y - random.choice([50, 80, 120])
            for ci in range(random.randint(3, 7)):
                self._coins_list.append(
                    Coin(SCREEN_WIDTH + 40 + ci * 28, float(base_y))
                )

        # Spawn power-ups
        self._pu_t -= dt
        if self._pu_t <= 0:
            self._pu_t = random.uniform(12, 20)
            self._powerups.append(RunnerPowerUp(SCREEN_WIDTH + 50))

        # Update obstacles
        for obs in self._obstacles:
            obs.update(dt, self._speed)
        self._obstacles = [o for o in self._obstacles if o.alive]

        # Collision: obstacle vs player
        for obs in self._obstacles[:]:
            if obs.rect.colliderect(self._player.rect):
                if self._player.take_damage():
                    self._particles.emit_burst(
                        self._player.x + 12, self._player.y + 25,
                        20, NEON_RED, 150
                    )
                    self._shake.shake(12, 0.4)
                    self._sound.play("crash")
                    self._lives_disp.set_lives(self._player.lives)
                    if not self._player.alive:
                        self._result = "dead"
                    else:
                        self._msgs.push(f"Lives: {self._player.lives}", NEON_RED, 2.0)
                        # Slow down slightly on hit
                        self._speed = max(self.INITIAL_SPEED, self._speed - 100)

        # Update coins
        for coin in self._coins_list:
            coin.update(dt, self._speed)
        self._coins_list = [c for c in self._coins_list if c.alive]

        # Collision: coin vs player (with magnet expansion)
        player_rect = self._player.rect
        if self._player.magnet:
            player_rect = player_rect.inflate(80, 80)

        for coin in self._coins_list[:]:
            if coin.rect.colliderect(player_rect):
                coin.alive = False
                self._coins += 1
                self._sound.play("coin")
                self._particles.emit_ring(coin.x, coin.y, 8, GOLD, radius=12, speed=40)
                self._floats.add("+50", coin.x, coin.y, GOLD, duration=0.6)

        # Update power-ups
        for pu in self._powerups:
            pu.update(dt, self._speed)
        self._powerups = [p for p in self._powerups if p.alive]

        for pu in self._powerups[:]:
            if pu.rect.colliderect(self._player.rect):
                pu.alive = False
                self._sound.play("powerup")
                if pu.kind == "magnet":
                    self._player.magnet_t = 8.0
                    self._msgs.push("MAGNET active!", GOLD, 2.0)
                elif pu.kind == "shield":
                    self._player.invincible_t = 6.0
                    self._msgs.push("SHIELD active!", NEON_CYAN, 2.0)
                elif pu.kind == "slow":
                    self._slow_t = 5.0
                    self._msgs.push("SLOW-MO active!", NEON_PURPLE, 2.0)
                self._particles.emit_ring(pu.x, pu.y, 20, pu.col, speed=80)

        # Distance milestone messages
        if int(self._dist) % 200 == 0 and int(self._dist) > 10:
            self._sound.play("speed_up")
            self._msgs.push(f"⚡ {int(self._dist)}m — Speed increasing!", NEON_ORANGE)

        # Systems
        self._particles.update(dt)
        self._floats.update(dt)
        self._msgs.update(dt)
        self._shake.update(dt)
        self._lives_disp.update(dt)
        self._vignette.update(dt)
        self._score_disp.set(self._score)
        self._score_disp.update(dt)
        self._speed_bar.progress = (self._speed - self.INITIAL_SPEED) / (self.MAX_SPEED - self.INITIAL_SPEED)

        if not self._player.alive:
            self._save.add_score(self._game_id, self._score)
            self._result = "dead"

        return None

    def draw(self, clock: pygame.time.Clock) -> None:
        ox, oy = self._shake.offset

        # Sky background
        self._screen.fill(self._sky_col)

        # Parallax layers (with shear at high speed)
        for layer in self._layers:
            layer.draw(self._screen, self._speed)

        # Ground
        ground_rect = pygame.Rect(0 + ox, GROUND_Y + oy,
                                  SCREEN_WIDTH, SCREEN_HEIGHT - GROUND_Y)
        pygame.draw.rect(self._screen, self._gtop_col,
                         (0 + ox, GROUND_Y + oy, SCREEN_WIDTH, 12))
        pygame.draw.rect(self._screen, self._gbody_col, ground_rect)

        # Ground grid lines (matrix visual)
        for gx in range(0, SCREEN_WIDTH, 60):
            pygame.draw.line(self._screen, self._gtop_col,
                             (gx + ox, GROUND_Y + oy + 12),
                             (gx + ox, SCREEN_HEIGHT + oy), 1)

        # Obstacles
        for obs in self._obstacles:
            obs.draw(self._screen)

        # Coins
        for coin in self._coins_list:
            coin.draw(self._screen)

        # Power-ups
        for pu in self._powerups:
            pu.draw(self._screen)

        # Player
        self._player.draw(self._screen)

        # Particles / floats
        self._particles.draw(self._screen)
        self._floats.draw(self._screen)

        # ── HUD ──────────────────────────────────────────────────
        hp_ratio = max(0.01, self._player.lives / LIVES)
        self._vignette.draw(self._screen, hp_ratio)
        self._score_disp.draw(self._screen)
        self._lives_disp.draw(self._screen)
        self._speed_bar.draw(self._screen)
        draw_text(self._screen, "SPEED", SCREEN_WIDTH // 2, 28, FONT_SMALL, NEON_ORANGE, anchor="midtop")

        if self._settings.show_fps:
            self._fps_cnt.update(clock)
            self._fps_cnt.draw(self._screen)

        # Distance
        lvl_txt = "THE ARCHITECT" if self._level == 6 else f"LEVEL {self._level}"
        col = GOLD if self._level == 6 else self._theme_col
        draw_text(self._screen, f"{lvl_txt} — {int(self._dist)} / {int(self._target_dist)} m", 10, 10, FONT_MEDIUM, col,
                  bold=True, anchor="topleft")

        # Coins counter
        draw_text(self._screen, f"COINS: {self._coins}",
                  10, SCREEN_HEIGHT - 38, FONT_SMALL, GOLD)

        # Theme name
        draw_text(self._screen, self._theme_name,
                  SCREEN_WIDTH - 10, SCREEN_HEIGHT - 38, FONT_SMALL,
                  NEON_PURPLE, anchor="topright")

        # Active power-up indicators
        if self._slow_t > 0:
            draw_text(self._screen, f"SLOW {self._slow_t:.1f}s",
                      10, SCREEN_HEIGHT - 58, FONT_SMALL, NEON_PURPLE)

        self._msgs.draw(self._screen)

        # Controls hint
        draw_text(self._screen,
                  "[Space] Jump  [Ctrl/Down] Slide",
                  SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18,
                  FONT_SMALL, DARK_GRAY, anchor="midbottom")
