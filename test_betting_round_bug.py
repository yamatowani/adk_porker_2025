#!/usr/bin/env python3
"""
テキサスホールデムのベッティングルール確認テスト
"""

from poker.game import PokerGame, GamePhase
from poker.player_models import RandomPlayer, PlayerStatus


def test_preflop_betting_round():
    """プリフロップでベッティングラウンドが適切に管理されるかテスト"""
    print("=== テスト1: プリフロップでのコール ===")
    game = PokerGame(small_blind=10, big_blind=20, initial_chips=1000)

    # 4人のRandomPlayerを追加
    for i in range(4):
        game.add_player(RandomPlayer(i, f"Player{i}", 1000))

    # ゲーム開始
    game.start_new_hand()

    print(f"Phase: {game.current_phase}")
    print(f"Current bet: {game.current_bet}")
    print(f"Pot: {game.pot}")
    print(f"Current player: {game.current_player_index}")
    print(f"Last raiser index: {game.last_raiser_index}")
    print(f"Betting round complete: {game.betting_round_complete}")

    # プレイヤーの状態確認
    for i, player in enumerate(game.players):
        print(
            f"Player {i}: chips={player.chips}, current_bet={player.current_bet}, "
            f"status={player.status}, is_big_blind={player.is_big_blind}"
        )

    print("\n--- 各プレイヤーがコールする ---")

    # 最初の2人がコール（UTGとその次）
    for _ in range(2):
        current_player = game.players[game.current_player_index]
        print(
            f"\nPlayer {game.current_player_index} (chips: {current_player.chips}) calls"
        )

        # コールアクション
        success = game.process_player_action(game.current_player_index, "call", 0)
        print(f"Action success: {success}")
        print(f"Betting round complete: {game.betting_round_complete}")

        if game.betting_round_complete:
            print("❌ ERROR: Betting round completed too early!")
            return False

    # スモールブラインドプレイヤーがコール
    current_player = game.players[game.current_player_index]
    print(
        f"\nPlayer {game.current_player_index} (Small Blind, chips: {current_player.chips}) calls"
    )

    success = game.process_player_action(game.current_player_index, "call", 0)
    print(f"Action success: {success}")
    print(f"Betting round complete: {game.betting_round_complete}")

    if game.betting_round_complete:
        print("❌ ERROR: Betting round completed before Big Blind had a chance to act!")
        return False

    # ビッグブラインドプレイヤーの番になっているか確認
    bb_player = None
    for player in game.players:
        if player.is_big_blind:
            bb_player = player
            break

    if bb_player and game.current_player_index == bb_player.id:
        print(f"✅ Correct: Big Blind player {bb_player.id} has a chance to act")

        # ビッグブラインドがチェック
        print(f"\nPlayer {game.current_player_index} (Big Blind) checks")
        success = game.process_player_action(game.current_player_index, "check", 0)
        print(f"Action success: {success}")
        print(f"Betting round complete: {game.betting_round_complete}")

        if not game.betting_round_complete:
            print("❌ ERROR: Betting round should be complete after Big Blind checks!")
            return False

        print("✅ Correct: Betting round completed after Big Blind acted")
        return True
    else:
        print(
            f"❌ ERROR: Current player {game.current_player_index} is not the Big Blind"
        )
        return False


def test_preflop_with_raise():
    """プリフロップでレイズがある場合のテスト"""
    print("\n=== テスト2: プリフロップでのレイズ ===")
    game = PokerGame(small_blind=10, big_blind=20, initial_chips=1000)

    # 4人のRandomPlayerを追加
    for i in range(4):
        game.add_player(RandomPlayer(i, f"Player{i}", 1000))

    # ゲーム開始
    game.start_new_hand()

    print(
        f"Initial state - Current player: {game.current_player_index}, Last raiser: {game.last_raiser_index}"
    )

    # UTGがレイズ
    print(f"\nPlayer {game.current_player_index} raises to 40")
    success = game.process_player_action(game.current_player_index, "raise", 20)
    print(f"Action success: {success}")
    print(f"New current bet: {game.current_bet}, Last raiser: {game.last_raiser_index}")
    print(f"Betting round complete: {game.betting_round_complete}")

    # 次の2人がフォールド
    for _ in range(2):
        current_player = game.players[game.current_player_index]
        print(f"\nPlayer {game.current_player_index} folds")
        success = game.process_player_action(game.current_player_index, "fold", 0)
        print(f"Action success: {success}")
        print(f"Betting round complete: {game.betting_round_complete}")

    # スモールブラインドがコール
    print(f"\nPlayer {game.current_player_index} (Small Blind) calls")
    success = game.process_player_action(game.current_player_index, "call", 0)
    print(f"Action success: {success}")
    print(f"Betting round complete: {game.betting_round_complete}")

    # ビッグブラインドがコール
    print(f"\nPlayer {game.current_player_index} (Big Blind) calls")
    success = game.process_player_action(game.current_player_index, "call", 0)
    print(f"Action success: {success}")
    print(f"Betting round complete: {game.betting_round_complete}")

    if not game.betting_round_complete:
        print("❌ ERROR: Betting round should be complete after all players acted!")
        return False

    print("✅ Correct: Betting round completed correctly with raise")
    return True


def test_postflop_betting():
    """フロップ以降のベッティングテスト"""
    print("\n=== テスト3: フロップでのベッティング ===")
    game = PokerGame(small_blind=10, big_blind=20, initial_chips=1000)

    # 4人のRandomPlayerを追加
    for i in range(4):
        game.add_player(RandomPlayer(i, f"Player{i}", 1000))

    # ゲーム開始（プリフロップを完了）
    game.start_new_hand()

    # プリフロップを簡単に終了（全員コール）
    while not game.betting_round_complete:
        current_player = game.players[game.current_player_index]
        if (
            current_player.is_big_blind
            and game.current_bet == current_player.current_bet
        ):
            # ビッグブラインドがチェック
            game.process_player_action(game.current_player_index, "check", 0)
        else:
            # 他はコール
            game.process_player_action(game.current_player_index, "call", 0)

    # フロップに進む
    game.advance_to_next_phase()
    print(f"Phase: {game.current_phase}")
    print(f"Current player: {game.current_player_index}")
    print(f"Current bet: {game.current_bet}")
    print(f"Last raiser: {game.last_raiser_index}")

    # 最初のプレイヤーがベット
    print(f"\nPlayer {game.current_player_index} bets 30")
    success = game.process_player_action(game.current_player_index, "raise", 30)
    print(f"Action success: {success}")
    print(f"Last raiser: {game.last_raiser_index}")
    print(f"Betting round complete: {game.betting_round_complete}")

    # 他のプレイヤーがフォールド
    while not game.betting_round_complete:
        current_player = game.players[game.current_player_index]
        print(f"\nPlayer {game.current_player_index} folds")
        success = game.process_player_action(game.current_player_index, "fold", 0)
        print(f"Action success: {success}")
        print(f"Betting round complete: {game.betting_round_complete}")

    print("✅ Correct: Post-flop betting completed correctly")
    return True


def run_all_tests():
    """全テストを実行"""
    tests = [test_preflop_betting_round, test_preflop_with_raise, test_postflop_betting]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test {test.__name__} failed!")
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")

    print(f"\n=== テスト結果 ===")
    print(f"合格: {passed}/{total}")

    if passed == total:
        print("✅ 全テスト合格！ベッティングラウンドは正しく動作しています。")
        return True
    else:
        print("❌ 一部のテストが失敗しました。")
        return False


if __name__ == "__main__":
    run_all_tests()
