"""
ゲーム画面UI管理
"""

import math
import re
import flet as ft
from typing import Dict, Any, Optional, Callable, List, Tuple
import threading
from .game import PokerGame, GamePhase
from .player_models import Player, HumanPlayer, PlayerStatus
from .evaluator import HandEvaluator

# グローバルなUI更新ロック（複数スレッドからの同時更新を防止）
UI_UPDATE_LOCK = threading.RLock()


class GameUI:
    """ゲーム画面UI管理クラス"""

    def __init__(self, on_back_to_setup: Callable[[], None]):
        """
        Args:
            on_back_to_setup: 設定画面に戻るためのコールバック関数
        """
        self.on_back_to_setup = on_back_to_setup
        self.page = None
        self.game = None
        self.current_player_id = 0
        self.debug_messages = []

        # UI コンポーネント
        self.game_info_text = None
        self.community_cards_row = None
        self.your_cards_row = None
        self.action_buttons_row = None
        self.action_history_column = None
        self.status_text = None

        # レイズ額入力用のダイアログ
        self.raise_dialog = None
        self.raise_amount_field = None

        # フェーズ遷移用フラグ
        self.phase_transition_confirmed = False
        self.showdown_continue_confirmed = False
        # ベッティングラウンド完了後のフェーズ遷移確認を待機中かどうか
        self.is_waiting_phase_confirmation = False

        # テーブル関連
        self.table_width = 1050
        self.table_height = 520
        self.table_stack: Optional[ft.Stack] = None
        self.table_background: Optional[ft.Container] = None
        self.community_cards_holder: Optional[ft.Container] = None
        self.pot_text: Optional[ft.Text] = None
        self.pot_holder: Optional[ft.Container] = None
        self.table_title_text: Optional[ft.Text] = None
        self.table_status_text: Optional[ft.Text] = None

        # ショーダウン結果表示
        self.showdown_results_container: Optional[ft.Container] = (
            None  # legacy (no longer placed in layout)
        )
        self._showdown_results_column: Optional[ft.Column] = None
        self.showdown_overlay_container: Optional[ft.Container] = None
        self._showdown_results_panel: Optional[ft.Container] = None

        # ゲーム結果表示（ゲーム終了時の最終結果）
        self._final_results_column: Optional[ft.Column] = None
        self._final_results_panel: Optional[ft.Container] = None
        self.final_results_overlay_container: Optional[ft.Container] = None

    def initialize(self, page: ft.Page):
        """ゲーム画面を初期化"""
        self.page = page
        self._init_ui_components()

    def _init_ui_components(self):
        """UIコンポーネントを初期化"""
        # ゲーム情報
        self.game_info_text = ft.Text(
            "ゲームを開始しています...",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLACK,
        )

        # コミュニティカード（テーブル中央に配置するRow本体）
        self.community_cards_row = ft.Row(
            controls=[], alignment=ft.MainAxisAlignment.CENTER, spacing=10
        )

        # 自分の手札
        self.your_cards_row = ft.Row(
            controls=[], alignment=ft.MainAxisAlignment.CENTER, spacing=10
        )

        # アクションボタン
        self.action_buttons_row = ft.Row(
            controls=[], alignment=ft.MainAxisAlignment.CENTER, spacing=15
        )

        # アクション履歴
        self.action_history_column = ft.Column(
            controls=[], scroll=ft.ScrollMode.AUTO, expand=True
        )

        # ステータステキスト
        self.status_text = ft.Text("ゲーム開始待ち", size=13, color=ft.Colors.BLUE)

        # レイズ額入力ダイアログ
        self.raise_amount_field = ft.TextField(
            label="レイズ額", keyboard_type=ft.KeyboardType.NUMBER, width=200
        )

        self.raise_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("レイズ額を入力"),
            content=self.raise_amount_field,
            actions=[
                ft.TextButton("キャンセル", on_click=self._close_raise_dialog),
                ft.TextButton("OK", on_click=self._confirm_raise),
            ],
        )

        # ポーカーテーブル（楕円）構築
        self.table_background = ft.Container(
            width=self.table_width,
            height=self.table_height,
            bgcolor=ft.Colors.GREEN_700,
            border=ft.border.all(6, ft.Colors.GREEN_900),
            border_radius=int(self.table_height / 2),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=12,
                color=ft.Colors.GREY_500,
                offset=ft.Offset(0, 4),
            ),
        )

        # テーブルヘッダーテキスト
        self.table_title_text = ft.Text(
            "🃏 ポーカーテーブル",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        )
        self.table_status_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_500,
        )

        # テーブル中央のコミュニティカード位置（横中央寄せ）
        self.community_cards_holder = ft.Container(
            content=self.community_cards_row,
            width=self.table_width,
            left=0,
            top=int(self.table_height * 0.30),
            alignment=ft.alignment.center,
        )

        # ポット表示（視認性向上のため大きめ&濃色）
        self.pot_text = ft.Text(
            "💰 Pot: 0",
            size=22,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.AMBER_900,
        )
        self.pot_holder = ft.Container(
            content=ft.Container(
                content=self.pot_text,
                padding=ft.padding.symmetric(horizontal=14, vertical=8),
                border=ft.border.all(2, ft.Colors.AMBER_600),
                border_radius=24,
                bgcolor=ft.Colors.AMBER_50,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color=ft.Colors.AMBER_200,
                    offset=ft.Offset(0, 2),
                ),
            ),
            width=self.table_width,
            left=0,
            top=int(self.table_height * 0.52),
            alignment=ft.alignment.center,
        )

        # Stackにテーブルと中央要素を追加（座席は動的に追加）
        self.table_stack = ft.Stack(
            width=self.table_width,
            height=self.table_height,
            controls=[
                self.table_background,
                self.community_cards_holder,
                self.pot_holder,
            ],
        )

        # ショーダウン結果オーバーレイ（テーブル上に被せる、初期は非表示）
        self._showdown_results_column = ft.Column(controls=[], spacing=6)
        self._showdown_results_panel = ft.Container(
            content=self._showdown_results_column,
            padding=12,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=10,
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=10,
                color=ft.Colors.GREY_500,
                offset=ft.Offset(0, 4),
            ),
            width=520,
        )
        self.showdown_overlay_container = ft.Container(
            left=0,
            top=0,
            width=self.table_width,
            height=self.table_height,
            visible=False,
            content=ft.Container(
                width=self.table_width,
                height=self.table_height,
                bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
                alignment=ft.alignment.center,
                content=self._showdown_results_panel,
            ),
        )

        # 最終結果オーバーレイ
        self._final_results_column = ft.Column(controls=[], spacing=6)
        self._final_results_panel = ft.Container(
            content=self._final_results_column,
            padding=12,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=10,
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=10,
                color=ft.Colors.GREY_500,
                offset=ft.Offset(0, 4),
            ),
            width=520,
        )
        self.final_results_overlay_container = ft.Container(
            left=0,
            top=0,
            width=self.table_width,
            height=self.table_height,
            visible=False,
            content=ft.Container(
                width=self.table_width,
                height=self.table_height,
                bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.BLACK),
                alignment=ft.alignment.center,
                content=self._final_results_panel,
            ),
        )

    def set_game(self, game: PokerGame, current_player_id: int):
        """ゲームオブジェクトを設定"""
        self.game = game
        self.current_player_id = current_player_id

    def build_layout(self) -> ft.Column:
        """ゲーム画面のレイアウトを構築"""
        # メインコンテンツ
        main_content = ft.Column(
            [
                # タイトル
                ft.Container(
                    content=ft.Text(
                        "🎰 ADK POKER - Texas Hold'em 🎰",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.GREEN_700,
                    padding=8,
                    border_radius=8,
                    margin=ft.margin.only(bottom=10),
                    alignment=ft.alignment.center,
                ),
                # ゲーム情報
                ft.Container(
                    content=self.game_info_text,
                    bgcolor=ft.Colors.LIGHT_GREEN_50,
                    padding=12,
                    border=ft.border.all(2, ft.Colors.GREEN_400),
                    border_radius=8,
                    margin=ft.margin.only(bottom=12),
                    shadow=ft.BoxShadow(
                        spread_radius=1,
                        blur_radius=3,
                        color=ft.Colors.GREY_300,
                        offset=ft.Offset(0, 2),
                    ),
                ),
                # ポーカーテーブル（楕円テーブル + 座席）とアクション履歴を横並び
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(
                                content=ft.Row(
                                    [self.table_title_text, self.table_status_text],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                bgcolor=ft.Colors.GREEN_800,
                                padding=8,
                                border_radius=6,
                                margin=ft.margin.only(bottom=8),
                            ),
                            ft.Row(
                                [
                                    # テーブル（左）
                                    ft.Container(
                                        content=self.table_stack,
                                        alignment=ft.alignment.center,
                                    ),
                                    # アクション履歴（右）
                                    ft.Container(
                                        width=320,
                                        content=ft.Column(
                                            [
                                                ft.Text(
                                                    "アクション履歴",
                                                    size=14,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                                ft.Container(
                                                    content=self.action_history_column,
                                                    height=self.table_height - 20,
                                                    border=ft.border.all(
                                                        1, ft.Colors.GREY_400
                                                    ),
                                                    border_radius=5,
                                                    padding=8,
                                                ),
                                            ],
                                            spacing=5,
                                        ),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                                spacing=10,
                            ),
                        ],
                        spacing=0,
                    ),
                    padding=10,
                    margin=ft.margin.only(bottom=15),
                    bgcolor=ft.Colors.WHITE,
                    border=ft.border.all(1, ft.Colors.GREEN_200),
                    border_radius=10,
                    shadow=ft.BoxShadow(
                        spread_radius=1,
                        blur_radius=5,
                        color=ft.Colors.GREY_300,
                        offset=ft.Offset(0, 3),
                    ),
                ),
                # アクション履歴はテーブル右側に移動済み
                # ステータス
                ft.Container(content=self.status_text, margin=ft.margin.only(bottom=8)),
                # アクションボタン
                self.action_buttons_row,
            ],
            spacing=5,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        return main_content

    def get_raise_dialog(self) -> ft.AlertDialog:
        """レイズダイアログを取得"""
        return self.raise_dialog

    def _create_card_face(
        self,
        rank_text: str,
        suit_symbol: str,
        color,
        *,
        width: int,
        height: int,
        border_radius: int,
        suit_font_size: int,
        rank_font_size: int,
    ) -> ft.Container:
        """カードの表面を安定したレイアウトで生成する。

        スートは常に中央、ランクは上左/下右に配置して桁数やフェーズに依存しない視覚を保証する。
        """
        rank_row_height = int(rank_font_size * 1.2)
        top_row = ft.Row(
            [
                ft.Text(
                    rank_text,
                    size=rank_font_size,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                    no_wrap=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.CLIP,
                )
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        # スート記号のフォントサイズは固定して視覚の一貫性を保つ
        adjusted_suit_font_size = suit_font_size

        center_suit = ft.Container(
            content=ft.Text(
                suit_symbol,
                size=adjusted_suit_font_size,
                weight=ft.FontWeight.BOLD,
                color=color,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )

        bottom_row = ft.Row(
            [
                ft.Text(
                    rank_text,
                    size=rank_font_size,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                    no_wrap=True,
                    max_lines=1,
                    overflow=ft.TextOverflow.CLIP,
                )
            ],
            alignment=ft.MainAxisAlignment.END,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(content=top_row, height=rank_row_height),
                    center_suit,
                    ft.Container(content=bottom_row, height=rank_row_height),
                ],
                spacing=0,
                expand=True,
            ),
            width=width,
            height=height,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=border_radius,
            padding=ft.padding.only(left=4, right=4, top=2, bottom=2),
            alignment=ft.alignment.center,
        )

    def create_card_widget(self, card_str: str) -> ft.Container:
        """カード表示ウィジェットを作成"""
        if not card_str or card_str == "??":
            # 裏向きのカード
            return ft.Container(
                content=ft.Text("🂠", size=28),
                width=45,
                height=60,
                bgcolor=ft.Colors.BLUE_100,
                border=ft.border.all(1, ft.Colors.BLUE_300),
                border_radius=6,
                alignment=ft.alignment.center,
            )

        # 表示をランクとスートに分離して安定配置
        rank_text = card_str[:-1]
        suit_symbol = card_str[-1]
        color = ft.Colors.RED if suit_symbol in ["♥", "♦"] else ft.Colors.BLACK

        return self._create_card_face(
            rank_text,
            suit_symbol,
            color,
            width=45,
            height=60,
            border_radius=6,
            suit_font_size=20,
            rank_font_size=13,
        )

    def create_card_widget_small(self, card_str: str) -> ft.Container:
        """小さめのカード表示（座席用）"""
        if not card_str or card_str == "??":
            return ft.Container(
                content=ft.Text("🂠", size=22),
                width=40,
                height=48,
                bgcolor=ft.Colors.BLUE_100,
                border=ft.border.all(1, ft.Colors.BLUE_300),
                border_radius=5,
                alignment=ft.alignment.center,
            )

        suit_symbol = card_str[-1]
        rank_text = card_str[:-1]
        color = ft.Colors.RED if suit_symbol in ["♥", "♦"] else ft.Colors.BLACK

        return self._create_card_face(
            rank_text,
            suit_symbol,
            color,
            width=40,
            height=48,
            border_radius=5,
            suit_font_size=16,
            rank_font_size=11,
        )

    def create_card_widget_medium(self, card_str: str) -> ft.Container:
        """自分用の少し大きめカード表示（座席用）"""
        if not card_str or card_str == "??":
            return ft.Container(
                content=ft.Text("🂠", size=26),
                width=42,
                height=56,
                bgcolor=ft.Colors.BLUE_100,
                border=ft.border.all(1, ft.Colors.BLUE_300),
                border_radius=6,
                alignment=ft.alignment.center,
            )

        suit_symbol = card_str[-1]
        rank_text = card_str[:-1]
        color = ft.Colors.RED if suit_symbol in ["♥", "♦"] else ft.Colors.BLACK

        return self._create_card_face(
            rank_text,
            suit_symbol,
            color,
            width=42,
            height=56,
            border_radius=6,
            suit_font_size=18,
            rank_font_size=12,
        )

    def _create_badge(self, text: str, bg_color, fg_color) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=10, weight=ft.FontWeight.BOLD, color=fg_color),
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            bgcolor=bg_color,
            border_radius=50,
        )

    def _build_seat_controls(self) -> list:
        """座席を楕円上に配置したPositionedコントロール群を生成"""
        if not self.game:
            return []

        players = self.game.players or []
        n = len(players)
        if n == 0:
            return []

        seat_controls: List[ft.Control] = []
        cx, cy = self.table_width / 2, self.table_height / 2
        rx = self.table_width * 0.42
        ry = self.table_height * 0.36
        seat_w, seat_h = 170, 115

        for i, player in enumerate(players):
            theta = 2 * math.pi * i / n + math.pi / 2  # 下から時計回り
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)

            is_current_turn = player.id == self.game.current_player_index
            is_you = player.id == self.current_player_id

            # カード（自分だけ公開、他は裏）
            seat_cards = []
            if player.hole_cards:
                if is_you:
                    for c in player.hole_cards:
                        seat_cards.append(self.create_card_widget_medium(str(c)))
                else:
                    seat_cards = [
                        self.create_card_widget_small("??"),
                        self.create_card_widget_small("??"),
                    ]
            else:
                seat_cards = [
                    self.create_card_widget_small("??"),
                    self.create_card_widget_small("??"),
                ]

            # バッジ（D / SB / BB）
            badges = []
            if player.is_dealer:
                badges.append(
                    self._create_badge("D", ft.Colors.AMBER_400, ft.Colors.BLACK)
                )
            if player.is_small_blind:
                badges.append(
                    self._create_badge("SB", ft.Colors.BLUE_300, ft.Colors.BLACK)
                )
            if player.is_big_blind:
                badges.append(
                    self._create_badge("BB", ft.Colors.BLUE_600, ft.Colors.WHITE)
                )

            # ステータス色
            if player.status in (PlayerStatus.FOLDED, PlayerStatus.BUSTED):
                bg = ft.Colors.GREY_100
                border_color = ft.Colors.GREY_400
            elif player.status == PlayerStatus.ALL_IN:
                bg = ft.Colors.PURPLE_50
                border_color = ft.Colors.PURPLE_400
            elif is_current_turn:
                bg = ft.Colors.ORANGE_50
                border_color = ft.Colors.ORANGE_500
            elif is_you:
                bg = ft.Colors.LIGHT_BLUE_100
                border_color = ft.Colors.BLUE_600
            else:
                bg = ft.Colors.WHITE
                border_color = ft.Colors.GREY_400

            # 座席の中身（オーバーレイ適用前）
            seat_inner = ft.Container(
                width=seat_w,
                height=seat_h,
                bgcolor=bg,
                border=ft.border.all(
                    2 if is_current_turn or is_you else 1, border_color
                ),
                border_radius=10,
                padding=8,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=4,
                    color=ft.Colors.GREY_400,
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Column(
                    [
                        # カード行
                        ft.Row(
                            seat_cards, alignment=ft.MainAxisAlignment.CENTER, spacing=6
                        ),
                        # 名前 + バッジ
                        ft.Row(
                            [
                                ft.Text(
                                    player.name,
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=(
                                        ft.Colors.GREY_600
                                        if player.status
                                        in (PlayerStatus.FOLDED, PlayerStatus.BUSTED)
                                        else ft.Colors.BLACK
                                    ),
                                    style=(
                                        ft.TextStyle(
                                            decoration=ft.TextDecoration.LINE_THROUGH
                                        )
                                        if player.status
                                        in (PlayerStatus.FOLDED, PlayerStatus.BUSTED)
                                        else None
                                    ),
                                ),
                                ft.Row(badges, spacing=4),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        # チップとベット
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(
                                        f"{player.chips:,}",
                                        size=11,
                                        color=(
                                            ft.Colors.GREY_700
                                            if player.status
                                            in (
                                                PlayerStatus.FOLDED,
                                                PlayerStatus.BUSTED,
                                            )
                                            else ft.Colors.GREEN_700
                                        ),
                                    ),
                                    bgcolor=(
                                        ft.Colors.GREY_100
                                        if player.status
                                        in (PlayerStatus.FOLDED, PlayerStatus.BUSTED)
                                        else ft.Colors.GREEN_50
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=2
                                    ),
                                    border_radius=6,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        (
                                            f"Bet {player.current_bet}"
                                            if player.current_bet > 0
                                            else "Bet 0"
                                        ),
                                        size=11,
                                        color=(
                                            ft.Colors.GREY_600
                                            if player.status
                                            in (
                                                PlayerStatus.FOLDED,
                                                PlayerStatus.BUSTED,
                                            )
                                            else (
                                                ft.Colors.RED_600
                                                if player.current_bet > 0
                                                else ft.Colors.GREY_600
                                            )
                                        ),
                                    ),
                                    bgcolor=(
                                        ft.Colors.GREY_100
                                        if player.status
                                        in (PlayerStatus.FOLDED, PlayerStatus.BUSTED)
                                        else (
                                            ft.Colors.YELLOW_50
                                            if player.current_bet > 0
                                            else ft.Colors.GREY_50
                                        )
                                    ),
                                    padding=ft.padding.symmetric(
                                        horizontal=6, vertical=2
                                    ),
                                    border_radius=6,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=4,
                ),
            )

            # フォールド/バスト時の見やすいオーバーレイ
            if player.status in (PlayerStatus.FOLDED, PlayerStatus.BUSTED):
                overlay_text = (
                    "❌ フォールド"
                    if player.status == PlayerStatus.FOLDED
                    else "❌ バスト"
                )
                state_overlay = ft.Container(
                    width=seat_w,
                    height=seat_h,
                    bgcolor=ft.Colors.with_opacity(0.55, ft.Colors.GREY_200),
                    border_radius=10,
                    alignment=ft.alignment.center,
                    content=ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),
                        border=ft.border.all(1, ft.Colors.RED_400),
                        border_radius=20,
                        content=ft.Text(
                            overlay_text,
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.RED_700,
                        ),
                    ),
                )
                seat = ft.Stack(
                    width=seat_w, height=seat_h, controls=[seat_inner, state_overlay]
                )
            else:
                seat = seat_inner

            seat_controls.append(
                ft.Container(
                    left=int(x - seat_w / 2),
                    top=int(y - seat_h / 2),
                    content=seat,
                )
            )

        return seat_controls

    def _get_player_name(self, player_id: int) -> str:
        player = self.game.get_player(player_id) if self.game else None
        return player.name if player else f"Player {player_id}"

    def _create_amount_badge(self, amount: int, color_bg, color_fg) -> ft.Container:
        return ft.Container(
            content=ft.Text(
                f"{amount}", size=10, weight=ft.FontWeight.BOLD, color=color_fg
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            bgcolor=color_bg,
            border=ft.border.all(1, color_fg),
            border_radius=20,
        )

    def _create_action_badge(self, text: str, bg, fg) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=10, weight=ft.FontWeight.BOLD, color=fg),
            padding=ft.padding.symmetric(horizontal=8, vertical=3),
            bgcolor=bg,
            border_radius=20,
        )

    def _create_action_history_item(self, action_text: str) -> ft.Container:
        """ポーカー風のアクション履歴アイテムを構築"""
        # Player-based actions
        m = re.match(r"Player (\d+) folded", action_text)
        if m:
            pid = int(m.group(1))
            return ft.Container(
                bgcolor=ft.Colors.RED_50,
                border=ft.border.all(1, ft.Colors.RED_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "FOLD", ft.Colors.RED_200, ft.Colors.RED_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"Player (\d+) checked", action_text)
        if m:
            pid = int(m.group(1))
            return ft.Container(
                bgcolor=ft.Colors.BLUE_50,
                border=ft.border.all(1, ft.Colors.BLUE_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "CHECK", ft.Colors.BLUE_200, ft.Colors.BLUE_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"Player (\d+) called (\d+)", action_text)
        if m:
            pid = int(m.group(1))
            amt = int(m.group(2))
            return ft.Container(
                bgcolor=ft.Colors.GREEN_50,
                border=ft.border.all(1, ft.Colors.GREEN_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "CALL", ft.Colors.GREEN_200, ft.Colors.GREEN_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                        self._create_amount_badge(
                            amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"Player (\d+) raised to (\d+)", action_text)
        if m:
            pid = int(m.group(1))
            to_amt = int(m.group(2))
            return ft.Container(
                bgcolor=ft.Colors.ORANGE_50,
                border=ft.border.all(1, ft.Colors.ORANGE_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "RAISE", ft.Colors.ORANGE_200, ft.Colors.ORANGE_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                        self._create_amount_badge(
                            to_amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"Player (\d+) went all-in with (\d+)", action_text)
        if m:
            pid = int(m.group(1))
            amt = int(m.group(2))
            return ft.Container(
                bgcolor=ft.Colors.PURPLE_50,
                border=ft.border.all(1, ft.Colors.PURPLE_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "ALL-IN", ft.Colors.PURPLE_200, ft.Colors.PURPLE_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                        self._create_amount_badge(
                            amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"Player (\d+) posted small blind (\d+)", action_text)
        if m:
            pid = int(m.group(1))
            amt = int(m.group(2))
            return ft.Container(
                bgcolor=ft.Colors.CYAN_50,
                border=ft.border.all(1, ft.Colors.CYAN_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "SB", ft.Colors.CYAN_200, ft.Colors.CYAN_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                        self._create_amount_badge(
                            amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"Player (\d+) posted big blind (\d+)", action_text)
        if m:
            pid = int(m.group(1))
            amt = int(m.group(2))
            return ft.Container(
                bgcolor=ft.Colors.INDIGO_50,
                border=ft.border.all(1, ft.Colors.INDIGO_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "BB", ft.Colors.INDIGO_200, ft.Colors.INDIGO_900
                        ),
                        ft.Text(self._get_player_name(pid), weight=ft.FontWeight.BOLD),
                        self._create_amount_badge(
                            amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        # Community cards dealt
        m = re.match(r"Flop dealt: (.+)", action_text)
        if m:
            cards_str = m.group(1)
            cards = [s.strip() for s in cards_str.split(",")]
            return ft.Container(
                bgcolor=ft.Colors.LIGHT_GREEN_50,
                border=ft.border.all(1, ft.Colors.LIGHT_GREEN_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "FLOP", ft.Colors.GREEN_200, ft.Colors.GREEN_900
                        ),
                        ft.Row(
                            [self.create_card_widget_small(c) for c in cards], spacing=4
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )

        m = re.match(r"Turn dealt: (.+)", action_text)
        if m:
            c = m.group(1).strip()
            return ft.Container(
                bgcolor=ft.Colors.LIGHT_GREEN_50,
                border=ft.border.all(1, ft.Colors.LIGHT_GREEN_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "TURN", ft.Colors.GREEN_200, ft.Colors.GREEN_900
                        ),
                        self.create_card_widget_small(c),
                    ],
                    spacing=8,
                ),
            )

        m = re.match(r"River dealt: (.+)", action_text)
        if m:
            c = m.group(1).strip()
            return ft.Container(
                bgcolor=ft.Colors.LIGHT_GREEN_50,
                border=ft.border.all(1, ft.Colors.LIGHT_GREEN_200),
                border_radius=8,
                padding=6,
                content=ft.Row(
                    [
                        self._create_action_badge(
                            "RIVER", ft.Colors.GREEN_200, ft.Colors.GREEN_900
                        ),
                        self.create_card_widget_small(c),
                    ],
                    spacing=8,
                ),
            )

        # Fallback generic item
        return ft.Container(
            bgcolor=ft.Colors.GREY_50,
            border=ft.border.all(1, ft.Colors.GREY_200),
            border_radius=8,
            padding=6,
            content=ft.Text(action_text, size=10),
        )

    def create_player_info_widget(
        self, player: Player, is_current: bool = False
    ) -> ft.Container:
        """プレイヤー情報ウィジェットを作成（見やすく改良版）"""
        # 状態インジケーター
        status_indicators = []

        if player.is_dealer:
            status_indicators.append("ディーラー")
        if player.is_small_blind:
            status_indicators.append("SB")
        if player.is_big_blind:
            status_indicators.append("BB")

        # ステータスアイコンと色
        status_icon = ""
        status_color = ft.Colors.BLACK
        if is_current:
            status_icon = "🎯 現在のプレイヤー"
            status_color = ft.Colors.ORANGE
        elif player.status == PlayerStatus.FOLDED:
            status_icon = "❌ フォールド"
            status_color = ft.Colors.GREY_600
        elif player.status == PlayerStatus.ALL_IN:
            status_icon = "🎲 オールイン"
            status_color = ft.Colors.PURPLE
        elif player.status == PlayerStatus.BUSTED:
            status_icon = "💀 バスト"
            status_color = ft.Colors.RED
        else:
            status_icon = "✅ アクティブ"
            status_color = ft.Colors.GREEN

        # 背景色を決定
        if player.id == self.current_player_id:
            bgcolor = ft.Colors.LIGHT_BLUE_100
            border_color = ft.Colors.BLUE_600
            border_width = 3
        elif is_current:
            bgcolor = ft.Colors.ORANGE_100
            border_color = ft.Colors.ORANGE_600
            border_width = 2
        elif player.status == PlayerStatus.FOLDED:
            bgcolor = ft.Colors.GREY_100
            border_color = ft.Colors.GREY_400
            border_width = 1
        else:
            bgcolor = ft.Colors.WHITE
            border_color = ft.Colors.GREY_400
            border_width = 1

        # ベット額の表示と色分け（このラウンドとハンド累計）
        bet_text = ""
        bet_color = ft.Colors.BLACK
        total_bet_text = f"累計ベット: {player.total_bet_this_hand}"
        if player.status == PlayerStatus.ALL_IN and player.current_bet > 0:
            bet_text = f"オールイン: {player.current_bet}"
            bet_color = ft.Colors.PURPLE
        elif player.current_bet > 0:
            bet_text = f"ベット: {player.current_bet}"
            bet_color = ft.Colors.RED_600
        else:
            bet_text = "ベット: なし"
            bet_color = ft.Colors.GREY_600

        return ft.Container(
            content=ft.Column(
                [
                    # プレイヤー名
                    ft.Container(
                        content=ft.Text(
                            player.name,
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.BLACK,
                        ),
                        bgcolor=(
                            ft.Colors.WHITE
                            if player.id != self.current_player_id
                            else ft.Colors.LIGHT_BLUE_200
                        ),
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border_radius=4,
                        margin=ft.margin.only(bottom=4),
                    ),
                    # チップ残高
                    ft.Container(
                        content=ft.Text(
                            f"{player.chips:,}チップ",
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.GREEN_700,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.Colors.GREEN_50,
                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                        margin=ft.margin.only(bottom=4),
                    ),
                    # ベット額（このラウンド）
                    ft.Container(
                        content=ft.Text(
                            bet_text,
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                            color=bet_color,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=(
                            ft.Colors.YELLOW_50
                            if player.current_bet > 0
                            else ft.Colors.GREY_50
                        ),
                        padding=ft.padding.symmetric(horizontal=4, vertical=2),
                        border_radius=4,
                        margin=ft.margin.only(bottom=4),
                    ),
                    # ハンド累計ベット
                    ft.Container(
                        content=ft.Text(
                            total_bet_text,
                            size=10,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.BLUE_GREY,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.Colors.GREY_50,
                        padding=ft.padding.symmetric(horizontal=4, vertical=1),
                        border_radius=4,
                        margin=ft.margin.only(bottom=4),
                    ),
                    # ステータス
                    ft.Text(
                        status_icon,
                        size=9,
                        weight=ft.FontWeight.W_500,
                        text_align=ft.TextAlign.CENTER,
                        color=status_color,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    # ポジション表示
                    ft.Container(
                        content=ft.Text(
                            " | ".join(status_indicators) if status_indicators else " ",
                            size=9,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.BLUE_600,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.Colors.BLUE_50 if status_indicators else None,
                        padding=ft.padding.symmetric(horizontal=4, vertical=1),
                        border_radius=3,
                        alignment=ft.alignment.center,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=1,
            ),
            width=140,
            height=150,
            padding=8,
            margin=ft.margin.only(right=8),
            bgcolor=bgcolor,
            border=ft.border.all(border_width, border_color),
            border_radius=8,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=3,
                color=ft.Colors.GREY_300,
                offset=ft.Offset(0, 2),
            ),
        )

    def update_display(self):
        """画面表示を更新"""
        if not self.game:
            return
        with UI_UPDATE_LOCK:
            # ゲーム情報を更新
            phase_names = {
                GamePhase.PREFLOP: "プリフロップ",
                GamePhase.FLOP: "フロップ",
                GamePhase.TURN: "ターン",
                GamePhase.RIVER: "リバー",
                GamePhase.SHOWDOWN: "ショーダウン",
                GamePhase.FINISHED: "終了",
            }
            phase_name = phase_names.get(self.game.current_phase, "不明")

            # 上部情報バーは簡素化（ポット/現在のベットはテーブル上に表示するため除外）
            self.game_info_text.value = (
                f"🎯 ハンド #{self.game.hand_number} | 🎲 フェーズ: {phase_name}"
            )

            # コミュニティカードを更新
            self.community_cards_row.controls.clear()
            if self.game.community_cards:
                for card in self.game.community_cards:
                    self.community_cards_row.controls.append(
                        self.create_card_widget(str(card))
                    )
            else:
                self.community_cards_row.controls.append(
                    ft.Text("まだカードがありません", size=12, color=ft.Colors.WHITE)
                )

            # 中央のポット/ベット表示を更新
            if self.pot_text:
                self.pot_text.value = (
                    f"💰 Pot: {self.game.pot:,}   💵 Bet: {self.game.current_bet:,}"
                )

            # テーブルヘッダーのステータスはハンド/フェーズのみ
            if self.table_status_text:
                self.table_status_text.value = (
                    f"Hand #{self.game.hand_number}  •  {phase_name}"
                )

            # 座席（Stack上のPositioned）を更新
            if self.table_stack:
                base_controls = [
                    self.table_background,
                    self.community_cards_holder,
                    self.pot_holder,
                ]
                seat_controls = self._build_seat_controls()
                # None を除外
                base_controls = [c for c in base_controls if c is not None]
                # オーバーレイは最前面に配置する
                overlay_controls = []
                if getattr(self, "showdown_overlay_container", None):
                    overlay_controls.append(self.showdown_overlay_container)
                if getattr(self, "final_results_overlay_container", None):
                    overlay_controls.append(self.final_results_overlay_container)
                self.table_stack.controls = (
                    base_controls + seat_controls + overlay_controls
                )

            # 自分の手札を更新
            self.your_cards_row.controls.clear()
            player = self.game.get_player(self.current_player_id)
            if player and player.hole_cards:
                for card in player.hole_cards:
                    self.your_cards_row.controls.append(
                        self.create_card_widget(str(card))
                    )

                # 現在の最強ハンドを表示
                if len(self.game.community_cards) >= 3:
                    hand_result = HandEvaluator.evaluate_hand(
                        player.hole_cards, self.game.community_cards
                    )
                    hand_desc = HandEvaluator.get_hand_strength_description(hand_result)
                    self.your_cards_row.controls.append(
                        ft.Container(
                            content=ft.Text(
                                f"現在のハンド:\n{hand_desc}",
                                size=10,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            padding=5,
                            margin=ft.margin.only(left=10),
                        )
                    )
            else:
                self.your_cards_row.controls.append(
                    ft.Text("手札がありません", size=12, color=ft.Colors.GREY_600)
                )

            # アクション履歴を更新（全件・最新が上）
            self.action_history_column.controls.clear()
            all_actions_desc = (
                list(reversed(self.game.action_history))
                if self.game.action_history
                else []
            )
            for action in all_actions_desc:
                self.action_history_column.controls.append(
                    self._create_action_history_item(action)
                )

            # ページを更新
            if self.page:
                self.page.update()

    def update_action_buttons(self):
        """アクションボタンを更新"""
        with UI_UPDATE_LOCK:
            # フェーズ遷移のユーザー確認を待っている間は上書きしない
            if getattr(self, "is_waiting_phase_confirmation", False):
                return

            self.action_buttons_row.controls.clear()

            if not self.game or self.game.current_phase in [
                GamePhase.SHOWDOWN,
                GamePhase.FINISHED,
            ]:
                return

            current_player = self.game.players[self.game.current_player_index]
            if current_player.id != self.current_player_id or not isinstance(
                current_player, HumanPlayer
            ):
                self.status_text.value = (
                    f"{current_player.name} のターンです（AIプレイヤー）"
                )
                self.status_text.color = ft.Colors.ORANGE
                if self.page:
                    self.page.update()
                return

            if current_player.status != PlayerStatus.ACTIVE:
                return

            # 利用可能なアクションを取得
            try:
                game_state = self.game.get_llm_game_state(self.current_player_id)
                available_actions = game_state.actions
            except Exception:
                return

            self.status_text.value = "アクションを選択してください"
            self.status_text.color = ft.Colors.BLUE

            # アクションボタンを作成
            for action in available_actions:
                if action == "fold":
                    btn = ft.ElevatedButton(
                        "フォールド",
                        on_click=lambda e, a="fold": self.handle_action(a, 0),
                        bgcolor=ft.Colors.RED_400,
                        color=ft.Colors.WHITE,
                    )
                elif action == "check":
                    btn = ft.ElevatedButton(
                        "チェック",
                        on_click=lambda e, a="check": self.handle_action(a, 0),
                        bgcolor=ft.Colors.BLUE_400,
                        color=ft.Colors.WHITE,
                    )
                elif action.startswith("call"):
                    amount = int(action.split("(")[1].split(")")[0])
                    btn = ft.ElevatedButton(
                        f"コール ({amount})",
                        on_click=lambda e, a="call", amt=amount: self.handle_action(
                            a, amt
                        ),
                        bgcolor=ft.Colors.GREEN_400,
                        color=ft.Colors.WHITE,
                    )
                elif action.startswith("raise"):
                    min_amount = int(action.split("min ")[1].split(")")[0])
                    btn = ft.ElevatedButton(
                        f"レイズ (最低{min_amount})",
                        on_click=lambda e, min_amt=min_amount: self._show_raise_dialog(
                            min_amt
                        ),
                        bgcolor=ft.Colors.ORANGE_400,
                        color=ft.Colors.WHITE,
                    )
                elif action.startswith("all-in"):
                    amount = int(action.split("(")[1].split(")")[0])
                    btn = ft.ElevatedButton(
                        f"オールイン ({amount})",
                        on_click=lambda e, a="all_in", amt=amount: self.handle_action(
                            a, amt
                        ),
                        bgcolor=ft.Colors.PURPLE_400,
                        color=ft.Colors.WHITE,
                    )
                else:
                    continue

                self.action_buttons_row.controls.append(btn)

            if self.page:
                self.page.update()

    def _show_raise_dialog(self, min_amount: int):
        """レイズ額入力ダイアログを表示"""
        with UI_UPDATE_LOCK:
            self.raise_amount_field.value = str(min_amount)
            self.raise_amount_field.helper_text = f"最低 {min_amount} チップ"
            self.raise_dialog.open = True
            if self.page:
                self.page.update()

    def _close_raise_dialog(self, e):
        """レイズダイアログを閉じる"""
        with UI_UPDATE_LOCK:
            self.raise_dialog.open = False
            if self.page:
                self.page.update()

    def _confirm_raise(self, e):
        """レイズを確定"""
        with UI_UPDATE_LOCK:
            try:
                amount = int(self.raise_amount_field.value)
                self.raise_dialog.open = False
                if self.page:
                    self.page.update()
            except ValueError:
                self.raise_amount_field.error_text = "有効な数値を入力してください"
                if self.page:
                    self.page.update()
                return
        # handle_action は内部でロックを取る
        self.handle_action("raise", amount)

    def handle_action(self, action: str, amount: int):
        """プレイヤーアクションを処理"""
        if not self.game:
            return
        with UI_UPDATE_LOCK:
            success = self.game.process_player_action(
                self.current_player_id, action, amount
            )
            if not success:
                self.status_text.value = "無効なアクションです"
                self.status_text.color = ft.Colors.RED
            else:
                self.status_text.value = f"アクション実行: {action}"
                self.status_text.color = ft.Colors.GREEN
        self.update_display()
        self.update_action_buttons()

    def add_debug_message(self, message: str):
        """デバッグメッセージをログに出力（UIには表示しない）"""
        import datetime
        import logging

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        # 旧: UI表示用の保持はしない
        # self.debug_messages.append(f"[{timestamp}] {message}")
        # self.debug_messages = self.debug_messages[-5:]

        # ロガーを使用
        logger = logging.getLogger("poker_game")
        logger.debug(message)

    def show_phase_transition_confirmation(self):
        """次のフェーズに進む確認を表示"""
        with UI_UPDATE_LOCK:
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
                on_click=self._on_phase_transition_confirmed,
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

            # 確認待ちフラグを有効化（他の更新で消されないようにする）
            self.is_waiting_phase_confirmation = True

            # UIを更新
            if self.page:
                self.page.update()

    def _on_phase_transition_confirmed(self, e):
        """フェーズ遷移が確認された際の処理"""
        self.add_debug_message("Player confirmed phase transition")
        with UI_UPDATE_LOCK:
            self.phase_transition_confirmed = True
            # 確認待ち終了
            self.is_waiting_phase_confirmation = False
            # ボタンを削除
            self.action_buttons_row.controls.clear()
            self.status_text.value = "次のフェーズに進んでいます..."
            self.status_text.color = ft.Colors.GREEN
            # UIを更新
            if self.page:
                self.page.update()

    # ==== ショーダウン結果（インライン） ====
    def show_showdown_results_inline(self, results: Dict[str, Any]):
        """ショーダウン結果をインラインで表示し、下に「次のハンドへ」ボタンを配置する"""
        if not self._showdown_results_column or not self.showdown_overlay_container:
            return
        with UI_UPDATE_LOCK:
            self._showdown_results_column.controls.clear()

            # 見出し
            self._showdown_results_column.controls.append(
                ft.Text(
                    "🎉 ショーダウン結果",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLACK,
                )
            )

            # コミュニティカード（ショーダウン時の場札）
            try:
                community_cards = self.game.community_cards if self.game else []
            except Exception:
                community_cards = []

            if community_cards:
                self._showdown_results_column.controls.append(
                    ft.Text("コミュニティカード", size=12, weight=ft.FontWeight.W_600)
                )
                self._showdown_results_column.controls.append(
                    ft.Row(
                        [
                            self.create_card_widget_small(str(c))
                            for c in community_cards
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
                )

            # 各プレイヤーのハンド表示（あれば）
            all_hands = results.get("all_hands", [])
            if all_hands:
                self._showdown_results_column.controls.append(
                    ft.Text("各プレイヤーのハンド", size=12, weight=ft.FontWeight.W_600)
                )
                for hand_info in all_hands:
                    pid = hand_info.get("player_id")
                    player_name = self._get_player_name(pid)
                    cards = hand_info.get("cards", [])
                    hand_desc = hand_info.get("hand", "")

                    row = ft.Row(
                        [
                            ft.Text(player_name, size=12, weight=ft.FontWeight.BOLD),
                            ft.Row(
                                [self.create_card_widget_small(c) for c in cards],
                                spacing=4,
                            ),
                            ft.Text(hand_desc, size=11, color=ft.Colors.BLUE_GREY),
                        ],
                        spacing=10,
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                    self._showdown_results_column.controls.append(row)

            # 勝者と配当
            results_list = results.get("results", [])
            if results_list:
                winners_header = ft.Text("勝者", size=12, weight=ft.FontWeight.W_600)
                self._showdown_results_column.controls.append(winners_header)

                for r in results_list:
                    pid = r.get("player_id")
                    winnings = r.get("winnings", 0)
                    hand_desc = r.get("hand", "")
                    player_name = self._get_player_name(pid)

                    winner_row = ft.Row(
                        [
                            ft.Text("🏆", size=14),
                            ft.Text(player_name, size=12, weight=ft.FontWeight.BOLD),
                            self._create_amount_badge(
                                winnings, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                            ),
                            ft.Text(hand_desc, size=11, color=ft.Colors.BLUE_GREY),
                        ],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                    self._showdown_results_column.controls.append(winner_row)

            # 次のハンドへボタン
            next_button = ft.ElevatedButton(
                text="次のハンドへ",
                on_click=self._on_showdown_continue_confirmed,
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
            )
            self._showdown_results_column.controls.append(
                ft.Container(
                    content=next_button,
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(top=6),
                )
            )

            # 表示（テーブル上オーバーレイを表示）
            self.showdown_overlay_container.visible = True
            if self.page:
                self.page.update()

    def clear_showdown_results_inline(self):
        """ショーダウン結果のインライン表示をクリア"""
        if not self._showdown_results_column or not self.showdown_overlay_container:
            return
        with UI_UPDATE_LOCK:
            self._showdown_results_column.controls.clear()
            self.showdown_overlay_container.visible = False
            if self.page:
                self.page.update()

    def _on_showdown_continue_confirmed(self, e):
        """ショーダウン後の『次のハンドへ』が押された"""
        self.add_debug_message("Player confirmed next hand after showdown")
        self.showdown_continue_confirmed = True
        # 見た目上はすぐに非表示にする
        self.clear_showdown_results_inline()

    # ==== ゲーム終了・最終結果表示 ====
    def show_final_results(self):
        """ゲーム終了時の最終結果をテーブル上のオーバーレイで表示する"""
        if not self._final_results_column or not self.final_results_overlay_container:
            return
        with UI_UPDATE_LOCK:
            self._final_results_column.controls.clear()

            # 見出し
            self._final_results_column.controls.append(
                ft.Text(
                    "🏁 ゲーム結果",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLACK,
                )
            )

            # 順位表（所持チップの多い順）
            standings = []
            try:
                standings = sorted(
                    self.game.players, key=lambda p: p.chips, reverse=True
                )
            except Exception:
                standings = []

            if standings:
                # 勝者
                winner = standings[0]
                self._final_results_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text(
                                    "🏆 WINNER", size=14, weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    winner.name, size=14, weight=ft.FontWeight.BOLD
                                ),
                                self._create_amount_badge(
                                    winner.chips,
                                    ft.Colors.AMBER_50,
                                    ft.Colors.AMBER_800,
                                ),
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=6,
                        bgcolor=ft.Colors.AMBER_50,
                        border=ft.border.all(1, ft.Colors.AMBER_200),
                        border_radius=8,
                        margin=ft.margin.only(bottom=6),
                    )
                )

                # 全プレイヤー順位
                self._final_results_column.controls.append(
                    ft.Text("最終順位", size=12, weight=ft.FontWeight.W_600)
                )
                for rank, p in enumerate(standings, start=1):
                    row = ft.Row(
                        [
                            ft.Text(f"#{rank}", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(p.name, size=12),
                            self._create_amount_badge(
                                p.chips, ft.Colors.GREY_50, ft.Colors.GREY_800
                            ),
                        ],
                        spacing=10,
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                    self._final_results_column.controls.append(row)

            # 終了ボタン（設定画面へ戻る）
            back_button = ft.ElevatedButton(
                text="設定画面に戻る",
                on_click=lambda e: (
                    self.on_back_to_setup() if callable(self.on_back_to_setup) else None
                ),
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
            )
            self._final_results_column.controls.append(
                ft.Container(
                    content=back_button,
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(top=8),
                )
            )

            # 表示
            self.final_results_overlay_container.visible = True
            if self.page:
                self.page.update()

    def clear_final_results(self):
        """最終結果の表示をクリア"""
        if not self._final_results_column or not self.final_results_overlay_container:
            return
        with UI_UPDATE_LOCK:
            self._final_results_column.controls.clear()
            self.final_results_overlay_container.visible = False
            if self.page:
                self.page.update()
