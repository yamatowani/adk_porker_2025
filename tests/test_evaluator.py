"""
Tests for poker.evaluator module
"""

import pytest
from poker.game_models import Card, Suit
from poker.evaluator import HandRank, HandResult, HandEvaluator


class TestHandRank:
    """HandRankクラスのテスト"""

    def test_hand_rank_values(self):
        """ハンドランクの値が正しいことを確認"""
        assert HandRank.ROYAL_FLUSH.value == 10
        assert HandRank.STRAIGHT_FLUSH.value == 9
        assert HandRank.FOUR_OF_A_KIND.value == 8
        assert HandRank.FULL_HOUSE.value == 7
        assert HandRank.FLUSH.value == 6
        assert HandRank.STRAIGHT.value == 5
        assert HandRank.THREE_OF_A_KIND.value == 4
        assert HandRank.TWO_PAIR.value == 3
        assert HandRank.ONE_PAIR.value == 2
        assert HandRank.HIGH_CARD.value == 1


class TestHandResult:
    """HandResultクラスのテスト"""

    def test_initialization(self):
        """初期化のテスト"""
        cards = [Card(14, Suit.SPADES), Card(13, Suit.SPADES)]
        result = HandResult(HandRank.HIGH_CARD, cards, [14, 13], "Test hand")

        assert result.rank == HandRank.HIGH_CARD
        assert result.cards == cards
        assert result.kickers == [14, 13]
        assert result.description == "Test hand"

    def test_initialization_default_kickers(self):
        """キッカーデフォルト値のテスト"""
        cards = [Card(14, Suit.SPADES)]
        result = HandResult(HandRank.HIGH_CARD, cards)

        assert result.kickers == []
        assert result.description == ""

    def test_comparison_different_ranks(self):
        """異なるランクの比較テスト"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(13, Suit.HEARTS)]

        pair = HandResult(HandRank.ONE_PAIR, cards1, [14])
        high_card = HandResult(HandRank.HIGH_CARD, cards2, [13])

        assert high_card < pair
        assert not pair < high_card

    def test_comparison_same_rank_different_kickers(self):
        """同じランク、異なるキッカーの比較テスト"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(13, Suit.HEARTS)]

        high_ace = HandResult(HandRank.HIGH_CARD, cards1, [14])
        high_king = HandResult(HandRank.HIGH_CARD, cards2, [13])

        assert high_king < high_ace
        assert not high_ace < high_king

    def test_comparison_same_rank_same_kickers(self):
        """同じランク、同じキッカーの比較テスト"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(14, Suit.HEARTS)]

        hand1 = HandResult(HandRank.HIGH_CARD, cards1, [14])
        hand2 = HandResult(HandRank.HIGH_CARD, cards2, [14])

        assert not hand1 < hand2
        assert not hand2 < hand1

    def test_equality_same_rank_same_kickers(self):
        """等価性テスト：同じランク、同じキッカー"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(14, Suit.HEARTS)]

        hand1 = HandResult(HandRank.HIGH_CARD, cards1, [14])
        hand2 = HandResult(HandRank.HIGH_CARD, cards2, [14])

        assert hand1 == hand2

    def test_equality_different_rank(self):
        """等価性テスト：異なるランク"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(14, Suit.HEARTS)]

        pair = HandResult(HandRank.ONE_PAIR, cards1, [14])
        high_card = HandResult(HandRank.HIGH_CARD, cards2, [14])

        assert pair != high_card

    def test_str_representation(self):
        """文字列表現のテスト"""
        cards = [Card(14, Suit.SPADES), Card(13, Suit.HEARTS)]
        result = HandResult(HandRank.HIGH_CARD, cards, [14, 13], "High Card: Ace")

        expected = "High Card: Ace - A♠, K♥"
        assert str(result) == expected


class TestHandEvaluator:
    """HandEvaluatorクラスのテスト"""

    def test_royal_flush(self):
        """ロイヤルフラッシュのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(13, Suit.SPADES)]
        community_cards = [
            Card(12, Suit.SPADES),
            Card(11, Suit.SPADES),
            Card(10, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.ROYAL_FLUSH
        assert result.kickers == [14]
        assert "Royal Flush" in result.description

    def test_straight_flush(self):
        """ストレートフラッシュのテスト"""
        hole_cards = [Card(9, Suit.HEARTS), Card(8, Suit.HEARTS)]
        community_cards = [
            Card(7, Suit.HEARTS),
            Card(6, Suit.HEARTS),
            Card(5, Suit.HEARTS),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.STRAIGHT_FLUSH
        assert result.kickers == [9]
        assert "Straight Flush" in result.description

    def test_four_of_a_kind(self):
        """フォーカードのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(14, Suit.HEARTS)]
        community_cards = [
            Card(14, Suit.DIAMONDS),
            Card(14, Suit.CLUBS),
            Card(13, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.FOUR_OF_A_KIND
        assert result.kickers[0] == 14  # Four Aces
        assert result.kickers[1] == 13  # King kicker
        assert "Four of a Kind" in result.description

    def test_full_house(self):
        """フルハウスのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(14, Suit.HEARTS)]
        community_cards = [
            Card(14, Suit.DIAMONDS),
            Card(13, Suit.CLUBS),
            Card(13, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.FULL_HOUSE
        assert result.kickers[0] == 14  # Three Aces
        assert result.kickers[1] == 13  # Pair of Kings
        assert "Full House" in result.description

    def test_flush(self):
        """フラッシュのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(12, Suit.SPADES)]
        community_cards = [
            Card(10, Suit.SPADES),
            Card(8, Suit.SPADES),
            Card(6, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.FLUSH
        assert result.kickers == [14, 12, 10, 8, 6]
        assert "Flush" in result.description

    def test_straight(self):
        """ストレートのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(13, Suit.HEARTS)]
        community_cards = [
            Card(12, Suit.DIAMONDS),
            Card(11, Suit.CLUBS),
            Card(10, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.STRAIGHT
        assert result.kickers == [14]
        assert "Straight" in result.description

    def test_straight_ace_low(self):
        """A-5ストレートのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(5, Suit.HEARTS)]
        community_cards = [
            Card(4, Suit.DIAMONDS),
            Card(3, Suit.CLUBS),
            Card(2, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.STRAIGHT
        assert result.kickers == [5]  # A-5 straight is 5-high

    def test_three_of_a_kind(self):
        """スリーカードのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(14, Suit.HEARTS)]
        community_cards = [
            Card(14, Suit.DIAMONDS),
            Card(13, Suit.CLUBS),
            Card(12, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.THREE_OF_A_KIND
        assert result.kickers[0] == 14  # Three Aces
        assert result.kickers[1:] == [13, 12]  # Kickers
        assert "Three of a Kind" in result.description

    def test_two_pair(self):
        """ツーペアのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(14, Suit.HEARTS)]
        community_cards = [
            Card(13, Suit.DIAMONDS),
            Card(13, Suit.CLUBS),
            Card(12, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.TWO_PAIR
        assert result.kickers[0:2] == [14, 13]  # Pairs (higher first)
        assert result.kickers[2] == 12  # Kicker
        assert "Two Pair" in result.description

    def test_one_pair(self):
        """ワンペアのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(14, Suit.HEARTS)]
        community_cards = [
            Card(13, Suit.DIAMONDS),
            Card(12, Suit.CLUBS),
            Card(11, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.ONE_PAIR
        assert result.kickers[0] == 14  # Pair of Aces
        assert result.kickers[1:] == [13, 12, 11]  # Kickers
        assert "One Pair" in result.description

    def test_high_card(self):
        """ハイカードのテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(12, Suit.HEARTS)]
        community_cards = [
            Card(10, Suit.DIAMONDS),
            Card(8, Suit.CLUBS),
            Card(6, Suit.SPADES),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.HIGH_CARD
        assert result.kickers == [14, 12, 10, 8, 6]
        assert "High Card" in result.description

    def test_evaluate_less_than_five_cards(self):
        """5枚未満のカードでの評価テスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(13, Suit.HEARTS)]
        community_cards = [Card(12, Suit.DIAMONDS)]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.HIGH_CARD
        assert result.kickers == [14, 13, 12]

    def test_evaluate_seven_cards_best_hand(self):
        """7枚から最強の5枚を選択するテスト"""
        hole_cards = [Card(14, Suit.SPADES), Card(14, Suit.HEARTS)]
        community_cards = [
            Card(14, Suit.DIAMONDS),
            Card(14, Suit.CLUBS),  # Four Aces
            Card(13, Suit.SPADES),
            Card(12, Suit.HEARTS),
            Card(11, Suit.DIAMONDS),
        ]

        result = HandEvaluator.evaluate_hand(hole_cards, community_cards)

        assert result.rank == HandRank.FOUR_OF_A_KIND
        assert result.kickers[0] == 14  # Four Aces
        assert result.kickers[1] == 13  # Best kicker (King)

    def test_is_straight_normal(self):
        """通常のストレート判定テスト"""
        ranks = [14, 13, 12, 11, 10]  # A-K-Q-J-10
        assert HandEvaluator._is_straight(ranks) is True

        ranks = [9, 8, 7, 6, 5]  # 9-8-7-6-5
        assert HandEvaluator._is_straight(ranks) is True

    def test_is_straight_ace_low(self):
        """A-5ストレート判定テスト"""
        ranks = [14, 5, 4, 3, 2]  # A-5-4-3-2
        assert HandEvaluator._is_straight(ranks) is True

    def test_is_not_straight(self):
        """ストレートでない場合のテスト"""
        ranks = [14, 13, 12, 11, 9]  # Missing 10
        assert HandEvaluator._is_straight(ranks) is False

        ranks = [14, 13, 12, 11, 11]  # Duplicate
        assert HandEvaluator._is_straight(ranks) is False

        ranks = [8, 7, 6, 5, 3]  # Gap
        assert HandEvaluator._is_straight(ranks) is False

    def test_compare_hands_different_ranks(self):
        """異なるランクのハンド比較テスト"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(13, Suit.HEARTS)]

        pair = HandResult(HandRank.ONE_PAIR, cards1, [14])
        high_card = HandResult(HandRank.HIGH_CARD, cards2, [13])

        assert HandEvaluator.compare_hands(pair, high_card) == 1
        assert HandEvaluator.compare_hands(high_card, pair) == -1

    def test_compare_hands_same_rank_different_kickers(self):
        """同じランク、異なるキッカーのハンド比較テスト"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(13, Suit.HEARTS)]

        high_ace = HandResult(HandRank.HIGH_CARD, cards1, [14])
        high_king = HandResult(HandRank.HIGH_CARD, cards2, [13])

        assert HandEvaluator.compare_hands(high_ace, high_king) == 1
        assert HandEvaluator.compare_hands(high_king, high_ace) == -1

    def test_compare_hands_tie(self):
        """同じハンドの比較テスト"""
        cards1 = [Card(14, Suit.SPADES)]
        cards2 = [Card(14, Suit.HEARTS)]

        hand1 = HandResult(HandRank.HIGH_CARD, cards1, [14])
        hand2 = HandResult(HandRank.HIGH_CARD, cards2, [14])

        assert HandEvaluator.compare_hands(hand1, hand2) == 0

    def test_get_hand_strength_description(self):
        """ハンドの強さ説明テスト"""
        cards = [Card(14, Suit.SPADES)]

        # 全ハンドランクをテスト
        test_cases = [
            (HandRank.ROYAL_FLUSH, "ロイヤルフラッシュ"),
            (HandRank.STRAIGHT_FLUSH, "ストレートフラッシュ"),
            (HandRank.FOUR_OF_A_KIND, "フォーカード"),
            (HandRank.FULL_HOUSE, "フルハウス"),
            (HandRank.FLUSH, "フラッシュ"),
            (HandRank.STRAIGHT, "ストレート"),
            (HandRank.THREE_OF_A_KIND, "スリーカード"),
            (HandRank.TWO_PAIR, "ツーペア"),
            (HandRank.ONE_PAIR, "ワンペア"),
            (HandRank.HIGH_CARD, "ハイカード"),
        ]

        for rank, expected_desc in test_cases:
            hand = HandResult(rank, cards, [], "")
            assert HandEvaluator.get_hand_strength_description(hand) == expected_desc

    def test_evaluate_five_cards_invalid_count(self):
        """5枚でないカードでの評価エラーテスト"""
        cards = [Card(14, Suit.SPADES), Card(13, Suit.HEARTS)]  # 2枚だけ

        with pytest.raises(ValueError, match="Must evaluate exactly 5 cards"):
            HandEvaluator._evaluate_five_cards(cards)
