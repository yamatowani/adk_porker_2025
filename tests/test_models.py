"""
Tests for poker.models module
"""

import pytest
import random
from poker.game_models import Suit, Card, Deck
from poker.player_models import (
    PlayerStatus,
    Player,
    HumanPlayer,
    RandomPlayer,
    LLMPlayer,
)


class TestSuit:
    """Suitクラスのテスト"""

    def test_suit_values(self):
        """スートの値が正しいことを確認"""
        assert Suit.HEARTS.value == "hearts"
        assert Suit.DIAMONDS.value == "diamonds"
        assert Suit.CLUBS.value == "clubs"
        assert Suit.SPADES.value == "spades"


class TestCard:
    """Cardクラスのテスト"""

    def test_card_creation_valid(self):
        """正常なカード作成"""
        card = Card(14, Suit.SPADES)
        assert card.rank == 14
        assert card.suit == Suit.SPADES

    def test_card_creation_invalid_rank_low(self):
        """不正なランク（低すぎる）でのエラー"""
        with pytest.raises(ValueError, match="Rank must be between 2 and 14"):
            Card(1, Suit.HEARTS)

    def test_card_creation_invalid_rank_high(self):
        """不正なランク（高すぎる）でのエラー"""
        with pytest.raises(ValueError, match="Rank must be between 2 and 14"):
            Card(15, Suit.HEARTS)

    def test_rank_name_property(self):
        """rank_nameプロパティのテスト"""
        assert Card(2, Suit.HEARTS).rank_name == "2"
        assert Card(10, Suit.HEARTS).rank_name == "10"
        assert Card(11, Suit.HEARTS).rank_name == "J"
        assert Card(12, Suit.HEARTS).rank_name == "Q"
        assert Card(13, Suit.HEARTS).rank_name == "K"
        assert Card(14, Suit.HEARTS).rank_name == "A"

    def test_suit_symbol_property(self):
        """suit_symbolプロパティのテスト"""
        assert Card(14, Suit.HEARTS).suit_symbol == "♥"
        assert Card(14, Suit.DIAMONDS).suit_symbol == "♦"
        assert Card(14, Suit.CLUBS).suit_symbol == "♣"
        assert Card(14, Suit.SPADES).suit_symbol == "♠"

    def test_str_representation(self):
        """文字列表現のテスト"""
        card = Card(14, Suit.SPADES)
        assert str(card) == "A♠"

        card2 = Card(10, Suit.HEARTS)
        assert str(card2) == "10♥"

    def test_equality(self):
        """等価性テスト"""
        card1 = Card(14, Suit.SPADES)
        card2 = Card(14, Suit.SPADES)
        card3 = Card(14, Suit.HEARTS)
        card4 = Card(13, Suit.SPADES)

        assert card1 == card2
        assert card1 != card3
        assert card1 != card4
        assert card1 != "not a card"

    def test_hash(self):
        """ハッシュのテスト"""
        card1 = Card(14, Suit.SPADES)
        card2 = Card(14, Suit.SPADES)
        card3 = Card(14, Suit.HEARTS)

        assert hash(card1) == hash(card2)
        assert hash(card1) != hash(card3)

    def test_repr(self):
        """repr表現のテスト"""
        card = Card(14, Suit.SPADES)
        assert repr(card) == "Card(A, spades)"


class TestDeck:
    """Deckクラスのテスト"""

    def test_deck_initialization(self):
        """デッキの初期化テスト"""
        deck = Deck()
        assert len(deck.cards) == 52
        assert deck.cards_remaining() == 52

    def test_deck_has_all_cards(self):
        """デッキに全52枚のカードが含まれていることを確認"""
        deck = Deck()
        # カードをソートして確認しやすくする
        deck.cards.sort(key=lambda c: (c.suit.value, c.rank))

        expected_cards = []
        for suit in Suit:
            for rank in range(2, 15):
                expected_cards.append(Card(rank, suit))

        expected_cards.sort(key=lambda c: (c.suit.value, c.rank))

        assert len(deck.cards) == len(expected_cards)
        for deck_card, expected_card in zip(deck.cards, expected_cards):
            assert deck_card == expected_card

    def test_deal_card(self):
        """カード配布のテスト"""
        deck = Deck()
        initial_count = deck.cards_remaining()

        card = deck.deal_card()
        assert isinstance(card, Card)
        assert deck.cards_remaining() == initial_count - 1

    def test_deal_card_empty_deck(self):
        """空デッキからの配布エラーテスト"""
        deck = Deck()
        # 全カードを配布
        while deck.cards_remaining() > 0:
            deck.deal_card()

        with pytest.raises(ValueError, match="Cannot deal from empty deck"):
            deck.deal_card()

    def test_reset(self):
        """デッキリセットのテスト"""
        deck = Deck()
        # いくつかカードを配布
        for _ in range(10):
            deck.deal_card()

        assert deck.cards_remaining() == 42

        deck.reset()
        assert deck.cards_remaining() == 52

    def test_shuffle(self):
        """シャッフルのテスト（統計的テスト）"""
        deck1 = Deck()
        deck2 = Deck()

        # 同じシードを使わないようにシャッフル
        deck1.shuffle()
        deck2.shuffle()

        # 完全に同じ順序になる確率は非常に低い
        # ただし、稀に同じになる可能性もあるので、複数回試行
        different = False
        for _ in range(5):
            deck1.shuffle()
            deck2.shuffle()
            if deck1.cards != deck2.cards:
                different = True
                break

        assert different, "Shuffle should change card order"


class TestPlayerStatus:
    """PlayerStatusクラスのテスト"""

    def test_player_status_values(self):
        """プレイヤーステータスの値確認"""
        assert PlayerStatus.ACTIVE.value == "active"
        assert PlayerStatus.FOLDED.value == "folded"
        assert PlayerStatus.ALL_IN.value == "all_in"
        assert PlayerStatus.BUSTED.value == "busted"


class TestRandomPlayer:
    """RandomPlayerクラス（Playerの具象クラス）のテスト"""

    def test_player_initialization(self):
        """プレイヤー初期化のテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        assert player.id == 1
        assert player.name == "Test Player"
        assert player.chips == 1000
        assert player.hole_cards == []
        assert player.current_bet == 0
        assert player.total_bet_this_hand == 0
        assert player.status == PlayerStatus.ACTIVE
        assert not player.is_dealer
        assert not player.is_small_blind
        assert not player.is_big_blind

    def test_reset_for_new_hand(self):
        """新ハンド用リセットのテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        player.hole_cards = [Card(14, Suit.SPADES), Card(13, Suit.HEARTS)]
        player.current_bet = 100
        player.total_bet_this_hand = 200
        player.status = PlayerStatus.FOLDED
        player.is_dealer = True

        player.reset_for_new_hand()

        assert player.hole_cards == []
        assert player.current_bet == 0
        assert player.total_bet_this_hand == 0
        assert player.status == PlayerStatus.ACTIVE
        assert not player.is_dealer
        assert not player.is_small_blind
        assert not player.is_big_blind

    def test_reset_for_new_hand_busted(self):
        """チップ0でのリセットテスト"""
        player = RandomPlayer(1, "Test Player", 0)
        player.reset_for_new_hand()
        assert player.status == PlayerStatus.BUSTED

    def test_reset_for_new_betting_round(self):
        """新ベッティングラウンド用リセットのテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        player.current_bet = 100
        player.total_bet_this_hand = 200

        player.reset_for_new_betting_round()

        assert player.current_bet == 0
        assert player.total_bet_this_hand == 200  # これは保持される

    def test_add_hole_card(self):
        """ホールカード追加のテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        card1 = Card(14, Suit.SPADES)
        card2 = Card(13, Suit.HEARTS)

        player.add_hole_card(card1)
        assert len(player.hole_cards) == 1
        assert player.hole_cards[0] == card1

        player.add_hole_card(card2)
        assert len(player.hole_cards) == 2
        assert player.hole_cards[1] == card2

    def test_add_hole_card_too_many(self):
        """3枚目のホールカード追加エラー"""
        player = RandomPlayer(1, "Test Player", 1000)
        player.add_hole_card(Card(14, Suit.SPADES))
        player.add_hole_card(Card(13, Suit.HEARTS))

        with pytest.raises(ValueError, match="Player already has 2 hole cards"):
            player.add_hole_card(Card(12, Suit.CLUBS))

    def test_bet_normal(self):
        """通常のベットテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        actual_bet = player.bet(100)

        assert actual_bet == 100
        assert player.chips == 900
        assert player.current_bet == 100
        assert player.total_bet_this_hand == 100
        assert player.status == PlayerStatus.ACTIVE

    def test_bet_all_in(self):
        """オールインベットのテスト"""
        player = RandomPlayer(1, "Test Player", 50)
        actual_bet = player.bet(100)  # チップより多い額をベット

        assert actual_bet == 50
        assert player.chips == 0
        assert player.current_bet == 50
        assert player.total_bet_this_hand == 50
        assert player.status == PlayerStatus.ALL_IN

    def test_bet_zero_or_negative(self):
        """0以下のベットテスト"""
        player = RandomPlayer(1, "Test Player", 1000)

        assert player.bet(0) == 0
        assert player.bet(-10) == 0
        assert player.chips == 1000
        assert player.current_bet == 0

    def test_fold(self):
        """フォールドのテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        player.fold()
        assert player.status == PlayerStatus.FOLDED

    def test_can_bet(self):
        """ベット可能性チェックのテスト"""
        player = RandomPlayer(1, "Test Player", 100)

        assert player.can_bet(50) is True
        assert player.can_bet(100) is True
        assert player.can_bet(101) is False

        player.fold()
        assert player.can_bet(50) is False

    def test_to_dict(self):
        """辞書変換のテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        player.current_bet = 100
        player.status = PlayerStatus.ACTIVE

        result = player.to_dict()
        expected = {"id": 1, "chips": 1000, "bet": 100, "status": "active"}
        assert result == expected

    def test_str_representation(self):
        """文字列表現のテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        assert str(player) == "Test Player (ID: 1, Chips: 1000)"

    def test_make_decision_with_actions(self):
        """意思決定のテスト（利用可能なアクション）"""
        player = RandomPlayer(1, "Test Player", 1000)
        game_state = {
            "actions": ["fold", "check", "call (20)", "raise (min 40)", "all-in"]
        }

        # RandomPlayer は GameState を想定しているため、簡易モックを用意
        class _GS:
            def __init__(self, d):
                self.actions = d["actions"]

            def to_dict(self):
                return {"actions": self.actions}

        decision = player.make_decision(_GS(game_state))

        assert "action" in decision
        assert "amount" in decision
        assert decision["action"] in ["fold", "check", "call", "raise", "all_in"]

        if decision["action"] == "fold":
            assert decision["amount"] == 0
        elif decision["action"] == "check":
            assert decision["amount"] == 0
        elif decision["action"] == "call":
            assert decision["amount"] == 20
        elif decision["action"] == "all_in":
            assert decision["amount"] == player.chips

    def test_make_decision_no_actions(self):
        """利用可能なアクションがない場合のテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        game_state = {"actions": []}

        class _GS:
            def __init__(self, d):
                self.actions = d["actions"]

            def to_dict(self):
                return {"actions": self.actions}

        decision = player.make_decision(_GS(game_state))
        assert decision == {"action": "fold", "amount": 0}

    def test_action_weights(self):
        """アクション重みのテスト"""
        player = RandomPlayer(1, "Test Player", 1000)
        expected_weights = {"fold": 30, "check_call": 50, "raise": 15, "all_in": 5}
        assert player.action_weights == expected_weights


class TestHumanPlayer:
    """HumanPlayerクラスのテスト"""

    def test_initialization(self):
        """初期化のテスト"""
        player = HumanPlayer(1, "Human Player", 1000)
        assert player.id == 1
        assert player.name == "Human Player"
        assert player.chips == 1000

    def test_make_decision_not_implemented(self):
        """make_decisionでNotImplementedErrorが発生することを確認"""
        player = HumanPlayer(1, "Human Player", 1000)
        with pytest.raises(
            NotImplementedError, match="Human player decisions are handled by UI layer"
        ):
            player.make_decision({})


class TestLLMPlayer:
    """LLMPlayerクラスのテスト"""

    def test_initialization(self):
        """初期化のテスト"""
        player = LLMPlayer(1, "LLM Player", 1000)
        assert player.id == 1
        assert player.name == "LLM Player"
        assert player.chips == 1000
        # LLMPlayer は ADK エージェント利用に変更されたためクライアント属性は存在しない
        assert hasattr(player, "_agent")

    def test_initialization_with_client(self):
        """LLMクライアント付き初期化のテスト"""
        # 旧仕様の llm_client 引数は廃止。model 引数に文字列を渡せることを確認
        model_id = "gemini-2.5-flash-lite"
        player = LLMPlayer(1, "LLM Player", 1000, model_id)
        assert player.model == model_id

    def test_make_decision_without_client(self):
        """LLMクライアントなしでの意思決定（ランダム動作）"""
        player = LLMPlayer(1, "LLM Player", 1000)
        game_state = {"actions": ["fold", "check"]}

        class _GS:
            def __init__(self, d):
                self.actions = d.get("actions", [])

            def to_dict(self):
                return {"actions": self.actions}

        decision = player.make_decision(_GS(game_state))

        assert "action" in decision
        assert "amount" in decision
        assert decision["action"] in ["fold", "check"]

    def test_create_decision_prompt(self):
        """決定プロンプト作成のテスト"""
        player = LLMPlayer(1, "LLM Player", 1000)
        game_state = {"test": "data", "actions": ["fold", "check"]}

        class _GS:
            def __init__(self, d):
                self._d = d
                self.actions = d.get("actions", [])

            def to_dict(self):
                return self._d

        prompt = player._create_decision_prompt(_GS(game_state))

        assert "現在のポーカー状況を分析して" in prompt
        assert "test" in prompt
        # 新しいプロンプトはJSONダンプを含む
        assert "actions" in prompt

    def test_parse_llm_response(self):
        """LLM応答パースのテスト（プレースホルダー）"""
        player = LLMPlayer(1, "LLM Player", 1000)
        response = "ACTION: fold\nAMOUNT: 0\nREASON: Bad hand"
        game_state = {}

        result = player._parse_llm_response(response, game_state)

        # 現在はプレースホルダーなのでfoldを返す
        assert result == {"action": "fold", "amount": 0}
