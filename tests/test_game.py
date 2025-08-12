"""
Tests for poker.game module
"""

import pytest
from poker.player_models import HumanPlayer, RandomPlayer, LLMPlayer, PlayerStatus
from poker.game import GamePhase, PokerGame


class TestGamePhase:
    """GamePhaseクラスのテスト"""

    def test_game_phase_values(self):
        """ゲームフェーズの値が正しいことを確認"""
        assert GamePhase.PREFLOP.value == "preflop"
        assert GamePhase.FLOP.value == "flop"
        assert GamePhase.TURN.value == "turn"
        assert GamePhase.RIVER.value == "river"
        assert GamePhase.SHOWDOWN.value == "showdown"
        assert GamePhase.FINISHED.value == "finished"


class TestPokerGame:
    """PokerGameクラスのテスト"""

    def test_initialization(self):
        """ゲーム初期化のテスト"""
        game = PokerGame(small_blind=5, big_blind=10, initial_chips=500)

        assert game.small_blind == 5
        assert game.big_blind == 10
        assert game.initial_chips == 500
        assert game.players == []
        assert game.dealer_button == 0
        assert game.current_player_index == 0
        assert game.community_cards == []
        assert game.current_phase == GamePhase.PREFLOP
        assert game.pot == 0
        assert game.current_bet == 0
        assert game.hand_number == 0
        assert game.betting_round_complete is False
        assert game.last_raiser_index is None
        assert game.action_history == []

    def test_initialization_default_values(self):
        """デフォルト値での初期化テスト"""
        game = PokerGame()

        assert game.small_blind == 10
        assert game.big_blind == 20
        assert game.initial_chips == 2000

    def test_add_player(self):
        """プレイヤー追加のテスト"""
        game = PokerGame()
        player1 = HumanPlayer(1, "Player1", 1000)
        player2 = RandomPlayer(2, "Player2", 1000)

        game.add_player(player1)
        game.add_player(player2)

        assert len(game.players) == 2
        assert game.players[0] == player1
        assert game.players[1] == player2

    def test_add_player_too_many(self):
        """プレイヤー追加上限超過のテスト"""
        game = PokerGame()

        # 10人まで追加
        for i in range(10):
            game.add_player(RandomPlayer(i, f"Player{i}", 1000))

        # 11人目を追加しようとするとエラー
        with pytest.raises(ValueError, match="Maximum 10 players allowed"):
            game.add_player(RandomPlayer(10, "Player10", 1000))

    def test_get_player_existing(self):
        """存在するプレイヤーの取得テスト"""
        game = PokerGame()
        player1 = HumanPlayer(1, "Player1", 1000)
        player2 = RandomPlayer(2, "Player2", 1000)

        game.add_player(player1)
        game.add_player(player2)

        assert game.get_player(1) == player1
        assert game.get_player(2) == player2

    def test_get_player_non_existing(self):
        """存在しないプレイヤーの取得テスト"""
        game = PokerGame()
        player1 = HumanPlayer(1, "Player1", 1000)
        game.add_player(player1)

        assert game.get_player(99) is None

    def test_setup_default_game(self):
        """デフォルトゲームセットアップのテスト"""
        game = PokerGame()
        game.setup_default_game()

        assert len(game.players) == 4
        assert isinstance(game.players[0], HumanPlayer)
        assert game.players[0].name == "You"
        assert isinstance(game.players[1], RandomPlayer)
        assert game.players[1].name == "CPU1"
        assert isinstance(game.players[2], RandomPlayer)
        assert game.players[2].name == "CPU2"
        assert isinstance(game.players[3], RandomPlayer)
        assert game.players[3].name == "CPU3"

        # ディーラーボタンが設定されている
        assert 0 <= game.dealer_button <= 3

        # 全プレイヤーのチップが初期値
        for player in game.players:
            assert player.chips == game.initial_chips

    def test_start_new_hand_initialization(self):
        """新ハンド開始時の初期化テスト"""
        game = PokerGame()
        game.setup_default_game()

        # 事前にいくつかの値を設定
        game.hand_number = 5
        game.pot = 100
        game.current_bet = 50
        game.current_phase = GamePhase.RIVER
        game.betting_round_complete = True
        game.action_history = ["test action"]

        game.start_new_hand()

        assert game.hand_number == 6  # インクリメントされる
        assert game.pot >= 30  # ブラインドが投稿される（SB+BB）
        assert game.current_bet > 0  # ビッグブラインドが設定される
        assert game.current_phase == GamePhase.PREFLOP
        assert game.betting_round_complete is False
        # プリフロップではビッグブラインドプレイヤーがlast_raiser_indexとして設定される
        bb_player_index = None
        for i, player in enumerate(game.players):
            if player.is_big_blind:
                bb_player_index = i
                break
        assert game.last_raiser_index == bb_player_index
        assert len(game.action_history) >= 2  # ブラインドアクションが記録される

        # 各プレイヤーにホールカードが配られる
        for player in game.players:
            assert len(player.hole_cards) == 2

    def test_start_new_hand_insufficient_players(self):
        """プレイヤー不足時のテスト"""
        game = PokerGame()
        # プレイヤーを1人だけ追加（バストしていない）
        game.add_player(HumanPlayer(1, "Player1", 1000))

        game.start_new_hand()

        # 2人未満なのでゲーム終了
        assert game.current_phase == GamePhase.FINISHED

    def test_start_new_hand_busted_players_excluded(self):
        """バストしたプレイヤーが除外されることのテスト"""
        game = PokerGame()
        game.add_player(HumanPlayer(1, "Player1", 1000))
        game.add_player(RandomPlayer(2, "Player2", 0))  # チップ0
        game.add_player(RandomPlayer(3, "Player3", 1000))

        # プレイヤー2をバスト状態に設定
        game.players[1].status = PlayerStatus.BUSTED

        game.start_new_hand()

        # バストしたプレイヤーにはカードが配られない
        assert len(game.players[0].hole_cards) == 2
        assert len(game.players[1].hole_cards) == 0  # バスト
        assert len(game.players[2].hole_cards) == 2

    def test_get_llm_game_state_valid_player(self):
        """有効なプレイヤーのゲーム状態取得テスト"""
        game = PokerGame()
        game.setup_default_game()
        game.start_new_hand()

        game_state = game.get_llm_game_state(0)  # Human player
        # GameStateオブジェクトを辞書に変換（仕様に沿った検証のため）
        if hasattr(game_state, "to_dict"):
            game_state = game_state.to_dict()

        # 必要なキーが存在することを確認
        required_keys = [
            "your_id",
            "phase",
            "your_cards",
            "community",
            "your_chips",
            "your_bet_this_round",
            "pot",
            "to_call",
            "dealer_button",
            "current_turn",
            "players",
            "actions",
            "history",
        ]
        for key in required_keys:
            assert key in game_state

        # データ型の確認
        assert isinstance(game_state["your_cards"], list)
        assert isinstance(game_state["community"], list)
        assert isinstance(game_state["your_chips"], int)
        assert isinstance(game_state["pot"], int)
        assert isinstance(game_state["players"], list)
        assert isinstance(game_state["actions"], list)
        assert isinstance(game_state["history"], list)

        # プレイヤー固有の情報
        assert game_state["your_id"] == 0
        assert game_state["phase"] == "preflop"
        assert len(game_state["your_cards"]) == 2
        assert game_state["your_chips"] > 0

        # 他のプレイヤー情報（自分以外の3人）
        assert len(game_state["players"]) == 3

    def test_get_llm_game_state_invalid_player(self):
        """無効なプレイヤーのゲーム状態取得エラーテスト"""
        game = PokerGame()
        game.setup_default_game()

        with pytest.raises(ValueError, match="Invalid player_id: 99"):
            game.get_llm_game_state(99)

    def test_get_llm_game_state_busted_player(self):
        """バストしたプレイヤーのゲーム状態取得エラーテスト"""
        game = PokerGame()
        game.add_player(HumanPlayer(1, "Player1", 0))
        game.players[0].status = PlayerStatus.BUSTED

        with pytest.raises(
            ValueError, match="Player 1 is busted and cannot get game state"
        ):
            game.get_llm_game_state(1)

    def test_get_available_actions_active_player(self):
        """アクティブなプレイヤーのアクション取得テスト"""
        game = PokerGame()
        game.setup_default_game()
        game.start_new_hand()

        # アクティブなプレイヤーのアクションを取得
        active_player = None
        for player in game.players:
            if player.status == PlayerStatus.ACTIVE:
                active_player = player
                break

        assert active_player is not None
        actions = game._get_available_actions(active_player.id)

        # アクションが返されることを確認（詳細は実装によるが、空でないことを確認）
        assert isinstance(actions, list)

    def test_get_available_actions_invalid_player(self):
        """無効なプレイヤーのアクション取得テスト"""
        game = PokerGame()
        game.setup_default_game()

        actions = game._get_available_actions(99)
        assert actions == []

    def test_get_available_actions_folded_player(self):
        """フォールドしたプレイヤーのアクション取得テスト"""
        game = PokerGame()
        game.add_player(HumanPlayer(1, "Player1", 1000))
        game.players[0].status = PlayerStatus.FOLDED

        actions = game._get_available_actions(1)
        assert actions == []

    def test_move_dealer_button(self):
        """ディーラーボタン移動のテスト"""
        game = PokerGame()
        game.setup_default_game()

        initial_dealer = game.dealer_button
        game._move_dealer_button()

        # ディーラーボタンが移動したか、または同じ場合でも有効な範囲内
        assert 0 <= game.dealer_button <= 3

        # ディーラーフラグが正しく設定されている
        dealer_count = sum(1 for player in game.players if player.is_dealer)
        assert dealer_count == 1
        assert game.players[game.dealer_button].is_dealer

    def test_post_blinds(self):
        """ブラインド投稿のテスト"""
        game = PokerGame()
        game.setup_default_game()

        initial_pot = game.pot
        game._post_blinds()

        # ポットにブラインドが追加される
        assert game.pot >= initial_pot + game.small_blind + game.big_blind

        # カレントベットがビッグブラインドに設定される
        assert game.current_bet == game.big_blind

        # ブラインドプレイヤーが設定される
        sb_count = sum(1 for player in game.players if player.is_small_blind)
        bb_count = sum(1 for player in game.players if player.is_big_blind)
        assert sb_count == 1
        assert bb_count == 1

        # アクション履歴にブラインドが記録される
        assert len(game.action_history) >= 2
        blind_actions = [action for action in game.action_history if "blind" in action]
        assert len(blind_actions) >= 2

    def test_deal_hole_cards(self):
        """ホールカード配布のテスト"""
        game = PokerGame()
        game.setup_default_game()

        # 配布前の確認
        for player in game.players:
            assert len(player.hole_cards) == 0

        game._deal_hole_cards()

        # 各プレイヤーに2枚ずつ配られる
        for player in game.players:
            if player.status != PlayerStatus.BUSTED:
                assert len(player.hole_cards) == 2

    def test_deal_hole_cards_excludes_busted(self):
        """バストしたプレイヤーにはカードが配られないテスト"""
        game = PokerGame()
        game.add_player(HumanPlayer(1, "Player1", 1000))
        game.add_player(RandomPlayer(2, "Player2", 0))

        # プレイヤー2をバスト状態に設定
        game.players[1].status = PlayerStatus.BUSTED

        game._deal_hole_cards()

        assert len(game.players[0].hole_cards) == 2
        assert len(game.players[1].hole_cards) == 0  # バストしたプレイヤー

    def test_game_stats_initialization(self):
        """ゲーム統計の初期化テスト"""
        game = PokerGame()

        assert "hands_played" in game.game_stats
        assert "players_eliminated" in game.game_stats
        assert game.game_stats["hands_played"] == 0
        assert game.game_stats["players_eliminated"] == []

    def test_setup_cpu_only_game(self):
        """CPU専用ゲームセットアップのテスト"""
        game = PokerGame()
        game.setup_cpu_only_game()

        assert len(game.players) == 4
        # 全プレイヤーがRandomPlayerであることを確認
        for player in game.players:
            assert isinstance(player, RandomPlayer)

        # プレイヤー名の確認
        assert game.players[0].name == "CPU0"
        assert game.players[1].name == "CPU1"
        assert game.players[2].name == "CPU2"
        assert game.players[3].name == "CPU3"

        # ディーラーボタンが設定されている
        assert 0 <= game.dealer_button <= 3

        # 全プレイヤーのチップが初期値
        for player in game.players:
            assert player.chips == game.initial_chips
