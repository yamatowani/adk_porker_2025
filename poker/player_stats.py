"""
プレイヤー統計情報管理
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict


class ActionType(Enum):
    """アクションタイプ"""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class PlayerActionStats:
    """プレイヤーアクション統計クラス"""
    
    def __init__(self, player_id: int, player_name: str):
        self.player_id = player_id
        self.player_name = player_name
        self.action_counts = defaultdict(int)
        self.preflop_participated = 0
        self.preflop_total_hands = 0
        self.post_preflop_hands = 0
        self.post_preflop_wins = 0
        self.hand_results = []
        self.preflop_actions_this_hand = False  # 現在のハンドでプリフロップアクションを取ったか
        
    def record_action(self, action_type: ActionType, phase: str, amount: int = 0):
        """アクションを記録"""
        self.action_counts[action_type] += 1
        
        # プリフロップでアクションを取った場合
        if phase == "preflop":
            self.preflop_actions_this_hand = True
            
    def record_preflop_participation(self, participated: bool):
        """プリフロップ参加を記録"""
        self.preflop_total_hands += 1
        if participated:
            self.preflop_participated += 1
        # ハンド終了時にリセット
        self.preflop_actions_this_hand = False
            
    def record_post_preflop_result(self, won: bool):
        """プリフロップ参加後の結果を記録"""
        self.post_preflop_hands += 1
        if won:
            self.post_preflop_wins += 1
            
    def record_hand_result(self, hand_data: Dict[str, Any]):
        """ハンド結果を記録"""
        self.hand_results.append(hand_data)
        
    @property
    def ppr(self) -> float:
        """プリフロップ参加率 (Preflop Participation Rate)"""
        if self.preflop_total_hands == 0:
            return 0.0
        return self.preflop_participated / self.preflop_total_hands
        
    @property
    def post_preflop_win_rate(self) -> float:
        """プリフロップ参加後勝利率"""
        if self.post_preflop_hands == 0:
            return 0.0
        return self.post_preflop_wins / self.post_preflop_hands
        
    def get_action_summary(self, max_hands: int = None) -> Dict[str, Any]:
        """アクション統計のサマリーを取得"""
        # max_handsが指定されている場合は、それを使用して総ハンド数を調整
        total_hands = max_hands if max_hands is not None else self.preflop_total_hands
        
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "ppr": self.ppr,
            "post_preflop_win_rate": self.post_preflop_win_rate,
            "action_counts": {action.value: count for action, count in self.action_counts.items()},
            "preflop_stats": {
                "participated": self.preflop_participated,
                "total_hands": total_hands
            },
            "post_preflop_stats": {
                "hands": self.post_preflop_hands,
                "wins": self.post_preflop_wins
            }
        }


class PlayerStatsManager:
    """プレイヤー統計管理クラス"""
    
    def __init__(self, max_hands: int = None):
        self.player_stats: Dict[int, PlayerActionStats] = {}
        self.current_hand_players: set = set()  # 現在のハンドに参加しているプレイヤー
        self.max_hands: int = max_hands
        
    def register_player(self, player_id: int, player_name: str):
        """プレイヤーを登録"""
        if player_id not in self.player_stats:
            self.player_stats[player_id] = PlayerActionStats(player_id, player_name)
            
    def record_action(self, player_id: int, action_type: ActionType, phase: str, amount: int = 0):
        """アクションを記録"""
        if player_id in self.player_stats:
            self.player_stats[player_id].record_action(action_type, phase, amount)
            
            # プリフロップでのアクションを記録
            if phase == "preflop":
                if action_type == ActionType.FOLD:
                    # フォールドした場合は参加者から除外
                    self.current_hand_players.discard(player_id)
                else:
                    # フォールド以外のアクションは参加とみなす
                    self.current_hand_players.add(player_id)
                
    def record_hand_start(self, active_players: List[int]):
        """ハンド開始時の処理"""
        # ハンド開始時にアクティブなプレイヤーを記録
        self.current_hand_players = set(active_players)
        
    def record_hand_end(self, winners: List[int], phase: str):
        """ハンド終了時の処理"""
        # 実際にプリフロップでアクションを取ったプレイヤーのみを参加としてカウント
        for player_id in self.player_stats.keys():
            player_stats = self.player_stats[player_id]
            # プリフロップでアクションを取ったかどうかで参加判定
            participated = player_stats.preflop_actions_this_hand
            self.player_stats[player_id].record_preflop_participation(participated)
            
            # プリフロップ参加後の結果を記録
            if participated:
                won = player_id in winners
                self.player_stats[player_id].record_post_preflop_result(won)
                
    def get_player_stats(self, player_id: int) -> Optional[PlayerActionStats]:
        """プレイヤーの統計を取得"""
        return self.player_stats.get(player_id)
        
    def get_all_stats(self) -> Dict[str, Any]:
        """全プレイヤーの統計を取得"""
        return {
            player_id: stats.get_action_summary(self.max_hands)
            for player_id, stats in self.player_stats.items()
        }
        
    def export_stats(self) -> Dict[str, Any]:
        """統計データをエクスポート"""
        return {
            "player_stats": self.get_all_stats(),
            "summary": {
                "total_players": len(self.player_stats),
                "total_hands": self.max_hands if self.max_hands is not None else max([stats.preflop_total_hands for stats in self.player_stats.values()], default=0)
            }
        }
