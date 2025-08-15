from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Dict, Tuple

__all__ = [
    "Suit",
    "Card",
    "parse_card",
    "parse_cards",
    "card_to_short",
    "card_to_unicode",
    "build_deck_excluding",
    "evaluate_hand_category",
]

HAND_STRENGTH_MAP: Dict[str, int] = {
    "straight flush": 9,
    "four of a kind": 8,
    "full house": 7,
    "flush": 6,
    "straight": 5,
    "three of a kind": 4,
    "two pair": 3,
    "one pair": 2,
    "high card": 1,
}

# ====== 型定義 ======

class Suit(Enum):
    HEARTS   = "h"
    DIAMONDS = "d"
    CLUBS    = "c"
    SPADES   = "s"

@dataclass(frozen=True, slots=True)
class Card:
    """ 例: Card(14, Suit.SPADES) == 'As' """
    rank: int            # 2..14 (14 = Ace)
    suit: Suit

    def __repr__(self) -> str:
        return card_to_short(self)

# ====== 内部ヘルパ ======

_RANK_TO_INT: Dict[str, int] = {
    "A": 14, "K": 13, "Q": 12, "J": 11, "T": 10, "10": 10,
    "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2,
}
_INT_TO_RANK: Dict[int, str] = {14:"A",13:"K",12:"Q",11:"J",10:"T",9:"9",8:"8",7:"7",6:"6",5:"5",4:"4",3:"3",2:"2"}

_UNICODE_TO_SUIT = {"♥": Suit.HEARTS, "♦": Suit.DIAMONDS, "♣": Suit.CLUBS, "♠": Suit.SPADES}
_LETTER_TO_SUIT  = {"H": Suit.HEARTS, "D": Suit.DIAMONDS, "C": Suit.CLUBS, "S": Suit.SPADES}

def _symbol_to_suit(symbol: str) -> Suit:
    sym = (symbol or "").strip()
    if sym in _UNICODE_TO_SUIT:
        return _UNICODE_TO_SUIT[sym]
    up = sym.upper()
    if up in _LETTER_TO_SUIT:
        return _LETTER_TO_SUIT[up]
    raise ValueError(f"Invalid suit symbol: {symbol!r}")

def _rank_to_int(rank_str: str) -> int:
    rs = (rank_str or "").strip().upper()
    if rs in _RANK_TO_INT:
        return _RANK_TO_INT[rs]
    try:
        v = int(rs)
        if 2 <= v <= 14:
            return v
    except Exception:
        pass
    raise ValueError(f"Invalid rank: {rank_str!r}")

def _parse_card_string(card_str: str) -> Card:
    s = (card_str or "").strip()
    if len(s) < 2:
        raise ValueError(f"Invalid card: {card_str!r}")
    return Card(_rank_to_int(s[:-1]), _symbol_to_suit(s[-1]))

def _is_straight(sorted_unique_ranks: List[int]) -> bool:
    """A を 1 としても扱い、A-2-3-4-5 も可。"""
    if len(sorted_unique_ranks) < 5:
        return False
    ranks = sorted_unique_ranks[:]
    if 14 in ranks:
        ranks = sorted(set(ranks + [1]))
    for i in range(len(ranks) - 4):
        w = ranks[i:i+5]
        if w[-1] - w[0] == 4 and len(set(w)) == 5:
            return True
    return False

# ====== 公開 API ======

def parse_card(card_str: str) -> Card:
    """'Ah' / 'A♥' / '10c' / 'Td' / '7S' などを Card に変換。"""
    return _parse_card_string(card_str)

def parse_cards(cards: Iterable[str]) -> List[Card]:
    """配列をまとめて Card 化。"""
    return [_parse_card_string(s) for s in (cards or [])]

def card_to_short(card: Card) -> str:
    """'Ah', '10c', 'Ks' の短縮表記へ。"""
    return f"{_INT_TO_RANK.get(card.rank, str(card.rank))}{card.suit.value}"

def card_to_unicode(card: Card) -> str:
    """'A♥', '10♣', 'K♠' のユニコード表記へ。"""
    suit_unicode = {Suit.HEARTS:"♥", Suit.DIAMONDS:"♦", Suit.CLUBS:"♣", Suit.SPADES:"♠"}[card.suit]
    return f"{_INT_TO_RANK.get(card.rank, str(card.rank))}{suit_unicode}"

def build_deck_excluding(excluded: Iterable[Card]) -> List[Card]:
    """指定カードを除いた 52 枚デッキを構築。"""
    ex = set(excluded or [])
    deck: List[Card] = []
    for suit in Suit:
        for rank in range(2, 15):
            c = Card(rank, suit)
            if c not in ex:
                deck.append(c)
    return deck

def hand_strength_from_name(hand_name: str) -> int:
    """
    役名から強さ(9..1)を返す。未知の表記は ValueError。
    許容例:
      "Full House", "full_house", "FULL-HOUSE", "fullhouse"
    """
    if not hand_name:
        raise ValueError("hand_name is empty")
    key = hand_name.strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())  # 余分な空白を畳む

    if key in HAND_STRENGTH_MAP:
        return HAND_STRENGTH_MAP[key]

    compact = key.replace(" ", "")
    if compact in _HAND_STRENGTH_COMPACT:
        return _HAND_STRENGTH_COMPACT[compact]

    raise ValueError(f"Unknown hand name: {hand_name!r}")

def evaluate_hand_category(hole_cards: List[Card], community_cards: List[Card]) -> Tuple[str, int]:
    """
    7枚からベスト5枚の「役カテゴリ」を返す（キッカー等は無視）。
    戻り値: (役名, 強さ値)
      9: Straight Flush
      8: Four of a Kind
      7: Full House
      6: Flush
      5: Straight
      4: Three of a Kind
      3: Two Pair
      2: One Pair
      1: High Card
    """
    all_cards = hole_cards + community_cards
    ranks = [c.rank for c in all_cards]
    suits = [c.suit for c in all_cards]

    # カウント
    rank_counts: Dict[int, int] = {}
    suit_counts: Dict[Suit, int] = {}
    for r in ranks: rank_counts[r] = rank_counts.get(r, 0) + 1
    for s in suits: suit_counts[s] = suit_counts.get(s, 0) + 1

    unique_ranks = sorted(set(ranks))

    # フラッシュ
    flush_suit = next((s for s, cnt in suit_counts.items() if cnt >= 5), None)
    is_flush = flush_suit is not None

    # ストレート
    is_straight = _is_straight(unique_ranks)

    # ストレートフラッシュ
    is_straight_flush = False
    if is_flush:
        suited_ranks = sorted(set(c.rank for c in all_cards if c.suit == flush_suit))
        if 14 in suited_ranks:
            suited_ranks = sorted(set(suited_ranks + [1]))
        for i in range(len(suited_ranks) - 4):
            w = suited_ranks[i:i+5]
            if w[-1] - w[0] == 4 and len(set(w)) == 5:
                is_straight_flush = True
                break

    counts_sorted = sorted(rank_counts.values(), reverse=True)
    max_count = counts_sorted[0] if counts_sorted else 0
    num_pairs = sum(1 for v in rank_counts.values() if v == 2)
    num_trips = sum(1 for v in rank_counts.values() if v == 3)
    has_full_house = (num_trips >= 1 and (num_pairs >= 1 or num_trips >= 2))

    if is_straight_flush: return "Straight Flush", 9
    if max_count == 4:    return "Four of a Kind", 8
    if has_full_house:    return "Full House", 7
    if is_flush:          return "Flush", 6
    if is_straight:       return "Straight", 5
    if max_count == 3:    return "Three of a Kind", 4
    if num_pairs >= 2:    return "Two Pair", 3
    if max_count == 2:    return "One Pair", 2
    return "High Card", 1


if __name__ == "__main__":
    # テスト用コード
    c1 = parse_card("As")
    c2 = parse_card("10h")
    print(c1, c2)
    print(card_to_short(c1), card_to_unicode(c2))

    deck = build_deck_excluding([c1, c2])
    print("Deck size excluding As and 10h:", len(deck))

    hand_name, strength = evaluate_hand_category([c1, c2], [])
    print(f"Hand: {hand_name}, Strength: {strength}")