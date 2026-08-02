"""
game.py
=======
GameManager — the central scene / state machine.
Owns the main loop, scene transitions, and wires together all systems.
"""

from __future__ import annotations

import sys
import asyncio
from typing import Optional

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE,
    GameState, GameID, BLACK, MATRIX_GREEN, DARK_BG,
    TOUCH_ENABLED,
)
from touch_controls import TouchOverlay
from settings   import Settings
from save_manager import SaveManager
from sound_manager import SoundManager
from ui import FPSCounter, CRTOverlay, SceneTransition, AchievementToastManager
from menu import (
    LoadingScreen, MainMenu, GameSelectScreen, LevelSelectScreen,
    PauseMenu, SettingsScreen, HighScoreScreen, ResultScreen, AvatarSelectScreen,
    ShopScreen, AchievementsScreen
)


# ─────────────────────────────────────────────────────────────────────────────
#  GameManager
# ─────────────────────────────────────────────────────────────────────────────

class GameManager:
    """
    Central controller that owns:
    • The pygame window / display surface
    • Global systems (settings, save, sound)
    • All scene objects
    • The main event-dispatch + draw loop
    """

    def __init__(self) -> None:
        # ── pygame init ──────────────────────────────────────────
        pygame.init()
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()

        self._settings = Settings.load()
        self._save     = SaveManager()
        self._sound    = SoundManager()
        self._sound.set_sfx_volume(self._settings.effective_sfx)
        self._sound.set_music_volume(self._settings.effective_music)

        # ── display ──────────────────────────────────────────────
        flags  = pygame.FULLSCREEN if self._settings.fullscreen else 0
        flags |= pygame.SCALED  # Auto-scales 1280x720 to the native device screen correctly
        self._screen: pygame.Surface = pygame.display.set_mode(
            self._settings.resolution, flags
        )
        pygame.display.set_caption(TITLE)
        pygame.mouse.set_visible(False)   # we draw our own cursor in-game

        self._clock    = pygame.time.Clock()
        self._ach_toast = AchievementToastManager()
        self._state    = GameState.LOADING
        self._prev_state: Optional[GameState] = None

        # ── active game / scenes ─────────────────────────────────
        self._active_game_id: Optional[GameID] = None
        self._active_game   = None              # type: ignore[assignment]
        self._result_screen: Optional[ResultScreen] = None

        # ── scene objects ────────────────────────────────────────
        self._loading  = LoadingScreen()
        self._touch_overlay = TouchOverlay() if TOUCH_ENABLED else None
        if self._touch_overlay:
            self._orig_get_pressed = pygame.key.get_pressed
            def get_pressed_with_touch():
                keys = list(self._orig_get_pressed())
                for k, v in self._touch_overlay.get_keys().items():
                    if v and k < len(keys):
                        keys[k] = True
                return tuple(keys)
            pygame.key.get_pressed = get_pressed_with_touch
        self._main_menu: Optional[MainMenu]         = None
        self._select:    Optional[GameSelectScreen] = None
        self._lvl_select:Optional[LevelSelectScreen]= None
        self._active_level: int                     = 1
        self._pause:     Optional[PauseMenu]        = None
        self._settings_scr: Optional[SettingsScreen] = None
        self._scores_scr:   Optional[HighScoreScreen] = None
        self._avatar_scr:   Optional[AvatarSelectScreen] = None
        self._shop_scr:     Optional[ShopScreen] = None
        self._ach_scr:      Optional[AchievementsScreen] = None
        
        self._crt = CRTOverlay(SCREEN_WIDTH, SCREEN_HEIGHT)
        self._transition = SceneTransition(duration=0.3)
        self._next_state: Optional[GameState] = None

        # Custom cursor surface
        self._cursor = self._make_cursor()

    # ── cursor ────────────────────────────────────────────────────────────────

    def _make_cursor(self) -> pygame.Surface:
        surf = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.line(surf, MATRIX_GREEN, (10, 0), (10, 20), 1)
        pygame.draw.line(surf, MATRIX_GREEN, (0, 10), (20, 10), 1)
        pygame.draw.circle(surf, MATRIX_GREEN, (10, 10), 6, 1)
        return surf

    # ── scene constructors ────────────────────────────────────────────────────

    def _build_main_menu(self) -> MainMenu:
        return MainMenu(
            on_play     = lambda: self._go_to(GameState.GAME_SELECT),
            on_avatar   = lambda: self._go_to(GameState.AVATAR_SELECT),
            on_scores   = lambda: self._go_to(GameState.HIGH_SCORES),
            on_shop     = lambda: self._go_to(GameState.SHOP),
            on_achievements = lambda: self._go_to(GameState.ACHIEVEMENTS),
            on_settings = lambda: self._go_to(GameState.SETTINGS,
                                               from_state=GameState.MAIN_MENU),
            on_quit     = self._quit,
        )

    def _build_shop(self) -> ShopScreen:
        return ShopScreen(self._save, self._sound, lambda: self._go_to(GameState.MAIN_MENU))

    def _build_achievements(self) -> AchievementsScreen:
        return AchievementsScreen(self._save, self._sound, lambda: self._go_to(GameState.MAIN_MENU))

    def _build_select(self) -> GameSelectScreen:
        return GameSelectScreen(
            on_select = lambda gid: self._go_to_level_select(gid),
            on_back   = lambda: self._go_to(GameState.MAIN_MENU),
            save_mgr  = self._save,
        )

    def _go_to_level_select(self, gid: GameID) -> None:
        self._active_game_id = gid
        self._go_to(GameState.LEVEL_SELECT)

    def _build_level_select(self) -> LevelSelectScreen:
        return LevelSelectScreen(
            game_id   = self._active_game_id,
            on_select = lambda lvl: self._start_game(self._active_game_id, lvl),
            on_back   = lambda: self._go_to(GameState.GAME_SELECT),
            save_mgr  = self._save,
        )

    def _build_pause(self) -> PauseMenu:
        return PauseMenu(
            on_resume       = lambda: self._go_to(GameState.PLAYING),
            on_settings     = lambda: self._go_to(GameState.SETTINGS,
                                               from_state=GameState.PAUSED),
            on_level_select = lambda: self._go_to(GameState.LEVEL_SELECT),
            on_quit         = lambda: self._go_to(GameState.MAIN_MENU),
        )

    def _build_settings(self) -> SettingsScreen:
        return SettingsScreen(
            settings = self._settings,
            on_back  = self._settings_back,
            sound    = self._sound,
        )

    def _build_scores(self) -> HighScoreScreen:
        return HighScoreScreen(
            save_mgr = self._save,
            on_back  = lambda: self._go_to(GameState.MAIN_MENU),
        )

    def _build_avatar(self) -> AvatarSelectScreen:
        return AvatarSelectScreen(
            settings = self._settings,
            on_back  = lambda: self._go_to(GameState.MAIN_MENU),
            sound    = self._sound,
        )

    # ── navigation helpers ────────────────────────────────────────────────────

    _settings_from: GameState = GameState.MAIN_MENU

    def _go_to(self, state: GameState, from_state: Optional[GameState] = None) -> None:
        """Starts a transition to a new state."""
        if state == self._state or self._next_state is not None:
            return
            
        self._next_state = state
        self._next_from_state = from_state
        self._transition.start_out()
        
    def _do_state_switch(self) -> None:
        """Actually performs the state switch after fade out."""
        state = self._next_state
        from_state = self._next_from_state
        self._next_state = None
        
        self._prev_state = self._state
        self._state = state

        if state == GameState.MAIN_MENU:
            self._main_menu  = self._build_main_menu()
            self._active_game = None
            self._sound.play_music("music_menu")

        elif state == GameState.GAME_SELECT:
            self._select = self._build_select()

        elif state == GameState.LEVEL_SELECT:
            self._lvl_select = self._build_level_select()

        elif state == GameState.PAUSED:
            self._pause = self._build_pause()

        elif state == GameState.SETTINGS:
            self._settings_scr = self._build_settings()
            if from_state:
                GameManager._settings_from = from_state

        elif state == GameState.HIGH_SCORES:
            self._scores_scr = self._build_scores()

        elif state == GameState.AVATAR_SELECT:
            self._avatar_scr = self._build_avatar()

        elif state == GameState.SHOP:
            self._shop_scr = self._build_shop()

        elif state == GameState.ACHIEVEMENTS:
            self._ach_scr = self._build_achievements()

        elif state == GameState.PLAYING:
            pass    # game already loaded

    def _settings_back(self) -> None:
        if self._settings_from == GameState.PAUSED:
            self._go_to(GameState.PAUSED)
        else:
            self._go_to(GameState.MAIN_MENU)

    def _start_game(self, game_id: GameID, level: int = 1) -> None:
        """Instantiate the chosen mini-game and start playing."""
        self._active_game_id = game_id
        self._active_level   = level
        self._active_game    = self._create_game(game_id, level)
        self._go_to(GameState.PLAYING)
        pygame.mouse.set_visible(False)

    def _create_game(self, game_id: GameID, level: int = 1):
        """Factory method for mini-games."""
        args = (self._screen, self._sound, self._settings, self._save, level)
        if game_id == GameID.SNIPER:
            from games.sniper import SniperGame
            return SniperGame(*args)
        elif game_id == GameID.ASSASSIN:
            from games.assassin import AssassinGame
            return AssassinGame(*args)
        elif game_id == GameID.SPACE:
            from games.space_battle import SpaceBattleGame
            return SpaceBattleGame(*args)
        elif game_id == GameID.RUNNER:
            from games.runner import RunnerGame
            return RunnerGame(*args)
        raise ValueError(f"Unknown game ID: {game_id}")

    def _quit(self) -> None:
        self._settings.save()
        pygame.quit()
        sys.exit()

    # ── main run loop ─────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Blocking main loop — returns never."""
        while True:
            dt = min(self._clock.tick(FPS) / 1000.0, 0.05)   # cap at 50 ms

            self._handle_events()
            self._update(dt)
            self._draw()
            await asyncio.sleep(0)

    # ── event dispatch ────────────────────────────────────────────────────────

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()

            if event.type == pygame.KEYDOWN:
                # Global escape handling
                if event.key == pygame.K_F11:
                    self._toggle_fullscreen()
                # On Android, the back gesture/button acts as K_ESCAPE or K_AC_BACK
                elif event.key == pygame.K_ESCAPE or getattr(event, 'key', None) == getattr(pygame, 'K_AC_BACK', None):
                    if self._state == GameState.PLAYING:
                        self._go_to(GameState.PAUSED)
                    elif self._state not in (GameState.MAIN_MENU, GameState.LOADING):
                        self._go_to(GameState.MAIN_MENU)

            # Route to active scene
            if self._state == GameState.LOADING:
                pass

            elif self._state == GameState.MAIN_MENU and self._main_menu:
                self._main_menu.handle_event(event, self._sound)

            elif self._state == GameState.GAME_SELECT and self._select:
                self._select.handle_event(event, self._sound)

            elif self._state == GameState.LEVEL_SELECT and self._lvl_select:
                self._lvl_select.handle_event(event, self._sound)

            elif self._state == GameState.PLAYING and self._active_game:
                if self._touch_overlay:
                    self._touch_overlay.handle_event(event)
                result = self._active_game.handle_event(event)
                if result == "pause":
                    self._go_to(GameState.PAUSED)

            elif self._state == GameState.PAUSED and self._pause:
                if self._touch_overlay:
                    self._touch_overlay.handle_event(event)
                self._pause.handle_event(event, self._sound)

            elif self._state == GameState.SETTINGS and self._settings_scr:
                self._settings_scr.handle_event(event)

            elif self._state == GameState.HIGH_SCORES and self._scores_scr:
                self._scores_scr.handle_event(event, self._sound)

            elif self._state == GameState.AVATAR_SELECT and self._avatar_scr:
                self._avatar_scr.handle_event(event, self._sound)

            elif self._state == GameState.SHOP and self._shop_scr:
                self._shop_scr.handle_event(event, self._sound)

            elif self._state == GameState.ACHIEVEMENTS and self._ach_scr:
                self._ach_scr.handle_event(event, self._sound)

            elif self._state in (GameState.GAME_OVER, GameState.GAME_WIN):
                if self._result_screen:
                    self._result_screen.handle_event(event, self._sound)

    def _toggle_fullscreen(self) -> None:
        self._settings.fullscreen = not self._settings.fullscreen
        flags = pygame.FULLSCREEN if self._settings.fullscreen else 0
        self._screen = pygame.display.set_mode(self._settings.resolution, flags)
        self._settings.save()

    # ── update ────────────────────────────────────────────────────────────────

    def _update(self, dt: float) -> None:
        # Cap dt to avoid huge jumps on window drag
        dt = min(dt, 0.1)

        self._transition.update(dt)
        if not TOUCH_ENABLED:
            self._crt.update(dt)
        self._ach_toast.update(dt)
        
        if self._transition.done and self._next_state is not None:
            self._do_state_switch()
            self._transition.start_in()

        if self._state == GameState.LOADING:
            self._loading.update(dt)
            if self._loading.done:
                self._main_menu = self._build_main_menu()
                self._go_to(GameState.MAIN_MENU)

        elif self._state == GameState.MAIN_MENU and self._main_menu:
            self._main_menu.update(dt)

        elif self._state == GameState.GAME_SELECT and self._select:
            self._select.update(dt)

        elif self._state == GameState.LEVEL_SELECT and self._lvl_select:
            self._lvl_select.update(dt)

        elif self._state == GameState.PLAYING and self._active_game:
            outcome = self._active_game.update(dt)
            if outcome == "win":
                self._finish_game(won=True)
            elif outcome == "dead":
                self._finish_game(won=False)

        elif self._state == GameState.PAUSED and self._pause:
            self._pause.update(dt)

        elif self._state == GameState.SETTINGS and self._settings_scr:
            self._settings_scr.update(dt)

        elif self._state == GameState.HIGH_SCORES and self._scores_scr:
            self._scores_scr.update(dt)

        elif self._state == GameState.AVATAR_SELECT and self._avatar_scr:
            self._avatar_scr.update(dt)

        elif self._state == GameState.SHOP and self._shop_scr:
            self._shop_scr.update(dt)

        elif self._state == GameState.ACHIEVEMENTS and self._ach_scr:
            self._ach_scr.update(dt)

        elif self._state in (GameState.GAME_OVER, GameState.GAME_WIN):
            if self._result_screen:
                self._result_screen.update(dt)

    def _finish_game(self, won: bool) -> None:
        """Transition to result screen after a mini-game ends."""
        gid   = self._active_game_id or GameID.SNIPER
        score = getattr(self._active_game, "_player", None)
        if score is None:
            score = 0
        else:
            score = getattr(score, "score", 0)
            if score == 0:
                score = getattr(self._active_game, "_score", 0)

        best  = self._save.get_best_score(gid)

        coins = score // 100
        if coins > 0:
            self._save.add_coins(coins)
            
        import achievements
        achievements.check_achievement(self._save, "score_10k", score >= 10000)

        if won:
            self._save.unlock_next_level(gid)

        on_next = None
        if won and self._active_level < 6:
            on_next = lambda: self._start_game(gid, self._active_level + 1)

        self._result_screen = ResultScreen(
            won        = won,
            score      = score,
            game_id    = gid,
            best_score = best,
            on_retry   = lambda: self._start_game(gid, self._active_level),
            on_menu    = lambda: self._go_to(GameState.LEVEL_SELECT),
            on_next    = on_next,
        )

        new_state = GameState.GAME_WIN if won else GameState.GAME_OVER
        self._state = new_state
        if won:
            self._sound.play("victory")
        else:
            self._sound.play("game_over")
        self._sound.stop_music()

    # ── draw ──────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        if self._state == GameState.LOADING:
            self._loading.draw(self._screen)

        elif self._state == GameState.MAIN_MENU and self._main_menu:
            self._main_menu.draw(self._screen)

        elif self._state == GameState.GAME_SELECT and self._select:
            self._select.draw(self._screen)

        elif self._state == GameState.LEVEL_SELECT and self._lvl_select:
            self._lvl_select.draw(self._screen)

        elif self._state == GameState.PLAYING and self._active_game:
            self._active_game.draw(self._clock)

        elif self._state == GameState.PAUSED:
            # Draw game underneath, then overlay pause
            if self._active_game:
                self._active_game.draw(self._clock)
            if self._pause:
                self._pause.draw(self._screen)

        elif self._state == GameState.SETTINGS and self._settings_scr:
            if self._prev_state == GameState.PAUSED and self._active_game:
                self._active_game.draw(self._clock)
            else:
                self._screen.fill(DARK_BG)
            self._settings_scr.draw(self._screen)

        elif self._state == GameState.HIGH_SCORES and self._scores_scr:
            self._scores_scr.draw(self._screen)

        elif self._state == GameState.AVATAR_SELECT and self._avatar_scr:
            self._avatar_scr.draw(self._screen)

        elif self._state == GameState.SHOP and self._shop_scr:
            self._shop_scr.draw(self._screen)

        elif self._state == GameState.ACHIEVEMENTS and self._ach_scr:
            self._ach_scr.draw(self._screen)

        elif self._state in (GameState.GAME_OVER, GameState.GAME_WIN):
            if self._active_game:
                self._active_game.draw(self._clock)
            if self._result_screen:
                self._result_screen.draw(self._screen)

        else:
            self._screen.fill(BLACK)

        # Touch overlay
        if self._touch_overlay and self._state == GameState.PLAYING:
            self._touch_overlay.draw(self._screen)

        if not TOUCH_ENABLED:
            self._crt.draw(self._screen)
        self._ach_toast.draw(self._screen)
        self._transition.draw(self._screen)

        # Draw custom cursor if not playing
        if self._state != GameState.PLAYING:
            mx, my = pygame.mouse.get_pos()
            self._screen.blit(self._cursor, (mx - 10, my - 10))

        pygame.display.flip()
