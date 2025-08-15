from typing import Dict, List

# 座席名（dealer_button から見て 0=BTN, 1=SB, 2=BB, ...）
_POSITIONS_BY_N: Dict[int, List[str]] = {
    2: ["BTN", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "UTG"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    6: ["BTN", "SB", "BB", "LJ", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "MP", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP1", "MP2", "HJ", "CO"],
}

# 人数×座席名ごとの推奨スコア（-1.0〜+1.0）
_SCORES_BY_N_POS: Dict[int, Dict[str, float]] = {
    2: {"BTN": +1.0, "BB": -1.0},
    3: {"BTN": +1.0, "SB": -0.7, "BB": -1.0},
    4: {"BTN": +1.0, "SB": -0.6, "BB": -1.0, "UTG": +0.2},
    5: {"BTN": +1.0, "SB": -0.65, "BB": -1.0, "UTG": +0.15, "CO": +0.55},
    6: {"BTN": +1.0, "SB": -0.7, "BB": -1.0, "LJ": +0.1, "HJ": +0.3, "CO": +0.6},
    7: {"BTN": +1.0, "SB": -0.7, "BB": -1.0, "UTG": +0.1, "MP": +0.2, "HJ": +0.4, "CO": +0.6},
    8: {"BTN": +1.0, "SB": -0.75, "BB": -1.0, "UTG": +0.05, "UTG+1": +0.15, "MP": +0.3, "HJ": +0.45, "CO": +0.65},
    9: {"BTN": +1.0, "SB": -0.8, "BB": -1.0, "UTG": 0.0, "UTG+1": +0.1, "MP1": +0.2, "MP2": +0.3, "HJ": +0.5, "CO": +0.7},
}

def position_check(your_id: int, dealer_button: int, player_num: int) -> dict:
    """
    Calculate your current table position and a positional advantage score.

    Args:
        your_id (int): Your seat/player ID (0..player_num-1).
        dealer_button (int): Seat ID of the dealer button.
        player_num (int): Number of players seated (>=2).

    Returns:
        dict: {
            "handed": <int>,
            "offset_from_button": <int>,   # 0=BTN, 1=SB, 2=BB, ...
            "position": "<name>",          # e.g., "BTN","SB","BB","UTG","CO",...
            "score": <float>               # -1.0..+1.0 (higher = more positional advantage)
        }
    """
    print(f"player_num: {player_num}, your_id: {your_id}, dealer_button: {dealer_button}")
    if player_num < 4:
        player_num = 4

    if not (0 <= your_id < player_num) or not (0 <= dealer_button < player_num):
        raise ValueError("your_id and dealer_button must be in [0, player_num).")

    # dealer_button からの相対座席
    offset = (your_id - dealer_button) % player_num

    # 座席名の決定
    ring = _POSITIONS_BY_N.get(player_num)
    if ring is None:
        # 未定義人数 → BTN,SB,BB の後は汎用ラベル
        ring = ["BTN", "SB", "BB"] + [f"SEAT{i}" for i in range(3, player_num)]

    position_name = ring[offset]

    # スコアの決定（人数×座席名の表 → なければ汎用スコア）
    scores_map = _SCORES_BY_N_POS.get(player_num)
    if scores_map is None:
        scores_map = _generic_scores(ring)

    score = scores_map.get(position_name)
    if score is None:
        # まれに表にない座席名が残った場合は汎用再計算
        score = _generic_scores(ring).get(position_name, 0.0)

    return {
        "player_num": player_num,
        "offset_from_button": offset,
        "position": position_name,
        "score": float(score),
    }
