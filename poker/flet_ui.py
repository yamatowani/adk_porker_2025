"""
Flet GUI User Interface for Poker Game - Main UI管理
"""

import json
from typing import Dict, Any, List
import flet as ft
from .game import PokerGame, GamePhase
from .player_models import Player, HumanPlayer, PlayerStatus
from .setup_ui import SetupUI
from .game_ui import GameUI
from .shared_state import set_current_game
from .state_server import ensure_state_server
from .game_ui import UI_UPDATE_LOCK


class PokerFletUI:
    """ポーカーゲームのFlet GUI統合管理"""

    def __init__(self):
        self.game = None
        self.page = None
        self.current_player_id = 0
        self.game_started = False  # ゲーム開始フラグ
        self.player_configs = []  # プレイヤー設定（タイプとモデル情報）

        # UI管理クラス
        self.setup_ui = SetupUI(self.on_game_start)
        self.game_ui = GameUI(self.on_back_to_setup)

    def main(self, page: ft.Page):
        """Fletアプリケーションのメイン関数"""
        self.page = page
        page.title = "ADK Poker - Texas Hold'em"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 10
        page.window.width = 1400
        page.window.height = 900

        # UI管理クラスを初期化
        self.setup_ui.initialize(page)
        self.game_ui.initialize(page)

        # GameUIのレイズダイアログをoverlayに追加
        self.page.overlay.append(self.game_ui.get_raise_dialog())

        # レイアウトを構築（設定画面から開始）
        self.build_layout()

    def on_game_start(self, player_configs: List[Dict[str, Any]]):
        """ゲーム開始時のコールバック"""
        self.player_configs = player_configs
        self.game_started = True
        self.build_layout()
        self.start_game()

    def on_back_to_setup(self):
        """設定画面に戻るコールバック"""
        self.game_started = False
        self.build_layout()

    def build_layout(self):
        """レイアウトを構築"""
        with UI_UPDATE_LOCK:
            self.page.controls.clear()

            if not self.game_started:
                # 設定画面を表示
                self.page.add(self.setup_ui.get_container())
            else:
                # ゲーム画面を表示
                self.page.add(self.game_ui.build_layout())

            self.page.update()

    def start_game(self):
        """ゲームを開始"""
        # ゲームセットアップ
        self.game = PokerGame()
        self.game.setup_configurable_game_with_models(self.player_configs)

        # 人間プレイヤーのIDを取得
        for player in self.game.players:
            if isinstance(player, HumanPlayer):
                self.current_player_id = player.id
                break

        # ゲームUIにゲーム情報を設定
        self.game_ui.set_game(self.game, self.current_player_id)

        # 共有状態に登録（Viewer用）
        try:
            set_current_game(self.game)
        except Exception:
            pass

        # JSON状態サーバーを起動（viewerがHTTPで取得）
        try:
            import threading

            server = ensure_state_server()
            threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception:
            pass

        # ゲームループを開始
        import threading

        threading.Thread(target=self.game_loop, daemon=True).start()

    def start_new_game(self):
        """新しいゲームを開始"""
        # ゲームセットアップ
        self.game = PokerGame()
        self.game.setup_configurable_game_with_models(self.player_configs)

        # 人間プレイヤーのIDを取得
        for player in self.game.players:
            if isinstance(player, HumanPlayer):
                self.current_player_id = player.id
                break

        # ゲームUIにゲーム情報を設定
        self.game_ui.set_game(self.game, self.current_player_id)

        # 共有状態に登録（Viewer用）
        try:
            set_current_game(self.game)
        except Exception:
            pass

        # JSON状態サーバーを起動（viewerがHTTPで取得）
        try:
            import threading

            server = ensure_state_server()
            threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception:
            pass

        # UIを初期状態に更新
        self.game_ui.update_display()

        # ゲームループを開始
        import threading

        threading.Thread(target=self.game_loop, daemon=True).start()

    def game_loop(self):
        """メインゲームループ"""
        while not self.game.is_game_over():
            # 新しいハンドを開始
            self.game.start_new_hand()

            if self.game.current_phase == GamePhase.FINISHED:
                break

            self.game_ui.update_display()

            # ハンドのメインループ
            while self.game.current_phase not in [
                GamePhase.SHOWDOWN,
                GamePhase.FINISHED,
            ]:
                # 各プレイヤーのアクション
                action_counter = 0  # 無限ループ防止
                while not self.game.betting_round_complete:
                    action_counter += 1
                    if action_counter > 100:  # 100回のアクション制限
                        self.game_ui.add_debug_message(
                            "Too many actions in betting round, breaking..."
                        )
                        break

                    current_player = self.game.players[self.game.current_player_index]
                    self.game_ui.add_debug_message(
                        f"Current player: {current_player.name} (ID: {current_player.id}), Status: {current_player.status}"
                    )

                    if current_player.status != PlayerStatus.ACTIVE:
                        self.game_ui.add_debug_message(
                            f"Player {current_player.name} is not active, advancing..."
                        )
                        self.game._advance_to_next_player()
                        continue

                    self.game_ui.update_display()
                    self.game_ui.update_action_buttons()

                    if isinstance(current_player, HumanPlayer):
                        # 人間プレイヤーのアクションを待つ
                        import time

                        timeout_counter = 0
                        while (
                            self.game.current_player_index == current_player.id
                            and not self.game.betting_round_complete
                        ):
                            time.sleep(0.1)
                            timeout_counter += 1
                            # 10秒でタイムアウト（デバッグ用）
                            if timeout_counter > 100:
                                self.game_ui.add_debug_message(
                                    f"Human player timeout, current_player_index: {self.game.current_player_index}"
                                )
                                break
                    else:
                        # AIプレイヤーのアクション
                        try:
                            self.game_ui.add_debug_message(
                                f"AI Player {current_player.name} is making decision..."
                            )

                            # 現在のプレイヤーインデックスを記録
                            old_player_index = self.game.current_player_index

                            game_state = self.game.get_llm_game_state(current_player.id)
                            decision = current_player.make_decision(game_state)

                            self.game_ui.add_debug_message(
                                f"Decision: {decision['action']} ({decision.get('amount', 0)})"
                            )

                            success = self.game.process_player_action(
                                current_player.id,
                                decision["action"],
                                decision.get("amount", 0),
                            )

                            self.game_ui.add_debug_message(
                                f"Action success: {success}, Index: {old_player_index} -> {self.game.current_player_index}"
                            )

                            if not success:
                                self.game_ui.add_debug_message(
                                    "Action failed, forcing fold..."
                                )
                                self.game.process_player_action(
                                    current_player.id, "fold", 0
                                )

                            # プレイヤーインデックスが変わらない場合は強制的に次のプレイヤーに進む
                            if (
                                self.game.current_player_index == old_player_index
                                and not self.game.betting_round_complete
                            ):
                                self.game_ui.add_debug_message(
                                    "Player index didn't change, advancing manually..."
                                )
                                self.game._advance_to_next_player()

                        except Exception as e:
                            self.game_ui.add_debug_message(
                                f"Exception in AI player: {str(e)}"
                            )
                            # エラーが発生した場合はフォールドして次のプレイヤーに進む
                            try:
                                self.game.process_player_action(
                                    current_player.id, "fold", 0
                                )
                            except:
                                # フォールドも失敗した場合は強制的に次のプレイヤーに進む
                                self.game._advance_to_next_player()

                        # AIのアクションを少し待つ
                        import time

                        time.sleep(1)

                # ベッティングラウンド完了後の処理
                self.game_ui.add_debug_message(
                    f"Betting round complete in phase: {self.game.current_phase.value}"
                )

                # 人間プレイヤーがいるかチェック
                has_human_player = any(
                    isinstance(p, HumanPlayer)
                    for p in self.game.players
                    if p.status == PlayerStatus.ACTIVE
                )

                if has_human_player:
                    # 人間プレイヤーがいる場合は、次のフェーズに進む確認を待つ
                    self.game_ui.add_debug_message(
                        "Waiting for player confirmation to advance to next phase..."
                    )
                    self.game_ui.show_phase_transition_confirmation()

                    # 確認を待つ
                    import time

                    while (
                        not hasattr(self.game_ui, "phase_transition_confirmed")
                        or not self.game_ui.phase_transition_confirmed
                    ):
                        time.sleep(0.1)

                    # フラグをリセット
                    self.game_ui.phase_transition_confirmed = False
                else:
                    # CPU専用の場合は短い待機時間後に進む
                    self.game_ui.add_debug_message(
                        "CPU-only game, advancing automatically in 2 seconds..."
                    )
                    import time

                    time.sleep(2)

                # 次のフェーズに進む
                self.game_ui.add_debug_message("Advancing to next phase...")
                if not self.game.advance_to_next_phase():
                    break
                # フェーズ遷移後に即時UI更新（オールイン時の自動進行でも盤面を段階表示）
                self.game_ui.update_display()

            # ショーダウン
            if self.game.current_phase == GamePhase.SHOWDOWN:
                results = self.game.conduct_showdown()
                self.game_ui.update_display()
                # ダイアログではなくインラインで結果表示し、次のハンドへボタンを待つ
                self.game_ui.show_showdown_results_inline(results)
                import time

                while not getattr(self.game_ui, "showdown_continue_confirmed", False):
                    time.sleep(0.1)
                # フラグをリセット
                self.game_ui.showdown_continue_confirmed = False

                # ショーダウン後、ゲーム終了条件を再確認
                if self.game.is_game_over():
                    break
            else:
                # ショーダウンにならなかった場合（全員フォールドなど）の続行確認
                if not self.ask_continue_game():
                    break

        # ゲーム終了時、最終結果を表示（勝者が決定している場合）
        try:
            if self.game.is_game_over():
                self.game_ui.update_display()
                self.game_ui.show_final_results()
        except Exception:
            pass

    def ask_continue_game(self) -> bool:
        """ゲーム続行確認"""
        import logging

        logger = logging.getLogger("poker_game")
        logger.debug("ask_continue_game called")

        import time

        result = [None]  # リストを使って値を保存

        def on_yes(e):
            result[0] = True
            dialog.open = False
            self.page.update()

        def on_no(e):
            result[0] = False
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("ハンド終了"),
            content=ft.Text("次のハンドを続けますか？"),
            actions=[
                ft.TextButton("次のハンドへ", on_click=on_yes),
                ft.TextButton("ゲーム終了", on_click=on_no),
            ],
        )

        with UI_UPDATE_LOCK:
            # 既存のダイアログをクリアしてから新しいダイアログを追加
            overlays_to_remove = [
                overlay
                for overlay in self.page.overlay
                if overlay != self.game_ui.get_raise_dialog()
            ]
            for overlay in overlays_to_remove:
                self.page.overlay.remove(overlay)

            # 新しいダイアログを追加して開く
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()

        # ユーザーの応答を待つ
        while result[0] is None:
            time.sleep(0.1)

        return result[0]

    # show_showdown_results, show_game_over, close_dialog はダイアログUIのため削除

    def add_debug_message(self, message: str):
        """デバッグメッセージを追加"""
        import datetime
        import logging

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.debug_messages.append(f"[{timestamp}] {message}")
        # 最新の5件のみ保持
        self.debug_messages = self.debug_messages[-5:]

        # ロガーを使用（main.pyの設定に従う）
        logger = logging.getLogger("poker_game")
        logger.debug(message)

    def show_phase_transition_confirmation(self):
        """次のフェーズに進む確認を表示"""
        # 現在のフェーズから次のフェーズを決定
        next_phase_name = ""
        if self.game.current_phase == GamePhase.PREFLOP:
            next_phase_name = "フロップ"
        elif self.game.current_phase == GamePhase.FLOP:
            next_phase_name = "ターン"
        elif self.game.current_phase == GamePhase.TURN:
            next_phase_name = "リバー"
        elif self.game.current_phase == GamePhase.RIVER:
            next_phase_name = "ショーダウン"

        # 確認ボタンを作成
        continue_button = ft.ElevatedButton(
            text=f"{next_phase_name}に進む",
            on_click=self.on_phase_transition_confirmed,
            bgcolor=ft.Colors.GREEN,
            color=ft.Colors.WHITE,
        )

        # ステータスメッセージを更新
        self.status_text.value = (
            f"ベッティングラウンドが完了しました。{next_phase_name}に進みますか？"
        )
        self.status_text.color = ft.Colors.BLUE

        # アクションボタンを確認ボタンに置き換え
        self.action_buttons_row.controls.clear()
        self.action_buttons_row.controls.append(continue_button)

        # UIを更新
        if self.page:
            self.page.update()

    def on_phase_transition_confirmed(self, e):
        """フェーズ遷移が確認された際の処理"""
        self.add_debug_message("Player confirmed phase transition")
        self.phase_transition_confirmed = True

        # ボタンを削除
        self.action_buttons_row.controls.clear()
        self.status_text.value = "次のフェーズに進んでいます..."
        self.status_text.color = ft.Colors.GREEN

        # UIを更新
        if self.page:
            self.page.update()


def run_flet_poker_app(with_viewer: bool = False, viewer_port: int = 8552):
    """Fletポーカーアプリを実行

    Args:
        with_viewer: True の場合、観戦用UIを別ポートで同時起動
        viewer_port: 観戦用UIのポート
    """
    if with_viewer:
        # Flet cannot be launched via app() in a non-main thread because of signal handling.
        # Launch the viewer in a separate background process instead of a thread.
        try:
            import multiprocessing as mp
            from .viewer_ui import run_flet_viewer_app

            viewer_proc = mp.Process(
                target=run_flet_viewer_app, args=(viewer_port,), daemon=True
            )
            viewer_proc.start()
        except Exception:
            # 観戦UI起動失敗は致命的ではないため無視して続行
            pass

    ui = PokerFletUI()
    ft.app(target=ui.main, view=ft.AppView.WEB_BROWSER, port=8551)
