"""
Poker game models: Card, Deck, Suit classes and game state types
"""

import random
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass


class Suit(Enum):
    """カードのスート"""

    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"


class Card:
    """トランプカードクラス"""

    # スートの記号マップ
    SUIT_SYMBOLS = {
        Suit.HEARTS: "♥",
        Suit.DIAMONDS: "♦",
        Suit.CLUBS: "♣",
        Suit.SPADES: "♠",
    }

    # ランクの表記マップ
    RANK_NAMES = {
        2: "2",
        3: "3",
        4: "4",
        5: "5",
        6: "6",
        7: "7",
        8: "8",
        9: "9",
        10: "10",
        11: "J",
        12: "Q",
        13: "K",
        14: "A",
    }

    def __init__(self, rank: int, suit: Suit):
        """
        Args:
            rank: カードのランク（2-14, 11=J, 12=Q, 13=K, 14=A）
            suit: カードのスート
        """
        if rank < 2 or rank > 14:
            raise ValueError("Rank must be between 2 and 14")
        self.rank = rank
        self.suit = suit

    @property
    def rank_name(self) -> str:
        """ランクの表示名を取得"""
        return self.RANK_NAMES[self.rank]

    @property
    def suit_symbol(self) -> str:
        """スートの記号を取得"""
        return self.SUIT_SYMBOLS[self.suit]

    def __str__(self) -> str:
        """カードの文字列表現（例: A♠）"""
        return f"{self.rank_name}{self.suit_symbol}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def __repr__(self) -> str:
        return f"Card({self.rank_name}, {self.suit.value})"


class Deck:
    """トランプデッキクラス"""

    def __init__(self):
        """標準的な52枚のデッキを作成"""
        self.cards: List[Card] = []
        self.reset()

    def reset(self):
        """デッキをリセットして全カードを追加"""
        self.cards = []
        for suit in Suit:
            for rank in range(2, 15):  # 2-14 (A)
                self.cards.append(Card(rank, suit))
        self.shuffle()

    def shuffle(self):
        """デッキをシャッフル"""
        random.shuffle(self.cards)

    def deal_card(self) -> Card:
        """カードを1枚配る"""
        if not self.cards:
            raise ValueError("Cannot deal from empty deck")
        return self.cards.pop()

    def cards_remaining(self) -> int:
        """残りカード数を取得"""
        return len(self.cards)


class GamePhase(Enum):
    """ゲームフェーズ"""

    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    FINISHED = "finished"


@dataclass
class PlayerInfo:
    """ゲーム状態用のプレイヤー情報（簡略版）"""

    id: int
    chips: int
    bet: int
    status: str


@dataclass
class GameState:
    """LLMプレイヤー用のゲーム状態"""

    your_id: int
    phase: str
    your_cards: List[str]
    community: List[str]
    your_chips: int
    your_bet_this_round: int
    your_total_bet_this_hand: int
    pot: int
    to_call: int
    dealer_button: int
    current_turn: int
    players: List[PlayerInfo]
    actions: List[str]
    history: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "your_id": self.your_id,
            "phase": self.phase,
            "your_cards": self.your_cards,
            "community": self.community,
            "your_chips": self.your_chips,
            "your_bet_this_round": self.your_bet_this_round,
            "your_total_bet_this_hand": self.your_total_bet_this_hand,
            "pot": self.pot,
            "to_call": self.to_call,
            "dealer_button": self.dealer_button,
            "current_turn": self.current_turn,
            "players": [
                {
                    "id": player.id,
                    "chips": player.chips,
                    "bet": player.bet,
                    "status": player.status,
                }
                for player in self.players
            ],
            "actions": self.actions,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameState":
        """辞書から作成"""
        players = [
            PlayerInfo(id=p["id"], chips=p["chips"], bet=p["bet"], status=p["status"])
            for p in data.get("players", [])
        ]

        return cls(
            your_id=int(data.get("your_id", 0)),
            phase=data.get("phase", ""),
            your_cards=data.get("your_cards", []),
            community=data.get("community", []),
            your_chips=data.get("your_chips", 0),
            your_bet_this_round=data.get("your_bet_this_round", 0),
            your_total_bet_this_hand=data.get("your_total_bet_this_hand", 0),
            pot=data.get("pot", 0),
            to_call=data.get("to_call", 0),
            dealer_button=data.get("dealer_button", 0),
            current_turn=data.get("current_turn", 0),
            players=players,
            actions=data.get("actions", []),
            history=data.get("history", []),
        )
