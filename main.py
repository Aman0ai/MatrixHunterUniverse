"""
main.py
=======
Entry point for Matrix Hunter Universe.

Usage:
    python main.py

Requirements:
    pip install pygame-ce
"""

from __future__ import annotations

import sys
import os
import asyncio

# ── ensure the project root is on sys.path ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── dependency check ─────────────────────────────────────────────────────────
def _check_deps() -> None:
    missing = []
    try:
        import pygame  # noqa: F401
    except ImportError:
        missing.append("pygame-ce")
    if missing:
        print("=" * 60)
        print("Missing dependencies:")
        for pkg in missing:
            print(f"  pip install {pkg}")
        print("=" * 60)
        sys.exit(1)

_check_deps()

import pygame

def main() -> None:
    """Initialise and run the game."""
    # Ensure data directory exists before any save/settings operations
    from config import DATA_DIR
    import os as _os
    _os.makedirs(DATA_DIR, exist_ok=True)

    from game import GameManager
    manager = GameManager()

    # asyncio wrapper kept for Pygbag (web) compatibility.
    # Falls back gracefully on Android where the event loop may differ.
    try:
        asyncio.run(manager.run())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.run())
        finally:
            loop.close()


if __name__ == "__main__":
    main()
