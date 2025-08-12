#!/usr/bin/env python3
"""
ターンフェーズでのアクション順番の問題を調査するテストツール
"""

import logging
import sys
from poker.game import PokerGame, GamePhase
from poker.player_models import HumanPlayer, RandomPlayer, PlayerStatus

# ログレベルを設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("turn_phase_bug_debug.log", mode="w"),
    ],
)


def test_turn_phase_actions():
    """
    ターンフェーズでのプレイヤーアクションを詳しくテスト
    """
    print("=== ターンフェーズでのアクション順番調査 ===")

    game = PokerGame(small_blind=10, big_blind=20, initial_chips=1000)

    # 人間プレイヤー1人とCPU3人
    game.add_player(HumanPlayer(0, "Human", 1000))
    game.add_player(RandomPlayer(1, "CPU1", 1000))
    game.add_player(RandomPlayer(2, "CPU2", 1000))
    game.add_player(RandomPlayer(3, "CPU3", 1000))

    print(f"プレイヤー構成:")
    for i, player in enumerate(game.players):
        print(f"  Player {i}: {player.name} ({player.__class__.__name__})")

    # 新しいハンドを開始
    print("\n=== ハンド開始 ===")
    game.start_new_hand()
    print(f"ディーラーボタン: {game.dealer_button}")

    # プリフロップを完了
    print("\n=== プリフロップ完了 ===")
    complete_betting_round(game, "PREFLOP")

    # フロップに進む
    print("\n=== フロップに進む ===")
    game.advance_to_next_phase()
    print(f"フェーズ: {game.current_phase.value}")
    print(f"コミュニティカード: {[str(card) for card in game.community_cards]}")

    # フロップを完了
    print("\n=== フロップ完了 ===")
    complete_betting_round(game, "FLOP")

    # ターンに進む
    print("\n=== ターンに進む ===")
    game.advance_to_next_phase()
    print(f"フェーズ: {game.current_phase.value}")
    print(f"コミュニティカード: {[str(card) for card in game.community_cards]}")

    # ターンでの詳細な動作確認
    print("\n=== ターンフェーズでの詳細確認 ===")
    print(f"現在のプレイヤー: {game.current_player_index}")
    print(f"ベッティング完了: {game.betting_round_complete}")
    print(f"現在のベット: {game.current_bet}")
    print(f"最後のレイザー: {game.last_raiser_index}")

    active_players = [
        i for i, p in enumerate(game.players) if p.status == PlayerStatus.ACTIVE
    ]
    print(f"アクティブプレイヤー: {active_players}")

    # ターンでのアクションを段階的に実行
    print("\n=== ターンでのアクション実行 ===")
    action_count = 0
    expected_actions = len(
        active_players
    )  # 最低でもアクティブプレイヤー数だけアクションがあるべき

    while (
        not game.betting_round_complete and action_count < expected_actions * 2
    ):  # 安全のため倍数で制限
        action_count += 1
        current_player = game.players[game.current_player_index]

        print(f"\n--- ターンアクション {action_count} ---")
        print(f"現在のプレイヤー: {current_player.name} (ID: {current_player.id})")
        print(f"プレイヤータイプ: {current_player.__class__.__name__}")
        print(f"プレイヤーステータス: {current_player.status}")
        print(f"現在のベット: {game.current_bet}")
        print(f"プレイヤーのベット: {current_player.current_bet}")

        if current_player.status != PlayerStatus.ACTIVE:
            print(f"プレイヤー {current_player.name} はアクティブではありません")
            game._advance_to_next_player()
            continue

        if isinstance(current_player, HumanPlayer):
            print(f">>> 人間プレイヤー {current_player.name} のターン")
            # シミュレーション: 人間プレイヤーがチェック
            success = game.process_player_action(current_player.id, "check", 0)
            print(f"Human player checks - 成功: {success}")
        else:
            print(f">>> CPUプレイヤー {current_player.name} のターン")
            # CPUプレイヤー
            success = game.process_player_action(current_player.id, "check", 0)
            print(f"CPU {current_player.name} checks - 成功: {success}")

        print(f"アクション後:")
        print(f"  フェーズ: {game.current_phase.value}")
        print(f"  ベッティング完了: {game.betting_round_complete}")
        print(f"  次のプレイヤー: {game.current_player_index}")

        if game.betting_round_complete:
            print("⚠️  ベッティングラウンドが完了しました")
            break

    print(f"\n=== ターンアクション完了 ===")
    print(f"総アクション数: {action_count}")
    print(f"期待されるアクション数: {expected_actions} (最低)")

    if action_count < expected_actions:
        print(
            f"❌ 問題発見: アクション数が不足しています ({action_count} < {expected_actions})"
        )
        print("   すべてのプレイヤーがアクションする前にベッティングが完了しています")
    else:
        print(f"✅ 正常: 十分なアクション数が実行されました")


def complete_betting_round(game, phase_name):
    """ベッティングラウンドを完了させる補助関数"""
    print(f"{phase_name}でのアクション:")
    action_count = 0

    while not game.betting_round_complete and action_count < 10:  # 無限ループ防止
        action_count += 1
        current_player = game.players[game.current_player_index]

        if current_player.status != PlayerStatus.ACTIVE:
            game._advance_to_next_player()
            continue

        if isinstance(current_player, HumanPlayer):
            if game.current_bet > current_player.current_bet:
                success = game.process_player_action(current_player.id, "call", 0)
                print(f"  Human calls - 成功: {success}")
            else:
                success = game.process_player_action(current_player.id, "check", 0)
                print(f"  Human checks - 成功: {success}")
        else:
            if game.current_bet > current_player.current_bet:
                success = game.process_player_action(current_player.id, "call", 0)
                print(f"  CPU {current_player.name} calls - 成功: {success}")
            else:
                success = game.process_player_action(current_player.id, "check", 0)
                print(f"  CPU {current_player.name} checks - 成功: {success}")

    print(f"{phase_name}完了 - アクション数: {action_count}")


if __name__ == "__main__":
    test_turn_phase_actions()
