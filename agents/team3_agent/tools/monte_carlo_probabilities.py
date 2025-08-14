from pokerkit import *
from typing import List

def monte_carlo_probabilities(your_cards: List[str], community: List[str], player_num: int = 5) -> dict:
    """
    Monte Carlo simulation to estimate the probabilities of different poker hands.

    Args:
        your_cards (List[str]): Your hole cards in short format (e.g., ["Ah", "Kd"]).
        community (List[str]): Community cards in short format (e.g., ["Tc", "Jc", "Qc"]).
        player_num (int): Number of player in this game.

    Returns:
        dict: Estimated probabilities of different poker hands.
    """
    try:
        hole_cards_str = ''.join(your_cards)
        community_cards_str = ''.join(community) if community else ""
        result = calculate_hand_strength(
        player_num,
        parse_range(hole_cards_str),
        Card.parse(community_cards_str) if community_cards_str else None,
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
