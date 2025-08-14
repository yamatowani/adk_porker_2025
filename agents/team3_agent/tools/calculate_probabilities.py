from typing import List, Dict, Tuple
from enum import Enum
from itertools import combinations
from ..utils.card_utils import *


def calculate_hand_probabilities(your_cards: List[str], community: List[str], phase: str = "") -> dict:
    """
    Returns only the probability distribution (%) of each final hand that can be achieved
    given the current hole cards and community cards, after the remaining streets (turn/river).

    Args:
        your_cards (List[str]): Your two hole cards (e.g., ["Ah","Kd"]).
        community (List[str]): 0-5 community cards (e.g., ["10s","Jc","Qd"]).
        phase (str, optional): "preflop" | "flop" | "turn" | "river".
            If omitted, it is inferred from the number of community cards.

    Returns:
        dict: "probably_hand: "most probably hand", "expected_value": expected value of the hand.
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

        # 残りデッキ
        deck = build_deck_excluding(hole_cards + community_cards)

        # 役確率だけ返す
        if phase == "flop":
            total = 0
            counts: Dict[str, int] = {}
            for c1, c2 in combinations(deck, 2):
                total += 1
                name, _ = evaluate_hand_category(hole_cards, community_cards + [c1, c2])
                counts[name] = counts.get(name, 0) + 1

            if total == 0:
                return {"probably_hand": "", "expected_value": 0.0}

            probs = {k: v / total for k, v in counts.items()}
            probably_hand, _ = max(probs.items(), key=lambda kv: kv[1])
            ev = sum(p * HAND_WEIGHTS.get(hand, 0.0) for hand, p in probs.items())

            return {"probably_hand": probably_hand, "expected_value": round(ev, 4)}

        if phase == "turn":
            total += 1
            name, _ = evaluate_hand_category(hole_cards, community_cards + [c1, c2])
            counts[name] = counts.get(name, 0) + 1

            if total == 0:
                return {"probably_hand": "", "expected_value": 0.0}

            probs = {k: v / total for k, v in counts.items()}
            probably_hand, _ = max(probs.items(), key=lambda kv: kv[1])
            ev = sum(p * HAND_WEIGHTS.get(hand, 0.0) for hand, p in probs.items())

            return {"probably_hand": probably_hand, "expected_value": round(ev, 4)}

        if phase == "river":
            name, _ = evaluate_hand_category(hole_cards, community_cards)
            ev = HAND_WEIGHTS.get(name, 0.0)
            return {"probably_hand": name, "expected_value": float(ev)}

        return {}
    except Exception as e:
        return {}
