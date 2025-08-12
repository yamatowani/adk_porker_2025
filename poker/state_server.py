"""
Lightweight HTTP JSON server exposing current PokerGame state for viewer.

This avoids adding external deps (FastAPI, etc.) by using http.server.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple

from .shared_state import get_current_game
from .player_models import PlayerStatus, LLMApiPlayer


def _card_to_str(card) -> str:
    try:
        return str(card)
    except Exception:
        return "??"


def _build_viewer_state() -> Dict[str, Any]:
    """Build a viewer-friendly JSON snapshot of the current game.

    All hole cards are exposed intentionally for spectator view.
    """
    game = get_current_game()
    if not game:
        return {"ready": False}

    def _latest_action_for_player(player_id: int) -> Tuple[str, int]:
        """Parse the game's action_history to find the latest action by player.

        Returns (action_label, amount). action_label examples: 'fold', 'check', 'call', 'raise', 'all_in', ''.
        """
        history: List[str] = list(getattr(game, "action_history", []))
        for entry in reversed(history):
            # Expected formats
            # 'Player {id} folded'
            # 'Player {id} checked'
            # 'Player {id} called {amt}'
            # 'Player {id} raised to {amt}'
            # 'Player {id} went all-in with {amt}'
            try:
                if entry.startswith(f"Player {player_id} "):
                    rest = entry.split(" ", 2)[2]
                    if rest.startswith("folded"):
                        return ("fold", 0)
                    if rest.startswith("checked"):
                        return ("check", 0)
                    if rest.startswith("called"):
                        amt = int(rest.split(" ")[1])
                        return ("call", amt)
                    if rest.startswith("raised to"):
                        amt = int(rest.split(" ")[-1])
                        return ("raise", amt)
                    if rest.startswith("went all-in with"):
                        amt = int(rest.split(" ")[-1])
                        return ("all_in", amt)
            except Exception:
                continue
        return ("", 0)

    players: List[Dict[str, Any]] = []
    llm_api_agents: List[Dict[str, Any]] = []
    for p in game.players:
        players.append(
            {
                "id": p.id,
                "name": p.name,
                "chips": p.chips,
                "current_bet": p.current_bet,
                "total_bet_this_hand": p.total_bet_this_hand,
                "status": getattr(p.status, "value", str(p.status)),
                "is_dealer": bool(getattr(p, "is_dealer", False)),
                "is_small_blind": bool(getattr(p, "is_small_blind", False)),
                "is_big_blind": bool(getattr(p, "is_big_blind", False)),
                "hole_cards": [_card_to_str(c) for c in getattr(p, "hole_cards", [])],
            }
        )

        # Collect LLM API agent info (latest action + last reasoning)
        if isinstance(p, LLMApiPlayer):
            action, amount = _latest_action_for_player(p.id)
            reasoning = getattr(p, "last_decision_reasoning", "")
            llm_api_agents.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "action": action,
                    "amount": amount,
                    "reasoning": reasoning,
                }
            )

    state: Dict[str, Any] = {
        "ready": True,
        "hand_number": game.hand_number,
        "phase": getattr(game.current_phase, "value", str(game.current_phase)),
        "pot": game.pot,
        "current_bet": game.current_bet,
        "dealer_button": game.dealer_button,
        "current_turn": game.current_player_index,
        "community_cards": [_card_to_str(c) for c in game.community_cards],
        "players": players,
        "action_history": list(game.action_history),
        "llm_api_agents": llm_api_agents,
    }
    return state


class _StateHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (keep stdlib signature)
        try:
            if self.path.startswith("/state"):
                state = _build_viewer_state()
                body = json.dumps(state).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                # Allow cross-origin for safety when opened from file or different port
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
        except Exception:
            self.send_response(500)
            self.end_headers()

    # Suppress stdlib log noise
    def log_message(self, format: str, *args):  # noqa: A003
        return


_server_singleton: ThreadingHTTPServer | None = None


def start_state_server(
    host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    """Start and return a new state server instance (no singleton guard)."""
    server = ThreadingHTTPServer((host, port), _StateHandler)
    return server


def ensure_state_server(
    host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    """Start state server once and return the singleton instance."""
    global _server_singleton
    if _server_singleton is None:
        _server_singleton = ThreadingHTTPServer((host, port), _StateHandler)
    return _server_singleton
