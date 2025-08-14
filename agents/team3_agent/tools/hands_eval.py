def evaluate_hands(hand_input: str) -> str:
    """
    Comprehensive Texas Hold'em preflop hand evaluation

    Args:
        hand_input: JSON array format like '["Ah", "4d"]' (using h/d/c/s for suits)

    Returns:
        Evaluation result string with rank and strategic recommendation
    """
    if not hand_input or not isinstance(hand_input, str):
        return "Rank D: Invalid input (Weakest rank - Recommend fold)"
    
    try:
        # JSON配列形式の文字列をパース
        if not hand_input.startswith('[') or not hand_input.endswith(']'):
            return "Rank D: Invalid format - must be JSON array (Weakest rank - Recommend fold)"
        
        import json
        try:
            cards = json.loads(hand_input)
        except json.JSONDecodeError:
            return "Rank D: Invalid JSON format (Weakest rank - Recommend fold)"
        
        # カードの検証
        if not isinstance(cards, list) or len(cards) != 2:
            return "Rank D: Invalid format - need exactly 2 cards (Weakest rank - Recommend fold)"
        
        card1, card2 = cards
        
        # カードの正規化
        if not isinstance(card1, str) or not isinstance(card2, str):
            return "Rank D: Invalid card format - must be strings (Weakest rank - Recommend fold)"
        
        if len(card1) < 2 or len(card2) < 2:
            return "Rank D: Invalid card length (Weakest rank - Recommend fold)"
        
        rank1, suit1 = card1[:-1], card1[-1]
        rank2, suit2 = card2[:-1], card2[-1]
        
        # ランクの正規化
        if rank1 == "10":
            rank1 = "T"
        if rank2 == "10":
            rank2 = "T"

        # 有効なランクとスートのチェック（短縮表記形式）
        valid_ranks = {"2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"}
        valid_suits = {"h", "d", "c", "s"}
        
        if rank1 not in valid_ranks or rank2 not in valid_ranks:
            return "Rank D: Invalid rank (Weakest rank - Recommend fold)"
        
        if suit1 not in valid_suits or suit2 not in valid_suits:
            return "Rank D: Invalid suit (Weakest rank - Recommend fold)"

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
            "AA", "AKs", "AKo", "KK", "QQ", "AQs", "AJs", "ATs", "KQs", "AQo", "JJ", "TT", "99"
        }
        
        if hand_notation in s_rank_hands:
            return f"Rank S: {hand_notation} (Premium hand - Always raise/call)"

        a_rank_hands = {
            "AJo", "ATo", "A9s", "A8s", "A7s", "A5s", "A4s", "A3s", "A2s", 
            "KJs", "KTs", "K9s","KQo", "QJs", "QTs", "AJo", "KJo", "T9s", "JTs", 
            "88", "77", "66", "55", 
        }
        
        if hand_notation in a_rank_hands:
            return f"Rank A: {hand_notation} (Strong hand - Always call or raise)"

        b_rank_hands = {
          "A9o","KTo", "QJo", "JTo", "Q9s", "J9s", "T8s", "98s", "44", "33", "22"
        }
        
        if hand_notation in b_rank_hands:
            return f"Rank B: {hand_notation} (Medium hand - Consider position and opponent action)"

        c_rank_hands = {
            "A8o", "A7o", "A6o",
            "K9o", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s", 
            "QTo", "Q9o", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s", 
            "J9o", "J8s", "J7s", "J6s",
            "T9s", "T8s", "T7s",
            "97s", "96s",
            "87s", "86s",
            "76s", "75s",
            "65s", "64s",
            "54s",
        }
        
        if hand_notation in c_rank_hands:
            return f"Rank C: {hand_notation} (Marginal hand - Position and bet size dependent)"
        
        return f"Rank D: {hand_notation} (Weak hand - Fold unless can check)"
            
    except Exception as e:
        return f"Rank D: Error - {str(e)} (Weakest rank - Recommend fold)"
