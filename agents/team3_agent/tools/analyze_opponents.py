import json
from typing import Any, Dict, List
from ..agents.analysis_agent import analysis_agent

def analyze_opponents(players: List[dict], history: List[str]) -> Dict[str, Any]:
    """
    Args:
        players: List of players information except yourself.
            Each player is a dict with keys like "id", "status", etc.
        history: List of strings representing the hand history (optional).
    Returns:
      {
        "opponent_strengths": [
          {"player_id": int, "positive": float}, ...
        ]
      }
    """

    results: List[Dict[str, Any]] = []

    for p in players:
        try:
            pid = int(p.get("id"))
            if p.get("status") == "active":
                out = analysis_agent.run({
                    "target_player_id": pid,
                    "history": history
                })
                if isinstance(out, str):
                    out = json.loads(out)
                positive = float(out.get("hand_strength", 0.0))
                # 0〜1にクリップ
                positive = 0.0 if positive < 0.0 else (1.0 if positive > 1.0 else positive)
                results.append({"player_id": pid, "positive": positive})
        except Exception:
            results.append({"player_id": int(p.get("id", -1)), "positive": 0.0})

    return {"opponent_strengths": results}
