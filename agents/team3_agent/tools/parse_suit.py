from typing import List, Dict, Tuple
from enum import Enum
from itertools import combinations
from ..utils.card_utils import *

def parse_suit(your_cards: List[str], community: List[str]) -> dict:
    """
    Change suit to character for later processing.
    Example: ♥|♦|♣|♠ → h|d|c|s

    Args:
        your_cards (List[str]): Player's hole cards (e.g., ["A♥", "K♦"]).
        community (List[str]): Community cards (e.g., ["10♣", "J♣", "Q♣"]).

    Returns:
        dict: A dictionary with suits of hole cards and community cards in h/d/c/s format.
    """
    try:
        parsed_your = [card_to_short(c) for c in parse_cards(your_cards)]
        parsed_community = [card_to_short(c) for c in parse_cards(community)]

        return {
            "your_cards": parsed_your,
            "community": parsed_community
        }
    except ValueError as e:
        return {"error": str(e)}