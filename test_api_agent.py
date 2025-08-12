import requests
import uuid
import json
from poker.player_models import LLMApiPlayer
from poker.game_models import Card, Suit, GameState


def test_api_agent():
    input_json = """
    {
        "your_id": 1,
        "phase": "preflop",
        "your_cards": [
            "7♥",
            "J♦"
        ],
        "community": [],
        "your_chips": 1000,
        "your_bet_this_round": 0,
        "pot": 30,
        "to_call": 20,
        "dealer_button": 2,
        "current_turn": 1,
        "players": [
            {
            "id": 0,
            "chips": 980,
            "bet": 20,
            "status": "active"
            },
            {
            "id": 2,
            "chips": 1000,
            "bet": 0,
            "status": "active"
            },
            {
            "id": 3,
            "chips": 990,
            "bet": 10,
            "status": "active"
            }
        ],
        "actions": [
            "fold",
            "call (20)",
            "raise (min 40)",
            "all-in (1000)"
        ],
        "history": [
            "Player 3 posted small blind 10",
            "Player 0 posted big blind 20"
        ]
    }
    """

    llm_player = LLMApiPlayer(
        player_id=0,
        name="test_player",
        app_name="team1_agent",
        user_id="test_user",
        url="http://localhost:8000",
        initial_chips=1000,
    )

    # JSON文字列をGameStateオブジェクトに変換
    game_state_dict = json.loads(input_json)
    game_state = GameState.from_dict(game_state_dict)

    print(llm_player.make_decision(game_state))


if __name__ == "__main__":
    test_api_agent()
