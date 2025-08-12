# ポーカーゲーム 設計書

## 1. プロジェクト構造

```
adk-porker/
├── docs/
│   ├── requirements.md
│   └── design.md
├── src/
│   └── poker/
│       ├── __init__.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── card.py          # Card, Deck クラス
│       │   ├── player.py        # Player, HumanPlayer, AIPlayer クラス
│       │   └── game.py          # Game クラス
│       ├── core/
│       │   ├── __init__.py
│       │   ├── hand_evaluator.py # ハンド評価ロジック
│       │   └── betting.py       # ベッティングロジック
│       ├── ui/
│       │   ├── __init__.py
│       │   └── cli.py           # CLI表示ロジック
│       └── utils/
│           ├── __init__.py
│           └── storage.py       # JSON保存/読み込み
├── main.py                      # エントリーポイント
├── pyproject.toml
└── README.md
```

## 2. クラス設計

### 2.1 Card クラス
```python
class Card:
    """トランプカードを表現するクラス"""
    
    # カードのスート（マーク）
    SUITS = ['♠', '♥', '♦', '♣']
    SUIT_NAMES = ['Spades', 'Hearts', 'Diamonds', 'Clubs']
    
    # カードのランク
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    RANK_VALUES = {rank: i + 2 for i, rank in enumerate(RANKS)}
    
    def __init__(self, suit: int, rank: int)
    def __str__(self) -> str
    def __repr__(self) -> str
    def __eq__(self, other) -> bool
    def __hash__(self) -> int
```

### 2.2 Deck クラス
```python
class Deck:
    """52枚のトランプデッキを管理するクラス"""
    
    def __init__(self)
    def shuffle(self) -> None
    def deal_card(self) -> Card
    def cards_remaining(self) -> int
    def reset(self) -> None
```

### 2.3 Player 抽象クラス
```python
from abc import ABC, abstractmethod

class Player(ABC):
    """プレイヤーの抽象基底クラス"""
    
    def __init__(self, name: str, chips: int = 1000)
    
    @abstractmethod
    def make_decision(self, game_state: dict) -> dict
    
    def add_chips(self, amount: int) -> None
    def remove_chips(self, amount: int) -> bool
    def is_all_in(self) -> bool
    def fold(self) -> None
    def reset_for_new_hand(self) -> None
```

### 2.4 HumanPlayer クラス
```python
class HumanPlayer(Player):
    """人間プレイヤークラス"""
    
    def make_decision(self, game_state: dict) -> dict:
        # CLI入力を受け取ってアクションを決定
        pass
```

### 2.5 AIPlayer クラス
```python
import random

class AIPlayer(Player):
    """AIプレイヤークラス（ランダム行動）"""
    
    def __init__(self, name: str, chips: int = 1000, 
                 fold_prob: float = 0.3,
                 call_prob: float = 0.5,
                 raise_prob: float = 0.15,
                 all_in_prob: float = 0.05)
    
    def make_decision(self, game_state: dict) -> dict:
        # 確率に基づいてランダムにアクションを選択
        pass
```

### 2.6 Game クラス
```python
class Game:
    """ゲーム全体を管理するメインクラス"""
    
    def __init__(self, players: list)
    def start_new_hand(self) -> None
    def deal_hole_cards(self) -> None
    def deal_flop(self) -> None
    def deal_turn(self) -> None
    def deal_river(self) -> None
    def betting_round(self) -> None
    def showdown(self) -> dict
    def determine_winner(self) -> Player
    def distribute_pot(self) -> None
    def is_game_over(self) -> bool
    def save_game_state(self) -> None
    def load_game_state(self) -> None
```

### 2.7 HandEvaluator クラス
```python
class HandEvaluator:
    """ポーカーハンドの強さを評価するクラス"""
    
    # ハンドランキングの定数
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10
    
    @staticmethod
    def evaluate_hand(hole_cards: list, community_cards: list) -> tuple:
        # 7枚のカードから最高の5枚を選んでハンドを評価
        pass
    
    @staticmethod
    def compare_hands(hand1: tuple, hand2: tuple) -> int:
        # 2つのハンドを比較（1が勝ち、-1が負け、0が引き分け）
        pass
    
    @staticmethod
    def get_hand_name(hand_rank: int) -> str:
        # ハンドランクから名前を取得
        pass
```

## 3. ゲーム状態管理

### 3.1 GameState データ構造
```python
game_state = {
    "current_hand": 1,
    "dealer_position": 0,
    "small_blind": 10,
    "big_blind": 20,
    "pot": 0,
    "current_bet": 0,
    "community_cards": [],
    "phase": "preflop",  # preflop, flop, turn, river, showdown
    "active_players": [],
    "folded_players": [],
    "current_player_index": 0,
    "betting_history": []
}
```

### 3.2 PlayerAction データ構造
```python
action = {
    "type": "fold|check|call|raise|all_in",
    "amount": 0,  # レイズ額（レイズの場合のみ）
    "player": "player_name"
}
```

## 4. UI設計

### 4.1 ゲーム画面レイアウト
```
================================
           POKER GAME
================================
Pot: $150              Hand: #5

Community Cards:
[A♠] [K♥] [Q♦] [--] [--]

Players:
  You      - Chips: $850  Bet: $50  [Active]
  CPU1     - Chips: $920  Bet: $50  [Active]
  CPU2     - Chips: $0    Bet: $0   [Folded]
  CPU3     - Chips: $930  Bet: $50  [Active]

Your Cards: [J♠] [10♥]

Current Bet: $50
Your Action:
1. Fold
2. Call ($50)
3. Raise (Enter amount)
4. All-in ($850)

Enter choice (1-4): 
```

### 4.2 アクション入力フロー
1. 選択肢の表示
2. ユーザー入力の受け取り
3. 入力値の検証
4. アクションの実行
5. 結果の表示

## 5. データ永続化

### 5.1 ゲーム状態の保存
- JSON形式でゲーム状態を保存
- プレイヤーの統計情報を記録
- ゲーム履歴の保存

### 5.2 保存データ構造
```json
{
  "current_game": {
    "hand_number": 1,
    "players": [...],
    "game_state": {...}
  },
  "statistics": {
    "games_played": 10,
    "hands_won": 3,
    "hands_played": 45,
    "total_winnings": 150
  },
  "history": [...]
}
```

## 6. エラーハンドリング

### 6.1 想定されるエラー
- 不正な入力値
- チップ不足
- ゲーム状態の不整合
- ファイル読み書きエラー

### 6.2 エラー対応方針
- ユーザーフレンドリーなエラーメッセージ
- 適切なデフォルト値の設定
- ゲーム状態の復旧機能

## 7. 実装順序

### Phase 1: 基本クラスの実装
1. Card, Deck クラス
2. Player 抽象クラス
3. HandEvaluator クラス

### Phase 2: ゲームロジックの実装
1. Game クラスの基本機能
2. ベッティングロジック
3. ハンド評価ロジック

### Phase 3: UI実装
1. CLI表示機能
2. ユーザー入力処理
3. AIプレイヤーの実装

### Phase 4: 機能拡張
1. データ永続化
2. 統計機能
3. エラーハンドリング強化 