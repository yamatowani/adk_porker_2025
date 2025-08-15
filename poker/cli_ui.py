"""
CLI User Interface for Poker Game
"""

import json
from time import sleep
from typing import Dict, Any, Tuple, Optional, List
from .game import PokerGame, GamePhase
from .player_models import Player, HumanPlayer, PlayerStatus
from .evaluator import HandEvaluator


class PokerUI:
    """ポーカーゲームのCLI UI"""

    def __init__(self):
        self.game = None

    def clear_screen(self):
        """画面をクリア（簡易版）"""
        print("\n" * 50)

    def print_separator(self, char="=", length=60):
        """区切り線を出力"""
        print(char * length)

    def print_title(self, title: str):
        """タイトルを出力"""
        self.print_separator()
        print(f"  {title}")
        self.print_separator()

    def display_game_state(self, player_id: int = 0):
        """現在のゲーム状況を表示"""
        if not self.game:
            return

        # プレイヤーIDが有効かチェック
        if self.game.get_player(player_id) is None:
            return

        self.clear_screen()
        self.print_title("TEXAS HOLD'EM POKER")

        # 基本情報
        print(
            f"ハンド #{self.game.hand_number} - フェーズ: {self._get_phase_name(self.game.current_phase)}"
        )
        print(f"ポット: {self.game.pot} チップ")
        print(f"現在のベット: {self.game.current_bet} チップ")
        print()

        # コミュニティカード
        self._display_community_cards()

        # プレイヤー情報
        self._display_players_info(player_id)

        # 自分の手札
        self._display_your_cards(player_id)

        # アクション履歴（最新3件）
        self._display_recent_actions()

    def _get_phase_name(self, phase: GamePhase) -> str:
        """フェーズ名を日本語で取得"""
        phase_names = {
            GamePhase.PREFLOP: "プリフロップ",
            GamePhase.FLOP: "フロップ",
            GamePhase.TURN: "ターン",
            GamePhase.RIVER: "リバー",
            GamePhase.SHOWDOWN: "ショーダウン",
            GamePhase.FINISHED: "終了",
        }
        return phase_names.get(phase, "不明")

    def _get_next_phase_name(self) -> str:
        """次のフェーズ名を日本語で取得"""
        if self.game.current_phase == GamePhase.PREFLOP:
            return "フロップ"
        elif self.game.current_phase == GamePhase.FLOP:
            return "ターン"
        elif self.game.current_phase == GamePhase.TURN:
            return "リバー"
        elif self.game.current_phase == GamePhase.RIVER:
            return "ショーダウン"
        else:
            return "不明"

    def _display_community_cards(self):
        """コミュニティカードを表示"""
        print("コミュニティカード:")
        if not self.game.community_cards:
            print("  まだありません")
        else:
            cards_str = "  " + " ".join(str(card) for card in self.game.community_cards)
            print(cards_str)
        print()

    def _display_players_info(self, current_player_id: int):
        """プレイヤー情報を表示"""
        print("プレイヤー情報:")

        for player in self.game.players:
            status_indicators = []

            # 現在のターンの表示
            if player.id == self.game.current_player_index:
                status_indicators.append(">>> アクション中 <<<")

            # 役職表示
            if player.is_dealer:
                status_indicators.append("D")
            if player.is_small_blind:
                status_indicators.append("SB")
            if player.is_big_blind:
                status_indicators.append("BB")

            # 状態表示
            status_map = {
                PlayerStatus.ACTIVE: "アクティブ",
                PlayerStatus.FOLDED: "フォールド",
                PlayerStatus.ALL_IN: "オールイン",
                PlayerStatus.BUSTED: "バストアウト",
            }
            status_indicators.append(status_map.get(player.status, "不明"))

            # プレイヤー名の装飾
            name_display = (
                f"【{player.name}】" if player.id == current_player_id else player.name
            )

            status_str = " | ".join(status_indicators)
            bet_info = (
                f"ベット: {player.current_bet} (累計: {player.total_bet_this_hand})"
                if player.current_bet > 0 or player.total_bet_this_hand > 0
                else ""
            )

            print(f"  {name_display} - チップ: {player.chips} {bet_info}")
            print(f"    状態: {status_str}")
        print()

    def _display_your_cards(self, player_id: int):
        """自分の手札を表示"""
        player = self.game.get_player(player_id)
        if player is None:
            return
        print("あなたの手札:")
        if player.hole_cards:
            cards_str = "  " + " ".join(str(card) for card in player.hole_cards)
            print(cards_str)

            # 現在の最強ハンドを表示
            if len(self.game.community_cards) >= 3:
                hand_result = HandEvaluator.evaluate_hand(
                    player.hole_cards, self.game.community_cards
                )
                print(
                    f"  現在のハンド: {HandEvaluator.get_hand_strength_description(hand_result)}"
                )
        else:
            print("  カードがありません")
        print()

    def _display_recent_actions(self):
        """最近のアクション履歴を表示"""
        if not self.game.action_history:
            return

        print("最近のアクション:")
        recent_actions = self.game.action_history[-3:]
        for action in recent_actions:
            print(f"  • {action}")
        print()

    def get_human_action(self, player_id: int) -> Tuple[str, int]:
        """
        人間プレイヤーからアクションを取得

        Returns:
            Tuple[action, amount]: アクションと金額
        """
        game_state = self.game.get_llm_game_state(player_id)
        available_actions = game_state["actions"]

        if not available_actions:
            print("利用可能なアクションがありません。")
            return "fold", 0

        print("利用可能なアクション:")
        for i, action in enumerate(available_actions, 1):
            print(f"  {i}. {self._translate_action(action)}")
        print()

        while True:
            try:
                choice = input("アクションを選択してください (番号): ").strip()
                if not choice:
                    continue

                choice_num = int(choice)
                if 1 <= choice_num <= len(available_actions):
                    selected_action = available_actions[choice_num - 1]
                    return self._parse_action_choice(selected_action)
                else:
                    print(f"1から{len(available_actions)}の間で選択してください。")

            except ValueError:
                print("有効な番号を入力してください。")
            except KeyboardInterrupt:
                print("\nゲームを終了します。")
                return "fold", 0

    def _translate_action(self, action: str) -> str:
        """アクションを日本語に翻訳"""
        if action == "fold":
            return "フォールド（諦める）"
        elif action == "check":
            return "チェック（パス）"
        elif action.startswith("call"):
            amount = action.split("(")[1].split(")")[0]
            return f"コール（{amount}チップでついていく）"
        elif action.startswith("raise"):
            min_amount = action.split("min ")[1].split(")")[0]
            return f"レイズ（最低{min_amount}チップで上げる）"
        elif action.startswith("all-in"):
            amount = action.split("(")[1].split(")")[0]
            return f"オールイン（{amount}チップで勝負）"
        else:
            return action

    def _parse_action_choice(self, action: str) -> Tuple[str, int]:
        """選択されたアクションをパース"""
        if action == "fold":
            return "fold", 0
        elif action == "check":
            return "check", 0
        elif action.startswith("call"):
            amount = int(action.split("(")[1].split(")")[0])
            return "call", amount
        elif action.startswith("raise"):
            min_amount = int(action.split("min ")[1].split(")")[0])
            # レイズ額を入力してもらう
            while True:
                try:
                    raise_amount = input(
                        f"レイズ額を入力してください (最低 {min_amount}): "
                    ).strip()
                    if not raise_amount:
                        continue
                    amount = int(raise_amount)
                    if amount >= min_amount:
                        return "raise", amount
                    else:
                        print(f"最低{min_amount}チップ以上でレイズしてください。")
                except ValueError:
                    print("有効な数値を入力してください。")
        elif action.startswith("all-in"):
            amount = int(action.split("(")[1].split(")")[0])
            return "all_in", amount
        else:
            return "fold", 0

    def display_showdown_results(self, results: Dict[str, Any]):
        """ショーダウン結果を表示"""
        print("\n")
        self.print_title("ショーダウン結果")

        if "all_hands" in results:
            print("各プレイヤーのハンド:")
            for hand_info in results["all_hands"]:
                player = self.game.get_player(hand_info["player_id"])
                player_name = (
                    player.name if player else f"Player {hand_info['player_id']}"
                )
                cards_str = " ".join(hand_info["cards"])
                print(f"  {player_name}: {cards_str} - {hand_info['hand']}")
            print()

        if results["results"]:
            print("勝者:")
            for result in results["results"]:
                player = self.game.get_player(result["player_id"])
                player_name = player.name if player else f"Player {result['player_id']}"
                print(f"  {player_name}: {result['winnings']}チップ獲得")
                print(f"    ハンド: {result['hand']}")

        input("\n続行するには Enter キーを押してください...")

    def display_game_over(self):
        """ゲーム終了画面を表示"""
        self.clear_screen()
        self.print_title("ゲーム終了")

        # 最終順位を表示
        players_by_chips = sorted(
            self.game.players, key=lambda p: p.chips, reverse=True
        )

        print("最終結果:")
        for i, player in enumerate(players_by_chips, 1):
            status = "バストアウト" if player.chips == 0 else f"{player.chips}チップ"
            print(f"  {i}位: {player.name} - {status}")

        print()
        print("ゲームをプレイしていただき、ありがとうございました！")

    def ask_continue_game(self) -> bool:
        """ゲーム続行確認"""
        while True:
            try:
                choice = input("\n次のハンドを続けますか？ (y/n): ").strip().lower()
                if choice in ["y", "yes", ""]:
                    return True
                elif choice in ["n", "no"]:
                    return False
                else:
                    print("'y' または 'n' で答えてください。")
            except KeyboardInterrupt:
                return False

    def display_welcome_message(self):
        """ウェルカムメッセージを表示"""
        self.clear_screen()
        self.print_title("テキサスホールデム ポーカーゲーム")

        print("ゲームルール:")
        print("• 4人プレイヤー（あなた + CPU3人）")
        print("• 初期チップ: 2000")
        print("• スモールブラインド: 10 / ビッグブラインド: 20")
        print("• No-Limit テキサスホールデム")
        print()

        print("操作方法:")
        print("• 数字を入力してアクションを選択")
        print("• Ctrl+C でゲーム終了")
        print()

        input("ゲームを開始するには Enter キーを押してください...")

    def display_json_state(self, player_id: int = 0):
        """デバッグ用：JSON形式のゲーム状態を表示"""
        if not self.game:
            return

        try:
            game_state = self.game.get_llm_game_state(player_id)
        except ValueError as e:
            print(f"ゲーム状態を取得できません: {e}")
            return
        print("\n" + "=" * 50)
        print("LLM用ゲーム状態 (JSON):")
        print("=" * 50)
        print(json.dumps(game_state.to_dict(), ensure_ascii=False, indent=2))
        print("=" * 50)

        input("\n続行するには Enter キーを押してください...")

    def run_game(self):
        """メインゲームループを実行"""
        self.display_welcome_message()

        # ゲームセットアップ
        self.game = PokerGame()
        self.game.setup_default_game()

        try:
            while not self.game.is_game_over():
                # 新しいハンドを開始
                self.game.start_new_hand()

                if self.game.current_phase == GamePhase.FINISHED:
                    break

                # ハンドのメインループ
                while self.game.current_phase not in [
                    GamePhase.SHOWDOWN,
                    GamePhase.FINISHED,
                ]:
                    # 各プレイヤーのアクション
                    while not self.game.betting_round_complete:
                        current_player = self.game.players[
                            self.game.current_player_index
                        ]

                        if current_player.status != PlayerStatus.ACTIVE:
                            self.game._advance_to_next_player()
                            continue

                        # 画面表示
                        self.display_game_state()

                        if isinstance(current_player, HumanPlayer):
                            # 人間プレイヤーのアクション
                            action, amount = self.get_human_action(current_player.id)
                            success = self.game.process_player_action(
                                current_player.id, action, amount
                            )

                            if not success:
                                print(
                                    "無効なアクションです。もう一度選択してください。"
                                )
                                input("続行するには Enter キーを押してください...")
                                continue
                        else:
                            # AIプレイヤーのアクション
                            game_state = self.game.get_llm_game_state(current_player.id)
                            decision = current_player.make_decision(game_state)

                            success = self.game.process_player_action(
                                current_player.id,
                                decision["action"],
                                decision.get("amount", 0),
                            )

                            if not success:
                                # AIの決定が無効な場合はフォールド
                                self.game.process_player_action(
                                    current_player.id, "fold", 0
                                )

                            # AIのアクションを少し待つ
                            import time

                            time.sleep(1)

                    # 次のフェーズに進む
                    print("\n" + "=" * 50)

                    # 人間プレイヤーがいるかチェック
                    has_human_player = any(
                        isinstance(p, HumanPlayer)
                        for p in self.game.players
                        if p.status == PlayerStatus.ACTIVE
                    )

                    if has_human_player:
                        # 人間プレイヤーがいる場合は確認を求める
                        next_phase_name = self._get_next_phase_name()
                        print(f"ベッティングラウンドが完了しました。")
                        print(f"次は {next_phase_name} です。")

                        while True:
                            choice = (
                                input(f"{next_phase_name}に進みますか？ (y/n): ")
                                .lower()
                                .strip()
                            )
                            if choice in ["y", "yes", ""]:
                                break
                            elif choice in ["n", "no"]:
                                print("ゲームを終了します。")
                                return
                            else:
                                print("y または n を入力してください。")
                    else:
                        # CPU専用の場合は短い待機時間後に進む
                        print("CPU専用ゲーム - 2秒後に次のフェーズに進みます...")
                        import time

                        time.sleep(2)

                    print("次のフェーズに進んでいます...")
                    if not self.game.advance_to_next_phase():
                        break

                # ショーダウン
                if self.game.current_phase == GamePhase.SHOWDOWN:
                    results = self.game.conduct_showdown()
                    self.display_game_state()
                    self.display_showdown_results(results)

                # ゲーム続行確認
                if not self.ask_continue_game():
                    break

            # ゲーム終了
            self.display_game_over()

        except KeyboardInterrupt:
            print("\n\nゲームを終了します。")
        except Exception as e:
            print(f"\nエラーが発生しました: {e}")
            print("ゲームを終了します。")

    def run_agent_only_mode(
        self, max_hands: int = 20, agents_config: str = "team1_agent:2,team2_agent:2"
    ):
        """
        エージェント専用モード - LLMエージェントのみで完全自動進行ゲーム

        Args:
            max_hands: 最大ハンド数（デフォルト20）
            agents_config: エージェント設定（例: "team1_agent:2,team2_agent:1,beginner_agent:1"）
        """
        print("=== エージェント専用モード ===")
        print("LLMエージェントのみで完全自動進行します")
        print(f"最大{max_hands}ハンドまで実行します")
        print(f"エージェント設定: {agents_config}\n")

        # エージェント設定を解析
        try:
            player_configs = self._parse_agents_config(agents_config)
            print(f"プレイヤー構成: {len(player_configs)}人")
            for i, config in enumerate(player_configs):
                print(f"  Player {i}: {config['agent_id']} ({config['type']})")
            print()
            print("ゲームを開始します。")
            sleep(3)
        except Exception as e:
            print(f"エージェント設定の解析に失敗しました: {e}")
            return

        # ゲームセットアップ
        self.game = PokerGame()
        self.game.setup_configurable_game_with_models(player_configs)

        # 統計情報の初期化
        player_stats = {}
        for player in self.game.players:
            player_stats[player.name] = {
                "hands_won": 0,
                "total_winnings": 0,
                "hands_played": 0,
                "agent_type": self._get_agent_type_for_player(player, player_configs),
            }

        import time

        try:
            hand_count = 0
            print("ゲーム開始...")
            print("-" * 60)

            while not self.game.is_game_over() and hand_count < max_hands:
                hand_count += 1

                # プレイヤー統計更新
                for player in self.game.players:
                    if player.status != PlayerStatus.BUSTED:
                        player_stats[player.name]["hands_played"] = hand_count

                # 新しいハンドを開始
                self.game.start_new_hand()

                if self.game.current_phase == GamePhase.FINISHED:
                    break

                # ハンド開始の表示（簡潔に）
                active_players = [
                    p for p in self.game.players if p.status == PlayerStatus.ACTIVE
                ]
                print(
                    f"ハンド #{self.game.hand_number:2d} | プレイヤー: {len(active_players)}人 | ポット: ${self.game.pot}"
                )

                # ハンドのメインループ
                while self.game.current_phase not in [
                    GamePhase.SHOWDOWN,
                    GamePhase.FINISHED,
                ]:
                    # 各プレイヤーのアクション
                    while not self.game.betting_round_complete:
                        current_player = self.game.players[
                            self.game.current_player_index
                        ]

                        if current_player.status != PlayerStatus.ACTIVE:
                            self.game._advance_to_next_player()
                            continue

                        # エージェントプレイヤーのアクション
                        game_state = self.game.get_llm_game_state(current_player.id)
                        decision = current_player.make_decision(game_state)

                        success = self.game.process_player_action(
                            current_player.id,
                            decision["action"],
                            decision.get("amount", 0),
                        )

                        if not success:
                            # エージェントの決定が無効な場合はフォールド
                            self.game.process_player_action(
                                current_player.id, "fold", 0
                            )

                        # 判断理由の表示（LLMApiPlayerの場合）
                        if hasattr(current_player, "last_decision_reasoning"):
                            reasoning = getattr(
                                current_player, "last_decision_reasoning", ""
                            )
                            if reasoning:
                                print(
                                    f"  {current_player.name}: {decision['action']} - {reasoning[:80]}..."
                                )

                        # 短い待機時間
                        time.sleep(0.1)  # エージェントモードでは少し長めに

                    # 次のフェーズに進む
                    if not self.game.advance_to_next_phase():
                        break

                # ショーダウン処理
                if self.game.current_phase == GamePhase.SHOWDOWN:
                    results = self.game.conduct_showdown()

                    # 勝者の統計更新
                    if results.get("results"):
                        for result_info in results["results"]:
                            winner_id = result_info["player_id"]
                            winner_player = self.game.get_player(winner_id)
                            if winner_player:
                                winner_name = winner_player.name
                                winnings = result_info["winnings"]
                                player_stats[winner_name]["hands_won"] += 1
                                player_stats[winner_name]["total_winnings"] += winnings

                        # 勝者表示
                        winner_names = []
                        winner_winnings = []
                        for result_info in results["results"]:
                            winner_id = result_info["player_id"]
                            winner_player = self.game.get_player(winner_id)
                            if winner_player:
                                winner_names.append(winner_player.name)
                                winner_winnings.append(f"${result_info['winnings']}")

                        if winner_names:
                            winners_str = ", ".join(winner_names)
                            winnings_str = ", ".join(winner_winnings)
                            print(f"       勝者: {winners_str} ({winnings_str})")

                # 5ハンドごとに中間結果表示
                if hand_count % 5 == 0:
                    print(f"\n--- {hand_count}ハンド完了 ---")
                    for player in self.game.players:
                        if player.status != PlayerStatus.BUSTED:
                            stats = player_stats[player.name]
                            agent_type = stats["agent_type"]
                            print(
                                f"{player.name:>8s} ({agent_type}): ${player.chips:4d} (勝利:{stats['hands_won']:2d}回)"
                            )
                    print("-" * 40)

            # 最終結果表示
            print(f"\n{'='*70}")
            print(f"エージェント専用モード完了 - {hand_count}ハンド実行")
            print(f"{'='*70}")

            # 最終チップ数でソート
            final_rankings = sorted(
                self.game.players, key=lambda p: p.chips, reverse=True
            )

            print("\n🏆 最終順位:")
            for i, player in enumerate(final_rankings):
                stats = player_stats[player.name]
                profit = player.chips - self.game.initial_chips
                profit_str = (
                    f"+${profit}"
                    if profit > 0
                    else f"-${abs(profit)}" if profit < 0 else "$0"
                )

                status_icon = (
                    "👑" if i == 0 else "💎" if i == 1 else "🥉" if i == 2 else "😢"
                )
                agent_type = stats["agent_type"]
                print(
                    f"{i+1}位 {status_icon} {player.name:>8s} ({agent_type:>12s}): ${player.chips:4d} ({profit_str:>6s}) "
                    f"| 勝利: {stats['hands_won']:2d}/{stats['hands_played']:2d}回"
                )

            print(f"\n📊 ゲーム統計:")
            print(f"   総ハンド数: {hand_count}")
            print(f"   総プレイヤー: {len(self.game.players)}")

            # エージェント別統計
            agent_stats = {}
            for stats in player_stats.values():
                agent_type = stats["agent_type"]
                if agent_type not in agent_stats:
                    agent_stats[agent_type] = {"wins": 0, "players": 0}
                agent_stats[agent_type]["wins"] += stats["hands_won"]
                agent_stats[agent_type]["players"] += 1

            print(f"\nエージェント別統計:")
            for agent_type, stats in agent_stats.items():
                avg_wins = (
                    stats["wins"] / stats["players"] if stats["players"] > 0 else 0
                )
                print(
                    f"   {agent_type:>15s}: {stats['wins']:3d}勝 / {stats['players']}人 (平均{avg_wins:.1f}勝)"
                )

            # 勝率計算
            total_wins = sum(stats["hands_won"] for stats in player_stats.values())
            print(f"   決着ハンド: {total_wins}")

            print(f"\n最多勝利者:")
            best_player = max(player_stats.items(), key=lambda x: x[1]["hands_won"])
            print(f"   {best_player[0]}: {best_player[1]['hands_won']}勝")

            print(f"\n最高利益者:")
            most_profitable = max(
                final_rankings, key=lambda p: p.chips - self.game.initial_chips
            )
            profit = most_profitable.chips - self.game.initial_chips
            print(f"   {most_profitable.name}: +${profit}")

            print(f"\n{'='*70}")

        except KeyboardInterrupt:
            print("\n\nエージェント専用モードを中断しました。")
        except Exception as e:
            print(f"\nエラーが発生しました: {e}")
            import traceback

            traceback.print_exc()

    def _parse_agents_config(self, agents_config: str) -> List[Dict[str, Any]]:
        """
        エージェント設定文字列を解析してプレイヤー設定リストを作成

        Args:
            agents_config: "team1_agent:2,team2_agent:1,beginner_agent:1" のような形式

        Returns:
            プレイヤー設定のリスト
        """
        available_agents = [
            "team1_agent",
            "team2_agent",
            "team3_agent",
            "team4_agent",
            "beginner_agent",
        ]
        player_configs = []
        player_id = 0

        for agent_spec in agents_config.split(","):
            agent_spec = agent_spec.strip()
            if ":" not in agent_spec:
                raise ValueError(
                    f"無効なエージェント設定: {agent_spec}. 形式: 'agent_name:count'"
                )

            agent_name, count_str = agent_spec.split(":", 1)
            agent_name = agent_name.strip()

            if agent_name not in available_agents:
                raise ValueError(
                    f"不明なエージェント: {agent_name}. 利用可能: {available_agents}"
                )

            try:
                count = int(count_str.strip())
                if count <= 0:
                    raise ValueError(
                        f"プレイヤー数は1以上である必要があります: {count}"
                    )
            except ValueError:
                raise ValueError(f"無効なプレイヤー数: {count_str}")

            # 指定された数だけプレイヤーを追加
            for i in range(count):
                player_configs.append(
                    {
                        "type": "llm_api",
                        "agent_id": agent_name,
                        "user_id": f"player_{player_id}",
                    }
                )
                player_id += 1

        if len(player_configs) < 2:
            raise ValueError("最低2人のプレイヤーが必要です")
        if len(player_configs) > 10:
            raise ValueError("最大10人のプレイヤーまでサポートされます")

        return player_configs

    def _get_agent_type_for_player(
        self, player: Player, player_configs: List[Dict[str, Any]]
    ) -> str:
        """プレイヤーに対応するエージェントタイプを取得"""
        # プレイヤーIDに基づいてagent_idを取得
        player_index = player.id
        if player_index < len(player_configs):
            config = player_configs[player_index]
            if config.get("agent_id"):
                return config["agent_id"]

        if hasattr(player, "app_name"):
            return player.app_name
        elif hasattr(player, "model"):
            return f"llm({player.model})"
        elif player.name.startswith("CPU"):
            return "random"
        else:
            return "unknown"

    def run_cpu_only_game(self, max_hands: int = 10, display_interval: int = 1):
        """
        全プレイヤーがCPUの自動進行ゲームを実行

        Args:
            max_hands: 最大ハンド数（デフォルト10）
            display_interval: 表示間隔（何ハンドおきに詳細表示するか）
        """
        print("=== CPU専用モード ===")
        print("全プレイヤーがCPU（ランダム）で自動進行します")
        print(f"最大{max_hands}ハンドまで実行します\n")

        # ゲームセットアップ
        self.game = PokerGame()
        self.game.setup_cpu_only_game()

        import time

        try:
            hand_count = 0
            while not self.game.is_game_over() and hand_count < max_hands:
                hand_count += 1

                # 新しいハンドを開始
                self.game.start_new_hand()

                if self.game.current_phase == GamePhase.FINISHED:
                    break

                # ハンド開始の表示
                if hand_count % display_interval == 0:
                    print(f"\n=== ハンド #{self.game.hand_number} ===")
                    self.display_game_state()
                    time.sleep(0.5)

                # ハンドのメインループ
                while self.game.current_phase not in [
                    GamePhase.SHOWDOWN,
                    GamePhase.FINISHED,
                ]:
                    # 各プレイヤーのアクション
                    while not self.game.betting_round_complete:
                        current_player = self.game.players[
                            self.game.current_player_index
                        ]

                        if current_player.status != PlayerStatus.ACTIVE:
                            self.game._advance_to_next_player()
                            continue

                        # CPUプレイヤーのアクション
                        game_state = self.game.get_llm_game_state(current_player.id)
                        decision = current_player.make_decision(game_state)

                        success = self.game.process_player_action(
                            current_player.id,
                            decision["action"],
                            decision.get("amount", 0),
                        )

                        if not success:
                            # AIの決定が無効な場合はフォールド
                            self.game.process_player_action(
                                current_player.id, "fold", 0
                            )

                        # アクション表示（詳細表示の場合のみ）
                        if hand_count % display_interval == 0:
                            action_desc = f"{decision['action']}"
                            if decision.get("amount", 0) > 0:
                                action_desc += f" ({decision['amount']})"
                            print(f"  {current_player.name}: {action_desc}")

                        # 短い待機時間
                        time.sleep(0.2)

                    # 次のフェーズに進む
                    if hand_count % display_interval == 0:
                        print("\n" + "=" * 50)
                        print("ベッティングラウンドが完了しました。")
                        next_phase_name = self._get_next_phase_name()
                        print(f"次は {next_phase_name} です。")
                        print("1秒後に次のフェーズに進みます...")
                        time.sleep(1)

                    if not self.game.advance_to_next_phase():
                        break

                    # フェーズ変更の表示
                    if hand_count % display_interval == 0:
                        print(
                            f"  フェーズ: {self._get_phase_name(self.game.current_phase)}"
                        )
                        if self.game.community_cards:
                            cards_str = " ".join(
                                str(card) for card in self.game.community_cards
                            )
                            print(f"  コミュニティカード: {cards_str}")
                        time.sleep(0.5)

                # ショーダウン
                if self.game.current_phase == GamePhase.SHOWDOWN:
                    showdown_result = self.game.conduct_showdown()

                    if hand_count % display_interval == 0:
                        print(f"  --- ショーダウン結果 ---")
                        for result in showdown_result.get("results", []):
                            player = self.game.get_player(result["player_id"])
                            player_name = (
                                player.name
                                if player
                                else f"Player {result['player_id']}"
                            )
                            print(
                                f"  {player_name}: {result['hand']} - {result['winnings']}チップ"
                            )
                        time.sleep(1)

                # 簡易進行状況表示（詳細表示でない場合）
                if hand_count % display_interval != 0:
                    print(f"ハンド {hand_count} 完了", end=" ")
                    if hand_count % 10 == 0:
                        print()  # 10ハンドごとに改行
                else:
                    print()

            # 最終状況表示
            print(f"\n=== ゲーム終了 ===")
            print(f"実行ハンド数: {hand_count}")
            print("\n最終チップ状況:")
            for player in self.game.players:
                status_str = ""
                if player.status == PlayerStatus.BUSTED:
                    status_str = " (BUSTED)"
                print(f"  {player.name}: {player.chips}チップ{status_str}")

            # 勝者の決定
            active_players = [
                p for p in self.game.players if p.status != PlayerStatus.BUSTED
            ]
            if active_players:
                winner = max(active_players, key=lambda p: p.chips)
                print(f"\n🏆 優勝: {winner.name} ({winner.chips}チップ)")

        except KeyboardInterrupt:
            print("\n\nCPU専用ゲームを中断しました。")
        except Exception as e:
            print(f"\nエラーが発生しました: {e}")
            print("ゲームを終了します。")
