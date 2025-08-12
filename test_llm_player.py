#!/usr/bin/env python3
"""
Test script for ADK LLM Player
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

sys.path.append(".")

from poker.player_models import LLMPlayer


def test_llm_player():
    """Test the LLM player with a sample game state"""

    # サンプルゲーム状態
    sample_game_state = {
        "hole_cards": ["A♠", "K♠"],
        "community_cards": ["Q♠", "J♠", "10♦"],
        "pot": 100,
        "current_bet": 20,
        "actions": ["fold", "call (20)", "raise (min 40)", "all-in"],
        "players": [
            {"id": 1, "chips": 1000, "bet": 0, "status": "active"},
            {"id": 2, "chips": 800, "bet": 20, "status": "active"},
        ],
        "phase": "flop",
    }

    print("=== ADK LLM Player Test ===")
    print(f"Game State: {sample_game_state}")
    print()

    # LLMプレイヤーを作成
    llm_player = LLMPlayer(
        player_id=1,
        name="ADK_Player",
        initial_chips=1000,
        model="gemini-2.5-flash-lite",
    )

    print(f"Created LLM Player: {llm_player}")
    print(f"Agent available: {llm_player._agent is not None}")
    print()

    try:
        # 意思決定をテスト
        print("Making decision...")
        decision = llm_player.make_decision(sample_game_state)

        print(f"Decision: {decision}")

        # 判断理由も表示
        reasoning = llm_player.get_last_reasoning()
        print(f"Reasoning: {reasoning}")
        print()

        # 決定の妥当性をチェック
        action = decision.get("action")
        amount = decision.get("amount")

        print("=== Decision Analysis ===")
        print(f"Action: {action}")
        print(f"Amount: {amount}")
        print(f"Reasoning: {reasoning}")
        print()

        print("=== Validation ===")
        # 基本的な妥当性チェック
        valid_actions = ["fold", "check", "call", "raise", "all_in"]
        if action in valid_actions:
            print("✅ Valid action")
        else:
            print("❌ Invalid action")

        if isinstance(amount, int) and amount >= 0:
            print("✅ Valid amount")
        else:
            print("❌ Invalid amount")

        if reasoning and len(reasoning.strip()) > 0:
            print("✅ Reasoning provided")
        else:
            print("❌ No reasoning provided")

    except Exception as e:
        print(f"❌ Error during decision making: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 環境変数チェック
    if not os.getenv("GOOGLE_API_KEY"):
        print(
            "Error: GOOGLE_API_KEY not set. You must set this environment variable for the LLM to work."
        )
        print("You can set it with: export GOOGLE_API_KEY=your_api_key")
        exit(1)

    test_llm_player()
