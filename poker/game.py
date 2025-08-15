"""
Texas Hold'em Poker Game Management
"""

import json
import random
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

from .game_models import Deck, GamePhase, GameState, PlayerInfo
from .player_models import (
    Player,
    HumanPlayer,
    RandomPlayer,
    LLMPlayer,
    LLMApiPlayer,
    PlayerStatus,
)
from .evaluator import HandEvaluator, HandResult

# ゲーム専用のロガーを設定
game_logger = logging.getLogger("poker_game")
game_logger.setLevel(logging.DEBUG)

# ハンドラーが既に存在しない場合のみ追加
if not game_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    game_logger.addHandler(handler)


class PokerGame:
    """テキサスホールデムゲーム管理クラス"""

    def __init__(
        self, small_blind: int = 10, big_blind: int = 20, initial_chips: int = 2000
    ):
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.initial_chips = initial_chips

        # プレイヤー管理
        self.players: List[Player] = []
        self.dealer_button = 0
        self.current_player_index = 0

        # ゲーム状態
        self.deck = Deck()
        self.community_cards = []
        self.current_phase = GamePhase.PREFLOP
        self.pot = 0
        self.current_bet = 0  # 現在の最高ベット額
        self.hand_number = 0

        # ベッティング管理
        self.betting_round_complete = False
        self.last_raiser_index = None
        # このベッティングラウンドでブラインド以外の「ベット/レイズ」が発生したか
        self.has_bet_or_raise_this_round = False

        # アクション履歴
        self.action_history = []

        # ゲーム統計
        self.game_stats = {"hands_played": 0, "players_eliminated": []}

        # 最後に実行したショーダウン結果（観戦UI向けに公開するため）
        self.last_showdown_results: Optional[Dict[str, Any]] = None

        game_logger.info(
            "PokerGame initialized with SB=%d, BB=%d, initial_chips=%d",
            small_blind,
            big_blind,
            initial_chips,
        )

    def add_player(self, player: Player):
        """プレイヤーを追加"""
        if len(self.players) >= 10:
            raise ValueError("Maximum 10 players allowed")
        self.players.append(player)

    def get_player(self, player_id: int) -> Optional[Player]:
        """プレイヤーIDでプレイヤーを取得"""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def setup_default_game(self):
        """デフォルトの4人ゲームをセットアップ"""
        self.add_player(HumanPlayer(0, "You", self.initial_chips))
        self.add_player(RandomPlayer(1, "CPU1", self.initial_chips))
        self.add_player(RandomPlayer(2, "CPU2", self.initial_chips))
        self.add_player(RandomPlayer(3, "CPU3", self.initial_chips))

        # ディーラーボタンをランダムに決定
        self.dealer_button = random.randint(0, 3)

    def setup_cpu_only_game(self):
        """全プレイヤーがCPU（ランダム）の4人ゲームをセットアップ"""
        self.add_player(RandomPlayer(0, "CPU0", self.initial_chips))
        self.add_player(RandomPlayer(1, "CPU1", self.initial_chips))
        self.add_player(RandomPlayer(2, "CPU2", self.initial_chips))
        self.add_player(RandomPlayer(3, "CPU3", self.initial_chips))

        # ディーラーボタンをランダムに決定
        self.dealer_button = random.randint(0, 3)

    def setup_configurable_game(self, player_types: List[str]):
        """
        カスタマイズ可能なゲームをセットアップ（2〜4人）
        player_types: ["human", "random", "llm", "llm_api"] のリスト
        """
        if not (2 <= len(player_types) <= 10):
            raise ValueError("player_types must be a list of 2 to 10 strings")

        self.players = []
        for i, player_type in enumerate(player_types):
            if player_type == "human":
                if i == 0:
                    self.add_player(HumanPlayer(i, "You", self.initial_chips))
                else:
                    self.add_player(HumanPlayer(i, f"Player{i}", self.initial_chips))
            elif player_type == "random":
                self.add_player(RandomPlayer(i, f"CPU{i}", self.initial_chips))
            elif player_type == "llm":
                self.add_player(LLMPlayer(i, f"AI{i}", self.initial_chips))
            else:
                raise ValueError(f"Unknown player type: {player_type}")

        # ディーラーボタンをランダムに決定
        self.dealer_button = random.randint(0, len(self.players) - 1)

    def setup_configurable_game_with_models(self, player_configs: List[Dict[str, Any]]):
        """
        カスタマイズ可能なゲームをセットアップ（2〜4人、モデル・Agent指定対応）
        player_configs: [{"type": "human|random|llm|llm_api", "model": "model_id", "agent_id": str, "user_id": str}, ...] のリスト
        """
        if not (2 <= len(player_configs) <= 10):
            raise ValueError("player_configs must be a list of 2 to 10 dictionaries")

        self.players = []
        for i, config in enumerate(player_configs):
            player_type = config.get("type")
            model = config.get("model")

            if player_type == "human":
                if i == 0:
                    self.add_player(HumanPlayer(i, "You", self.initial_chips))
                else:
                    self.add_player(HumanPlayer(i, f"Player{i}", self.initial_chips))
            elif player_type == "random":
                self.add_player(RandomPlayer(i, f"CPU{i}", self.initial_chips))
            elif player_type == "llm":
                if model:
                    self.add_player(
                        LLMPlayer(i, f"AI{i}", self.initial_chips, model=model)
                    )
                else:
                    # デフォルトモデルを使用
                    self.add_player(LLMPlayer(i, f"AI{i}", self.initial_chips))
            elif player_type == "llm_api":
                # LLMApiPlayerの場合、agentパラメータが必要
                agent_id = config.get(
                    "agent_id", "team1_agent"
                )  # デフォルトはteam1_agent
                user_id = config.get("user_id", f"player_{i}")
                self.add_player(
                    LLMApiPlayer(
                        player_id=i,
                        name=f"Agent{i}",
                        app_name=agent_id,
                        user_id=user_id,
                        initial_chips=self.initial_chips,
                    )
                )
            else:
                raise ValueError(f"Unknown player type: {player_type}")

        # ディーラーボタンをランダムに決定
        self.dealer_button = random.randint(0, len(self.players) - 1)

    def start_new_hand(self):
        """新しいハンドを開始"""
        self.hand_number += 1
        game_logger.info(f"=== STARTING NEW HAND #{self.hand_number} ===")

        self.deck.reset()
        self.community_cards = []
        self.current_phase = GamePhase.PREFLOP
        self.pot = 0
        self.current_bet = 0
        self.betting_round_complete = False
        self.last_raiser_index = None
        self.has_bet_or_raise_this_round = False
        # 前ハンドのショーダウン表示内容をクリア
        self.last_showdown_results = None

        # プレイヤーをリセット
        for player in self.players:
            player.reset_for_new_hand()

        # アクティブなプレイヤー数をチェック
        active_players = [p for p in self.players if p.status != PlayerStatus.BUSTED]
        game_logger.info(f"Active players for new hand: {len(active_players)}")

        if len(active_players) < 2:
            game_logger.info("Not enough players - setting phase to FINISHED")
            self.current_phase = GamePhase.FINISHED
            return

        # ディーラーボタンを移動
        game_logger.info("Moving dealer button")
        self._move_dealer_button()

        # ブラインドを設定
        game_logger.info("Posting blinds")
        self._post_blinds()

        # カードを配る
        game_logger.info("Dealing hole cards")
        self._deal_hole_cards()

        # 最初のアクションプレイヤーを設定
        game_logger.info("Setting first actor for preflop")
        self._set_first_actor_preflop()

        self._log_game_state("HAND_STARTED")

    def _move_dealer_button(self):
        """ディーラーボタンを次のアクティブプレイヤーに移動"""
        active_players = [
            i for i, p in enumerate(self.players) if p.status != PlayerStatus.BUSTED
        ]

        if not active_players:
            return

        # 現在のディーラーがアクティブプレイヤーリストにない場合
        if self.dealer_button not in active_players:
            self.dealer_button = active_players[0]
        else:
            current_dealer_pos = active_players.index(self.dealer_button)
            next_dealer_pos = (current_dealer_pos + 1) % len(active_players)
            self.dealer_button = active_players[next_dealer_pos]

        # ディーラーフラグを設定
        for i, player in enumerate(self.players):
            player.is_dealer = i == self.dealer_button

    def _post_blinds(self):
        """ブラインドを投稿"""
        active_players = [
            i for i, p in enumerate(self.players) if p.status != PlayerStatus.BUSTED
        ]

        if len(active_players) < 2:
            return

        dealer_pos = active_players.index(self.dealer_button)

        if len(active_players) == 2:
            # ヘッズアップではディーラーがSB、相手がBB
            sb_pos = self.dealer_button
            other_index = 1 - dealer_pos
            bb_pos = active_players[other_index]
        else:
            # スモールブラインド（ディーラーの次）
            sb_pos = active_players[(dealer_pos + 1) % len(active_players)]
            # ビッグブラインド（スモールブラインドの次）
            bb_pos = active_players[(dealer_pos + 2) % len(active_players)]

        self.players[sb_pos].is_small_blind = True
        sb_amount = self.players[sb_pos].bet(self.small_blind)
        self.pot += sb_amount
        self.action_history.append(f"Player {sb_pos} posted small blind {sb_amount}")

        self.players[bb_pos].is_big_blind = True
        bb_amount = self.players[bb_pos].bet(self.big_blind)
        self.pot += bb_amount
        self.current_bet = bb_amount
        # ビッグブラインドを最後のレイザーとして設定（プリフロップのベッティング制御のため）
        self.last_raiser_index = bb_pos
        self.action_history.append(f"Player {bb_pos} posted big blind {bb_amount}")

    def _deal_hole_cards(self):
        """各プレイヤーにホールカードを配る"""
        for _ in range(2):  # 2枚ずつ
            for player in self.players:
                if player.status != PlayerStatus.BUSTED:
                    player.add_hole_card(self.deck.deal_card())

    def _set_first_actor_preflop(self):
        """プリフロップの最初のアクションプレイヤーを設定"""
        active_players = [
            i
            for i, p in enumerate(self.players)
            if p.status not in [PlayerStatus.BUSTED, PlayerStatus.FOLDED]
        ]

        if len(active_players) < 2:
            self.betting_round_complete = True
            return

        # ディーラーがアクティブプレイヤーにいない場合の処理
        if self.dealer_button not in active_players:
            self.current_player_index = active_players[0]
            return

        dealer_pos = active_players.index(self.dealer_button)

        # ヘッズアップ（2人）の場合、ディーラーが最初にアクション
        if len(active_players) == 2:
            self.current_player_index = self.dealer_button
        else:
            # 3人以上の場合、ビッグブラインドの次（UTG）がアクション
            # Dealer -> SB -> BB -> UTG（最初のアクション）
            utg_pos = (dealer_pos + 3) % len(active_players)
            self.current_player_index = active_players[utg_pos]

    def get_llm_game_state(self, player_id: int) -> GameState:
        """
        LLM用の簡潔なゲーム状態を生成（数値整合性を保証）
        game_state_format.mdの仕様に従う
        """
        player = self.get_player(player_id)
        if player is None:
            raise ValueError(f"Invalid player_id: {player_id}")

        # バストしたプレイヤーは状態を取得できない
        if player.status == PlayerStatus.BUSTED:
            raise ValueError(f"Player {player_id} is busted and cannot get game state")

        # カードを視覚的な記号に変換
        your_cards = [str(card) for card in player.hole_cards]
        community = [str(card) for card in self.community_cards]

        # 他プレイヤーの状態（自分以外、バストしたプレイヤーを除く）
        players_info = []
        for p in self.players:
            if p.id != player_id and p.status != PlayerStatus.BUSTED:
                players_info.append(
                    PlayerInfo(
                        id=p.id, chips=p.chips, bet=p.current_bet, status=p.status.value
                    )
                )

        # 利用可能なアクション
        actions = self._get_available_actions(player_id)

        # コールに必要な額
        to_call = max(0, self.current_bet - player.current_bet)

        # 最近のアクション履歴（最新20件）
        recent_history = self.action_history[-20:] if self.action_history else []

        return GameState(
            your_id=player_id,
            phase=self.current_phase.value,
            your_cards=your_cards,
            community=community,
            your_chips=player.chips,
            your_bet_this_round=player.current_bet,
            your_total_bet_this_hand=player.total_bet_this_hand,
            pot=self.pot,
            to_call=to_call,
            dealer_button=self.dealer_button,
            current_turn=self.current_player_index,
            players=players_info,
            actions=actions,
            history=recent_history,
        )

    def _get_available_actions(self, player_id: int) -> List[str]:
        """プレイヤーが利用可能なアクションリストを取得"""
        player = self.get_player(player_id)
        if player is None:
            return []
        actions = []

        if player.status != PlayerStatus.ACTIVE:
            return actions

        # フォールド（常に可能）
        if player.status == PlayerStatus.ACTIVE:
            actions.append("fold")

        # コールに必要な額
        to_call = max(0, self.current_bet - player.current_bet)

        # チェック（ベットがない場合）
        if to_call == 0:
            actions.append("check")

        # コール（ベットがある場合でチップが足りる場合）
        if to_call > 0 and player.chips >= to_call:
            actions.append(f"call ({to_call})")

        # レイズ/ベットの可否を厳密化
        can_open_bet = self.current_bet == 0
        can_raise = to_call > 0

        # プリフロップのビッグブラインドのオプション（全員コールの後に1回だけレイズ権）
        is_big_blind_option = False
        if (
            self.current_phase == GamePhase.PREFLOP
            and not self.has_bet_or_raise_this_round
            and to_call == 0
            and self.current_bet == self.big_blind
        ):
            bb_index = None
            for i, p in enumerate(self.players):
                if p.is_big_blind:
                    bb_index = i
                    break
            is_big_blind_option = bb_index is not None and player_id == bb_index

        # 最低レイズ（総額）。オープンベット時はBB、既存ベットがある場合は current_bet + BB
        min_raise_total = (
            self.big_blind if can_open_bet else (self.current_bet + self.big_blind)
        )

        # raise は (オープンベット) or (既存ベットへのレイズ) or (BBオプション) のときのみ
        if (
            (can_open_bet or can_raise or is_big_blind_option)
            and player.chips >= min_raise_total
            and to_call < player.chips
        ):
            actions.append(f"raise (min {min_raise_total})")

        # all-in は raise と同条件か、コールしきれない時の代替
        if player.chips > 0:
            if can_open_bet or can_raise or is_big_blind_option:
                actions.append(f"all-in ({player.chips})")
            elif to_call > 0 and player.chips < to_call:
                actions.append(f"all-in ({player.chips})")

        return actions

    def process_player_action(
        self, player_id: int, action: str, amount: int = 0
    ) -> bool:
        """
        プレイヤーのアクションを処理

        Returns:
            bool: アクションが正常に処理されたかどうか
        """
        game_logger.info(
            f">>> PROCESS_ACTION: Player {player_id} attempts '{action}' with amount {amount}"
        )
        self._log_game_state("BEFORE_ACTION")

        if player_id != self.current_player_index:
            game_logger.warning(
                f"Player {player_id} tried to act but current player is {self.current_player_index}"
            )
            return False

        player = self.get_player(player_id)
        if player is None:
            game_logger.error(f"Player {player_id} not found")
            return False
        if player.status != PlayerStatus.ACTIVE:
            game_logger.warning(
                f"Player {player_id} is not active (status: {player.status})"
            )
            return False

        action_description = ""

        if action == "fold":
            player.fold()
            action_description = f"Player {player_id} folded"

        elif action == "check":
            if self.current_bet > player.current_bet:
                game_logger.warning(
                    f"Player {player_id} cannot check - current bet {self.current_bet} > player bet {player.current_bet}"
                )
                return False  # チェックできない状況
            action_description = f"Player {player_id} checked"

        elif action == "call":
            to_call = self.current_bet - player.current_bet
            # テキサスホールデムでは to_call == 0 のとき、"call" は実質的に "check" と同義
            if to_call <= 0:
                action_description = f"Player {player_id} checked"
            else:
                if player.chips < to_call:
                    game_logger.warning(
                        f"Player {player_id} cannot call - to_call: {to_call}, chips: {player.chips}"
                    )
                    return False

                actual_call = player.bet(to_call)
                self.pot += actual_call
                action_description = f"Player {player_id} called {actual_call}"

        elif action == "raise":
            to_call = self.current_bet - player.current_bet
            total_needed = to_call + amount

            if player.chips < total_needed:
                game_logger.warning(
                    f"Player {player_id} cannot raise - needs {total_needed}, has {player.chips}"
                )
                return False

            actual_bet = player.bet(total_needed)
            self.pot += actual_bet
            self.current_bet = player.current_bet
            self.last_raiser_index = player_id
            self.has_bet_or_raise_this_round = True
            action_description = f"Player {player_id} raised to {self.current_bet}"

        elif action == "all_in":
            if player.chips <= 0:
                game_logger.warning(
                    f"Player {player_id} cannot go all-in - no chips left"
                )
                return False

            actual_bet = player.bet(player.chips)
            self.pot += actual_bet

            # オールイン額が現在のベットを上回る場合はレイズ扱い
            if player.current_bet > self.current_bet:
                self.current_bet = player.current_bet
                self.last_raiser_index = player_id
                self.has_bet_or_raise_this_round = True

            player.status = PlayerStatus.ALL_IN
            action_description = f"Player {player_id} went all-in with {actual_bet}"

        else:
            game_logger.error(f"Unknown action: {action}")
            return False

        # アクション履歴に追加
        self.action_history.append(action_description)
        game_logger.info(f"ACTION_EXECUTED: {action_description}")

        self._log_game_state("AFTER_ACTION", f"Action: {action_description}")

        # 次のプレイヤーに移動
        game_logger.info(">>> ADVANCING to next player")
        self._advance_to_next_player()

        # ベッティングラウンド完了チェック
        game_logger.info(">>> CHECKING betting round completion")
        self._check_betting_round_complete()

        self._log_game_state(
            "AFTER_BETTING_CHECK", f"Betting complete: {self.betting_round_complete}"
        )

        return True

    def _advance_to_next_player(self):
        """次のアクティブプレイヤーに移動（座席順序を維持）"""
        game_logger.debug("_advance_to_next_player called")

        # アクティブプレイヤー（アクションが必要なプレイヤー）を確認
        active_players = [
            i for i, p in enumerate(self.players) if p.status == PlayerStatus.ACTIVE
        ]

        game_logger.debug(f"Active players: {active_players}")

        # 座席順序を維持して次のアクティブプレイヤーを探す
        old_player = self.current_player_index
        total_players = len(self.players)

        # 現在のプレイヤーの次から順番に探す
        for i in range(1, total_players + 1):
            next_index = (self.current_player_index + i) % total_players
            next_player = self.players[next_index]

            # アクティブなプレイヤーが見つかった場合
            if next_player.status == PlayerStatus.ACTIVE:
                self.current_player_index = next_index
                game_logger.info(
                    f"Advanced from player {old_player} to player {self.current_player_index} (seat order)"
                )
                return

        # ここに到達した場合はアクティブプレイヤーが見つからなかった
        game_logger.warning(
            "No active player found in seat order - marking betting round complete"
        )
        self.betting_round_complete = True

    def _check_betting_round_complete(self):
        """ベッティングラウンドが完了したかチェック（座席順序ベース）"""
        game_logger.debug("_check_betting_round_complete called")

        active_players = [p for p in self.players if p.status == PlayerStatus.ACTIVE]
        all_in_players = [p for p in self.players if p.status == PlayerStatus.ALL_IN]

        game_logger.debug(
            f"Active: {len(active_players)}, All-in: {len(all_in_players)}"
        )

        # 1人しか残っていない場合
        if len(active_players) + len(all_in_players) <= 1:
            game_logger.info("Betting complete: Only 1 or fewer players remaining")
            self.betting_round_complete = True
            return

        # アクティブプレイヤーがいない場合（全員フォールドまたはオールイン）
        if len(active_players) == 0:
            game_logger.info("Betting complete: No active players")
            self.betting_round_complete = True
            return

        # アクティブプレイヤーが1人の場合の特別処理
        if len(active_players) == 1:
            # その1人がまだベットをマッチしていない場合は継続
            single_player = active_players[0]
            if single_player.current_bet < self.current_bet:
                game_logger.debug(
                    f"Single active player {single_player.name} needs to match bet: {single_player.current_bet} < {self.current_bet}"
                )
                return
            else:
                # ベットをマッチしている場合は終了
                game_logger.info(
                    "Betting complete: Single active player has matched the bet"
                )
                self.betting_round_complete = True
                return

        # アクティブなプレイヤーが全員同じベット額でない場合は継続
        player_bets = [p.current_bet for p in active_players]
        all_same_bet = all(p.current_bet == self.current_bet for p in active_players)
        game_logger.debug(
            f"Player bets: {player_bets}, Current bet: {self.current_bet}, All same: {all_same_bet}"
        )

        if not all_same_bet:
            game_logger.debug("Betting continues: Not all players have same bet")
            return

        # 全員が同じベット額の場合、ベッティングラウンド完了の条件をチェック
        # このラウンドで誰かがベット/レイズしており、全員がマッチした場合は即終了
        if self.last_raiser_index is not None and getattr(
            self, "has_bet_or_raise_this_round", False
        ):
            game_logger.info("Betting complete: All players matched after a bet/raise")
            self.betting_round_complete = True
            return
        active_players_indices = [
            i for i, p in enumerate(self.players) if p.status == PlayerStatus.ACTIVE
        ]

        game_logger.debug(f"Active player indices: {active_players_indices}")
        game_logger.debug(f"Last raiser index: {self.last_raiser_index}")
        game_logger.debug(f"Current player index: {self.current_player_index}")

        if self.last_raiser_index is None:
            # 誰もレイズしていない場合（全員チェック）、全員が一度アクションしたら終了
            # これはフロップ以降でのみ発生（プリフロップではビッグブラインドがlast_raiser_indexになる）

            # フロップ以降では、最初のアクター（ディーラーの次）から座席順序で一周した場合に終了
            first_actor_index = self._get_first_actor_for_phase()

            game_logger.debug(f"First actor index: {first_actor_index}")

            # 現在のプレイヤーが最初のアクターに戻ってきた場合、全員がアクションを完了
            if self.current_player_index == first_actor_index:
                game_logger.info(
                    f"Betting complete: Back to first actor {first_actor_index} (all players have acted)"
                )
                self.betting_round_complete = True
            else:
                game_logger.debug(
                    f"Betting continues: Current player {self.current_player_index} != first actor {first_actor_index}"
                )
        elif self.last_raiser_index not in active_players_indices:
            # 最後にレイズしたプレイヤーがもうアクティブでない場合（フォールドまたはオールイン）
            game_logger.info(
                f"Betting complete: Last raiser {self.last_raiser_index} is no longer active"
            )
            self.betting_round_complete = True
        else:
            # 最後にレイズしたプレイヤーの次のプレイヤーが座席順序でアクションしようとしているかチェック
            next_after_raiser_index = self._get_next_active_player_from(
                self.last_raiser_index
            )

            game_logger.debug(
                f"Next after last raiser {self.last_raiser_index}: {next_after_raiser_index}"
            )

            # 現在のプレイヤーが最後にレイズしたプレイヤーの次のプレイヤーの場合、
            # 最後にレイズしたプレイヤーは既にアクションを完了しているのでベッティング終了
            if self.current_player_index == next_after_raiser_index:
                game_logger.info(
                    f"Betting complete: Back to player {next_after_raiser_index} after last raiser {self.last_raiser_index}"
                )
                self.betting_round_complete = True
            else:
                game_logger.debug(
                    f"Betting continues: Current player {self.current_player_index} != next after raiser {next_after_raiser_index}"
                )

    def _get_first_actor_for_phase(self):
        """現在のフェーズでの最初のアクターを取得（座席順序ベース）"""
        active_players_indices = [
            i for i, p in enumerate(self.players) if p.status == PlayerStatus.ACTIVE
        ]

        if self.current_phase == GamePhase.PREFLOP:
            # プリフロップでは、ビッグブラインドの次（UTG）が最初のアクター
            # 座席順序で探す
            bb_index = None
            for i, player in enumerate(self.players):
                if player.is_big_blind:
                    bb_index = i
                    break

            if bb_index is not None:
                # ビッグブラインドの次のアクティブプレイヤーを座席順序で探す
                for i in range(1, len(self.players)):
                    next_index = (bb_index + i) % len(self.players)
                    if next_index in active_players_indices:
                        return next_index
        else:
            # フロップ以降では、ディーラーの次が最初のアクター
            # 座席順序で探す
            for i in range(1, len(self.players)):
                next_index = (self.dealer_button + i) % len(self.players)
                if next_index in active_players_indices:
                    return next_index

        # 見つからない場合は最初のアクティブプレイヤー
        return active_players_indices[0] if active_players_indices else None

    def _get_next_active_player_from(self, from_player_index):
        """指定されたプレイヤーの次のアクティブプレイヤーを座席順序で取得"""
        active_players_indices = [
            i for i, p in enumerate(self.players) if p.status == PlayerStatus.ACTIVE
        ]

        # 座席順序で次のアクティブプレイヤーを探す
        for i in range(1, len(self.players)):
            next_index = (from_player_index + i) % len(self.players)
            if next_index in active_players_indices:
                return next_index

        return None

    def advance_to_next_phase(self):
        """次のフェーズに進む"""
        game_logger.info(
            f">>> ADVANCE_TO_NEXT_PHASE called - Current phase: {self.current_phase.value}"
        )
        game_logger.info(f"Betting round complete: {self.betting_round_complete}")

        if not self.betting_round_complete:
            game_logger.warning("Cannot advance phase - betting round not complete")
            return False

        # 残りプレイヤーチェック
        remaining_players = [
            p
            for p in self.players
            if p.status in [PlayerStatus.ACTIVE, PlayerStatus.ALL_IN]
        ]

        game_logger.info(f"Remaining players: {len(remaining_players)}")
        for i, p in enumerate(remaining_players):
            game_logger.debug(
                f"  Remaining P{p.id}: {p.name}, status: {p.status.value}"
            )

        if len(remaining_players) <= 1:
            game_logger.info("Going to SHOWDOWN - only 1 or fewer players remaining")
            self.current_phase = GamePhase.SHOWDOWN
            self._log_game_state("PHASE_CHANGED_TO_SHOWDOWN")
            return True

        old_phase = self.current_phase

        # フェーズを進める
        if self.current_phase == GamePhase.PREFLOP:
            self.current_phase = GamePhase.FLOP
            game_logger.info("Phase changed: PREFLOP -> FLOP")
            self._deal_flop()
        elif self.current_phase == GamePhase.FLOP:
            self.current_phase = GamePhase.TURN
            game_logger.info("Phase changed: FLOP -> TURN")
            self._deal_turn()
        elif self.current_phase == GamePhase.TURN:
            self.current_phase = GamePhase.RIVER
            game_logger.info("Phase changed: TURN -> RIVER")
            self._deal_river()
        elif self.current_phase == GamePhase.RIVER:
            self.current_phase = GamePhase.SHOWDOWN
            game_logger.info("Phase changed: RIVER -> SHOWDOWN")
            self._log_game_state("PHASE_CHANGED_TO_SHOWDOWN")
            return True
        else:
            game_logger.error(f"Cannot advance from phase: {self.current_phase}")
            return False

        # 新しいベッティングラウンドを開始
        game_logger.info("Starting new betting round")
        self._start_new_betting_round()
        self._log_game_state(
            "NEW_BETTING_ROUND_STARTED",
            f"Phase: {old_phase.value} -> {self.current_phase.value}",
        )
        return True

    def _deal_flop(self):
        """フロップを配る（3枚）"""
        self.deck.deal_card()  # バーンカード
        for _ in range(3):
            self.community_cards.append(self.deck.deal_card())
        self.action_history.append(
            f"Flop dealt: {', '.join(str(card) for card in self.community_cards)}"
        )

    def _deal_turn(self):
        """ターンを配る（1枚）"""
        self.deck.deal_card()  # バーンカード
        self.community_cards.append(self.deck.deal_card())
        self.action_history.append(f"Turn dealt: {str(self.community_cards[-1])}")

    def _deal_river(self):
        """リバーを配る（1枚）"""
        self.deck.deal_card()  # バーンカード
        self.community_cards.append(self.deck.deal_card())
        self.action_history.append(f"River dealt: {str(self.community_cards[-1])}")

    def _start_new_betting_round(self):
        """新しいベッティングラウンドを開始"""
        game_logger.debug("_start_new_betting_round called")

        # プレイヤーのベットをリセット
        for player in self.players:
            player.reset_for_new_betting_round()

        self.current_bet = 0
        self.betting_round_complete = False
        self.last_raiser_index = None

        game_logger.info(
            "Reset: current_bet=0, betting_round_complete=False, last_raiser_index=None"
        )

        # 最初のアクションプレイヤーを設定（フェーズ規則に基づき計算）
        # ALL_INプレイヤーはアクションできないため除外
        active_players = [
            i for i, p in enumerate(self.players) if p.status == PlayerStatus.ACTIVE
        ]

        game_logger.debug(f"Active players for new betting round: {active_players}")
        game_logger.debug(f"Dealer button: {self.dealer_button}")

        if len(active_players) > 0:
            first_actor_index = self._get_first_actor_for_phase()
            if first_actor_index is not None:
                old_player = self.current_player_index
                self.current_player_index = first_actor_index
                game_logger.info(
                    f"First actor: Player {self.current_player_index} (by phase rule), was {old_player}"
                )
            else:
                # 念のためのフォールバック（通常は到達しない）
                old_player = self.current_player_index
                self.current_player_index = active_players[0]
                game_logger.info(
                    f"First actor: Player {self.current_player_index} (fallback first active), was {old_player}"
                )
        else:
            # アクティブプレイヤーがいない場合はベッティング終了
            game_logger.warning("No active players - marking betting complete")
            self.betting_round_complete = True

    def conduct_showdown(self) -> Dict[str, Any]:
        """ショーダウンを実行して勝者を決定"""
        remaining_players = [
            p
            for p in self.players
            if p.status in [PlayerStatus.ACTIVE, PlayerStatus.ALL_IN]
        ]

        # ログ: ショーダウン開始情報
        try:
            game_logger.info("=== SHOWDOWN_STARTED ===")
            game_logger.info(
                "Pot: %d, Community cards: %s",
                self.pot,
                [str(card) for card in self.community_cards],
            )
            for p in remaining_players:
                game_logger.info(
                    "  Player %d status=%s cards=%s",
                    p.id,
                    p.status.value,
                    [str(card) for card in p.hole_cards],
                )
        except Exception as e:
            # ログ出力はゲーム進行を止めない
            game_logger.debug("Showdown logging (start) failed: %s", e)

        if len(remaining_players) == 0:
            game_logger.warning("Showdown called with no remaining players")
            result: Dict[str, Any] = {"winners": [], "results": []}
            self.last_showdown_results = result
            # 履歴にショーダウン結果を追記
            self.action_history.append("Showdown: no remaining players")
            return result

        if len(remaining_players) == 1:
            # 1人だけ残った場合
            winner = remaining_players[0]
            winner.chips += self.pot
            try:
                game_logger.info(
                    "Showdown winner by default: Player %d awarded %d",
                    winner.id,
                    self.pot,
                )
                game_logger.info("=== SHOWDOWN_RESULTS_RECORDED ===")
            except Exception as e:
                game_logger.debug("Showdown logging (single winner) failed: %s", e)
            result = {
                "winners": [winner.id],
                "results": [
                    {
                        "player_id": winner.id,
                        "hand": "Won by default",
                        "winnings": self.pot,
                    }
                ],
            }
            self.last_showdown_results = result
            # 履歴にショーダウン結果を追記
            self.action_history.append(f"Showdown: Player {winner.id} won {self.pot}")
            return result

        # 複数プレイヤーでのショーダウン
        player_hands = []
        for player in remaining_players:
            hand_result = HandEvaluator.evaluate_hand(
                player.hole_cards, self.community_cards
            )
            player_hands.append({"player": player, "hand": hand_result})

        # 履歴: ショーダウン参加者のハンド情報を追記
        for ph in player_hands:
            try:
                self.action_history.append(
                    "Showdown: Player "
                    + str(ph["player"].id)
                    + " hand="
                    + str(ph["hand"])
                    + " cards="
                    + ", ".join(str(card) for card in ph["player"].hole_cards)
                )
            except Exception:
                # 履歴追記はゲーム進行を止めない
                pass

        # 各プレイヤーの役をログ
        try:
            for ph in player_hands:
                game_logger.info(
                    "  Player %d hand=%s cards=%s",
                    ph["player"].id,
                    str(ph["hand"]),
                    [str(card) for card in ph["player"].hole_cards],
                )
        except Exception as e:
            game_logger.debug("Showdown logging (hands) failed: %s", e)

        # ID -> HandResult のマップ
        hands_by_id = {ph["player"].id: ph["hand"] for ph in player_hands}

        # サイドポットを含めたポット階層を構築
        contributions = {
            p.id: max(0, int(getattr(p, "total_bet_this_hand", 0)))
            for p in self.players
        }
        # 0 の寄付は除外
        contributions = {pid: c for pid, c in contributions.items() if c > 0}

        def build_pot_layers(contrib_map: Dict[int, int]) -> List[Dict[str, Any]]:
            if not contrib_map:
                return []
            unique_levels = sorted(set(contrib_map.values()))
            layers: List[Dict[str, Any]] = []
            prev = 0
            for level in unique_levels:
                width = level - prev
                if width <= 0:
                    prev = level
                    continue
                eligible_contributors = [
                    pid for pid, amt in contrib_map.items() if amt >= level
                ]
                layer_amount = width * len(eligible_contributors)
                layers.append(
                    {
                        "amount": layer_amount,
                        "contributors": eligible_contributors,
                    }
                )
                prev = level
            return layers

        pot_layers = build_pot_layers(contributions)

        # レイヤー情報をログ
        try:
            for idx, layer in enumerate(pot_layers):
                game_logger.info(
                    "Pot layer %d: amount=%d, contributors=%s",
                    idx,
                    layer["amount"],
                    layer["contributors"],
                )
        except Exception:
            pass

        # 勝者決定の補助関数（対象ID集合の中で最強ハンドを持つ者を返す）
        def determine_winner_ids(
            eligible_ids: List[int],
        ) -> Tuple[List[int], Optional[HandResult]]:
            best: Optional[HandResult] = None
            winners_local: List[int] = []
            for pid in eligible_ids:
                hand = hands_by_id.get(pid)
                if hand is None:
                    continue
                if best is None:
                    best = hand
                    winners_local = [pid]
                else:
                    # hand が best より強い場合
                    if hand.rank.value > best.rank.value or (
                        hand.rank.value == best.rank.value
                        and hand.kickers > best.kickers
                    ):
                        best = hand
                        winners_local = [pid]
                    elif (
                        hand.rank.value == best.rank.value
                        and hand.kickers == best.kickers
                    ):
                        winners_local.append(pid)
            return winners_local, best

        # 各レイヤーごとに分配
        winnings_map: Dict[int, int] = {}
        total_awarded = 0

        # ショーダウンに参加している（フォールドしていない）プレイヤーID
        showdown_ids = {p.id for p in remaining_players}

        for layer_idx, layer in enumerate(pot_layers):
            amount = layer["amount"]
            # このレイヤーでの受給資格者（コントリビュータかつショーダウン参加）
            eligible_ids = [pid for pid in layer["contributors"] if pid in showdown_ids]

            if not eligible_ids:
                # 受給資格者がいない場合はスキップ（通常は発生しない想定）
                game_logger.warning(
                    "No eligible players for pot layer %d; amount=%d is unclaimed",
                    layer_idx,
                    amount,
                )
                continue

            winner_ids, best_hand_in_layer = determine_winner_ids(eligible_ids)

            # 分配
            base_share = amount // len(winner_ids)
            remainder = amount % len(winner_ids)

            # 座席順（player.idの昇順）で余りを配分
            winner_ids_sorted = sorted(winner_ids)
            for i, pid in enumerate(winner_ids_sorted):
                share = base_share + (1 if i < remainder else 0)
                winnings_map[pid] = winnings_map.get(pid, 0) + share
                total_awarded += share

            # 履歴用のサマリ
            try:
                self.action_history.append(
                    "Side pot layer "
                    + str(layer_idx)
                    + ": amount="
                    + str(amount)
                    + ", winners="
                    + ", ".join(str(pid) for pid in winner_ids_sorted)
                    + (
                        " best_hand=" + str(best_hand_in_layer)
                        if best_hand_in_layer is not None
                        else ""
                    )
                )
            except Exception:
                pass

        # 実際にチップを配布し、結果を作成
        results = []
        for pid, win_amount in sorted(winnings_map.items()):
            player = self.get_player(pid)
            if player is None:
                continue
            player.chips += win_amount
            results.append(
                {
                    "player_id": pid,
                    "hand": str(hands_by_id.get(pid)),
                    "winnings": win_amount,
                }
            )

        # 参考: 全体のベストハンド（UI用）を計算
        all_ids = list(hands_by_id.keys())
        overall_winner_ids, overall_best_hand = determine_winner_ids(all_ids)

        # ログ
        try:
            game_logger.info(
                "Showdown total awarded: %d (game.pot=%d)", total_awarded, self.pot
            )
            game_logger.info(
                "Showdown winners (aggregated): %s",
                [pid for pid in sorted(winnings_map.keys())],
            )
            for r in results:
                game_logger.info(
                    "  Awarded %d to Player %d (hand=%s)",
                    r["winnings"],
                    r["player_id"],
                    r["hand"],
                )
            game_logger.info("=== SHOWDOWN_RESULTS_RECORDED ===")
        except Exception as e:
            game_logger.debug("Showdown logging (results) failed: %s", e)

        # all_hands 情報
        all_hands_payload = [
            {
                "player_id": ph["player"].id,
                "hand": str(ph["hand"]),
                "cards": [str(card) for card in ph["player"].hole_cards],
            }
            for ph in player_hands
        ]

        # ポットは全額配布済みとして 0 にする（念のため負値回避）
        try:
            self.pot = max(0, self.pot - total_awarded)
        except Exception:
            self.pot = 0

        result = {
            "winners": overall_winner_ids,
            "results": results,
            "all_hands": all_hands_payload,
        }
        self.last_showdown_results = result
        return result

    def is_game_over(self) -> bool:
        """ゲーム終了条件をチェック"""
        active_players = [p for p in self.players if p.chips > 0]
        return len(active_players) <= 1

    def save_game_state(self, filename: str):
        """ゲーム状態をJSONファイルに保存"""
        game_data = {
            "hand_number": self.hand_number,
            "phase": self.current_phase.value,
            "pot": self.pot,
            "current_bet": self.current_bet,
            "dealer_button": self.dealer_button,
            "community_cards": [
                {"rank": card.rank, "suit": card.suit.value}
                for card in self.community_cards
            ],
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "chips": p.chips,
                    "current_bet": p.current_bet,
                    "total_bet_this_hand": p.total_bet_this_hand,
                    "status": p.status.value,
                    "hole_cards": [
                        {"rank": card.rank, "suit": card.suit.value}
                        for card in p.hole_cards
                    ],
                    "is_dealer": p.is_dealer,
                    "is_small_blind": p.is_small_blind,
                    "is_big_blind": p.is_big_blind,
                }
                for p in self.players
            ],
            "action_history": self.action_history,
            "game_stats": self.game_stats,
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(game_data, f, ensure_ascii=False, indent=2)

    def load_game_state(self, filename: str):
        """JSONファイルからゲーム状態を読み込み"""
        # TODO: 実装（必要に応じて）
        pass

    def _log_game_state(self, context: str, extra_info: str = ""):
        """現在のゲーム状態を詳細にログに記録"""
        active_players = [p for p in self.players if p.status == PlayerStatus.ACTIVE]
        all_in_players = [p for p in self.players if p.status == PlayerStatus.ALL_IN]
        folded_players = [p for p in self.players if p.status == PlayerStatus.FOLDED]

        player_info = []
        for i, p in enumerate(self.players):
            player_info.append(
                f"P{i}({p.name}): chips={p.chips}, bet={p.current_bet}, status={p.status.value}"
            )

        game_logger.info(f"=== {context} ===")
        game_logger.info(f"Hand #{self.hand_number}, Phase: {self.current_phase.value}")
        game_logger.info(
            f"Current player: {self.current_player_index}, Dealer: {self.dealer_button}"
        )
        game_logger.info(f"Pot: {self.pot}, Current bet: {self.current_bet}")
        game_logger.info(f"Last raiser: {self.last_raiser_index}")
        game_logger.info(f"Betting round complete: {self.betting_round_complete}")
        game_logger.info(
            f"Active players: {len(active_players)}, All-in: {len(all_in_players)}, Folded: {len(folded_players)}"
        )
        game_logger.info(
            f"Community cards: {[str(card) for card in self.community_cards]}"
        )
        for info in player_info:
            game_logger.info(f"  {info}")
        if extra_info:
            game_logger.info(f"Extra: {extra_info}")
        game_logger.info("=" * 50)
