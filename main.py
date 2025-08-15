"""
Texas Hold'em Poker Game - Main Entry Point
"""

import sys
import argparse
import asyncio
import logging
import os
from datetime import datetime
from poker.cli_ui import PokerUI
from poker.flet_ui import run_flet_poker_app


def setup_logging():
    """ログ設定をセットアップ（常にデバッグモード）"""
    # ログディレクトリの作成
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # タイムスタンプ付きのログファイル名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"poker_game_{timestamp}.log")

    # poker_gameロガーの設定
    poker_logger = logging.getLogger("poker_game")
    poker_logger.setLevel(logging.DEBUG)

    # 既存のハンドラーをクリア（重複を避けるため）
    poker_logger.handlers.clear()

    # ファイルハンドラーを追加（常に）
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # フォーマッターを設定
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # コンソールハンドラーを追加（常に）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # ハンドラーをロガーに追加
    poker_logger.addHandler(file_handler)
    poker_logger.addHandler(console_handler)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="テキサスホールデム ポーカーゲーム")
    parser.add_argument(
        "--cli", action="store_true", help="CLI（コマンドライン）モードで実行"
    )
    parser.add_argument(
        "--llm-mode", action="store_true", help="LLMプレイヤーモード（現在は未実装）"
    )
    parser.add_argument(
        "--with-viewer",
        action="store_true",
        help="観戦ビューアを別ポートで同時起動（デフォルト: 8552）",
    )
    parser.add_argument(
        "--viewer-port",
        type=int,
        default=8552,
        help="観戦ビューアのポート（デフォルト: 8552）",
    )
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="CPU専用モード（全プレイヤーがCPU、自動進行）",
    )
    parser.add_argument(
        "--agent-only",
        action="store_true",
        help="エージェント専用モード（LLMエージェントのみで完全自動進行）",
    )
    parser.add_argument(
        "--agents",
        type=str,
        default="team1_agent:2,team2_agent:2",
        help="使用するエージェントと人数を指定（例: team1_agent:2,team2_agent:1,beginner_agent:1）",
    )
    parser.add_argument(
        "--max-hands",
        type=int,
        default=10,
        help="CPU専用・エージェント専用モードでの最大ハンド数（CPU専用:10、エージェント専用:20）",
    )
    parser.add_argument(
        "--display-interval",
        type=int,
        default=1,
        help="CPU専用モードでの詳細表示間隔（デフォルト: 1）",
    )
    args = parser.parse_args()

    # ログ設定をセットアップ（常にデバッグモード）
    setup_logging()

    try:
        if args.cli:
            # CLI モード
            ui = PokerUI()

            if args.cpu_only:
                # CPU専用モードを実行
                print("CPU専用モードで実行します...")
                ui.run_cpu_only_game(
                    max_hands=args.max_hands, display_interval=args.display_interval
                )
            elif args.agent_only:
                # エージェント専用モードを実行
                print("エージェント専用モードで実行します...")
                max_hands = (
                    args.max_hands if args.max_hands != 10 else 20
                )  # エージェント専用モードのデフォルトは20
                ui.run_agent_only_mode(max_hands=max_hands, agents_config=args.agents)
            else:
                # 通常のゲームを実行
                ui.run_game()
        else:
            # Webアプリモードでエージェント専用オプションが指定された場合の警告
            if args.agent_only:
                print(
                    "警告: エージェント専用モードは現在CLI専用です。--cli オプションを追加してください。"
                )
                print("例: uv run python main.py --cli --agent-only")
                sys.exit(1)

            run_flet_poker_app(
                with_viewer=args.with_viewer, viewer_port=args.viewer_port
            )

    except KeyboardInterrupt:
        print("\n\nゲームを終了します。")
        sys.exit(0)
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        print("詳細なエラー情報:")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
