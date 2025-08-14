from typing import List, Dict, Tuple
from enum import Enum
from itertools import combinations
from ..utils.card_utils import *


def calculate_hand_probabilities(your_cards: List[str], community: List[str], phase: str = "") -> Dict[str, float]:
    """
    Returns only the probability distribution (%) of each final hand that can be achieved
    given the current hole cards and community cards, after the remaining streets (turn/river).

    Args:
        your_cards (List[str]): Your two hole cards (e.g., ["Ah","Kd"]).
        community (List[str]): 0-5 community cards (e.g., ["10s","Jc","Qd"]).
        phase (str, optional): "preflop" | "flop" | "turn" | "river".
            If omitted, it is inferred from the number of community cards.

    Returns:
        Dict[str, float]: Mapping from hand name to probability (%).
            Returns a distribution only on the flop/turn;
            on the river it is fully determined (100%),
            and on preflop it returns {}.
    """
    try:
        if not your_cards or len(your_cards) != 2:
            return {}

        # 文字列 → Card
        try:
            hole_cards = parse_cards(your_cards)
            community_cards = parse_cards(community)
        except Exception:
            return {}

        # ステージ判定（phaseが正しい形式なら優先、なければ公開札の枚数から）
        stage = (phase or "").lower()
        if stage not in ("preflop", "flop", "turn", "river"):
            n = len(community_cards)
            stage = "preflop" if n == 0 else "flop" if n == 3 else "turn" if n == 4 else "river" if n >= 5 else "invalid"

        # 残りデッキ
        deck = build_deck_excluding(hole_cards + community_cards)

        # 役確率だけ返す
        if stage == "flop":
            total = 0
            counts: Dict[str, int] = {}
            for c1, c2 in combinations(deck, 2):
                total += 1
                name, _ = evaluate_hand_category(hole_cards, community_cards + [c1, c2])
                counts[name] = counts.get(name, 0) + 1
            print(f"Flop stage: {total} combinations evaluated.")
            return {k: round(v * 100.0 / total, 2) for k, v in counts.items()} if total else {"empty": 100}

        if stage == "turn":
            total = len(deck)
            counts: Dict[str, int] = {}
            for c in deck:
                name, _ = evaluate_hand_category(hole_cards, community_cards + [c])
                counts[name] = counts.get(name, 0) + 1
            return {k: round(v * 100.0 / total, 2) for k, v in counts.items()} if total else {}

        if stage == "river":
            name, _ = evaluate_hand_category(hole_cards, community_cards)
            return {name: 100.0}

        # preflop や invalid
        return {}
    except Exception as e:
        print(f"Error calculating hand probabilities: {e}")
        return {}
