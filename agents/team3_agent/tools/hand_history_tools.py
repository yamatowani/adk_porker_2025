from __future__ import annotations
import sqlite3
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

# ====== ユーティリティ：役名→強さ（必要ならショーダウン集計で使用） ======
HAND_STRENGTH_ORDER = {
    "Straight Flush": 9,
    "Four of a Kind": 8,
    "Full House": 7,
    "Flush": 6,
    "Straight": 5,
    "Three of a Kind": 4,
    "Two Pair": 3,
    "One Pair": 2,
    "High Card": 1,
}
def hand_category_strength(name: str) -> int:
    # 安全側：未知の表記は 0
    return HAND_STRENGTH_ORDER.get(name.strip(), 0)


# ====== DB レイヤ ======
class PlayerStatsDB:
    def __init__(self, path: str = "poker_stats.sqlite3"):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS player_stats (
              player_id INTEGER PRIMARY KEY,
              hands_played INTEGER NOT NULL DEFAULT 0,
              saw_flop INTEGER NOT NULL DEFAULT 0,
              went_to_showdown INTEGER NOT NULL DEFAULT 0,
              won_showdown INTEGER NOT NULL DEFAULT 0,
              vpip INTEGER NOT NULL DEFAULT 0,
              pfr INTEGER NOT NULL DEFAULT 0,
              three_bet INTEGER NOT NULL DEFAULT 0,
              cold_call INTEGER NOT NULL DEFAULT 0,
              total_contributed INTEGER NOT NULL DEFAULT 0,
              total_won INTEGER NOT NULL DEFAULT 0
            );

            -- ショーダウンの役カテゴリ分布（任意拡張用）
            CREATE TABLE IF NOT EXISTS showdown_buckets (
              player_id INTEGER NOT NULL,
              category TEXT NOT NULL,
              count INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (player_id, category)
            );
            """
        )
        self.conn.commit()

    def _ensure_player(self, pid: int):
        cur = self.conn.execute("SELECT 1 FROM player_stats WHERE player_id=?", (pid,))
        if not cur.fetchone():
            self.conn.execute("INSERT INTO player_stats(player_id) VALUES (?)", (pid,))

    def inc(self, pid: int, column: str, delta: int = 1):
        self._ensure_player(pid)
        self.conn.execute(
            f"UPDATE player_stats SET {column} = {column} + ? WHERE player_id = ?",
            (delta, pid),
        )

    def add_contribution(self, pid: int, chips: int):
        self._ensure_player(pid)
        self.conn.execute(
            "UPDATE player_stats SET total_contributed = total_contributed + ? WHERE player_id=?",
            (chips, pid),
        )

    def add_won(self, pid: int, chips: int):
        self._ensure_player(pid)
        self.conn.execute(
            "UPDATE player_stats SET total_won = total_won + ? WHERE player_id=?",
            (chips, pid),
        )

    def inc_bucket(self, pid: int, category: str, delta: int = 1):
        self._ensure_player(pid)
        self.conn.execute(
            """
            INSERT INTO showdown_buckets(player_id, category, count)
            VALUES (?, ?, ?)
            ON CONFLICT(player_id, category) DO UPDATE SET count = count + excluded.count
            """,
            (pid, category, delta),
        )

    def commit(self):
        self.conn.commit()


# ====== ハンド状態（インクリメンタル更新用） ======
@dataclass
class HandState:
    # ハンド内の一時状態
    in_hand: Set[int] = field(default_factory=set)
    street: str = "preflop"  # preflop/flop/turn/river
    pfr_player: Optional[int] = None  # プリフロップの初回レイザー
    has_preflop_raise: bool = False
    # チップの支払い累計（ストリート内/ハンド全体）
    street_paid: Dict[int, int] = field(default_factory=dict)
    total_paid: Dict[int, int] = field(default_factory=dict)
    # 事象フラグ
    vpip_set: Set[int] = field(default_factory=set)
    pfr_set: Set[int] = field(default_factory=set)
    three_bet_set: Set[int] = field(default_factory=set)
    cold_call_set: Set[int] = field(default_factory=set)
    saw_flop_marked: bool = False
    # ショーダウン
    went_to_showdown: Set[int] = field(default_factory=set)
    winners: Dict[int, int] = field(default_factory=dict)  # winner_id -> won_chips
    revealed_category: Dict[int, str] = field(default_factory=dict)  # 任意


# ====== インジェスト・エンジン ======
class HistoryIngestor:
    # 代表的なログ行パターン
    RE_SMALL_BLIND = re.compile(r"^Player (\d+) posted small blind (\d+)")
    RE_BIG_BLIND   = re.compile(r"^Player (\d+) posted big blind (\d+)")
    RE_RAISED_TO   = re.compile(r"^Player (\d+) raised to (\d+)")
    RE_CALLED      = re.compile(r"^Player (\d+) called (\d+)")
    RE_BET         = re.compile(r"^Player (\d+) bet (\d+)")  # 一部ログ用（簡易扱い）
    RE_CHECKED     = re.compile(r"^Player (\d+) checked")
    RE_FOLDED      = re.compile(r"^Player (\d+) folded")
    RE_DEALT       = re.compile(r"^(Flop|Turn|River) dealt:")
    RE_WON         = re.compile(r"^Showdown: Player (\d+) won (\d+)")
    RE_WINNERS     = re.compile(r"^Showdown winners: ([\d, ]+).*pot=(\d+)")
    RE_SHOWDOWN_HAND = re.compile(r"^Showdown: Player (\d+) hand=([^:]+):")

    RE_HAND_START  = re.compile(r"^Player \d+ posted small blind \d+")

    def __init__(self, db: PlayerStatsDB):
        self.db = db

    def ingest_history(self, history_lines: List[str], players_in_snapshot: Optional[List[Dict]] = None):
        """
        履歴全体（複数ハンド混在可）を受け取り、ハンドごとに分割して集計。
        players_in_snapshot はオプション（現在着席プレイヤーの id など）。無くてもOK。
        """
        hand_lines = self._extract_latest_hand_by_showdown(history_lines)
        print(f"-------hand_lines: {hand_lines}------------")
        if hand_lines:
            self._ingest_single_hand(hand_lines)

        self.db.commit()

    def _extract_latest_hand_by_showdown(self, lines: List[str]) -> List[str]:
        """
        最新ショーダウン行（含む）を終端とし、直前ショーダウン行の「次の行」を始端とする区間を返す。
        直前が無ければ先頭〜最新ショーダウン。ショーダウンが無ければフォールバック。
        """
        if not lines:
            return []

        # “Showdown” を含む全インデックスを取得（不戦勝/公開どちらも拾える）
        showdown_idxs = [
            i for i, ln in enumerate(lines)
            if (
                self.RE_WON.search(ln)            # "Showdown: ... won ..."
                or self.RE_WINNERS.search(ln)     # "Showdown winners: ..."
            )
        ]
        if showdown_idxs:
            last = showdown_idxs[-1]                             # 最新ショーダウン（終端、含む）
            prev = showdown_idxs[-2] if len(showdown_idxs) >= 2 else None
            start = (prev + 1) if prev is not None else 0       # 直前ショーダウンの次行 or 先頭
            return lines[start:last + 1]

        else:
            return lines[:]

    def _ingest_single_hand(self, lines: List[str]):
        # 初期化：このハンドに登場した player_id を動的に収集
        state = HandState()

        # ハンド参加者検出（粗いが十分）：最初の blind/行動したプレイヤーを in_hand に追加
        def ensure_player(pid: int):
            state.in_hand.add(pid)
            if pid not in state.street_paid:
                state.street_paid[pid] = 0
            if pid not in state.total_paid:
                state.total_paid[pid] = 0

        # ハンド開始：hands_played++ は「最初にアクションが出た人」を分母にすると歪む。
        # ここでは blinds/post/act があったプレイヤーのみ +1（着席全員で分母にしたい場合は別管理）
        seen_any_action: Set[int] = set()

        for raw in lines:
            line = raw.strip()

            # --- blinds ---
            m = self.RE_SMALL_BLIND.match(line)
            if m:
                pid, amt = int(m.group(1)), int(m.group(2))
                ensure_player(pid)
                self._pay(pid, amt, state)
                seen_any_action.add(pid)
                continue

            m = self.RE_BIG_BLIND.match(line)
            if m:
                pid, amt = int(m.group(1)), int(m.group(2))
                ensure_player(pid)
                self._pay(pid, amt, state)
                seen_any_action.add(pid)
                continue

            # --- actions ---
            m = self.RE_RAISED_TO.match(line)
            if m:
                pid, to_amt = int(m.group(1)), int(m.group(2))
                ensure_player(pid)
                add = max(0, to_amt - state.street_paid.get(pid, 0))
                self._pay(pid, add, state)
                seen_any_action.add(pid)

                # preflop 情報
                if state.street == "preflop":
                    if not state.has_preflop_raise:
                        state.has_preflop_raise = True
                        state.pfr_player = pid
                        state.pfr_set.add(pid)
                    else:
                        # 3bet 以上
                        state.three_bet_set.add(pid)
                else:
                    # ポストフロップのレイズは今は詳細未集計
                    pass

                # VPIP（自発参加）判定：blind 以外のコール/レイズで一度だけ
                state.vpip_set.add(pid)
                continue

            m = self.RE_CALLED.match(line)
            if m:
                pid, amt = int(m.group(1)), int(m.group(2))
                ensure_player(pid)
                # call は「to X」表記でなく差分。ここでは素直に amt を支払いとして計上
                self._pay(pid, amt, state)
                seen_any_action.add(pid)

                if state.street == "preflop":
                    if state.has_preflop_raise:
                        # 既に誰かがレイズしていて未投資者のコール → cold call になりうるが
                        # 正確には「その時点の street_paid==0 だったか」で判定
                        # ここでは簡略：preflopに raise が存在 → cold_call 候補
                        state.cold_call_set.add(pid)
                    # VPIP
                    state.vpip_set.add(pid)
                else:
                    # ポストフロップのコールは今は未細分化（拡張フック）
                    pass
                continue

            m = self.RE_BET.match(line)
            if m:
                pid, amt = int(m.group(1)), int(m.group(2))
                ensure_player(pid)
                # ベットの表記は実装依存。簡易的に「差分=amt」を支払いとして計上
                self._pay(pid, amt, state)
                seen_any_action.add(pid)
                # ポストフロップの c-bet/プローブ/ドンク等の判定フックはここに追加可能
                continue

            m = self.RE_CHECKED.match(line)
            if m:
                pid = int(m.group(1))
                ensure_player(pid)
                seen_any_action.add(pid)
                continue

            m = self.RE_FOLDED.match(line)
            if m:
                pid = int(m.group(1))
                ensure_player(pid)
                # フォールド：以後 in_hand から除外
                if pid in state.in_hand:
                    state.in_hand.remove(pid)
                seen_any_action.add(pid)
                continue

            m = self.RE_DEALT.match(line)
            if m:
                street_word = m.group(1).lower()
                # ストリート遷移
                state.street = street_word
                state.street_paid = {pid: 0 for pid in state.in_hand}
                # フロップが配られた瞬間に、残存者へ saw_flop++
                if street_word == "flop" and not state.saw_flop_marked:
                    for pid in state.in_hand:
                        self.db.inc(pid, "saw_flop", 1)
                    state.saw_flop_marked = True
                continue

            m = self.RE_SHOWDOWN_HAND.match(line)
            if m:
                pid = int(m.group(1))
                cat = m.group(2).strip()
                state.went_to_showdown.add(pid)
                state.revealed_category[pid] = cat
                continue

            m = self.RE_WON.match(line)
            if m:
                pid, chips = int(m.group(1)), int(m.group(2))
                state.winners[pid] = state.winners.get(pid, 0) + chips
                continue

            m = self.RE_WINNERS.match(line)
            if m:
                # バックアップ：Winner IDs + pot。個別配分は不明なのでここではスキップ or 均等割りにしたい場合は下記を使う
                # winners_str, pot = m.group(1), int(m.group(2))
                # winner_ids = [int(x.strip()) for x in winners_str.split(",")]
                # share = pot // len(winner_ids)
                # for wid in winner_ids:
                #     state.winners[wid] = state.winners.get(wid, 0) + share
                pass

        # hands_played++（そのハンドで何らかの行動/ブラインドを記録したプレイヤーに付与）
        for pid in seen_any_action:
            self.db.inc(pid, "hands_played", 1)

        # went_to_showdown / won_showdown / total_won
        for pid in state.went_to_showdown:
            self.db.inc(pid, "went_to_showdown", 1)
        for wid, amt in state.winners.items():
            self.db.inc(wid, "won_showdown", 1)
            self.db.add_won(wid, amt)

        # 役カテゴリのヒストグラム
        for pid, cat in state.revealed_category.items():
            self.db.inc_bucket(pid, cat, 1)

        # VPIP / PFR / 3bet / cold_call
        for pid in state.vpip_set:
            self.db.inc(pid, "vpip", 1)
        for pid in state.pfr_set:
            self.db.inc(pid, "pfr", 1)
        for pid in state.three_bet_set:
            self.db.inc(pid, "three_bet", 1)
        for pid in state.cold_call_set:
            self.db.inc(pid, "cold_call", 1)

        # ここで commit はまとめて行う（ingest_history の最後で commit 済み）

    def _pay(self, pid: int, add_amount: int, state: HandState):
        if add_amount <= 0:
            return
        state.street_paid[pid] = state.street_paid.get(pid, 0) + add_amount
        state.total_paid[pid] = state.total_paid.get(pid, 0) + add_amount
        # DB の total_contributed も即時更新（ハンド途中で落ちても差分が反映される）
        self.db.add_contribution(pid, add_amount)

def save_history(history: List[str])-> None:
    """
    Ingest raw poker hand history lines and persist per-player statistics.

    This utility function takes a chronological list of raw log lines
    (e.g., "Player 1 posted small blind 10", "Flop dealt: ...", 
    "Showdown: Player 0 won 190", ...), splits them into hands, parses
    actions per street, and updates an SQLite database with incremental
    player stats.

    Parameters
    ----------
    history : List[str]
        Chronologically ordered log lines. May contain **multiple hands**.
        Hand boundaries are detected by lines like "Player X posted small blind Y".
        Example:
            [
              "Player 1 posted small blind 10",
              "Player 2 posted big blind 20",
              "Player 0 raised to 80",
              "Flop dealt: 3♣, 7♥, 5♣",
              "Showdown: Player 1 won 190",
              "Player 0 posted small blind 10",
              "Player 1 posted big blind 20",
              ...
            ]
    """
    db = PlayerStatsDB("./team3_agent/db/poker_stats.sqlite3")
    ingestor = HistoryIngestor(db)
    ingestor.ingest_history(history)
    return None


if __name__ == "__main__":
    db = PlayerStatsDB("poker_stats.sqlite3")  # ファイル保存なら "poker_stats.sqlite3" or ":memory:"
    ingestor = HistoryIngestor(db)

    history = [
        # Hand 1
        "Player 1 posted small blind 10",
        "Player 2 posted big blind 20",
        "Player 3 folded",
        "Player 0 raised to 80",
        "Player 1 called 70",
        "Player 2 folded",
        "Flop dealt: 3♣, 7♥, 5♣",
        "Player 0 folded",
        "Showdown: Player 1 won 190",
        # Hand 2
        "Player 0 posted small blind 10",
        "Player 1 posted big blind 20",
        "Player 2 folded",
        "Player 3 folded",
        "Player 0 folded",
        "Showdown: Player 1 won 30",
    ]

    ingestor.ingest_history(history)

    # ダンプ
    for row in db.conn.execute("SELECT * FROM player_stats ORDER BY player_id"):
        print(row)
    for row in db.conn.execute("SELECT * FROM showdown_buckets ORDER BY player_id, category"):
        print(row)
