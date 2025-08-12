"""
Shared game state registry for cross-UI coordination inside the same process.

This module allows the main player UI and the spectator (viewer) UI to share
the same PokerGame instance without introducing a network server.
"""

from __future__ import annotations

from typing import Optional
from threading import Lock

try:
    # Import lazily to avoid circular imports at module import time
    from .game import PokerGame
except Exception:
    PokerGame = None  # type: ignore


_lock: Lock = Lock()
_current_game: Optional["PokerGame"] = None


def set_current_game(game: "PokerGame") -> None:
    """Register the active PokerGame instance to be shared by other UIs."""
    global _current_game
    with _lock:
        _current_game = game


def get_current_game() -> Optional["PokerGame"]:
    """Get the currently active PokerGame instance if available."""
    with _lock:
        return _current_game
