from typing import List, Dict, Tuple
from enum import Enum
from itertools import combinations


class Suit(Enum):
    HEARTS = "h"
    DIAMONDS = "d"
    CLUBS = "c"
    SPADES = "s"


class Card:
    def __init__(self, rank: int, suit: Suit):
        self.rank = rank
        self.suit = suit

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))

    def __repr__(self):
        rank_str = {14: "A", 13: "K", 12: "Q", 11: "J"}.get(self.rank, str(self.rank))
        return f"{rank_str}{self.suit.value}"


# --- parsing helpers ---------------------------------------------------------

def _symbol_to_suit(symbol: str) -> Suit:
    """'♥♦♣♠' だけでなく 'H/D/C/S' も許容"""
    sym = symbol.strip()
    mapping = {
        "♥": Suit.HEARTS, "H": Suit.HEARTS, "h": Suit.HEARTS,
        "♦": Suit.DIAMONDS, "D": Suit.DIAMONDS, "d": Suit.DIAMONDS,
        "♣": Suit.CLUBS, "C": Suit.CLUBS, "c": Suit.CLUBS,
        "♠": Suit.SPADES, "S": Suit.SPADES, "s": Suit.SPADES,
    }
    if sym in mapping:
        return mapping[sym]
    raise ValueError(f"Invalid suit symbol: {symbol}")


def _rank_to_int(rank_str: str) -> int:
    rs = rank_str.strip().upper()
    rank_map = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10, "10": 10,
                "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2}
    if rs in rank_map:
        return rank_map[rs]
    try:
        val = int(rs)
        if 2 <= val <= 14:
            return val
    except Exception:
        pass
    raise ValueError(f"Invalid rank: {rank_str}")


def _parse_card_string(card_str: str) -> Card:
    s = card_str.strip()
    if len(s) < 2:
        raise ValueError(f"Invalid card: {card_str}")
    suit_symbol = s[-1]
    rank_str = s[:-1]
    return Card(_rank_to_int(rank_str), _symbol_to_suit(suit_symbol))

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
        parsed_your = [repr(_parse_card_string(c)) for c in your_cards]
        parsed_community = [repr(_parse_card_string(c)) for c in community]

        return {
            "your_cards": parsed_your,
            "community": parsed_community
        }
    except ValueError as e:
        return {"error": str(e)}