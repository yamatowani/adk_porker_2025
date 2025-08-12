"""
Poker hand evaluation system
"""

from typing import List, Tuple, Optional
from enum import Enum
from collections import Counter
from .game_models import Card


class HandRank(Enum):
    """ハンドランキング（強い順）"""

    ROYAL_FLUSH = 10
    STRAIGHT_FLUSH = 9
    FOUR_OF_A_KIND = 8
    FULL_HOUSE = 7
    FLUSH = 6
    STRAIGHT = 5
    THREE_OF_A_KIND = 4
    TWO_PAIR = 3
    ONE_PAIR = 2
    HIGH_CARD = 1


class HandResult:
    """ハンド評価結果"""

    def __init__(
        self,
        rank: HandRank,
        cards: List[Card],
        kickers: List[int] = None,
        description: str = "",
    ):
        self.rank = rank
        self.cards = cards  # ハンドを構成する5枚のカード
        self.kickers = kickers or []  # 同じランクの場合の比較用
        self.description = description

    def __lt__(self, other):
        """ハンドの強さを比較（弱い方がTrue）"""
        if self.rank.value != other.rank.value:
            return self.rank.value < other.rank.value

        # 同じランクの場合はキッカーで比較
        for my_kicker, other_kicker in zip(self.kickers, other.kickers):
            if my_kicker != other_kicker:
                return my_kicker < other_kicker

        return False  # 同じ強さ

    def __eq__(self, other):
        """ハンドの強さが同じかチェック"""
        return self.rank == other.rank and self.kickers == other.kickers

    def __str__(self):
        return f"{self.description} - {', '.join(str(card) for card in self.cards)}"


class HandEvaluator:
    """ハンド評価クラス"""

    @staticmethod
    def evaluate_hand(
        hole_cards: List[Card], community_cards: List[Card]
    ) -> HandResult:
        """
        プレイヤーのホールカードとコミュニティカードから最強のハンドを評価

        Args:
            hole_cards: プレイヤーの手札（2枚）
            community_cards: コミュニティカード（最大5枚）

        Returns:
            HandResult: 最強ハンドの評価結果
        """
        all_cards = hole_cards + community_cards

        if len(all_cards) < 5:
            # 5枚未満の場合はハイカードとして評価
            sorted_cards = sorted(all_cards, key=lambda c: c.rank, reverse=True)
            return HandResult(
                HandRank.HIGH_CARD,
                sorted_cards,
                [c.rank for c in sorted_cards],
                f"High Card: {sorted_cards[0]}",
            )

        # 7枚から最強の5枚の組み合わせを探す
        from itertools import combinations

        best_hand = None
        for five_cards in combinations(all_cards, 5):
            hand_result = HandEvaluator._evaluate_five_cards(list(five_cards))
            if (
                best_hand is None
                or hand_result.rank.value > best_hand.rank.value
                or (hand_result.rank == best_hand.rank and not hand_result < best_hand)
            ):
                best_hand = hand_result

        return best_hand

    @staticmethod
    def _evaluate_five_cards(cards: List[Card]) -> HandResult:
        """5枚のカードからハンドを評価"""
        if len(cards) != 5:
            raise ValueError("Must evaluate exactly 5 cards")

        # カードをランク順にソート（降順）
        sorted_cards = sorted(cards, key=lambda c: c.rank, reverse=True)
        ranks = [c.rank for c in sorted_cards]
        suits = [c.suit for c in sorted_cards]

        # 各ランクの枚数をカウント
        rank_counts = Counter(ranks)
        count_values = sorted(rank_counts.values(), reverse=True)

        # フラッシュとストレートをチェック
        is_flush = len(set(suits)) == 1
        is_straight = HandEvaluator._is_straight(ranks)

        # ロイヤルフラッシュ
        if is_flush and is_straight and ranks[0] == 14:  # A-K-Q-J-10
            return HandResult(HandRank.ROYAL_FLUSH, sorted_cards, [14], "Royal Flush")

        # ストレートフラッシュ
        if is_flush and is_straight:
            high_card = ranks[0] if ranks != [14, 5, 4, 3, 2] else 5  # A-5 straight
            return HandResult(
                HandRank.STRAIGHT_FLUSH,
                sorted_cards,
                [high_card],
                f"Straight Flush: {sorted_cards[0]}-high",
            )

        # フォーカード
        if count_values == [4, 1]:
            four_rank = [rank for rank, count in rank_counts.items() if count == 4][0]
            kicker = [rank for rank, count in rank_counts.items() if count == 1][0]
            return HandResult(
                HandRank.FOUR_OF_A_KIND,
                sorted_cards,
                [four_rank, kicker],
                f"Four of a Kind: {Card.RANK_NAMES[four_rank]}s",
            )

        # フルハウス
        if count_values == [3, 2]:
            three_rank = [rank for rank, count in rank_counts.items() if count == 3][0]
            pair_rank = [rank for rank, count in rank_counts.items() if count == 2][0]
            return HandResult(
                HandRank.FULL_HOUSE,
                sorted_cards,
                [three_rank, pair_rank],
                f"Full House: {Card.RANK_NAMES[three_rank]}s over {Card.RANK_NAMES[pair_rank]}s",
            )

        # フラッシュ
        if is_flush:
            return HandResult(
                HandRank.FLUSH, sorted_cards, ranks, f"Flush: {sorted_cards[0]}-high"
            )

        # ストレート
        if is_straight:
            high_card = ranks[0] if ranks != [14, 5, 4, 3, 2] else 5  # A-5 straight
            return HandResult(
                HandRank.STRAIGHT,
                sorted_cards,
                [high_card],
                f"Straight: {Card.RANK_NAMES[high_card]}-high",
            )

        # スリーカード
        if count_values == [3, 1, 1]:
            three_rank = [rank for rank, count in rank_counts.items() if count == 3][0]
            kickers = sorted(
                [rank for rank, count in rank_counts.items() if count == 1],
                reverse=True,
            )
            return HandResult(
                HandRank.THREE_OF_A_KIND,
                sorted_cards,
                [three_rank] + kickers,
                f"Three of a Kind: {Card.RANK_NAMES[three_rank]}s",
            )

        # ツーペア
        if count_values == [2, 2, 1]:
            pairs = sorted(
                [rank for rank, count in rank_counts.items() if count == 2],
                reverse=True,
            )
            kicker = [rank for rank, count in rank_counts.items() if count == 1][0]
            return HandResult(
                HandRank.TWO_PAIR,
                sorted_cards,
                pairs + [kicker],
                f"Two Pair: {Card.RANK_NAMES[pairs[0]]}s and {Card.RANK_NAMES[pairs[1]]}s",
            )

        # ワンペア
        if count_values == [2, 1, 1, 1]:
            pair_rank = [rank for rank, count in rank_counts.items() if count == 2][0]
            kickers = sorted(
                [rank for rank, count in rank_counts.items() if count == 1],
                reverse=True,
            )
            return HandResult(
                HandRank.ONE_PAIR,
                sorted_cards,
                [pair_rank] + kickers,
                f"One Pair: {Card.RANK_NAMES[pair_rank]}s",
            )

        # ハイカード
        return HandResult(
            HandRank.HIGH_CARD, sorted_cards, ranks, f"High Card: {sorted_cards[0]}"
        )

    @staticmethod
    def _is_straight(ranks: List[int]) -> bool:
        """ストレートかどうかをチェック"""
        sorted_ranks = sorted(set(ranks), reverse=True)

        if len(sorted_ranks) != 5:
            return False

        # 通常のストレート
        if sorted_ranks[0] - sorted_ranks[4] == 4:
            return True

        # A-5ストレート（A, 5, 4, 3, 2）
        if sorted_ranks == [14, 5, 4, 3, 2]:
            return True

        return False

    @staticmethod
    def compare_hands(hand1: HandResult, hand2: HandResult) -> int:
        """
        2つのハンドを比較

        Returns:
            1: hand1が勝ち
            -1: hand2が勝ち
            0: 引き分け
        """
        if hand1.rank.value > hand2.rank.value:
            return 1
        elif hand1.rank.value < hand2.rank.value:
            return -1
        else:
            # 同じランクの場合はキッカーで比較
            for k1, k2 in zip(hand1.kickers, hand2.kickers):
                if k1 > k2:
                    return 1
                elif k1 < k2:
                    return -1
            return 0  # 完全に同じ

    @staticmethod
    def get_hand_strength_description(hand: HandResult) -> str:
        """ハンドの強さを日本語で説明"""
        descriptions = {
            HandRank.ROYAL_FLUSH: "ロイヤルフラッシュ",
            HandRank.STRAIGHT_FLUSH: "ストレートフラッシュ",
            HandRank.FOUR_OF_A_KIND: "フォーカード",
            HandRank.FULL_HOUSE: "フルハウス",
            HandRank.FLUSH: "フラッシュ",
            HandRank.STRAIGHT: "ストレート",
            HandRank.THREE_OF_A_KIND: "スリーカード",
            HandRank.TWO_PAIR: "ツーペア",
            HandRank.ONE_PAIR: "ワンペア",
            HandRank.HIGH_CARD: "ハイカード",
        }
        return descriptions.get(hand.rank, "不明なハンド")
