# tools/hand_history_tools.py
from typing import List, Dict, Any
import re
import sqlite3
import json
from collections import defaultdict

# -------------------------
# SQLite: 初期化ヘルパ
# -------------------------
def _ensure_db(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS player_stats (
            player_id INTEGER PRIMARY KEY,
            hands_played INTEGER NOT NULL DEFAULT 0,
            showdowns INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            total_contributed INTEGER NOT NULL DEFAULT 0,
            total_won INTEGER NOT NULL DEFAULT 0
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS hands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_history TEXT NOT NULL,
            winners_json TEXT,
            pot INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        con.commit()
    finally:
        con.close()

# -------------------------
# ハンド切り出し
# -------------------------
_SHOWDOWN_WON_RE   = re.compile(r"^Showdown:\s*Player\s+(\d+)\s+won\s+(\d+)", re.I)
_SHOWDOWN_WINNERS  = re.compile(r"^Showdown winners:\s*([0-9,\s]+).*\bpot=(\d+)\b.*(?:split=(\d+))?", re.I)
_SHOW_HAND_RE      = re.compile(r"^Showdown:\s*Player\s+(\d+)\s+hand=", re.I)

_BLIND_SB_RE       = re.compile(r"^Player\s+(\d+)\s+posted\s+small blind\s+(\d+)", re.I)
_BLIND_BB_RE       = re.compile(r"^Player\s+(\d+)\s+posted\s+big blind\s+(\d+)", re.I)
_CALL_RE           = re.compile(r"^Player\s+(\d+)\s+called\s+(\d+)", re.I)
_RAISE_TO_RE       = re.compile(r"^Player\s+(\d+)\s+raised\s+to\s+(\d+)", re.I)
_BET_RE            = re.compile(r"^Player\s+(\d+)\s+bet\s+(\d+)", re.I)
_CHECK_RE          = re.compile(r"^Player\s+(\d+)\s+checked", re.I)
_FOLD_RE           = re.compile(r"^Player\s+(\d+)\s+folded", re.I)

_STREET_RE         = re.compile(r"^(Flop|Turn|River)\s+dealt:", re.I)

def _slice_last_completed_hand(history: List[str]) -> List[str]:
    """末尾から見て最後に完了（Showdown〜）した1ハンドを切り出す。無ければ []。"""
    if not history: 
        return []
    # 最後のショーダウン行を探す
    last_i = -1
    for i in range(len(history)-1, -1, -1):
        line = history[i]
        if _SHOWDOWN_WON_RE.search(line) or _SHOWDOWN_WINNERS.search(line):
            last_i = i
            break
    if last_i == -1:
        return []

    # そのハンドの開始位置（直前の SB/BB 投稿 を起点にするのが安全）
    start_i = 0
    for j in range(last_i, -1, -1):
        if _BLIND_SB_RE.search(history[j]) or _BLIND_BB_RE.search(history[j]):
            start_i = j
            # さらに直前にも SB/BB が連続しているケースに備えて、最も近い “かたまり” の先頭へ
            k = j
            while k-1 >= 0 and (_BLIND_SB_RE.search(history[k-1]) or _BLIND_BB_RE.search(history[k-1])):
                k -= 1
                start_i = k
            break

    return history[start_i:last_i+1]

# -------------------------
# コントリビューション集計
# -------------------------
def _sum_contributions(hand_lines: List[str]) -> Dict[int, int]:
    """
    ハンド内のプレイヤー別投資総額（チップ）を概算。
    ストリートごとに “raise to X / bet X” は当該プレイヤーのそのストリート支払累計を X に上書き、
    差分だけ総額にカウント。street 切替（Flop/Turn/River dealt）で per-street 累計をリセット。
    """
    total_by_player: Dict[int, int] = defaultdict(int)
    street_paid: Dict[int, int] = defaultdict(int)  # ストリート内での支払累計
    for line in hand_lines:
        if _STREET_RE.search(line):
            street_paid = defaultdict(int)
            continue

        m = _BLIND_SB_RE.search(line)
        if m:
            pid, amt = int(m.group(1)), int(m.group(2))
            total_by_player[pid] += amt
            # プリフロップのストリート貢献として上書き
            street_paid[pid] += amt
            continue

        m = _BLIND_BB_RE.search(line)
        if m:
            pid, amt = int(m.group(1)), int(m.group(2))
            total_by_player[pid] += amt
            street_paid[pid] += amt
            continue

        m = _CALL_RE.search(line)
        if m:
            pid, amt = int(m.group(1)), int(m.group(2))
            total_by_player[pid] += amt
            street_paid[pid] += amt
            continue

        m = _RAISE_TO_RE.search(line)
        if m:
            pid, to_amt = int(m.group(1)), int(m.group(2))
            add = max(0, to_amt - street_paid.get(pid, 0))
            total_by_player[pid] += add
            street_paid[pid] = to_amt
            continue

        m = _BET_RE.search(line)
        if m:
            pid, bet_amt = int(m.group(1)), int(m.group(2))
            add = max(0, bet_amt - street_paid.get(pid, 0))
            total_by_player[pid] += add
            street_paid[pid] = bet_amt
            continue

        # checked/folded は投資なし
        # その他の行は無視
    return dict(total_by_player)

# -------------------------
# 勝者・ショーダウン参加者の抽出
# -------------------------
def _extract_winners_and_showdowns(hand_lines: List[str]) -> Dict[str, Any]:
    winners: List[int] = []
    total_won_by_player: Dict[int, int] = defaultdict(int)
    showdown_participants: set[int] = set()

    pot_sum = None

    for line in hand_lines:
        m = _SHOW_HAND_RE.search(line)
        if m:
            showdown_participants.add(int(m.group(1)))
            continue

        m = _SHOWDOWN_WON_RE.search(line)
        if m:
            pid, won = int(m.group(1)), int(m.group(2))
            winners = [pid]
            total_won_by_player[pid] += won
            # pot_sum 不明だが won を pot として扱う（単独勝ち想定）
            pot_sum = (pot_sum or 0) + won
            continue

        m = _SHOWDOWN_WINNERS.search(line)
        if m:
            ids_str, pot, split = m.group(1), int(m.group(2)), m.group(3)
            ids = [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
            winners = ids
            pot_sum = pot
            if split is not None:
                each = int(split)
                for pid in ids:
                    total_won_by_player[pid] += each
            # split が無い場合は配分不明のため total_won_by_player は更新しない

    return {
        "winners": winners,
        "total_won_by_player": dict(total_won_by_player),
        "showdown_participants": list(showdown_participants),
        "pot": pot_sum,
    }

# -------------------------
# DB 更新
# -------------------------
def _update_db_with_hand(db_path: str,
                         hand_lines: List[str],
                         contrib: Dict[int, int],
                         winners: List[int],
                         won_by: Dict[int, int],
                         showdowners: List[int]) -> Dict[str, Any]:
    _ensure_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()

        # hands テーブルへ原文保存
        cur.execute(
            "INSERT INTO hands(raw_history, winners_json, pot) VALUES (?, ?, ?)",
            (json.dumps(hand_lines, ensure_ascii=False), json.dumps(winners), None)
        )

        # 参加者の推定：投資がある or ショーダウン出現 or 勝者
        participants = set(contrib.keys()) | set(showdowners) | set(winners)
        for pid in participants:
            cur.execute("""
                INSERT INTO player_stats(player_id) VALUES(?)
                ON CONFLICT(player_id) DO NOTHING
            """, (pid,))
            # hands_played
            cur.execute("UPDATE player_stats SET hands_played = hands_played + 1 WHERE player_id = ?", (pid,))
            # contributed
            added = int(contrib.get(pid, 0))
            if added:
                cur.execute("UPDATE player_stats SET total_contributed = total_contributed + ? WHERE player_id = ?", (added, pid))
            # showdown
            if pid in showdowners:
                cur.execute("UPDATE player_stats SET showdowns = showdowns + 1 WHERE player_id = ?", (pid,))
            # win / won amount
            if pid in winners:
                cur.execute("UPDATE player_stats SET wins = wins + 1 WHERE player_id = ?", (pid,))
            won_amt = int(won_by.get(pid, 0))
            if won_amt:
                cur.execute("UPDATE player_stats SET total_won = total_won + ? WHERE player_id = ?", (won_amt, pid))

        con.commit()
    finally:
        con.close()

    return {
        "participants": sorted(list(participants)),
        "contributed": contrib,
        "winners": winners,
        "won_by": won_by,
    }

# -------------------------
# 公開ツール1：記録＆更新
# -------------------------
def record_hand_from_history(history: List[str], db_path: str = "poker_stats.sqlite") -> Dict[str, Any]:
    """
    直近のショーダウンまでの1ハンドを解析し、DBに反映。
    Returns:
      {
        "success": true/false,
        "hand_summary": {
          "participants": [...],
          "contributed": {player_id: chips, ...},
          "winners": [player_id, ...],
          "won_by": {player_id: chips, ...}
        },
        "error": "... (optional)"
      }
    """
    try:
        hand = _slice_last_completed_hand(history or [])
        if not hand:
            return {"success": False, "error": "No completed hand with showdown found."}

        contrib = _sum_contributions(hand)
        wd = _extract_winners_and_showdowns(hand)
        summary = _update_db_with_hand(
            db_path=db_path,
            hand_lines=hand,
            contrib=contrib,
            winners=wd["winners"],
            won_by=wd["total_won_by_player"],
            showdowners=wd["showdown_participants"],
        )
        return {"success": True, "hand_summary": summary}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}

# -------------------------
# 公開ツール2：集計取得
# -------------------------
def get_player_stats(db_path: str = "poker_stats.sqlite") -> Dict[str, Any]:
    """
    Returns:
      {
        "success": true,
        "stats": [
          {"player_id": 0, "hands_played": 3, "showdowns": 2, "wins": 1, "total_contributed": 480, "total_won": 310},
          ...
        ]
      }
    """
    try:
        _ensure_db(db_path)
        con = sqlite3.connect(db_path)
        try:
            cur = con.cursor()
            cur.execute("""
              SELECT player_id, hands_played, showdowns, wins, total_contributed, total_won
              FROM player_stats ORDER BY player_id
            """)
            rows = cur.fetchall()
        finally:
            con.close()

        stats = [{
            "player_id": r[0],
            "hands_played": r[1],
            "showdowns": r[2],
            "wins": r[3],
            "total_contributed": r[4],
            "total_won": r[5],
        } for r in rows]
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}
