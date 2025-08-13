"""
Spectator (viewer) UI for ADK Poker.

This UI displays the full table status with all players' hole cards face-up.
It is read-only and periodically polls the shared game state.
"""

from __future__ import annotations

import asyncio
import math
from typing import List, Optional
import flet as ft
import os
import requests
import re


class PokerViewerUI:
    def __init__(self):
        self.page: Optional[ft.Page] = None
        self.table_width = 1050
        self.table_height = 520
        # Viewer fetches JSON state from main process HTTP endpoint
        self.state_url = os.environ.get(
            "ADK_POKER_STATE_URL", "http://127.0.0.1:8765/state"
        )
        self._last_state: Optional[dict] = None

        # Root controls
        self.game_info_text: Optional[ft.Text] = None
        self.community_cards_row: Optional[ft.Row] = None
        self.action_history_column: Optional[ft.Column] = None
        self.table_stack: Optional[ft.Stack] = None
        self.table_background: Optional[ft.Container] = None
        self.community_cards_holder: Optional[ft.Container] = None
        self.pot_text: Optional[ft.Text] = None
        self.pot_holder: Optional[ft.Container] = None
        self.table_title_text: Optional[ft.Text] = None
        self.table_status_text: Optional[ft.Text] = None
        self.llm_agents_grid: Optional[ft.Row] = None
        self.llm_agents_row: Optional[ft.Row] = None

    # --- UI helpers -----------------------------------------------------
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

    def _create_card_small(self, card_str: str) -> ft.Container:
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

    def _create_badge(self, text: str, bg_color, fg_color) -> ft.Container:
        return ft.Container(
            content=ft.Text(text, size=10, weight=ft.FontWeight.BOLD, color=fg_color),
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            bgcolor=bg_color,
            border_radius=50,
        )

    def _get_player_name(self, player_id: int) -> str:
        state = self._last_state or {}
        for p in state.get("players", []):
            try:
                if int(p.get("id")) == int(player_id):
                    return str(p.get("name", f"Player {player_id}"))
            except Exception:
                continue
        return f"Player {player_id}"

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
        # Player folded
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
                        ft.Text(
                            self._get_player_name(pid),
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=8,
                ),
            )

        # Player checked
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
                        ft.Text(
                            self._get_player_name(pid),
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=8,
                ),
            )

        # Player called X
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
                        ft.Text(
                            self._get_player_name(pid),
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        self._create_amount_badge(
                            amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        # Player raised to X
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
                        ft.Text(
                            self._get_player_name(pid),
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        self._create_amount_badge(
                            to_amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        # Player went all-in with X
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
                        ft.Text(
                            self._get_player_name(pid),
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        self._create_amount_badge(
                            amt, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                        ),
                    ],
                    spacing=8,
                ),
            )

        # Small blind
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

        # Big blind
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

        # Flop dealt
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
                        ft.Row([self._create_card_small(c) for c in cards], spacing=4),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )

        # Turn dealt
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
                        self._create_card_small(c),
                    ],
                    spacing=8,
                ),
            )

        # River dealt
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
                        self._create_card_small(c),
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
            content=ft.Text(
                action_text,
                size=10,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        )

    def _create_llm_agent_card(self, agent: dict) -> ft.Container:
        name = str(agent.get("name", "Agent"))
        action = str(agent.get("action", "")).lower()
        amount = int(agent.get("amount", 0) or 0)
        reasoning = str(agent.get("reasoning", "")).strip()

        # Build action row
        row_items: List[ft.Control] = []
        if action == "fold":
            row_items.append(
                self._create_action_badge("FOLD", ft.Colors.RED_200, ft.Colors.RED_900)
            )
        elif action == "check":
            row_items.append(
                self._create_action_badge(
                    "CHECK", ft.Colors.BLUE_200, ft.Colors.BLUE_900
                )
            )
        elif action == "call":
            row_items.append(
                self._create_action_badge(
                    "CALL", ft.Colors.GREEN_200, ft.Colors.GREEN_900
                )
            )
        elif action == "raise":
            row_items.append(
                self._create_action_badge(
                    "RAISE", ft.Colors.ORANGE_200, ft.Colors.ORANGE_900
                )
            )
        elif action in ("all_in", "all-in"):
            row_items.append(
                self._create_action_badge(
                    "ALL-IN", ft.Colors.PURPLE_200, ft.Colors.PURPLE_900
                )
            )

        if amount > 0:
            row_items.append(
                self._create_amount_badge(
                    amount, ft.Colors.AMBER_50, ft.Colors.AMBER_800
                )
            )
        if not row_items:
            row_items.append(ft.Text("—", size=10, color=ft.Colors.GREY_500))

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        name,
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row(row_items, spacing=6),
                    ft.Container(
                        content=ft.Text(
                            reasoning if reasoning else "(理由なし)",
                            size=11,
                            color=ft.Colors.GREY_800,
                            max_lines=6,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        bgcolor=ft.Colors.WHITE,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        border_radius=6,
                        padding=6,
                    ),
                ],
                spacing=6,
            ),
            width=260,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            padding=10,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=4,
                color=ft.Colors.GREY_200,
                offset=ft.Offset(0, 2),
            ),
        )

    # --- Build & update --------------------------------------------------
    def _init_ui(self):
        self.game_info_text = ft.Text(
            "観戦ビューを待機中...",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.BLACK,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.community_cards_row = ft.Row(
            controls=[], alignment=ft.MainAxisAlignment.CENTER, spacing=10
        )

        self.action_history_column = ft.Column(
            controls=[], scroll=ft.ScrollMode.AUTO, expand=True
        )

        # Viewer-only: LLM API agents latest decisions (responsive wrap)
        self.llm_agents_grid = ft.Row(
            controls=[], wrap=True, spacing=10, run_spacing=10
        )

        # Viewer-only: LLM API agents latest decision panel
        self.llm_agents_row = ft.Row(controls=[], spacing=10)

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

        self.table_title_text = ft.Text(
            "👀 ポーカーテーブル（観戦）",
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        )
        self.table_status_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_500,
            no_wrap=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.community_cards_holder = ft.Container(
            content=self.community_cards_row,
            width=self.table_width,
            left=0,
            top=int(self.table_height * 0.30),
            alignment=ft.alignment.center,
        )

        self.pot_text = ft.Text(
            "💰 Pot: 0", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_900
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

        self.table_stack = ft.Stack(
            width=self.table_width,
            height=self.table_height,
            controls=[
                self.table_background,
                self.community_cards_holder,
                self.pot_holder,
            ],
        )

    def _build_layout(self) -> ft.Column:
        header = ft.Container(
            content=ft.Text(
                "🎥 ADK POKER - Viewer",
                size=20,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
            bgcolor=ft.Colors.GREEN_700,
            padding=8,
            border_radius=8,
            margin=ft.margin.only(bottom=10),
            alignment=ft.alignment.center,
        )

        table_area = ft.Container(
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
                            ft.Container(
                                content=self.table_stack, alignment=ft.alignment.center
                            ),
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
                                            border=ft.border.all(1, ft.Colors.GREY_400),
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
        )

        return ft.Column(
            [
                header,
                ft.Container(
                    content=self.game_info_text,
                    bgcolor=ft.Colors.LIGHT_GREEN_50,
                    padding=12,
                    border=ft.border.all(2, ft.Colors.GREEN_400),
                    border_radius=8,
                    margin=ft.margin.only(bottom=12),
                ),
                table_area,
                # LLM API Agents latest decisions under the board
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "LLMエージェントの最新判断",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Container(content=self.llm_agents_grid),
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.GREY_50,
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=6,
                ),
            ],
            spacing=5,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _build_seat_controls(self) -> List[ft.Control]:
        state = self._last_state or {}
        players = state.get("players", [])
        n = len(players)
        if n == 0:
            return []

        seat_controls: List[ft.Control] = []
        cx, cy = self.table_width / 2, self.table_height / 2
        rx = self.table_width * 0.42
        ry = self.table_height * 0.36
        seat_w, seat_h = 170, 115

        for i, player in enumerate(players):
            theta = 2 * math.pi * i / n + math.pi / 2
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)

            # Show hole cards face-up in viewer
            seat_cards = []
            hole_cards = player.get("hole_cards", [])
            if hole_cards:
                for c in hole_cards:
                    seat_cards.append(self._create_card_small(str(c)))
            else:
                seat_cards = [
                    self._create_card_small("??"),
                    self._create_card_small("??"),
                ]

            # Badges
            badges = []
            if player.get("is_dealer"):
                badges.append(
                    self._create_badge("D", ft.Colors.AMBER_400, ft.Colors.BLACK)
                )
            if player.get("is_small_blind"):
                badges.append(
                    self._create_badge("SB", ft.Colors.BLUE_300, ft.Colors.BLACK)
                )
            if player.get("is_big_blind"):
                badges.append(
                    self._create_badge("BB", ft.Colors.BLUE_600, ft.Colors.WHITE)
                )

            # Status background (normalize and fallback)
            status = str(player.get("status", "")).lower()
            if status in ("bust", "busted_out"):
                status = "busted"
            if not status and int(player.get("chips", 0) or 0) <= 0:
                status = "busted"
            if status in ("folded", "busted"):
                bg = ft.Colors.GREY_100
                border_color = ft.Colors.GREY_400
            elif status == "all_in":
                bg = ft.Colors.PURPLE_50
                border_color = ft.Colors.PURPLE_400
            else:
                bg = ft.Colors.WHITE
                border_color = ft.Colors.GREY_400

            # seat inner content
            seat_inner = ft.Container(
                width=seat_w,
                height=seat_h,
                bgcolor=bg,
                border=ft.border.all(1, border_color),
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
                        ft.Row(
                            seat_cards, alignment=ft.MainAxisAlignment.CENTER, spacing=6
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    player.get("name", f"P{i}"),
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=(
                                        ft.Colors.GREY_600
                                        if status in ("folded", "busted")
                                        else ft.Colors.BLACK
                                    ),
                                    style=(
                                        ft.TextStyle(
                                            decoration=ft.TextDecoration.LINE_THROUGH
                                        )
                                        if status in ("folded", "busted")
                                        else None
                                    ),
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(badges, spacing=4),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text(
                                        f"{player.get('chips', 0):,}",
                                        size=11,
                                        color=(
                                            ft.Colors.GREY_700
                                            if status in ("folded", "busted")
                                            else ft.Colors.GREEN_700
                                        ),
                                    ),
                                    bgcolor=(
                                        ft.Colors.GREY_100
                                        if status in ("folded", "busted")
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
                                            f"Bet {player.get('current_bet', 0)}"
                                            if player.get("current_bet", 0) > 0
                                            else "Bet 0"
                                        ),
                                        size=11,
                                        color=(
                                            ft.Colors.GREY_600
                                            if status in ("folded", "busted")
                                            else (
                                                ft.Colors.RED_600
                                                if player.get("current_bet", 0) > 0
                                                else ft.Colors.GREY_600
                                            )
                                        ),
                                    ),
                                    bgcolor=(
                                        ft.Colors.GREY_100
                                        if status in ("folded", "busted")
                                        else (
                                            ft.Colors.YELLOW_50
                                            if player.get("current_bet", 0) > 0
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

            if status in ("folded", "busted"):
                overlay_text = "❌ フォールド" if status == "folded" else "❌ バスト"
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
                    left=int(x - seat_w / 2), top=int(y - seat_h / 2), content=seat
                )
            )

        return seat_controls

    def _phase_name(self, phase_value: str) -> str:
        names = {
            "preflop": "プリフロップ",
            "flop": "フロップ",
            "turn": "ターン",
            "river": "リバー",
            "showdown": "ショーダウン",
            "finished": "終了",
        }
        return names.get(phase_value, "不明")

    def update_display(self):
        state = self._last_state
        if not state or not state.get("ready"):
            self.game_info_text.value = (
                "ゲーム待機中... プレイヤーUIでゲーム開始してください"
            )
            if self.page:
                self.page.update()
            return

        # Info bar
        phase_name = self._phase_name(state.get("phase", ""))
        self.game_info_text.value = (
            f"🎯 ハンド #{state.get('hand_number', 0)} | 🎲 フェーズ: {phase_name}"
        )

        # Community cards
        self.community_cards_row.controls.clear()
        community = state.get("community_cards", [])
        if community:
            for card in community:
                self.community_cards_row.controls.append(
                    self._create_card_small(str(card))
                )
        else:
            self.community_cards_row.controls.append(
                ft.Text("まだカードがありません", size=12, color=ft.Colors.WHITE)
            )

        # Pot / Bet
        if self.pot_text:
            pot = state.get("pot", 0)
            current_bet = state.get("current_bet", 0)
            self.pot_text.value = f"💰 Pot: {pot:,}   💵 Bet: {current_bet:,}"

        # Header status
        if self.table_status_text:
            self.table_status_text.value = (
                f"Hand #{state.get('hand_number', 0)}  •  {phase_name}"
            )

        # Seats
        if self.table_stack:
            base_controls = [
                self.table_background,
                self.community_cards_holder,
                self.pot_holder,
            ]
            base_controls = [c for c in base_controls if c is not None]
            self.table_stack.controls = base_controls + self._build_seat_controls()

        # Action history (latest first) - styled same as game_ui
        self.action_history_column.controls.clear()
        actions = state.get("action_history", [])
        all_actions_desc = list(reversed(actions)) if actions else []
        for action in all_actions_desc:
            self.action_history_column.controls.append(
                self._create_action_history_item(action)
            )

        # LLM API Agents panel (latest decisions) - responsive wrap
        if self.llm_agents_grid is not None:
            self.llm_agents_grid.controls.clear()
            agents = state.get("llm_api_agents", []) or []
            for agent in agents:
                self.llm_agents_grid.controls.append(self._create_llm_agent_card(agent))

        if self.page:
            self.page.update()

    async def _poll_loop(self):
        while True:
            try:
                # Fetch state from HTTP server hosted by main process
                try:
                    resp = requests.get(self.state_url, timeout=1.0)
                    if resp.ok:
                        self._last_state = resp.json()
                    else:
                        self._last_state = {"ready": False}
                except Exception:
                    self._last_state = {"ready": False}

                self.update_display()
                await asyncio.sleep(0.5)
            except Exception:
                # Avoid breaking the loop on transient errors
                await asyncio.sleep(0.5)

    # --- Flet entry ------------------------------------------------------
    def main(self, page: ft.Page):
        self.page = page
        page.title = "ADK Poker - Viewer"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 10
        page.window.width = 1400
        page.window.height = 900

        self._init_ui()
        layout = self._build_layout()
        page.add(layout)
        page.update()

        # Start polling JSON state periodically
        page.run_task(self._poll_loop)


def run_flet_viewer_app(port: int = 8552):
    ui = PokerViewerUI()
    ft.app(target=ui.main, view=ft.AppView.WEB_BROWSER, port=port)


async def run_flet_viewer_app_async(port: int = 8552):
    ui = PokerViewerUI()
    await ft.app_async(target=ui.main, view=ft.AppView.WEB_BROWSER, port=port)
