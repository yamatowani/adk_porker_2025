"""
Poker player models: Player classes and related types
"""

import os
import random
import logging
import asyncio
import json
import requests
import uuid
import re
import logging
import time
import concurrent.futures as cf

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum

from .game_models import Card, GameState, PlayerInfo

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


class PlayerStatus(Enum):
    """プレイヤーの状態"""

    ACTIVE = "active"
    FOLDED = "folded"
    ALL_IN = "all_in"
    BUSTED = "busted"


class Player(ABC):
    """プレイヤー抽象基底クラス"""

    def __init__(self, player_id: int, name: str, initial_chips: int = 1000):
        self.id = player_id
        self.name = name
        self.chips = initial_chips
        self.hole_cards: List[Card] = []
        self.current_bet = 0  # 現在のベッティングラウンドでのベット額
        self.total_bet_this_hand = 0  # このハンドでの累積ベット額
        self.status = PlayerStatus.ACTIVE
        self.is_dealer = False
        self.is_small_blind = False
        self.is_big_blind = False

    def reset_for_new_hand(self):
        """新しいハンド用にリセット"""
        self.hole_cards = []
        self.current_bet = 0
        self.total_bet_this_hand = 0
        if self.chips > 0:
            self.status = PlayerStatus.ACTIVE
        else:
            self.status = PlayerStatus.BUSTED
        self.is_dealer = False
        self.is_small_blind = False
        self.is_big_blind = False

    def reset_for_new_betting_round(self):
        """新しいベッティングラウンド用にリセット"""
        self.current_bet = 0

    def add_hole_card(self, card: Card):
        """ホールカードを追加"""
        if len(self.hole_cards) >= 2:
            raise ValueError("Player already has 2 hole cards")
        self.hole_cards.append(card)

    def bet(self, amount: int) -> int:
        """ベットを行う（実際にベットした額を返す）"""
        if amount <= 0:
            return 0

        # チップが足りない場合はオールイン
        actual_bet = min(amount, self.chips)
        self.chips -= actual_bet
        self.current_bet += actual_bet
        self.total_bet_this_hand += actual_bet

        if self.chips == 0:
            self.status = PlayerStatus.ALL_IN

        return actual_bet

    def fold(self):
        """フォールドする"""
        self.status = PlayerStatus.FOLDED

    def can_bet(self, amount: int) -> bool:
        """指定した額をベットできるかチェック"""
        return self.chips >= amount and self.status == PlayerStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        """プレイヤー情報を辞書形式で返す（JSON用）"""
        return {
            "id": self.id,
            "chips": self.chips,
            "bet": self.current_bet,
            "status": self.status.value,
        }

    @abstractmethod
    def make_decision(self, game_state: GameState) -> Dict[str, Any]:
        """
        ゲーム状態を受け取ってアクションを決定

        Args:
            game_state: 型安全なゲーム状態オブジェクト

        Returns:
            {"action": "fold|check|call|raise|all_in", "amount": int}
        """
        pass

    def _parse_llm_response(
        self, response: str, game_state: GameState, response_type: str = "LLM"
    ) -> Dict[str, Any]:
        """
        LLMの応答をパース（共通実装）

        Args:
            response: LLMからの応答文字列
            game_state: ゲーム状態
            response_type: "LLM" or "LLM API" (ログメッセージ用)

        Returns:
            {"action": "fold|check|call|raise|all_in", "amount": int}
        """
        import json
        import re
        import logging

        logger = logging.getLogger("poker_game")
        logger.debug(f"[{self.name}] Starting {response_type} response parsing")
        logger.debug(f"[{self.name}] Raw response content: {repr(response)}")

        try:
            # JSONパターンを探す（reasoningフィールドも含む）
            # Markdownコードブロック形式に対応

            # まずMarkdownコードブロックを除去
            cleaned_response = response
            if "```json" in response:
                logger.debug(f"[{self.name}] Markdown code block detected")
                # ```json から ``` までの内容を抽出
                markdown_match = re.search(
                    r"```json\s*\n(.*?)\n```", response, re.DOTALL
                )
                if markdown_match:
                    cleaned_response = markdown_match.group(1)
                    logger.debug(
                        f"[{self.name}] Extracted content from markdown: {repr(cleaned_response)}"
                    )
                else:
                    logger.debug(
                        f"[{self.name}] Markdown pattern found but failed to extract content"
                    )
            else:
                logger.debug(f"[{self.name}] No markdown code block detected")

            json_match = re.search(
                r'\{[^}]*"action"[^}]*\}', cleaned_response, re.DOTALL
            )
            if json_match:
                json_str = json_match.group()
                logger.debug(f"[{self.name}] JSON pattern found: {json_str}")

                decision = json.loads(json_str)
                logger.debug(f"[{self.name}] JSON parsing successful: {decision}")

                # バリデーション
                action = decision.get("action", "fold").lower()
                amount = decision.get("amount", 0)
                reasoning = decision.get("reasoning", "理由が提供されませんでした")

                logger.debug(
                    f"[{self.name}] Extracted values - action: '{action}', amount: {amount}"
                )

                # 理由を保存（last_decision_reasoningがある場合のみ）
                if hasattr(self, "last_decision_reasoning"):
                    self.last_decision_reasoning = reasoning

                # アクションの正規化
                if action in ["fold", "check"]:
                    amount = 0
                    logger.debug(
                        f"[{self.name}] Action '{action}' normalized - amount set to 0"
                    )
                elif action == "call":
                    # コール額を計算
                    available_actions = game_state.actions
                    logger.debug(
                        f"[{self.name}] Processing call action - available actions: {available_actions}"
                    )
                    original_amount = amount
                    for act in available_actions:
                        if "call" in str(act).lower():
                            # "call (20)" のような形式から金額を抽出
                            call_match = re.search(r"call.*\((\d+)\)", str(act))
                            if call_match:
                                amount = int(call_match.group(1))
                                logger.debug(
                                    f"[{self.name}] Call amount extracted from '{act}': {amount}"
                                )
                            break
                    if original_amount != amount:
                        logger.debug(
                            f"[{self.name}] Call amount adjusted from {original_amount} to {amount}"
                        )
                elif action == "all_in" or action == "all-in":
                    original_action = action
                    action = "all_in"
                    amount = self.chips
                    logger.debug(
                        f"[{self.name}] Action '{original_action}' normalized to 'all_in' - amount set to {amount}"
                    )
                elif action == "raise":
                    # 最低レイズ額をゲーム状態から取得
                    min_raise = 0
                    available_actions = game_state.actions
                    logger.debug(
                        f"[{self.name}] Processing raise action - available actions: {available_actions}"
                    )
                    original_amount = amount
                    for act in available_actions:
                        if "raise" in str(act).lower():
                            # "raise (min 40)" のような形式から最低額を抽出
                            raise_match = re.search(r"raise.*min (\d+)", str(act))
                            if raise_match:
                                min_raise = int(raise_match.group(1))
                                logger.debug(
                                    f"[{self.name}] Minimum raise amount extracted from '{act}': {min_raise}"
                                )
                                break

                    # 最低レイズ額を下回る場合のみ調整
                    if min_raise > 0 and amount < min_raise:
                        logger.debug(
                            f"[{self.name}] Adjusting raise amount from {amount} to minimum {min_raise}"
                        )
                        amount = min_raise
                    else:
                        logger.debug(
                            f"[{self.name}] Raise amount {amount} is valid (min: {min_raise})"
                        )
                else:
                    logger.warning(
                        f"[{self.name}] Unknown action '{action}' - no specific normalization applied"
                    )

                final_decision = {"action": action, "amount": int(amount)}
                logger.debug(f"[{self.name}] Final parsed decision: {final_decision}")
                # 追加のログ（両方の実装に追加）
                logger.info(
                    f"[{self.name}] Successfully parsed decision: {action}, {amount}, {reasoning}"
                )
                return final_decision
            else:
                logger.warning(
                    f"[{self.name}] No JSON pattern found in cleaned response"
                )

        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            logger.error(f"{response_type} response format error for {self.name}: {e}")
            logger.error(f"Invalid response content: {repr(response)}")
            logger.error(
                'Expected format: {"action": "fold|check|call|raise|all_in", "amount": <number>, "reasoning": "<text>"}'
            )

        # パースに失敗した場合はフォールド
        if hasattr(self, "last_decision_reasoning"):
            self.last_decision_reasoning = (
                "レスポンスのパースに失敗したため、フォールドします"
            )
        return {"action": "fold", "amount": 0}

    def __str__(self) -> str:
        return f"{self.name} (ID: {self.id}, Chips: {self.chips})"


class HumanPlayer(Player):
    """人間プレイヤークラス"""

    def make_decision(self, game_state: GameState) -> Dict[str, Any]:
        """
        人間プレイヤーの場合、UIから入力を受け取る
        実際の実装はUI層で行い、ここではプレースホルダー
        """
        # この部分は後でUI層から呼び出される
        raise NotImplementedError("Human player decisions are handled by UI layer")


class RandomPlayer(Player):
    """ランダムプレイヤークラス（ランダム行動）"""

    def __init__(self, player_id: int, name: str, initial_chips: int = 1000):
        super().__init__(player_id, name, initial_chips)
        # 要件定義書に従った確率重み
        self.action_weights = {"fold": 30, "check_call": 50, "raise": 15, "all_in": 5}

    def make_decision(self, game_state: GameState) -> Dict[str, Any]:
        """
        ランダムな意思決定を行う

        Args:
            game_state: 型安全なゲーム状態オブジェクト

        Returns:
            {"action": "fold|check|call|raise|all_in", "amount": int}
        """
        available_actions = game_state.actions

        if not available_actions:
            return {"action": "fold", "amount": 0}

        # 利用可能なアクションに基づいて重み付きランダム選択
        action_options = []
        weights = []

        for action in available_actions:
            if action == "fold":
                action_options.append({"action": "fold", "amount": 0})
                weights.append(self.action_weights["fold"])
            elif action.startswith("check"):
                action_options.append({"action": "check", "amount": 0})
                weights.append(self.action_weights["check_call"])
            elif action.startswith("call"):
                # "call (20)" のような形式から金額を抽出
                amount = int(action.split("(")[1].split(")")[0])
                action_options.append({"action": "call", "amount": amount})
                weights.append(self.action_weights["check_call"])
            elif action.startswith("raise"):
                # "raise (min 40)" のような形式から最低レイズ額を抽出
                amount = int(action.split("min ")[1].split(")")[0])
                # ランダムにレイズ額を決定（最低額の1-3倍）
                raise_amount = amount * random.randint(1, 3)
                raise_amount = min(raise_amount, self.chips)
                action_options.append({"action": "raise", "amount": raise_amount})
                weights.append(self.action_weights["raise"])
            elif action.startswith("all-in"):
                action_options.append({"action": "all_in", "amount": self.chips})
                weights.append(self.action_weights["all_in"])

        # 重み付きランダム選択
        selected_action = random.choices(action_options, weights=weights)[0]
        return selected_action


class LLMPlayer(Player):
    """LLMプレイヤークラス（ADK使用）"""

    def __init__(
        self,
        player_id: int,
        name: str,
        initial_chips: int = 1000,
        model: str = "gemini-2.5-flash-lite",
    ):
        super().__init__(player_id, name, initial_chips)
        self.model = model
        self._agent = None
        self.last_decision_reasoning = ""  # 最後の判断理由を保存
        self._setup_agent()

    def _setup_agent(self):
        """ADKエージェントをセットアップ"""
        try:
            self._agent = Agent(
                name=f"poker_player_{self.id}",
                model=self.model,
                description="Expert Texas Hold'em poker player that makes strategic decisions",
                instruction="""You are an expert Texas Hold'em poker player. 

Your task is to analyze the current game state and make the best possible decision.

You will receive a game state with:
- Your hole cards
- Community cards (if any)
- Available actions
- Pot size and betting information
- Opponent information

You must respond with EXACTLY this JSON format:
{
  "action": "fold|check|call|raise|all_in",
  "amount": <number>,
  "reasoning": "Detailed explanation of your decision and strategic reasoning"
}

Rules:
- For "fold" and "check": amount should be 0
- For "call": use the exact amount needed to call
- For "raise": specify the total raise amount
- For "all_in": use your remaining chips
- ALWAYS include detailed reasoning explaining your strategic thinking

Consider:
- Hand strength and potential
- Pot odds and expected value
- Position advantage/disadvantage
- Opponent behavior patterns
- Stack sizes and tournament considerations
- Bluffing opportunities
- Risk vs reward analysis

Be strategic and analytical. Provide clear reasoning for every decision.""",
            )
        except ImportError:
            print("Warning: ADK not available, falling back to random behavior")
            self._agent = None

    def make_decision(self, game_state: GameState) -> Dict[str, Any]:
        """
        LLMを使った意思決定

        Args:
            game_state: 型安全なゲーム状態オブジェクト

        Returns:
            {"action": "fold|check|call|raise|all_in", "amount": int}
        """
        if self._agent is None:
            # ADKが利用できない場合はランダム行動
            random_player = RandomPlayer(self.id, self.name, self.chips)
            return random_player.make_decision(game_state)

        # ロガーは先に用意して例外時にも参照可能にする
        logger = logging.getLogger("poker_game")
        try:
            # ゲーム状態をプロンプトに変換
            prompt = self._create_decision_prompt(game_state)

            # ロガーを使ってプロンプトをログファイルに出力
            logger.info(f"LLM Prompt for {self.name}: {prompt}")

            # ADKエージェントに問い合わせ
            session_service = InMemorySessionService()
            runner = Runner(
                agent=self._agent,
                app_name="poker_game",
                session_service=session_service,
            )

            async def get_decision():
                session = await session_service.create_session(
                    app_name="poker_game",
                    user_id=f"player_{self.id}",
                    session_id=f"session_{self.id}",
                )

                # Content型のメッセージを作成
                content = types.Content(role="user", parts=[types.Part(text=prompt)])

                # run_asyncはイベントストリームを返すので、最終レスポンスを取得
                final_response_text = None
                async for event in runner.run_async(
                    user_id=f"player_{self.id}",
                    session_id=session.id,
                    new_message=content,
                ):
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            final_response_text = event.content.parts[0].text
                        break

                return final_response_text

            # 非同期関数を同期的に実行 (Python 3.7+)
            response_content = asyncio.run(get_decision())
            logger.info(f"LLM Response for {self.name}: {response_content}")

            print(f"test: {type(response_content)}")
            print(f"test: {response_content}")

            return self._parse_llm_response(response_content, game_state)

        except Exception as e:
            logger.error(f"LLM decision error for {self.name}: {e}")
            # エラー時はランダム行動
            random_player = RandomPlayer(self.id, self.name, self.chips)
            return random_player.make_decision(game_state)

    def _create_decision_prompt(self, game_state: GameState) -> str:
        """LLM用のプロンプトを作成"""

        return f"""
現在のポーカー状況を分析して、最適な行動を決定してください：

{json.dumps(game_state.to_dict(), ensure_ascii=False, indent=2)}

あなたのチップ数: {self.chips}
現在のベット額: {self.current_bet}

利用可能なアクション: {game_state.actions}

以下の要素を考慮して戦略的な判断を行ってください：
- ハンドの強さ
- ポットオッズ
- ポジション
- 相手の行動パターン
- スタックサイズ

最適な行動を以下のJSON形式で回答してください：
{{
  "action": "fold|check|call|raise|all_in",
  "amount": <数値>,
  "reasoning": "この行動を選択した理由"
}}

"""

    def _parse_llm_response(
        self, response: str, game_state: GameState
    ) -> Dict[str, Any]:
        """LLMの応答をパース（共通実装を使用）"""
        return super()._parse_llm_response(response, game_state, "LLM")

    def reset_for_new_hand(self):
        """新しいハンド用にリセット（理由もクリア）"""
        super().reset_for_new_hand()
        self.last_decision_reasoning = ""

    def get_last_reasoning(self) -> str:
        """最後の判断理由を取得"""
        return (
            self.last_decision_reasoning
            if self.last_decision_reasoning
            else "理由が記録されていません"
        )


class LLMApiPlayer(Player):
    """adk api_serverを使用し、Localhostに公開されたAgentを使用するプレイヤー"""

    def __init__(
        self,
        player_id: int,
        name: str,
        app_name: str,  # agents内のフォルダ名 (team1_agent)
        user_id: str,
        url: str = "http://localhost:8000",
        initial_chips: int = 1000,
    ):
        super().__init__(player_id, name, initial_chips)
        self.app_name = app_name
        self.user_id = user_id
        self.url = url
        self.last_decision_reasoning = ""  # 最後の判断理由を保存

    def make_decision(self, game_state: GameState) -> Dict[str, Any]:
        """
        LLMを使った意思決定

        Args:
            game_state: 型安全なゲーム状態オブジェクト

        Returns:
            {"action": "fold|check|call|raise|all_in", "amount": int}
        """

        try:
            logger = logging.getLogger("poker_game")
            session_id = str(uuid.uuid4())

            # ゲーム状態をJSON文字列に変換
            input_json = json.dumps(game_state.to_dict(), ensure_ascii=False, indent=2)
            logger.debug(f"LLM Prompt for {self.name}: {input_json}")

            # セッションの作成（短いタイムアウト）
            try:
                create_session = requests.post(
                    f"{self.url}/apps/{self.app_name}/users/{self.user_id}/sessions/{session_id}",
                    json={},
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                )
                if create_session.status_code != 200:
                    logger.error(
                        f"Session creation failed with status {create_session.status_code}: {create_session.text}"
                    )
                else:
                    logger.debug(f"Create Session: {create_session.json()}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Session creation request error for {self.name}: {e}")

            # 実際の実行リクエストを別スレッドで発行し、20秒待機・10秒ごとにログ
            def run_request():
                try:
                    return requests.post(
                        f"{self.url}/run",
                        json={
                            "app_name": self.app_name,
                            "user_id": self.user_id,
                            "session_id": session_id,
                            "new_message": {
                                "role": "user",
                                "parts": [{"text": input_json}],
                            },
                        },
                        headers={"Content-Type": "application/json"},
                        timeout=22,  # スレッド側は22秒でタイムアウト
                    )
                except Exception as e:
                    return e

            start = time.time()
            logged_10 = False
            with cf.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_request)
                response = None
                while True:
                    elapsed = time.time() - start
                    # 10秒経過ログ
                    if not logged_10 and elapsed >= 10:
                        logger.info(
                            f"Waiting for LLM API response for {self.name}... 10 seconds elapsed"
                        )
                        logged_10 = True
                    try:
                        # 短い待機でポーリング
                        response = future.result(timeout=0.2)
                        break
                    except cf.TimeoutError:
                        pass
                    if elapsed >= 20:
                        logger.warning(
                            f"LLM API response timeout for {self.name} after 20 seconds - folding"
                        )
                        if hasattr(self, "last_decision_reasoning"):
                            self.last_decision_reasoning = (
                                "20秒経過しても応答がないため、フォールドします"
                            )
                        return {
                            "action": "fold",
                            "amount": 0,
                            "reasoning": "20秒経過しても応答がないため、フォールドします",
                        }

            # スレッド結果の処理
            if isinstance(response, Exception):
                logger.error(f"LLM decision error for {self.name}: {response}")
                random_player = RandomPlayer(self.id, self.name, self.chips)
                return random_player.make_decision(game_state)

            if response is None:
                logger.error(f"Empty response received for {self.name}")
                return {
                    "action": "fold",
                    "amount": 0,
                    "reasoning": "20秒経過しても応答がないため、フォールドします",
                }

            if response.status_code != 200:
                logger.error(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
                if response.status_code == 422:
                    logger.error(
                        f"422 Error details - Request data: {json.dumps({
                        'app_name': self.app_name,
                        'user_id': self.user_id,
                        'session_id': session_id,
                        'message_preview': input_json[:200] + '...' if len(input_json) > 200 else input_json
                    }, indent=2)}"
                    )
                # 失敗時はフォールドで安全に進行
                return {
                    "action": "fold",
                    "amount": 0,
                    "reasoning": "20秒経過しても応答がないため、フォールドします",
                }

            # 正常応答
            try:
                logger.info(f"LLM raw Response for {self.name}: {response.json()}")
                logger.debug(
                    f"LLM [-1]['content']['parts'][0]['text'] for {self.name}:"
                )
                logger.debug(response.json()[-1]["content"]["parts"][0]["text"])
            except Exception:
                # JSONでない/形式不正でも後続のパースで対応
                pass

            return self._parse_llm_response(
                response.json()[-1]["content"]["parts"][0]["text"],
                game_state,
            )

        except Exception as e:
            logger = logging.getLogger("poker_game")
            logger.error(f"LLM decision error for {self.name}: {e}")
            # エラー時はランダム行動
            random_player = RandomPlayer(self.id, self.name, self.chips)
            return random_player.make_decision(game_state)

    def _parse_llm_response(
        self, response: str, game_state: GameState
    ) -> Dict[str, Any]:
        """LLMの応答をパース（共通実装を使用）"""
        return super()._parse_llm_response(response, game_state, "LLM API")

    def reset_for_new_hand(self):
        """新しいハンド用にリセット（理由もクリア）"""
        super().reset_for_new_hand()
        self.last_decision_reasoning = ""

    def get_last_reasoning(self) -> str:
        """最後の判断理由を取得"""
        return (
            self.last_decision_reasoning
            if self.last_decision_reasoning
            else "理由が記録されていません"
        )
