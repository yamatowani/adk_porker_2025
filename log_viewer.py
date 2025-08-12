"""
Poker Game Log Viewer - ポーカーゲームのログを可視化するWebアプリケーション
"""

import flet as ft
import os
import re
import json
import sys
import argparse
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class LogEventType(Enum):
    """ログイベントのタイプ"""

    HAND_START = "hand_start"
    HAND_END = "hand_end"
    PHASE_CHANGE = "phase_change"
    PLAYER_ACTION = "player_action"
    GAME_STATE = "game_state"
    SHOWDOWN = "showdown"
    LLM_DECISION = "llm_decision"
    OTHER = "other"


class GameState:
    """現在のゲーム状態を保持するクラス"""

    def __init__(self):
        self.current_hand = None
        self.current_phase = "waiting"
        self.pot = 0
        self.current_bet = 0
        self.community_cards = []
        self.players = {}
        self.dealer_button = 0
        self.current_player = None
        self.last_updated = None


class LogParser:
    """ログファイルを解析するクラス"""

    def __init__(self):
        self.events = []
        self.current_hand = None
        self.players = {}
        self.game_state = GameState()
        self.last_file_position = 0

    def parse_file(self, filepath: str) -> List[Dict[str, Any]]:
        """ログファイルを解析してイベントリストを返す"""
        self.events = []
        self.current_hand = None
        self.players = {}

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # タイムスタンプとログレベルを抽出
            timestamp_match = re.match(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - poker_game - (\w+) - (.+)",
                line,
            )
            if not timestamp_match:
                i += 1
                continue

            timestamp_str, log_level, message = timestamp_match.groups()
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

            # イベントタイプを判定して解析
            event = self._parse_message(message, timestamp, log_level, lines, i)
            if event:
                self.events.append(event)
                self._update_game_state(event)

            i += 1

        return self.events

    def parse_new_lines(self, filepath: str) -> List[Dict[str, Any]]:
        """ログファイルの新しい行のみを解析"""
        new_events = []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                f.seek(self.last_file_position)
                new_lines = f.readlines()
                self.last_file_position = f.tell()
        except (FileNotFoundError, IOError):
            return new_events

        # 複数行にわたるメッセージを正しく処理するため、行リスト全体を処理
        i = 0
        while i < len(new_lines):
            line = new_lines[i].strip()
            if not line:
                i += 1
                continue

            # タイムスタンプとログレベルを抽出
            timestamp_match = re.match(
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - poker_game - (\w+) - (.+)",
                line,
            )
            if not timestamp_match:
                i += 1
                continue

            timestamp_str, log_level, message = timestamp_match.groups()
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")

            # イベントタイプを判定して解析（全行リストを渡して複数行JSONに対応）
            event = self._parse_message(message, timestamp, log_level, new_lines, i)
            if event:
                new_events.append(event)
                self.events.append(event)
                self._update_game_state(event)

            i += 1

        return new_events

    def _update_game_state(self, event: Dict[str, Any]):
        """イベントからゲーム状態を更新"""
        event_type = event["type"]

        if event_type == LogEventType.HAND_START:
            self.game_state.current_hand = event["hand_number"]
            self.game_state.current_phase = "preflop"
            self.game_state.community_cards = []  # 新しいハンドでリセット
            # 新しいハンドでプレイヤーのカード情報をリセット
            for player_id in self.game_state.players:
                self.game_state.players[player_id]["cards"] = []
            self.game_state.last_updated = event["timestamp"]
            print(
                f"DEBUG: New hand #{event['hand_number']} started, reset player cards"
            )

        elif event_type == LogEventType.PHASE_CHANGE:
            self.game_state.current_phase = event["to_phase"].lower()
            self.game_state.last_updated = event["timestamp"]

        elif event_type == LogEventType.GAME_STATE:
            # ゲーム状態メッセージからプレイヤー情報を抽出
            self._extract_player_info_from_message(event["message"])
            # ポットと現在のベット情報を更新
            if "pot" in event:
                self.game_state.pot = event["pot"]
            if "current_bet" in event:
                self.game_state.current_bet = event["current_bet"]
            self.game_state.last_updated = event["timestamp"]
            print(
                f"DEBUG: Updated game state - Pot: {self.game_state.pot}, Current bet: {self.game_state.current_bet}"
            )
            print(f"DEBUG: Total players in game state: {len(self.game_state.players)}")

        elif event_type == LogEventType.PLAYER_ACTION:
            player_id = event.get("player_id")
            if player_id is not None:
                if player_id not in self.game_state.players:
                    self.game_state.players[player_id] = {
                        "name": event.get("player_name", f"Player {player_id}"),
                        "chips": 2000,  # デフォルト値
                        "current_bet": 0,
                        "cards": [],
                        "status": "active",
                    }
                    print(
                        f"DEBUG: Created player from action: P{player_id} ({self.game_state.players[player_id]['name']})"
                    )
                # プレイヤーのアクション履歴を更新
                self.game_state.players[player_id]["last_action"] = event["action"]
                self.game_state.players[player_id]["last_amount"] = event.get(
                    "amount", 0
                )

                # フォールドアクションの場合はステータスを更新
                if event["action"] == "folds":
                    self.game_state.players[player_id]["status"] = "folded"
                elif event["action"] == "goes all-in":
                    self.game_state.players[player_id]["status"] = "all_in"
                else:
                    self.game_state.players[player_id]["status"] = "active"

            self.game_state.last_updated = event["timestamp"]

        elif event_type == LogEventType.LLM_DECISION:
            # LLMプロンプトからプレイヤーカードとコミュニティカードを抽出は
            # 既に _parse_message で処理済み
            pass

    def _collect_multi_line_json(
        self, lines: List[str], start_index: int, first_line: str
    ) -> str:
        """複数行にわたるJSONメッセージを収集"""
        json_lines = [first_line]

        # 次の行から完全なJSONを探す
        i = start_index + 1
        brace_count = first_line.count("{") - first_line.count("}")
        # print(f"DEBUG: Starting multi-line JSON collection, initial brace_count: {brace_count}")

        while i < len(lines) and brace_count > 0:
            line = lines[i].strip()
            # ログ形式の行（日時から始まる）でない場合はJSONの続き
            timestamp_pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}"
            if not re.match(timestamp_pattern, line):
                json_lines.append(line)
                brace_count += line.count("{") - line.count("}")
                # print(f"DEBUG: Added line {i}, brace_count: {brace_count}, line: {line[:50]}...")
            else:
                # print(f"DEBUG: Found timestamp line, breaking: {line[:50]}...")
                break
            i += 1

        result = "\n".join(json_lines)
        print(
            f"DEBUG: Collected JSON for prompt, lines: {len(json_lines)}, length: {len(result)}"
        )
        return result

    def _extract_cards_from_json_message(self, full_message: str, player_name: str):
        """完全なJSONメッセージからカード情報を抽出"""
        try:
            # JSONパートを抽出
            json_start = full_message.find("{")
            json_end = full_message.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = full_message[json_start:json_end]
                prompt_data = json.loads(json_str)

                # プレイヤーIDを特定する改良されたロジック
                target_player_id = None

                # 1. 既存のプレイヤーから名前で検索
                for pid, pinfo in self.game_state.players.items():
                    if pinfo["name"] == player_name:
                        target_player_id = pid
                        break

                # 2. プレイヤーが見つからない場合、名前からIDを推定
                if target_player_id is None:
                    if player_name.startswith("Agent"):
                        try:
                            # Agent1 -> ID 1, Agent2 -> ID 2, Agent3 -> ID 3
                            target_player_id = int(player_name.replace("Agent", ""))
                        except ValueError:
                            print(f"DEBUG: Agent名前からID抽出失敗: {player_name}")
                            return
                    elif player_name == "You":
                        # "You" の場合、プロンプト内のcurrent_turnかプレイヤーリストから推定
                        if "current_turn" in prompt_data:
                            target_player_id = prompt_data["current_turn"]
                        else:
                            print(f"DEBUG: 'You'のプレイヤーID特定失敗")
                            return
                    else:
                        print(f"DEBUG: 不明なプレイヤー名: {player_name}")
                        return

                    # 新規プレイヤー作成
                    self.game_state.players[target_player_id] = {
                        "name": player_name,
                        "chips": 2000,  # デフォルト値
                        "current_bet": 0,
                        "cards": [],
                        "status": "active",
                    }
                    print(
                        f"DEBUG: 新規プレイヤー作成: P{target_player_id} ({player_name})"
                    )

                # プレイヤーカードを抽出
                if "your_cards" in prompt_data:
                    player_cards = prompt_data["your_cards"]
                    if isinstance(player_cards, list) and len(player_cards) == 2:
                        self.game_state.players[target_player_id][
                            "cards"
                        ] = player_cards
                        print(
                            f"DEBUG: {player_name} (ID:{target_player_id}) のカードを設定: {player_cards}"
                        )

                # コミュニティカードを抽出
                if "community" in prompt_data:
                    community_cards = prompt_data["community"]
                    if isinstance(community_cards, list):
                        self.game_state.community_cards = community_cards
                        print(f"DEBUG: コミュニティカードを設定: {community_cards}")

                # プロンプト内の他のプレイヤー情報も利用してゲーム状態を更新
                if "players" in prompt_data and isinstance(
                    prompt_data["players"], list
                ):
                    for player_info in prompt_data["players"]:
                        if "id" in player_info:
                            pid = player_info["id"]
                            if pid not in self.game_state.players:
                                self.game_state.players[pid] = {
                                    "name": f"Player{pid}",
                                    "chips": player_info.get("chips", 2000),
                                    "current_bet": player_info.get("bet", 0),
                                    "cards": [],
                                    "status": player_info.get("status", "active"),
                                }
                            else:
                                # 既存プレイヤーの情報を更新（カードは保持）
                                existing_cards = self.game_state.players[pid].get(
                                    "cards", []
                                )
                                self.game_state.players[pid]["chips"] = player_info.get(
                                    "chips", self.game_state.players[pid]["chips"]
                                )
                                self.game_state.players[pid]["current_bet"] = (
                                    player_info.get(
                                        "bet",
                                        self.game_state.players[pid]["current_bet"],
                                    )
                                )
                                self.game_state.players[pid]["status"] = (
                                    player_info.get(
                                        "status", self.game_state.players[pid]["status"]
                                    )
                                )
                                self.game_state.players[pid]["cards"] = existing_cards

                # ポット情報とベット情報も更新
                if "pot" in prompt_data:
                    self.game_state.pot = prompt_data["pot"]
                if "to_call" in prompt_data:
                    # current_betの推定
                    current_player_bet = prompt_data.get("your_bet_this_round", 0)
                    to_call = prompt_data["to_call"]
                    self.game_state.current_bet = current_player_bet + to_call

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"DEBUG: カード抽出エラー: {e}")
            print(
                f"DEBUG: 問題のあるJSON: {json_str[:200] if 'json_str' in locals() else 'N/A'}"
            )
            pass  # JSONパースエラーは無視

    def _extract_player_info_from_message(self, message: str):
        """ゲーム状態メッセージからプレイヤー情報を抽出"""
        # "  P0(You): chips=980, bet=20, status=active" の形式を解析
        # より柔軟な正規表現パターンに修正
        player_pattern = (
            r"P(\d+)\(([^)]+)\):\s*chips=(\d+),\s*bet=(\d+),\s*status=(\w+)"
        )

        # 行ごとに処理
        for line in message.split("\n"):
            line = line.strip()
            if not line or "P" not in line or "chips=" not in line:
                continue

            matches = re.findall(player_pattern, line)
            print(f"DEBUG: Processing line: {line}")
            print(f"DEBUG: Found {len(matches)} matches")

            for match in matches:
                player_id = int(match[0])
                player_name = match[1]
                chips = int(match[2])
                current_bet = int(match[3])
                status = match[4]

                print(
                    f"DEBUG: Extracting info for P{player_id}: {player_name}, chips={chips}, bet={current_bet}, status={status}"
                )

                if player_id not in self.game_state.players:
                    self.game_state.players[player_id] = {
                        "name": player_name,
                        "chips": chips,
                        "current_bet": current_bet,
                        "cards": [],
                        "status": status,
                    }
                    print(f"DEBUG: Created new player P{player_id}")
                else:
                    # 既存プレイヤーの情報を更新（カード情報は保持）
                    existing_cards = self.game_state.players[player_id].get("cards", [])
                    self.game_state.players[player_id]["chips"] = chips
                    self.game_state.players[player_id]["current_bet"] = current_bet
                    self.game_state.players[player_id]["status"] = status
                    # 名前も更新（"You" -> 実際の名前など）
                    self.game_state.players[player_id]["name"] = player_name
                    # カード情報は保持
                    self.game_state.players[player_id]["cards"] = existing_cards
                    print(
                        f"DEBUG: Updated P{player_id}, preserved cards: {existing_cards}"
                    )

    def _parse_message(
        self,
        message: str,
        timestamp: datetime,
        log_level: str,
        lines: List[str],
        line_index: int,
    ) -> Optional[Dict[str, Any]]:
        """メッセージを解析してイベントを生成"""

        # ハンド開始
        if "=== STARTING NEW HAND #" in message:
            match = re.search(r"HAND #(\d+)", message)
            if match:
                self.current_hand = int(match.group(1))
                return {
                    "type": LogEventType.HAND_START,
                    "timestamp": timestamp,
                    "hand_number": self.current_hand,
                    "message": message,
                }

        # ハンド終了
        elif "=== HAND COMPLETE ===" in message:
            return {
                "type": LogEventType.HAND_END,
                "timestamp": timestamp,
                "hand_number": self.current_hand,
                "message": message,
            }

        # フェーズ変更
        elif "Phase changed:" in message:
            match = re.search(r"Phase changed: (\w+) -> (\w+)", message)
            if match:
                return {
                    "type": LogEventType.PHASE_CHANGE,
                    "timestamp": timestamp,
                    "hand_number": self.current_hand,
                    "from_phase": match.group(1),
                    "to_phase": match.group(2),
                    "message": message,
                }

        # プレイヤーアクション
        elif "ACTION_EXECUTED:" in message:
            return self._parse_action(message, timestamp)

        # ショーダウン
        elif "SHOWDOWN results:" in message or "Winner:" in message:
            return {
                "type": LogEventType.SHOWDOWN,
                "timestamp": timestamp,
                "hand_number": self.current_hand,
                "message": message,
            }

        # LLMプロンプト（デバッグログレベルもチェック）
        elif "LLM Prompt for" in message and log_level in ["DEBUG", "INFO"]:
            print(f"DEBUG: Found LLM Prompt for {message.split(':')[0].split()[-1]}")
            player_match = re.search(r"LLM Prompt for (\w+):", message)
            if player_match:
                player_name = player_match.group(1)

                # 複数行のJSONを収集
                full_json_message = self._collect_multi_line_json(
                    lines, line_index, message
                )

                # カード情報を抽出してゲーム状態を更新
                self._extract_cards_from_json_message(full_json_message, player_name)

                # JSONプロンプト内容を抽出
                json_start = full_json_message.find("{")
                json_end = full_json_message.rfind("}") + 1
                prompt_content = "プロンプト送信"
                if json_start != -1 and json_end > json_start:
                    try:
                        json_str = full_json_message[json_start:json_end]
                        prompt_data = json.loads(json_str)
                        # プロンプトの主要情報を抽出して要約
                        prompt_summary = []
                        if "your_cards" in prompt_data:
                            prompt_summary.append(
                                f"カード: {prompt_data['your_cards']}"
                            )
                        if "phase" in prompt_data:
                            prompt_summary.append(f"フェーズ: {prompt_data['phase']}")
                        if "pot" in prompt_data:
                            prompt_summary.append(f"ポット: {prompt_data['pot']}")
                        if "to_call" in prompt_data:
                            prompt_summary.append(f"コール額: {prompt_data['to_call']}")
                        if "your_chips" in prompt_data:
                            prompt_summary.append(
                                f"所持チップ: {prompt_data['your_chips']}"
                            )

                        if prompt_summary:
                            prompt_content = " | ".join(prompt_summary)
                            print(
                                f"DEBUG: Created prompt summary for {player_name}: {prompt_content}"
                            )
                        else:
                            prompt_content = (
                                json_str[:100] + "..."
                                if len(json_str) > 100
                                else json_str
                            )
                    except (json.JSONDecodeError, KeyError) as e:
                        prompt_content = "プロンプト解析エラー"
                        print(f"DEBUG: JSON parsing failed for {player_name}: {e}")

                return {
                    "type": LogEventType.LLM_DECISION,  # タイプを変更してフィルターに含める
                    "timestamp": timestamp,
                    "hand_number": self.current_hand,
                    "player": player_name,
                    "action": "prompt",  # プロンプト送信アクションとして扱う
                    "amount": 0,
                    "reasoning": prompt_content,  # プロンプト内容を表示
                    "full_prompt": full_json_message,  # 完全なプロンプトも保存
                    "message": message,
                }

        # LLMの決定
        elif "Successfully parsed decision:" in message:
            # パターンを修正: "action, amount, reasoning" の形式
            match = re.search(
                r"\[(.+?)\] Successfully parsed decision: (.+?), (\d+), (.+)", message
            )
            if match:
                player_name = match.group(1)
                action = match.group(2)
                amount = match.group(3)
                reasoning = match.group(4)

                return {
                    "type": LogEventType.LLM_DECISION,
                    "timestamp": timestamp,
                    "hand_number": self.current_hand,
                    "player": player_name,
                    "action": action,
                    "amount": int(amount),
                    "reasoning": reasoning,
                    "message": message,
                }

        # ゲーム状態
        elif "Pot:" in message and "Current bet:" in message:
            pot_match = re.search(r"Pot: (\d+)", message)
            bet_match = re.search(r"Current bet: (\d+)", message)
            if pot_match and bet_match:
                return {
                    "type": LogEventType.GAME_STATE,
                    "timestamp": timestamp,
                    "hand_number": self.current_hand,
                    "pot": int(pot_match.group(1)),
                    "current_bet": int(bet_match.group(1)),
                    "message": message,
                }

        return None

    def _parse_action(
        self, message: str, timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """アクションメッセージを解析"""
        # ACTION_EXECUTED: Player 0 (You) calls 20
        # ACTION_EXECUTED: Player 1 (Agent1) folds
        # ACTION_EXECUTED: Player 2 (Agent2) raises to 50

        patterns = [
            r"Player (\d+) \((.+?)\) (folds|checks|calls|raises to|goes all-in)(?: (\d+))?",
            r"Player (\d+) \((.+?)\) (folds|checks|calls) (\d+)",
            r"Player (\d+) \((.+?)\) raises to (\d+)",
            r"Player (\d+) \((.+?)\) goes all-in for (\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                groups = match.groups()
                player_id = int(groups[0])
                player_name = groups[1]
                action = groups[2]
                amount = int(groups[3]) if len(groups) > 3 and groups[3] else 0

                return {
                    "type": LogEventType.PLAYER_ACTION,
                    "timestamp": timestamp,
                    "hand_number": self.current_hand,
                    "player_id": player_id,
                    "player_name": player_name,
                    "action": action,
                    "amount": amount,
                    "message": message,
                }

        return None


class LogViewerApp:
    """ログビューワーのメインアプリケーション"""

    def __init__(self, initial_log_file=None):
        self.parser = LogParser()
        self.events = []
        self.filtered_events = []
        self.current_file = None
        self.initial_log_file = initial_log_file
        self.auto_refresh = True
        self.refresh_thread = None
        self.page = None
        self._needs_ui_update = False

        # Agent毎の色設定
        self.agent_colors = {
            "You": ft.Colors.BLUE_300,
            "Agent1": ft.Colors.GREEN_300,
            "Agent2": ft.Colors.ORANGE_300,
            "Agent3": ft.Colors.PURPLE_300,
            "Agent4": ft.Colors.RED_300,
            "Agent5": ft.Colors.YELLOW_300,
        }

        # Agent毎の背景色設定
        self.agent_bg_colors = {
            "You": ft.Colors.BLUE_900,
            "Agent1": ft.Colors.GREEN_900,
            "Agent2": ft.Colors.ORANGE_900,
            "Agent3": ft.Colors.PURPLE_900,
            "Agent4": ft.Colors.RED_900,
            "Agent5": ft.Colors.YELLOW_900,
        }

    def get_agent_color(self, player_name: str) -> str:
        """プレイヤー名からAgent色を取得"""
        return self.agent_colors.get(player_name, ft.Colors.WHITE)

    def get_agent_bg_color(self, player_name: str) -> str:
        """プレイヤー名からAgent背景色を取得"""
        return self.agent_bg_colors.get(player_name, ft.Colors.GREY_800)

    def main(self, page: ft.Page):
        """Fletアプリケーションのエントリポイント"""
        self.page = page
        page.title = "Poker Game Log Viewer"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window.width = 1800  # 幅をさらに拡大（フィルター削除により）
        page.window.height = 1000  # 高さを拡大

        # ログファイルリスト
        self.file_list = ft.ListView(expand=1, spacing=5, padding=ft.padding.all(10))

        # イベントリスト
        self.event_list = ft.ListView(
            expand=1, spacing=10, padding=ft.padding.all(10), auto_scroll=True
        )

        # フィルター機能を削除 - すべてのイベントを表示

        # 統計情報
        self.stats_text = ft.Text("ログファイルを選択してください", size=14)

        # 現在の状況表示
        self.game_status = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "ゲーム状況",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Text("待機中...", size=12, color=ft.Colors.WHITE70),
                ],
                scroll=ft.ScrollMode.AUTO,  # スクロール可能にする
            ),
            bgcolor=ft.Colors.GREY_800,
            border_radius=8,
            padding=12,
            width=420,  # 幅を拡大
            expand=True,  # 残り空間を使用
        )

        # リアルタイム更新のトグル
        self.auto_refresh_toggle = ft.Switch(
            label="リアルタイム更新", value=True, on_change=self.toggle_auto_refresh
        )

        # レイアウト
        left_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text("ログファイル", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    self.file_list,
                    ft.Divider(),
                    self.auto_refresh_toggle,
                    ft.Container(height=10),
                    self.game_status,
                ]
            ),
            width=450,
            bgcolor=ft.Colors.GREY_800,
            border_radius=10,
            padding=10,
        )

        main_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text("ゲーム進行ログ", size=18, weight=ft.FontWeight.BOLD),
                    self.stats_text,
                    ft.Divider(),
                    self.event_list,
                ]
            ),
            expand=True,
            bgcolor=ft.Colors.GREY_800,
            border_radius=10,
            padding=10,
        )

        page.add(ft.Row([left_panel, main_panel], expand=True))

        # ログファイルをロード
        self.load_log_files(page)

        # 初期ログファイルが指定されていれば自動的に読み込む
        # 指定されていない場合は最新ログファイルを自動選択
        if self.initial_log_file and os.path.exists(self.initial_log_file):
            self.load_log_file(self.initial_log_file, page)
        else:
            self.auto_select_latest_log(page)

        # ページ終了時のクリーンアップを設定
        page.on_window_event = self.on_window_event

        # UI更新チェック用のタイマーを設定（1秒間隔）
        def check_ui_updates():
            if self._needs_ui_update:
                try:
                    self.apply_filters(None)
                    self.update_game_status()
                    page.update()
                    self._needs_ui_update = False
                    print("DEBUG: UI updated via timer")
                except Exception as timer_error:
                    print(f"タイマーUI更新エラー: {timer_error}")

        # UI更新チェック用のタイマーを開始
        def timer_loop():
            while True:
                if hasattr(self, "page") and self.page:
                    check_ui_updates()
                time.sleep(1)

        timer_thread = threading.Thread(target=timer_loop, daemon=True)
        timer_thread.start()

    def auto_select_latest_log(self, page: ft.Page):
        """最新のログファイルを自動選択して読み込む"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return

        files = sorted(
            [f for f in os.listdir(log_dir) if f.endswith(".log")], reverse=True
        )

        if files:
            latest_file = os.path.join(log_dir, files[0])
            print(f"DEBUG: Auto-selecting latest log file: {latest_file}")
            self.load_log_file(latest_file, page)

    def load_log_files(self, page: ft.Page):
        """ログディレクトリからファイルをロード"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            self.file_list.controls.append(
                ft.Text("ログディレクトリが見つかりません", color=ft.Colors.ERROR)
            )
            page.update()
            return

        files = sorted(
            [f for f in os.listdir(log_dir) if f.endswith(".log")], reverse=True
        )

        if not files:
            self.file_list.controls.append(
                ft.Text("ログファイルが見つかりません", color=ft.Colors.ERROR)
            )
            page.update()
            return

        for filename in files:
            filepath = os.path.join(log_dir, filename)
            file_stat = os.stat(filepath)
            file_size = file_stat.st_size / 1024  # KB

            # ファイル名から日時を抽出
            date_match = re.search(r"(\d{8})_(\d{6})", filename)
            if date_match:
                date_str = date_match.group(1)
                time_str = date_match.group(2)
                formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
            else:
                formatted_date = filename

            file_button = ft.ElevatedButton(
                text=f"{formatted_date} ({file_size:.1f}KB)",
                on_click=lambda e, f=filepath: self.load_log_file(f, page),
                width=260,
            )

            self.file_list.controls.append(file_button)

        page.update()

    def load_log_file(self, filepath: str, page: ft.Page):
        """選択されたログファイルを読み込む"""
        self.current_file = filepath
        self.events = self.parser.parse_file(filepath)
        self.apply_filters(None)

        # ゲーム状況を更新
        self.update_game_status()

        # 統計情報を更新
        hand_count = len(
            [e for e in self.events if e["type"] == LogEventType.HAND_START]
        )

        self.stats_text.value = (
            f"ハンド数: {hand_count}, 総イベント数: {len(self.events)}"
        )

        # リアルタイム更新を開始
        if self.auto_refresh:
            self.start_auto_refresh()

        page.update()

    def apply_filters(self, e):
        """フィルター機能を削除 - 全イベントを表示"""
        if not self.events:
            return

        # 全イベントを表示
        self.filtered_events = self.events

        # イベントリストを更新
        self.update_event_list()

    def update_event_list(self):
        """イベントリストを更新"""
        self.event_list.controls.clear()

        for event in self.filtered_events:
            event_control = self.create_event_control(event)
            if event_control:
                self.event_list.controls.append(event_control)

    def create_event_control(self, event: Dict[str, Any]) -> Optional[ft.Control]:
        """イベントに応じたUIコントロールを作成"""
        event_type = event["type"]
        timestamp = event["timestamp"].strftime("%H:%M:%S")

        if event_type == LogEventType.HAND_START:
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"🎯 ハンド #{event['hand_number']} 開始",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(timestamp, size=12, color=ft.Colors.WHITE70),
                    ]
                ),
                bgcolor=ft.Colors.BLUE_800,
                padding=10,
                border_radius=5,
                width=float("inf"),
            )

        elif event_type == LogEventType.HAND_END:
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"✅ ハンド #{event['hand_number']} 終了",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(timestamp, size=12, color=ft.Colors.WHITE70),
                    ]
                ),
                bgcolor=ft.Colors.GREEN_800,
                padding=10,
                border_radius=5,
                width=float("inf"),
            )

        elif event_type == LogEventType.PLAYER_ACTION:
            action_icons = {
                "folds": "🚫",
                "checks": "✔️",
                "calls": "📞",
                "raises to": "📈",
                "goes all-in": "💰",
            }
            icon = action_icons.get(event["action"], "🎲")

            action_text = event["action"]
            if event["amount"] > 0:
                action_text += f" {event['amount']}"

            player_name = event["player_name"]
            player_color = self.get_agent_color(player_name)
            bg_color = self.get_agent_bg_color(player_name)

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Text(icon, size=20),
                        ft.Column(
                            [
                                ft.Text(
                                    f"{player_name} {action_text}",
                                    size=14,
                                    color=player_color,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(timestamp, size=10, color=ft.Colors.WHITE70),
                            ],
                            expand=True,
                        ),
                    ]
                ),
                bgcolor=bg_color,
                padding=8,
                border_radius=5,
                border=ft.border.all(1, player_color),
            )

        elif event_type == LogEventType.PHASE_CHANGE:
            phase_icons = {
                "FLOP": "🃏🃏🃏",
                "TURN": "🃏",
                "RIVER": "🃏",
                "SHOWDOWN": "👁️",
            }
            icon = phase_icons.get(event["to_phase"], "➡️")

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Text(icon, size=18),
                        ft.Column(
                            [
                                ft.Text(
                                    f"フェーズ変更: {event['from_phase']} → {event['to_phase']}",
                                    size=14,
                                ),
                                ft.Text(timestamp, size=10, color=ft.Colors.WHITE70),
                            ]
                        ),
                    ]
                ),
                bgcolor=ft.Colors.YELLOW_100,
                padding=8,
                border_radius=5,
            )

        elif event_type == LogEventType.SHOWDOWN:
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text("🏆 ショーダウン", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(event["message"], size=12),
                        ft.Text(timestamp, size=10, color=ft.Colors.WHITE70),
                    ]
                ),
                bgcolor=ft.Colors.RED_100,
                padding=10,
                border_radius=5,
                width=float("inf"),
            )

        elif event_type == LogEventType.LLM_DECISION:
            reasoning = event.get("reasoning", "")
            reasoning_preview = (
                reasoning[:80] + "..." if len(reasoning) > 80 else reasoning
            )

            player_name = event.get("player", "Unknown")
            player_color = self.get_agent_color(player_name)
            bg_color = self.get_agent_bg_color(player_name)

            # 理由またはプロンプトを展開するダイアログ
            def show_reasoning_dialog(e):
                # プロンプトアクションの場合は完全なプロンプトを表示
                content_text = reasoning
                dialog_title = f"{player_name} の思考過程"

                if event.get("action") == "prompt" and "full_prompt" in event:
                    dialog_title = f"{player_name} へのプロンプト"
                    content_text = event["full_prompt"]

                dialog = ft.AlertDialog(
                    title=ft.Text(dialog_title),
                    content=ft.Container(
                        content=ft.Text(content_text, size=12, selectable=True),
                        width=600,
                        height=400,
                        padding=10,
                    ),
                    actions=[
                        ft.TextButton(
                            "閉じる", on_click=lambda e: self.close_dialog(dialog)
                        )
                    ],
                )
                self.page.overlay.append(dialog)
                dialog.open = True
                self.page.update()

            # ヘッダー行のコントロールを動的に構築
            header_controls = [
                ft.Text("🤖", size=20),
                ft.Text(
                    f"{player_name} - {event.get('action', '')}",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=player_color,
                ),
            ]

            # 理由があるか、またはプロンプトアクションの場合は詳細ボタンを追加
            if reasoning or event.get("action") == "prompt":
                tooltip_text = (
                    "プロンプト詳細を表示"
                    if event.get("action") == "prompt"
                    else "詳細な理由を表示"
                )
                header_controls.append(
                    ft.IconButton(
                        icon=ft.Icons.VISIBILITY,
                        tooltip=tooltip_text,
                        on_click=show_reasoning_dialog,
                        icon_size=16,
                        icon_color=player_color,
                    )
                )

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Row(header_controls),
                        ft.Text(
                            reasoning_preview,
                            size=12,
                            color=ft.Colors.WHITE70,
                        ),
                        ft.Text(timestamp, size=10, color=ft.Colors.WHITE70),
                    ]
                ),
                bgcolor=bg_color,
                padding=10,
                border_radius=5,
                width=float("inf"),
                border=ft.border.all(1, player_color),
            )

        return None

    def toggle_auto_refresh(self, e):
        """リアルタイム更新のON/OFF切り替え"""
        self.auto_refresh = e.control.value
        if self.auto_refresh and self.current_file:
            self.start_auto_refresh()
        else:
            self.stop_auto_refresh()

    def start_auto_refresh(self):
        """リアルタイム更新を開始"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return

        self.refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.refresh_thread.start()

    def stop_auto_refresh(self):
        """リアルタイム更新を停止"""
        self.auto_refresh = False

    def _refresh_loop(self):
        """リアルタイム更新のメインループ"""
        while self.auto_refresh and self.current_file:
            try:
                # 新しいログ行を解析
                new_events = self.parser.parse_new_lines(self.current_file)

                # 新しいイベントがある場合はUI更新フラグを設定
                if new_events:
                    self._needs_ui_update = True
                    print(
                        f"DEBUG: Marked UI for update with {len(new_events)} new events"
                    )

                time.sleep(2)  # 2秒間隔で更新
            except Exception as e:
                print(f"リアルタイム更新エラー: {e}")
                break

    def update_game_status(self):
        """ゲーム状況表示を更新"""
        game_state = self.parser.game_state

        # デバッグ情報
        print(
            f"DEBUG: update_game_status called - Hand #{game_state.current_hand}, Phase: {game_state.current_phase}"
        )
        print(f"DEBUG: Players count: {len(game_state.players)}")
        for pid, pinfo in game_state.players.items():
            print(
                f"DEBUG: Player {pid}: {pinfo['name']}, Cards: {pinfo.get('cards', [])}, Chips: {pinfo.get('chips', 'N/A')}, Bet: {pinfo.get('current_bet', 0)}, Status: {pinfo.get('status', 'N/A')}"
            )

        if not game_state.current_hand:
            self.game_status.content = ft.Column(
                [
                    ft.Text(
                        "ゲーム状況",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Text("待機中...", size=12, color=ft.Colors.WHITE70),
                ]
            )
        else:
            # ハンド情報
            hand_info = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            f"ハンド #{game_state.current_hand}",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Text(
                            f"フェーズ: {game_state.current_phase.upper()}",
                            size=12,
                            color=ft.Colors.WHITE70,
                        ),
                        ft.Text(
                            f"ポット: {game_state.pot}  現在ベット: {game_state.current_bet}",
                            size=12,
                            color=ft.Colors.WHITE70,
                        ),
                        ft.Text(
                            f"最終更新: {game_state.last_updated.strftime('%H:%M:%S') if game_state.last_updated else 'N/A'}",
                            size=10,
                            color=ft.Colors.WHITE60,
                        ),
                    ]
                ),
                bgcolor=ft.Colors.BLUE_900,
                padding=10,
                border_radius=5,
                margin=ft.margin.only(bottom=10),
            )

            # コミュニティカード
            community_container = None
            if game_state.community_cards:
                community_cards_widgets = []
                for card in game_state.community_cards:
                    community_cards_widgets.append(self.create_card_widget(card))

                community_container = ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "コミュニティカード",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Row(community_cards_widgets, wrap=True),
                        ]
                    ),
                    bgcolor=ft.Colors.GREEN_900,
                    padding=10,
                    border_radius=5,
                    margin=ft.margin.only(bottom=10),
                )

            # プレイヤー情報
            players_widgets = []
            for player_id, player_info in game_state.players.items():
                # プレイヤーカード
                player_cards = []
                if player_info.get("cards"):
                    for card in player_info["cards"]:
                        player_cards.append(self.create_card_widget(card))

                # アクション情報
                action_info = ""
                action_color = ft.Colors.WHITE70
                if "last_action" in player_info:
                    action_info = player_info["last_action"]
                    if player_info.get("last_amount", 0) > 0:
                        action_info += f" {player_info['last_amount']}"

                    # アクションに応じた色分け
                    if action_info.startswith("fold"):
                        action_color = ft.Colors.RED_300
                    elif action_info.startswith("raise"):
                        action_color = ft.Colors.ORANGE_300
                    elif action_info.startswith("call"):
                        action_color = ft.Colors.GREEN_300
                    else:
                        action_color = ft.Colors.BLUE_300

                # チップとベット情報
                chips_info = f"💰 {player_info.get('chips', 'N/A')}チップ"
                bet_info = f"📊 ベット: {player_info.get('current_bet', 0)}"

                # ステータス色分け
                status_color = ft.Colors.WHITE70
                status = player_info.get("status", "active")
                if status == "folded":
                    status_color = ft.Colors.RED_300
                elif status == "all_in":
                    status_color = ft.Colors.ORANGE_300
                elif status == "active":
                    status_color = ft.Colors.GREEN_300

                # プレイヤー毎の色分け
                player_name = player_info["name"]
                player_color = self.get_agent_color(player_name)
                player_bg_color = self.get_agent_bg_color(player_name)

                player_widget = ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                f"P{player_id}: {player_name}",
                                size=10,
                                weight=ft.FontWeight.BOLD,
                                color=player_color,
                            ),
                            ft.Row(
                                [
                                    ft.Text(
                                        chips_info, size=7, color=ft.Colors.AMBER_300
                                    ),
                                    ft.Text(bet_info, size=7, color=ft.Colors.CYAN_300),
                                ]
                            ),
                            (
                                ft.Row(player_cards)
                                if player_cards
                                else ft.Text(
                                    "カード未公開", size=7, color=ft.Colors.WHITE60
                                )
                            ),
                            ft.Row(
                                [
                                    (
                                        ft.Text(
                                            f"アクション: {action_info}",
                                            size=7,
                                            color=action_color,
                                        )
                                        if action_info
                                        else ft.Container()
                                    ),
                                    ft.Text(
                                        f"状態: {status}", size=7, color=status_color
                                    ),
                                ],
                                wrap=True,
                            ),
                        ]
                    ),
                    bgcolor=player_bg_color,
                    padding=6,
                    border_radius=4,
                    margin=ft.margin.only(bottom=3, right=3),
                    width=180,  # 2x2レイアウト用に幅を調整
                    height=120,  # 高さを制限
                    border=ft.border.all(1, player_color),
                )
                players_widgets.append(player_widget)

            # 全体をまとめる
            content_widgets = [
                ft.Text(
                    "ゲーム状況",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                hand_info,
            ]

            if community_container:
                content_widgets.append(community_container)

            # プレイヤーウィジェットを2x2のグリッドに配置
            if players_widgets:
                # プレイヤーを2つずつのペアに分割
                player_pairs = []
                for i in range(0, len(players_widgets), 2):
                    pair = players_widgets[i : i + 2]
                    # 1つしかない場合は空のコンテナを追加
                    if len(pair) == 1:
                        pair.append(ft.Container())
                    player_pairs.append(ft.Row(pair, spacing=5))

                content_widgets.extend(player_pairs)

            self.game_status.content = ft.Column(
                content_widgets, scroll=ft.ScrollMode.AUTO
            )

    def create_card_widget(self, card_str: str) -> ft.Container:
        """カード表示ウィジェット作成"""
        if not card_str or card_str == "??":
            return ft.Container(
                content=ft.Text("🂠", size=10),
                width=20,
                height=28,
                bgcolor=ft.Colors.BLUE_200,
                border=ft.border.all(1, ft.Colors.BLUE_800),
                border_radius=3,
                alignment=ft.alignment.center,
                margin=ft.margin.only(right=2),
            )

        # カードの色を決定
        if "♥" in card_str or "♦" in card_str:
            text_color = ft.Colors.RED_700
        else:
            text_color = ft.Colors.BLACK

        return ft.Container(
            content=ft.Text(
                card_str, size=7, weight=ft.FontWeight.BOLD, color=text_color
            ),
            width=16,
            height=22,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.BLACK),
            border_radius=2,
            alignment=ft.alignment.center,
            margin=ft.margin.only(right=1),
        )

    def close_dialog(self, dialog):
        """ダイアログを閉じる"""
        dialog.open = False
        self.page.update()

    def on_window_event(self, e):
        """ウィンドウイベントハンドラー"""
        if e.data == "close":
            self.stop_auto_refresh()


def main():
    """アプリケーションのエントリポイント"""
    parser = argparse.ArgumentParser(description="Poker Game Log Viewer")
    parser.add_argument(
        "logfile", nargs="?", help="読み込むログファイルのパス（省略時は一覧から選択）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8553,
        help="Webサーバーのポート番号（デフォルト: 8553）",
    )

    args = parser.parse_args()

    # ログファイルが指定されていて存在しない場合はエラー
    if args.logfile and not os.path.exists(args.logfile):
        print(
            f"エラー: ログファイル '{args.logfile}' が見つかりません", file=sys.stderr
        )
        sys.exit(1)

    app = LogViewerApp(initial_log_file=args.logfile)

    print(f"ログビューワーを起動中... http://localhost:{args.port}")
    print("終了するには Ctrl+C を押してください")

    try:
        ft.app(target=app.main, port=args.port)
    except OSError as e:
        if "address already in use" in str(e).lower():
            print(f"\nエラー: ポート {args.port} は既に使用されています。")
            print(
                f"別のポートを指定してください: python log_viewer.py --port {args.port + 1}"
            )
        else:
            raise


if __name__ == "__main__":
    main()
