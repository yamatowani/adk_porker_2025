"""
設定画面UI管理
"""

import flet as ft
from typing import List, Dict, Any, Callable
from .agent_manager import AgentManager

# 利用可能なLLMモデル定義
AVAILABLE_MODELS = [
    {
        "id": "gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite",
        "description": "高速・効率的",
    },
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "バランス型"},
]


class SetupUI:
    """設定画面UI管理クラス"""

    def __init__(self, on_game_start: Callable[[List[Dict[str, Any]]], None]):
        """
        Args:
            on_game_start: ゲーム開始時のコールバック関数
        """
        self.on_game_start = on_game_start
        self.page = None

        # UI コンポーネント
        self.setup_container = None
        self.cpu_type_dropdowns = []
        self.model_dropdowns = []
        self.player_settings_column = None

        # Agent管理機能
        self.agent_manager = AgentManager()

        # プレイヤー人数
        self.total_players = 4  # デフォルト4名（Human1 + CPU最大3名）
        self.total_players_dropdown = None

        # CPUコンテナ参照
        self.cpu_containers = []

    def initialize(self, page: ft.Page):
        """設定画面を初期化"""
        self.page = page
        self.agent_manager.set_page(page)
        self.agent_manager.set_ui_refresh_callback(self._refresh_agent_dropdowns)
        self.agent_manager.fetch_agents_from_server()
        self._init_setup_ui()

    def _init_setup_ui(self):
        """設定画面のUIコンポーネントを初期化"""
        # CPUタイプ選択用のドロップダウン
        self.cpu_type_dropdowns = []
        self.model_dropdowns = []
        self.agent_dropdowns = []  # Agent選択用のドロップダウンを追加

        # プレイヤー設定UIを作成（レスポンシブなグリッド表示）
        # 画面幅に応じて 1列（xs:12）/ 2列（sm:6）/ 3列（md:4）になる
        self.player_settings_column = ft.ResponsiveRow(
            controls=[],
            columns=12,
            spacing=10,
            run_spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
            expand=True,
        )

        # プレイヤー人数選択（2〜4）
        self.total_players_dropdown = ft.Dropdown(
            label="プレイヤー人数",
            width=200,
            options=[
                ft.dropdown.Option("2", "2"),
                ft.dropdown.Option("3", "3"),
                ft.dropdown.Option("4", "4"),
                ft.dropdown.Option("5", "5"),
                ft.dropdown.Option("6", "6"),
                ft.dropdown.Option("7", "7"),
                ft.dropdown.Option("8", "8"),
                ft.dropdown.Option("9", "9"),
                ft.dropdown.Option("10", "10"),
            ],
            value=str(self.total_players),
            on_change=self._on_total_players_changed,
        )

        for i in range(1, 10):  # CPU1 .. CPU9（最大10人=Human1+CPU9）
            # プレイヤータイプ選択
            type_dropdown = ft.Dropdown(
                label=f"CPU{i}のタイプ",
                width=None,
                expand=True,
                options=[
                    ft.dropdown.Option("random", "ランダムプレイヤー"),
                    ft.dropdown.Option("llm", "LLMプレイヤー(AI)"),
                    ft.dropdown.Option("llm_api", "Agent API プレイヤー"),
                ],
                value="random",
                on_change=lambda e, idx=i - 1: self._on_player_type_changed(e, idx),
            )
            self.cpu_type_dropdowns.append(type_dropdown)

            # モデル選択（最初は非表示）
            model_dropdown = ft.Dropdown(
                label=f"CPU{i}のモデル",
                width=None,
                expand=True,
                options=[
                    ft.dropdown.Option(
                        model["id"], f"{model['name']} - {model['description']}"
                    )
                    for model in AVAILABLE_MODELS
                ],
                value="gemini-2.5-flash-lite",
                visible=False,
            )
            self.model_dropdowns.append(model_dropdown)

            # Agent選択（最初は非表示）
            agent_dropdown = ft.Dropdown(
                label=f"CPU{i}のAgent",
                width=None,
                expand=True,
                options=[],  # 動的に更新される
                visible=False,
            )
            self.agent_dropdowns.append(agent_dropdown)

            # プレイヤー設定コンテナ
            player_container = ft.Container(
                content=ft.Column(
                    [type_dropdown, model_dropdown, agent_dropdown],
                    spacing=10,
                    expand=True,
                ),
                bgcolor=ft.Colors.GREY_50,
                padding=15,
                border_radius=8,
                border=ft.border.all(1, ft.Colors.GREY_300),
            )
            # レスポンシブ列幅を指定: xs=12(1列), sm=6(2列), md=4(3列)
            player_container.col = {"xs": 12, "sm": 6, "md": 4}
            self.player_settings_column.controls.append(player_container)
            self.cpu_containers.append(player_container)

        # Agent接続テスト部分を作成
        agent_test_section = self.agent_manager.create_agent_test_section()

        # 設定画面のコンテナ
        self.setup_container = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(
                            "🎰 ADK POKER - Texas Hold'em ゲーム設定 🎰",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        bgcolor=ft.Colors.GREEN_700,
                        padding=10,
                        border_radius=8,
                        margin=ft.margin.only(bottom=20),
                        alignment=ft.alignment.center,
                    ),
                    ft.Text(
                        "総プレイヤー人数と各CPUプレイヤーのタイプを選択してください",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "あなたは常にPlayer0として参加します",
                        size=12,
                        color=ft.Colors.GREY_600,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=20),  # スペーサー
                    # プレイヤー人数選択
                    ft.Row(
                        [self.total_players_dropdown],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Container(height=10),  # スペーサー
                    # CPU設定
                    ft.Column(
                        [
                            ft.Text(
                                "CPUプレイヤーの設定",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                            self.player_settings_column,
                        ],
                        spacing=10,
                    ),
                    ft.Container(height=30),  # スペーサー
                    # Agent接続テスト部分
                    agent_test_section,
                    ft.Container(height=30),  # スペーサー
                    # 説明テキスト
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "プレイヤータイプの説明:",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    "• ランダムプレイヤー: 重み付きランダムで行動するシンプルなAI",
                                    size=12,
                                ),
                                ft.Text(
                                    "• LLMプレイヤー(AI): Google ADKを使用した戦略的なAI",
                                    size=12,
                                ),
                                ft.Text(
                                    "  - 複数のモデルから選択可能（Gemini 2.5 Flash Lite、Gemini 2.5 Flash等）",
                                    size=11,
                                    color=ft.Colors.BLUE_700,
                                ),
                                ft.Text(
                                    "  - LLMプレイヤーを使用するにはGOOGLE_API_KEYが必要です",
                                    size=10,
                                    color=ft.Colors.GREY_600,
                                ),
                                ft.Text(
                                    "  - Agent接続テストでセッション作成・確認を実行します",
                                    size=10,
                                    color=ft.Colors.GREEN_700,
                                ),
                            ],
                            spacing=5,
                        ),
                        bgcolor=ft.Colors.BLUE_50,
                        padding=15,
                        border_radius=8,
                        border=ft.border.all(1, ft.Colors.BLUE_200),
                    ),
                    ft.Container(height=30),  # スペーサー
                    # ゲーム開始ボタン
                    ft.ElevatedButton(
                        "ゲーム開始",
                        on_click=self._start_game_with_settings,
                        bgcolor=ft.Colors.GREEN_600,
                        color=ft.Colors.WHITE,
                        width=200,
                        height=40,
                        icon=ft.Icons.PLAY_ARROW,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                scroll=ft.ScrollMode.AUTO,  # スクロール機能を有効化
                expand=True,
            ),  # 利用可能なスペースを使用
            padding=20,
            alignment=ft.alignment.center,
            expand=True,  # コンテナも拡張
        )

        # 初期可視状態を更新
        self._update_cpu_visibility()

    def _on_player_type_changed(self, e, player_index):
        """プレイヤータイプが変更されたときの処理"""
        selected_type = e.control.value
        model_dropdown = self.model_dropdowns[player_index]
        agent_dropdown = self.agent_dropdowns[player_index]

        if selected_type == "llm":
            # LLMが選択された場合、モデル選択を表示
            model_dropdown.visible = True
            agent_dropdown.visible = False
        elif selected_type == "llm_api":
            # Agent APIが選択された場合、Agent選択を表示
            model_dropdown.visible = False
            agent_dropdown.visible = True
            # 接続テスト成功済みのAgentでオプションを更新
            self._update_agent_options(agent_dropdown, player_index + 1)
        else:
            # ランダムが選択された場合、両方を非表示
            model_dropdown.visible = False
            agent_dropdown.visible = False

        if self.page:
            self.page.update()

    def _on_total_players_changed(self, e):
        """プレイヤー人数が変更されたときの処理"""
        try:
            self.total_players = max(2, min(10, int(e.control.value)))
        except Exception:
            self.total_players = 4
        self._update_cpu_visibility()
        if self.page:
            self.page.update()

    def _update_cpu_visibility(self):
        """選択された人数に応じてCPU設定の表示/非表示を切り替え"""
        cpu_needed = max(1, min(9, self.total_players - 1))
        for i, container in enumerate(self.cpu_containers):
            container.visible = i < cpu_needed

    def _update_agent_options(self, agent_dropdown: ft.Dropdown, cpu_number: int):
        """接続テスト成功済みのAgentでドロップダウンのオプションを更新"""
        # テスト結果から成功したAgentを取得
        test_results = self.agent_manager.get_test_results()
        successful_agents = []

        for agent_id, result in test_results.items():
            if result.get("status") == "success":
                # 成功したAgentを追加
                agent_info = next(
                    (
                        agent
                        for agent in self.agent_manager.get_available_agents()
                        if agent.get("id") == agent_id
                    ),
                    None,
                )
                if agent_info:
                    successful_agents.append(agent_info)

        # 成功したAgentがない場合は、全てのAgentを確認
        if not successful_agents:
            all_agents = self.agent_manager.get_available_agents()
            if all_agents:
                successful_agents = all_agents
            else:
                # Agentが全く存在しない場合は「Not Found」オプションを追加
                agent_dropdown.label = f"CPU{cpu_number}のAgent - Not Found"
                agent_dropdown.options = [
                    ft.dropdown.Option("not_found", "Not Found - No agents available")
                ]
                agent_dropdown.value = "not_found"
                agent_dropdown.disabled = True
                return

        # ドロップダウンのオプションを更新
        agent_dropdown.label = f"CPU{cpu_number}のAgent"
        agent_dropdown.options = [
            ft.dropdown.Option(
                agent.get("id", "unknown"),
                f"{agent.get('name', 'Unknown')} - {agent.get('description', 'No description')}",
            )
            for agent in successful_agents
        ]

        # ドロップダウンを有効化
        agent_dropdown.disabled = False

        # デフォルト値を設定（最初のAgentを選択）
        if agent_dropdown.options:
            agent_dropdown.value = agent_dropdown.options[0].key

    def _refresh_agent_dropdowns(self):
        """Agent refresh後にすべてのAgent dropdownを更新"""
        try:
            print("DEBUG: Refreshing agent dropdowns...")

            for i, agent_dropdown in enumerate(self.agent_dropdowns):
                # llm_api タイプが選択されているAgent dropdownのみ更新
                type_dropdown = self.cpu_type_dropdowns[i]
                if type_dropdown.value == "llm_api" and agent_dropdown.visible:
                    self._update_agent_options(agent_dropdown, i + 1)

            # UIを更新
            if self.page:
                self.page.update()
                print("DEBUG: Agent dropdowns refreshed successfully")

        except Exception as e:
            print(f"ERROR: Failed to refresh agent dropdowns: {e}")

    def _start_game_with_settings(self, e):
        """設定に基づいてゲームを開始"""
        # 設定を取得
        player_configs = [{"type": "human", "model": None}]  # プレイヤー0は常に人間

        cpu_needed = max(1, min(9, self.total_players - 1))
        for i, type_dropdown in enumerate(self.cpu_type_dropdowns[:cpu_needed]):
            config = {"type": type_dropdown.value}
            if type_dropdown.value == "llm":
                config["model"] = self.model_dropdowns[i].value
            elif type_dropdown.value == "llm_api":
                agent_id = self.agent_dropdowns[i].value
                if agent_id == "not_found":
                    # Agent が見つからない場合は、ランダムプレイヤーにフォールバック
                    config["type"] = "random"
                    config["model"] = None
                    print(
                        f"WARNING: Agent not available for CPU{i+1}, falling back to random player"
                    )
                else:
                    config["agent_id"] = agent_id
                    config["user_id"] = self.agent_manager.get_browser_user_id()
            else:
                config["model"] = None
            player_configs.append(config)

        # コールバック関数を呼び出してゲーム開始
        self.on_game_start(player_configs)

    def get_container(self) -> ft.Container:
        """設定画面のコンテナを取得"""
        return self.setup_container
