from typing import List, Dict, Tuple
from enum import Enum
from itertools import combinations


class Suit(Enum):
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"


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


# --- deck builder ------------------------------------------------------------

def _build_deck_excluding(excluded: List[Card]) -> List[Card]:
    excluded_set = set(excluded)
    deck: List[Card] = []
    for suit in Suit:
        for rank in range(2, 15):
            c = Card(rank, suit)
            if c not in excluded_set:
                deck.append(c)
    return deck


# --- hand evaluation (category only) ----------------------------------------

def _is_straight(sorted_unique_ranks: List[int]) -> bool:
    """A-5も許容するストレート判定"""
    if len(sorted_unique_ranks) < 5:
        return False
    ranks = sorted_unique_ranks[:]
    if 14 in ranks:  # Aを1としても扱う
        ranks = sorted(set(ranks + [1]))
    for i in range(len(ranks) - 4):
        window = ranks[i:i+5]
        if window[-1] - window[0] == 4 and len(set(window)) == 5:
            return True
    return False


def _evaluate_hand(hole_cards: List[Card], community_cards: List[Card]) -> Tuple[str, int]:
    """
    7枚からベスト5枚の「役カテゴリ」を評価（キッカー等は無視）。
    返値: (役名, 強さ値) 強さ値が大きいほど強い。
    9:SF, 8:4K, 7:FH, 6:F, 5:S, 4:3K, 3:2P, 2:1P, 1:HC
    """
    all_cards = hole_cards + community_cards
    ranks = [c.rank for c in all_cards]
    suits = [c.suit for c in all_cards]

    # カウント
    rank_counts: Dict[int, int] = {}
    suit_counts: Dict[Suit, int] = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1

    unique_ranks = sorted(set(ranks))

    # フラッシュ
    flush_suit = None
    for s, cnt in suit_counts.items():
        if cnt >= 5:
            flush_suit = s
            break
    is_flush = flush_suit is not None

    # ストレート
    is_straight = _is_straight(unique_ranks)

    # ストレートフラッシュ
    is_straight_flush = False
    if is_flush:
        suited_ranks = sorted(set([c.rank for c in all_cards if c.suit == flush_suit]))
        if 14 in suited_ranks:
            suited_ranks = sorted(set(suited_ranks + [1]))
        for i in range(len(suited_ranks) - 4):
            window = suited_ranks[i:i+5]
            if window[-1] - window[0] == 4 and len(set(window)) == 5:
                is_straight_flush = True
                break

    counts = sorted(rank_counts.values(), reverse=True)
    max_count = counts[0] if counts else 0
    num_pairs = sum(1 for v in rank_counts.values() if v == 2)
    num_trips = sum(1 for v in rank_counts.values() if v == 3)
    has_full_house = (num_trips >= 1 and (num_pairs >= 1 or num_trips >= 2))

    if is_straight_flush:
        return "Straight Flush", 9
    elif max_count == 4:
        return "Four of a Kind", 8
    elif has_full_house:
        return "Full House", 7
    elif is_flush:
        return "Flush", 6
    elif is_straight:
        return "Straight", 5
    elif max_count == 3:
        return "Three of a Kind", 4
    elif num_pairs >= 2:
        return "Two Pair", 3
    elif max_count == 2:
        return "One Pair", 2
    else:
        return "High Card", 1


# --- tool entry --------------------------------------------------------------

def calculate_hand_probabilities(your_cards: List[str], community: List[str], phase: str = "") -> Dict[str, float]:
    """
    現在のホールカードとコミュニティカードから、ターン/リバーで最終的に成立しうる
    各役の確率分布（%）だけを返す。

    Args:
        your_cards (List[str]): 自分のホールカード2枚（例: ["A♥","K♦"] または ["Ah","Kd"]）
        community (List[str]): 公開札0〜5枚（例: ["10♣","J♣","Q♣"]）
        phase (str, optional): "preflop" | "flop" | "turn" | "river"（未指定なら community 枚数から推定）

    Returns:
        Dict[str, float]: 役名 → 確率（%）。flop/turn のみ分布を返す。river は確定100%。preflopは{}。
    """
    try:
        if not your_cards or len(your_cards) != 2:
            return {}

        # 文字列 → Card
        try:
            hole_cards = [_parse_card_string(s) for s in your_cards]
            community_cards = [_parse_card_string(s) for s in community]
        except Exception:
            return {}

        # ステージ判定（phaseが正しい形式なら優先、なければ公開札の枚数から）
        stage = (phase or "").lower()
        if stage not in ("preflop", "flop", "turn", "river"):
            n = len(community_cards)
            stage = "preflop" if n == 0 else "flop" if n == 3 else "turn" if n == 4 else "river" if n >= 5 else "invalid"

        # 残りデッキ
        deck = _build_deck_excluding(hole_cards + community_cards)

        # 役確率だけ返す
        if stage == "flop":
            total = 0
            counts: Dict[str, int] = {}
            for c1, c2 in combinations(deck, 2):
                total += 1
                name, _ = _evaluate_hand(hole_cards, community_cards + [c1, c2])
                counts[name] = counts.get(name, 0) + 1
            return {k: round(v * 100.0 / total, 2) for k, v in counts.items()} if total else {}

        if stage == "turn":
            total = len(deck)
            counts: Dict[str, int] = {}
            for c in deck:
                name, _ = _evaluate_hand(hole_cards, community_cards + [c])
                counts[name] = counts.get(name, 0) + 1
            return {k: round(v * 100.0 / total, 2) for k, v in counts.items()} if total else {}

        if stage == "river":
            name, _ = _evaluate_hand(hole_cards, community_cards)
            return {name: 100.0}

        # preflop や invalid
        return {}
    except Exception:
        return {}