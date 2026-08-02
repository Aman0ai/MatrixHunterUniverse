"""
save_manager.py
===============
High-score persistence and per-game save-state management.
All data is stored in data/highscores.json and data/save.json.
"""

from __future__ import annotations

import json
import os
from typing import Any

from config import HIGHSCORES_FILE, SAVE_FILE, DATA_DIR, GameID


class SaveManager:
    """Centralised save / load for high scores and game states."""

    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self._scores: dict[str, list[int]] = self._load_scores()
        self._state:  dict[str, Any]       = self._load_state()

    # ── High Scores ───────────────────────────────────────────────

    def _load_scores(self) -> dict[str, list[int]]:
        """Load high-score table from disk (returns empty dict on failure)."""
        if os.path.exists(HIGHSCORES_FILE):
            try:
                with open(HIGHSCORES_FILE, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, IOError):
                pass
        return {gid.value: [] for gid in GameID}

    def _save_scores(self) -> None:
        """Persist high-score table to disk."""
        with open(HIGHSCORES_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._scores, fh, indent=2)

    def add_score(self, game_id: GameID, score: int) -> None:
        """Insert a new score, keep only the top-10 per game."""
        key = game_id.value
        if key not in self._scores:
            self._scores[key] = []
        self._scores[key].append(score)
        self._scores[key].sort(reverse=True)
        self._scores[key] = self._scores[key][:10]
        self._save_scores()

    def get_top_scores(self, game_id: GameID, n: int = 5) -> list[int]:
        """Return top-n scores for a given game (descending)."""
        key = game_id.value
        return self._scores.get(key, [])[:n]

    def get_best_score(self, game_id: GameID) -> int:
        """Return the single best score (0 if none)."""
        scores = self.get_top_scores(game_id, n=1)
        return scores[0] if scores else 0

    def all_scores(self) -> dict[str, list[int]]:
        """Return the complete score table."""
        return dict(self._scores)

    def get_global_scores(self, game_id: GameID, n: int = 5) -> list[tuple[str, int]]:
        """Mock global leaderboard by combining fake players with local best."""
        import random
        # deterministic fake scores based on game
        random.seed(game_id.value)
        fake_names = ["Neo", "Trinity", "Morpheus", "Smith", "Cypher", "Oracle", "Dozer"]
        global_list = []
        for i in range(10):
            global_list.append((random.choice(fake_names), random.randint(1000, 25000)))
        
        # Add local best
        local_best = self.get_best_score(game_id)
        if local_best > 0:
            global_list.append(("You", local_best))
            
        global_list.sort(key=lambda x: x[1], reverse=True)
        # Restore random seed
        random.seed()
        return global_list[:n]

    # ── Game State ────────────────────────────────────────────────

    def _load_state(self) -> dict[str, Any]:
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def save_state(self, game_id: GameID, state: dict[str, Any]) -> None:
        """Persist arbitrary game-specific state (level, lives, etc.)."""
        self._state[game_id.value] = state
        with open(SAVE_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=2)

    def load_state(self, game_id: GameID) -> dict[str, Any]:
        """Retrieve previously saved state for a game (empty dict if none)."""
        return dict(self._state.get(game_id.value, {}))

    def clear_state(self, game_id: GameID) -> None:
        """Erase saved state for a specific game."""
        self._state.pop(game_id.value, None)
        with open(SAVE_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=2)

    # ── Global State (Coins, Shop, Achievements) ──────────────────

    def get_coins(self) -> int:
        return self._state.get("coins", 0)

    def add_coins(self, amount: int) -> None:
        self._state["coins"] = self.get_coins() + amount
        with open(SAVE_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=2)

    def spend_coins(self, amount: int) -> bool:
        if self.get_coins() >= amount:
            self._state["coins"] -= amount
            with open(SAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2)
            return True
        return False

    def get_unlocked_items(self) -> list[str]:
        return self._state.get("unlocked_items", [])

    def unlock_item(self, item_id: str) -> None:
        items = self.get_unlocked_items()
        if item_id not in items:
            items.append(item_id)
            self._state["unlocked_items"] = items
            with open(SAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2)

    def get_unlocked_achievements(self) -> list[str]:
        return self._state.get("achievements", [])

    def unlock_achievement(self, ach_id: str) -> None:
        achs = self.get_unlocked_achievements()
        if ach_id not in achs:
            achs.append(ach_id)
            self._state["achievements"] = achs
            with open(SAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2)

    def get_unlocked_level(self, game_id: GameID) -> int:
        """Returns the highest unlocked level for a game (min 1, max 11)."""
        prog = self._state.get("level_progress", {})
        return 11 # Unlocked for testing
        
    def unlock_next_level(self, game_id: GameID) -> None:
        """Unlocks the next level if below max (11)."""
        prog = self._state.get("level_progress", {})
        current = prog.get(game_id.value, 1)
        if current < 11:
            prog[game_id.value] = current + 1
            self._state["level_progress"] = prog
            with open(SAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._state, fh, indent=2)
