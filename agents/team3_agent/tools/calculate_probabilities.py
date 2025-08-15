from typing import List, Dict, Tuple
from enum import Enum
from itertools import combinations
from ..utils.card_utils import parse_cards, build_deck_excluding, evaluate_hand_category, hand_strength_from_name
import logging
logger = logging.getLogger(__name__)


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

        logger.info(f"calculate_hand_probabilities called with your_cards: {your_cards}, community: {community}, phase: {phase}")
        # 文字列 → Card
        try:
            hole_cards = parse_cards(your_cards)
            community_cards = parse_cards(community)
        except Exception:
            return {}

        # 残りデッキ
        deck = build_deck_excluding(hole_cards + community_cards)

        total = 0
        counts: Dict[str, int] = {}
        # 役確率だけ返す
        if phase == "flop":
            for c1, c2 in combinations(deck, 2):
                total += 1
                name, _ = evaluate_hand_category(hole_cards, community_cards + [c1, c2])
                counts[name] = counts.get(name, 0) + 1

            if total == 0:
                return {"probably_hand": "", "expected_value": 0.0}

            probs = {k: v / total for k, v in counts.items()}
            logger.info(f"counts: {counts}")
            probably_hand, _ = max(probs.items(), key=lambda kv: kv[1])
            ev = sum(p * hand_strength_from_name(hand) for hand, p in probs.items())

            logger.info(f"phase is {phase}")
            logger.info(f"Turn probably_hand: {probably_hand}, expected_value: {ev}")

            return {"probably_hand": probably_hand, "expected_value": round(ev, 4)}

        elif phase == "turn":
            for c1 in deck:
                total += 1
                name, _ = evaluate_hand_category(hole_cards, community_cards + [c1])
                counts[name] = counts.get(name, 0) + 1

            if total == 0:
                return {"probably_hand": "", "expected_value": 0.0}

            probs = {k: v / total for k, v in counts.items()}
            probably_hand, _ = max(probs.items(), key=lambda kv: kv[1])
            ev = sum(p * hand_strength_from_name(hand) for hand, p in probs.items())

            logger.info(f"phase is {phase}")
            logger.info(f"Turn probably_hand: {probably_hand}, expected_value: {ev}")

            return {"probably_hand": probably_hand, "expected_value": round(ev, 4)}

        elif phase == "river":
            name, _ = evaluate_hand_category(hole_cards, community_cards)
            ev = hand_strength_from_name(name)

            logger.info(f"phase is {phase}")
            logger.info(f"Turn probably_hand: {name}, expected_value: float(ev)")

            return {"probably_hand": name, "expected_value": float(ev)}

        else:
            return {}
    except Exception as e:
        logger.warning(f"Error in calculate_hand_probabilities: {e}")
        return {}

def calculate_hand_ranking(your_cards: List[str], community: List[str], phase: str = "") -> int:
    """
    Returns the hand category and strength value based on the current hole cards and community cards.

    Args:
        your_cards (List[str]): Your two hole cards (e.g., ["Ah","Kd"]).
        community (List[str]): 0-5 community cards (e.g., ["10s","Jc","Qd"]).
        phase (str, optional): "preflop" | "flop" | "turn" | "river".

    Returns:
        Tuple[str, int]: Hand category name and its strength value.
    """
    try:
        if not your_cards or len(your_cards) != 2:
            return 2

        calculate_hand_probabilities(your_cards, community, phase)
    except Exception as e:
        logger.warning(f"Error in calculate_hand_ranking: {e}")
        return 2