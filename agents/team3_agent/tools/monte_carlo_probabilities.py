from pokerkit import *
from typing import List

def monte_carlo_probabilities(your_cards: List[str], community: List[str],players_num: int = 5) -> dict:
    """
    Monte Carlo simulation to estimate the probabilities of different poker hands.

    Args:
        your_cards (List[str]): Your hole cards (e.g., ["Ah", "Kd"]).
        community (List[str]): Community cards (e.g., ["10c", "Jc", "Qc"]).
        players_num (int): Number of player in this game.

    Returns:
        dict: Estimated probabilities of different poker hands.
    """
    try:
        result = calculate_hand_strength(
        players_num,
        parse_range(''.join(your_cards)),
        Card.parse(''.join(community)),
        2,
        5,
        Deck.STANDARD,
        (StandardHighHand,),
        sample_count=1000,
        )
        print(f"Monte Carlo simulation result: {result}")
        return {
            "monte_carlo_win_rate": result,
        }

    except Exception as e:
        print(f"Error during Monte Carlo simulation: {e}")
        return {}