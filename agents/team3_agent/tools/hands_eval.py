def evaluate_hands(hand_input: str) -> str:
    """
    Comprehensive Texas Hold'em preflop hand evaluation

    Args:
        hand_input: Format like "5c 4s" (using c/s/h/d for suits)

    Returns:
        Evaluation result string with rank and strategic recommendation
    """
    if not hand_input or not isinstance(hand_input, str):
        return "Rank D: Invalid input (Weakest rank - Recommend fold)"
    
    try:
        cards = hand_input.strip().split()
        if len(cards) != 2:
            return "Rank D: Invalid format (Weakest rank - Recommend fold)"
        
        card1, card2 = cards
        
        rank1, suit1 = card1[:-1], card1[-1]
        rank2, suit2 = card2[:-1], card2[-1]
        
        if rank1 == "10":
            rank1 = "T"
        if rank2 == "10":
            rank2 = "T"

        is_suited = suit1 == suit2

        rank_order = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
        
        if rank_order[rank1] >= rank_order[rank2]:
            high_rank, low_rank = rank1, rank2
        else:
            high_rank, low_rank = rank2, rank1

        if high_rank == low_rank:
            hand_notation = f"{high_rank}{low_rank}"  # Pair
        else:
            suited_marker = "s" if is_suited else "o"
            hand_notation = f"{high_rank}{low_rank}{suited_marker}"

        s_rank_hands = {
            "AA", "AKs", "AKo", "KK", "QQ", "AQs", "AJs", "ATs", "KQs", "AQo"
        }
        
        if hand_notation in s_rank_hands:
            return f"Rank S: {hand_notation} (Premium hand - Always raise/call)"

        a_rank_hands = {
            "A9s", "A8s", "A7s", "A5s", "A4s", "A3s", "A2s", 
            "KTs", "K9s", "QTs", "KJo", "ATo", "T9s", 
            "JJ", "TT", "99", "88", "77", "66", "55"
        }
        
        if hand_notation in a_rank_hands:
            return f"Rank A: {hand_notation} (Strong hand - Always call or raise)"

        b_rank_hands = {
            "Q9s", "QJo", "J9s", "A9o", "98s", "44", "33", "22"
        }
        
        if hand_notation in b_rank_hands:
            return f"Rank B: {hand_notation} (Medium hand - Consider position and opponent action)"

        c_rank_hands = {
            "Q5s", "Q4s", "Q3s", "Q2s", "J6s", "T7s", "96s", "98o", 
            "86s", "75s", "A6o", "64s", "54s"
        }
        
        if hand_notation in c_rank_hands:
            return f"Rank C: {hand_notation} (Marginal hand - Position and bet size dependent)"
        
        return f"Rank D: {hand_notation} (Weak hand - Fold unless can check)"
            
    except Exception as e:
        return f"Rank D: Error - {str(e)} (Weakest rank - Recommend fold)"
