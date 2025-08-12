"""
Agent管理・接続テスト機能
"""

import flet as ft
from typing import List, Dict, Any
import requests
import uuid
import os


class AgentManager:
    """Agent管理・接続テスト機能を提供するクラス"""

    def __init__(self, agent_server_url: str = "http://localhost:8000"):
        """
        Args:
            agent_server_url: AgentサーバーのURL
        """
        self.agent_server_url = agent_server_url
        self.dynamic_agents = []  # APIから取得したAgent一覧
        self.agent_cards = []  # UI上のAgentカード一覧
        self.test_results = {}  # テスト結果保存
        self.page = None  # Fletページ参照
        self.browser_user_id = None  # ブラウザセッション固有のuser_id
        self.agent_cards_column = None  # Agent cards columnの参照
        self.ui_refresh_callback = None  # UI更新のためのコールバック

    def set_page(self, page: ft.Page):
        """Fletページを設定"""
        self.page = page

    def set_ui_refresh_callback(self, callback):
        """UI更新のためのコールバックを設定"""
        self.ui_refresh_callback = callback

    def get_browser_user_id(self) -> str:
        """ブラウザセッション固有のuser_idを取得または生成"""
        if self.browser_user_id is None:
            # UUIDベースでuser_idを生成（4桁の数字）
            if self.page and hasattr(self.page, "session_id") and self.page.session_id:
                # Fletのsession_idがある場合はそれをベースに4桁の数字を生成
                session_hash = abs(hash(self.page.session_id)) % 10000
                self.browser_user_id = f"user-{session_hash:04d}"
            else:
                # フォールバック: UUIDベースで4桁の数字を生成
                user_uuid_int = abs(hash(str(uuid.uuid4()))) % 10000
                self.browser_user_id = f"user-{user_uuid_int:04d}"

            print(f"DEBUG: Generated browser user_id: {self.browser_user_id}")

        return self.browser_user_id

    def fetch_agents_from_server(self):
        """サーバーからAgent一覧を取得"""
        try:
            response = requests.get(f"{self.agent_server_url}/list-apps", timeout=5)
            if response.status_code == 200:
                agents_data = response.json()
                self.dynamic_agents = self._parse_agents_response(agents_data)
            else:
                print(f"Failed to fetch agents: HTTP {response.status_code}")
                print(f"DEBUG: Response text: {response.text}")
                self.dynamic_agents = []  # フォールバック
        except requests.exceptions.RequestException as e:
            print(f"Error fetching agents from server: {e}")
            self.dynamic_agents = []  # フォールバック
        except Exception as e:
            print(f"Unexpected error in fetch_agents_from_server: {e}")
            self.dynamic_agents = []  # フォールバック

    def _parse_agents_response(self, agents_data) -> List[Dict[str, Any]]:
        """Agent APIレスポンスをパースして内部形式に変換"""
        parsed_agents = []

        try:
            # デバッグ情報を出力
            print(f"DEBUG: agents_data type: {type(agents_data)}")
            print(f"DEBUG: agents_data content: {agents_data}")

            # APIレスポンスの形式に応じて適切にパース
            if isinstance(agents_data, list):
                for i, agent_info in enumerate(agents_data):
                    # agent_infoが文字列の場合
                    if isinstance(agent_info, str):
                        parsed_agent = {
                            "id": agent_info,
                            "name": agent_info.replace("_", " ").title(),
                            "description": f"Agent: {agent_info}",
                            "model": "unknown",
                            "path": "",
                            "url": f"{self.agent_server_url}/{agent_info}",
                        }
                    # agent_infoが辞書の場合
                    elif isinstance(agent_info, dict):
                        parsed_agent = {
                            "id": agent_info.get("id", f"agent_{i}"),
                            "name": agent_info.get("name", f"Agent {i+1}"),
                            "description": agent_info.get("description", "説明なし"),
                            "model": agent_info.get("model", "unknown"),
                            "path": agent_info.get("path", ""),
                            "url": agent_info.get(
                                "url",
                                f"{self.agent_server_url}/{agent_info.get('id', f'agent_{i}')}",
                            ),
                        }
                    else:
                        # その他の型の場合はスキップ
                        print(
                            f"DEBUG: Skipping unknown agent_info type: {type(agent_info)}"
                        )
                        continue

                    parsed_agents.append(parsed_agent)

            elif isinstance(agents_data, dict):
                # レスポンスがdict形式の場合
                for agent_id, agent_info in agents_data.items():
                    if isinstance(agent_info, str):
                        # 値が文字列の場合
                        parsed_agent = {
                            "id": agent_id,
                            "name": agent_id.replace("_", " ").title(),
                            "description": f"Agent: {agent_info}",
                            "model": "unknown",
                            "path": "",
                            "url": f"{self.agent_server_url}/{agent_id}",
                        }
                    elif isinstance(agent_info, dict):
                        # 値が辞書の場合
                        parsed_agent = {
                            "id": agent_id,
                            "name": agent_info.get("name", agent_id),
                            "description": agent_info.get("description", "説明なし"),
                            "model": agent_info.get("model", "unknown"),
                            "path": agent_info.get("path", ""),
                            "url": agent_info.get(
                                "url", f"{self.agent_server_url}/{agent_id}"
                            ),
                        }
                    else:
                        # agent_info が辞書でも文字列でもない場合
                        parsed_agent = {
                            "id": agent_id,
                            "name": agent_id.replace("_", " ").title(),
                            "description": f"Agent: {str(agent_info)}",
                            "model": "unknown",
                            "path": "",
                            "url": f"{self.agent_server_url}/{agent_id}",
                        }

                    parsed_agents.append(parsed_agent)
            else:
                print(f"DEBUG: Unknown agents_data format: {type(agents_data)}")

        except Exception as e:
            print(f"DEBUG: Error parsing agents response: {e}")
            print(f"DEBUG: Returning empty agent list")

        return parsed_agents

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """利用可能なAgent一覧を取得"""
        return self.dynamic_agents if self.dynamic_agents else []

    def create_agent_test_section(self) -> ft.Column:
        """Agent接続テスト部分のUIを作成"""
        # Agent カード一覧を作成
        self.agent_cards = []
        self.agent_cards_column = ft.Column([], spacing=10)

        # 動的に取得したAgentリストを使用
        agents_to_display = self.get_available_agents()

        self._populate_agent_cards(agents_to_display)

        # 全Agentテストボタン
        test_all_button = ft.ElevatedButton(
            "全Agent接続テスト",
            on_click=self.test_all_agents,
            bgcolor=ft.Colors.GREEN_600,
            color=ft.Colors.WHITE,
            width=150,
            height=32,
            icon=ft.Icons.PLAY_ARROW,
        )

        # Agentリスト再取得ボタン
        refresh_button = ft.ElevatedButton(
            "リスト更新",
            on_click=self.refresh_agents,
            bgcolor=ft.Colors.ORANGE_600,
            color=ft.Colors.WHITE,
            width=100,
            height=32,
            icon=ft.Icons.REFRESH,
        )

        # Agent接続テスト部分
        return ft.Column(
            [
                ft.Text("🤖 Agent接続テスト", size=14, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "セッション作成・確認でAgent接続状態を確認",
                    size=11,
                    color=ft.Colors.GREY_600,
                ),
                ft.Container(height=10),  # スペーサー
                self.agent_cards_column,
                ft.Container(height=10),  # スペーサー
                ft.Row(
                    [test_all_button, refresh_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                # テスト説明の追加
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("テスト項目:", size=11, weight=ft.FontWeight.BOLD),
                            ft.Text("• セッション作成（POST）", size=10),
                            ft.Text("• セッション確認（GET）", size=10),
                            ft.Text("• Agentサーバーとの通信確認", size=10),
                        ],
                        spacing=3,
                    ),
                    bgcolor=ft.Colors.BLUE_50,
                    padding=10,
                    border_radius=6,
                    border=ft.border.all(1, ft.Colors.BLUE_200),
                    margin=ft.margin.only(top=10),
                ),
            ],
            spacing=8,
        )

    def _populate_agent_cards(self, agents_to_display):
        """Agent cardsを作成してcolumnに追加"""
        self.agent_cards_column.controls.clear()

        # Agentが存在しない場合は、メッセージを表示
        if not agents_to_display:
            no_agents_message = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            name=ft.Icons.INFO_OUTLINE,
                            color=ft.Colors.GREY_500,
                            size=24,
                        ),
                        ft.Text(
                            "No agents available",
                            size=14,
                            color=ft.Colors.GREY_600,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "請使用「リスト更新」ボタンでagent serverの状態を確認してください",
                            size=10,
                            color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=5,
                ),
                bgcolor=ft.Colors.GREY_50,
                padding=20,
                border_radius=8,
                border=ft.border.all(1, ft.Colors.GREY_300),
                alignment=ft.alignment.center,
            )
            self.agent_cards_column.controls.append(no_agents_message)
            return

        for agent in agents_to_display:
            # Agentが辞書でない場合はスキップ
            if not isinstance(agent, dict):
                print(f"DEBUG: Skipping non-dict agent: {agent}")
                continue

            # Agent状態アイコン
            status_icon = ft.Icon(
                name=ft.Icons.CIRCLE, color=ft.Colors.GREY_400, size=16
            )

            # 接続情報表示エリア（初期状態） - ブラウザ固有のuser_idを表示
            browser_user_id = self.get_browser_user_id()
            connection_info = ft.Text(
                f"User: {browser_user_id} | Session: None",
                size=9,
                color=ft.Colors.GREY_500,
                visible=True,  # 最初から表示
            )

            # Agent情報表示（コンパクト版）
            agent_info = ft.Column(
                [
                    ft.Text(
                        agent.get("name", "Unknown Agent"),
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLACK87,
                    ),
                    ft.Text(
                        agent.get("description", "説明なし"),
                        size=10,
                        color=ft.Colors.GREY_600,
                    ),
                    connection_info,  # 接続情報を追加
                ],
                spacing=2,
            )

            # Agent IDを安全に取得
            agent_id = agent.get("id", f"unknown_{len(self.agent_cards)}")

            # テストボタン
            test_button = ft.ElevatedButton(
                "テスト",
                on_click=lambda e, aid=agent_id: self.test_agent_connection(aid),
                bgcolor=ft.Colors.BLUE_500,
                color=ft.Colors.WHITE,
                width=80,
                height=28,
            )

            # テスト結果表示エリア
            result_text = ft.Text(
                "未テスト", size=9, color=ft.Colors.GREY_600, visible=True
            )

            # Agent カード（コンパクト版）
            agent_card = ft.Container(
                content=ft.Row(
                    [
                        status_icon,
                        ft.Container(content=agent_info, expand=True),
                        ft.Column(
                            [test_button, result_text],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=3,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=10,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=12,
                border_radius=8,
                border=ft.border.all(1, ft.Colors.GREY_300),
                shadow=ft.BoxShadow(
                    spread_radius=0.5,
                    blur_radius=2,
                    color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                    offset=ft.Offset(0, 1),
                ),
            )

            # コンポーネントを保存（後でアクセスするため）
            agent_card_data = {
                "container": agent_card,
                "status_icon": status_icon,
                "test_button": test_button,
                "result_text": result_text,
                "connection_info": connection_info,  # 接続情報を追加
                "agent_id": agent_id,  # 安全に取得したagent_idを使用
            }
            self.agent_cards.append(agent_card_data)
            self.agent_cards_column.controls.append(agent_card)

    def test_agent_connection(self, agent_id: str):
        """個別Agentの接続テスト"""
        # 対象のAgentカードを取得
        agent_card = next(
            (card for card in self.agent_cards if card["agent_id"] == agent_id), None
        )
        if not agent_card:
            return

        # テスト中状態に更新
        agent_card["status_icon"].name = ft.Icons.HOURGLASS_EMPTY
        agent_card["status_icon"].color = ft.Colors.ORANGE_400
        agent_card["result_text"].value = "セッション作成中..."
        agent_card["result_text"].color = ft.Colors.ORANGE_600
        browser_user_id = self.get_browser_user_id()
        agent_card["connection_info"].value = (
            f"User: {browser_user_id} | Session: テスト中..."
        )
        agent_card["connection_info"].color = ft.Colors.ORANGE_600
        agent_card["test_button"].disabled = True

        if self.page:
            self.page.update()

        # 実際のAgent接続テストを実装
        try:
            # Agent情報を取得（動的Agentリストから）
            agents_to_use = self.get_available_agents()
            agent_info = next(
                (agent for agent in agents_to_use if agent.get("id") == agent_id), None
            )

            if not agent_info:
                raise ValueError(f"Agent not found: {agent_id}")

            print(f"DEBUG: Testing agent {agent_id}: {agent_info}")

            # サーバーベースのAgentの場合はセッション作成・確認でテスト
            if agent_info.get("url") or agent_id:
                try:
                    # ブラウザ固有のuser_idとテスト用のsession_idを生成
                    test_user_id = self.get_browser_user_id()
                    test_session_id = str(uuid.uuid4())

                    # セッション作成エンドポイント
                    session_url = f"{self.agent_server_url}/apps/{agent_id}/users/{test_user_id}/sessions/{test_session_id}"
                    print(f"DEBUG: Testing session creation at: {session_url}")

                    # セッション作成 (POST)
                    create_response = requests.post(session_url, json={}, timeout=5)
                    if create_response.status_code in [200, 201]:
                        print(f"DEBUG: Session created successfully")

                        # UI更新: セッション確認中
                        agent_card["result_text"].value = "セッション確認中..."
                        if self.page:
                            self.page.update()

                        # セッション確認 (GET)
                        check_response = requests.get(session_url, timeout=5)
                        if check_response.status_code == 200:
                            session_data = (
                                check_response.json() if check_response.content else {}
                            )
                            print(f"DEBUG: Session confirmed: {session_data}")

                            agent_card["status_icon"].name = ft.Icons.CHECK_CIRCLE
                            agent_card["status_icon"].color = ft.Colors.GREEN_500
                            # 接続情報を名前とボタンの間に表示（横並び）
                            agent_card["connection_info"].value = (
                                f"User: {test_user_id} | Session: {test_session_id}"
                            )
                            agent_card["connection_info"].color = ft.Colors.GREEN_700
                            # 右側の結果テキストは簡潔に
                            agent_card["result_text"].value = "接続成功"
                            agent_card["result_text"].color = ft.Colors.GREEN_600
                            self.test_results[agent_id] = {
                                "status": "success",
                                "message": f"セッション作成・確認成功",
                                "user_id": test_user_id,
                                "session_id": test_session_id,
                                "session_url": session_url,
                            }
                        else:
                            raise Exception(
                                f"セッション確認失敗: HTTP {check_response.status_code}"
                            )
                    else:
                        raise Exception(
                            f"セッション作成失敗: HTTP {create_response.status_code}"
                        )

                except requests.exceptions.RequestException as req_e:
                    print(f"DEBUG: Session test failed: {req_e}")
                    raise Exception(f"セッションテストエラー: {str(req_e)}")

            # ローカルファイルベースのAgentの場合
            elif agent_info.get("path"):
                try:
                    # ファイル存在確認
                    if not os.path.exists(agent_info["path"]):
                        raise FileNotFoundError(
                            f"Agent file not found: {agent_info['path']}"
                        )

                    # TODO: Context7 MCPを使った実際のテスト実装予定
                    # - Agent モジュールのimport
                    # - Agent インスタンスの生成
                    # - 簡単な応答テスト

                    agent_card["status_icon"].name = ft.Icons.CHECK_CIRCLE
                    agent_card["status_icon"].color = ft.Colors.GREEN_500
                    agent_card["connection_info"].value = (
                        f"User: Local | Session: File:{os.path.basename(agent_info['path'])}"
                    )
                    agent_card["connection_info"].color = ft.Colors.GREEN_700
                    agent_card["result_text"].value = "ローカル成功"
                    agent_card["result_text"].color = ft.Colors.GREEN_600
                    self.test_results[agent_id] = {
                        "status": "success",
                        "message": "ローカルファイル確認成功",
                    }
                except Exception as file_e:
                    print(f"DEBUG: File test failed: {file_e}")
                    raise Exception(f"ファイルエラー: {str(file_e)}")

            else:
                # URLもパスも指定されていない場合、基本的な存在確認のみ
                agent_card["status_icon"].name = ft.Icons.CHECK_CIRCLE
                agent_card["status_icon"].color = ft.Colors.YELLOW_600
                browser_user_id = self.get_browser_user_id()
                agent_card["connection_info"].value = (
                    f"User: {browser_user_id} | Session: Unknown"
                )
                agent_card["connection_info"].color = ft.Colors.YELLOW_600
                agent_card["result_text"].value = "情報不足"
                agent_card["result_text"].color = ft.Colors.YELLOW_600
                self.test_results[agent_id] = {
                    "status": "warning",
                    "message": "Agent情報が不完全",
                }

        except Exception as e:
            # テスト失敗
            print(f"DEBUG: Agent {agent_id} test failed: {e}")
            agent_card["status_icon"].name = ft.Icons.ERROR
            agent_card["status_icon"].color = ft.Colors.RED_500
            browser_user_id = self.get_browser_user_id()
            agent_card["connection_info"].value = (
                f"User: {browser_user_id} | Session: Error"
            )
            agent_card["connection_info"].color = ft.Colors.RED_500

            # エラーメッセージを短縮して表示
            error_msg = str(e)
            if "セッション" in error_msg:
                agent_card["result_text"].value = f"セッション失敗"
            elif "HTTP" in error_msg:
                agent_card["result_text"].value = f"接続失敗"
            else:
                agent_card["result_text"].value = f"エラー: {error_msg[:10]}..."

            agent_card["result_text"].color = ft.Colors.RED_600
            self.test_results[agent_id] = {"status": "error", "message": str(e)}

        finally:
            agent_card["test_button"].disabled = False
            if self.page:
                self.page.update()

    def test_all_agents(self, e):
        """全Agentの接続テスト"""
        try:
            agents_to_use = self.get_available_agents()
            print(f"DEBUG: Testing {len(agents_to_use)} agents")

            for agent in agents_to_use:
                if isinstance(agent, dict) and agent.get("id"):
                    self.test_agent_connection(agent["id"])
                else:
                    print(f"DEBUG: Skipping invalid agent: {agent}")

        except Exception as e:
            print(f"ERROR: Failed to test all agents: {e}")

    def refresh_agents(self, e):
        """Agentリストを再取得してUIを更新"""
        try:
            print("DEBUG: Refreshing agents...")

            # Agentリストを再取得
            self.fetch_agents_from_server()

            # Agent cards UIを再構築
            if self.agent_cards_column is not None:
                agents_to_display = self.get_available_agents()
                self._populate_agent_cards(agents_to_display)
                print(f"DEBUG: Updated UI with {len(agents_to_display)} agents")

                if self.page:
                    self.page.update()

            # UIコールバックがある場合は実行（SetupUIの更新など）
            if self.ui_refresh_callback:
                self.ui_refresh_callback()

            print("DEBUG: Agent refresh completed successfully")

        except Exception as e:
            print(f"ERROR: Failed to refresh agents: {e}")
            # エラーが発生した場合は空リストにフォールバック
            self.dynamic_agents = []

            # UIも空で更新
            if self.agent_cards_column is not None:
                self._populate_agent_cards([])
                if self.page:
                    self.page.update()

    def get_test_results(self) -> Dict[str, Dict[str, str]]:
        """テスト結果を取得"""
        return self.test_results
