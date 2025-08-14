# ゲーム状態データフォーマット仕様書

## 概要
LLMに現在のポーカーゲーム状況を伝達し、意思決定を支援するための簡潔なデータフォーマット仕様。

## 最低限フォーマット（戦略情報追加）

最低限の戦略判断に必要な情報のみを追加：

```json
{
  "your_id": 0,
  "phase": "flop",
  "your_cards": ["A♥", "K♠"],
  "community": ["Q♥", "J♦", "10♣"],
  "your_chips": 970,
  "your_bet_this_round": 0,
  "your_total_bet_this_hand": 30,
  "pot": 140,
  "to_call": 20,
  "dealer_button": 3,
  "current_turn": 0,
  "players": [
    {"id": 1, "chips": 970, "bet": 0, "status": "active"},
    {"id": 2, "chips": 970, "bet": 0, "status": "active"},
    {"id": 3, "chips": 950, "bet": 20, "status": "active"}
  ],
  "actions": ["fold", "call (20)", "raise (min 40)", "all-in (970)"],
  "history": [
    "Preflop: All players called 30",
    "Flop dealt: Q♥ J♦ 10♣",
    "Player 3 bet 20"
  ]
}
```


## フィールド説明

- **your_id**: あなたのプレイヤーID
- **phase**: 現在のゲームフェーズ（preflop/flop/turn/river）
- **your_cards**: プレイヤーの手札（♥♦♠♣で表記）
- **community**: コミュニティカード（フェーズに応じて0-5枚）
- **your_chips**: プレイヤーの残りチップ数
- **your_bet_this_round**: 現在のラウンドでのベット額
- **your_total_bet_this_hand**: そのハンド全体でこれまでに投じた累計ベット額（ブラインド含む）
- **pot**: 現在のポット額（全プレイヤーのベット合計）
- **to_call**: コールに必要な額（現在の最高ベット額 - 自分のベット額）
- **dealer_button**: ディーラーボタンの位置（プレイヤーID）
- **current_turn**: 現在アクションするプレイヤーのID
 - **players**: 他プレイヤーの状態（chips + bet = 2000になるように整合性を保つ）
- **actions**: 利用可能なアクション一覧
- **history**: 直近のアクション履歴（最新20件。ベット額とチップの整合性を保つ）

## ゲームフェーズ別の例

### プリフロップ例
```json
{
  "your_id": 0,
  "phase": "preflop",
  "your_cards": ["A♥", "K♠"],
  "community": [],
  "your_chips": 1000,
  "your_bet_this_round": 0,
  "your_total_bet_this_hand": 0,
  "pot": 30,
  "to_call": 20,
  "dealer_button": 3,
  "current_turn": 0,
  "players": [
    {"id": 1, "chips": 990, "bet": 10, "status": "active"},
    {"id": 2, "chips": 980, "bet": 20, "status": "active"},
    {"id": 3, "chips": 1000, "bet": 0, "status": "active"}
  ],
  "actions": ["fold", "call (20)", "raise (min 40)", "all-in (1000)"],
  "history": [
    "Player 1 posted small blind 10",
    "Player 2 posted big blind 20"
  ]
}
```

### ターン例（Player 0がコール後）
```json
{
  "your_id": 0,
  "phase": "turn",
  "your_cards": ["A♥", "K♠"],
  "community": ["Q♥", "J♦", "10♣", "9♠"],
  "your_chips": 950,
  "your_bet_this_round": 0,
  "your_total_bet_this_hand": 50,
  "pot": 200,
  "to_call": 0,
  "dealer_button": 3,
  "current_turn": 0,
  "players": [
    {"id": 1, "chips": 950, "bet": 0, "status": "active"},
    {"id": 2, "chips": 950, "bet": 0, "status": "active"},
    {"id": 3, "chips": 950, "bet": 0, "status": "active"}
  ],
  "actions": ["check", "bet (min 20)", "all-in (950)"],
  "history": [
    "Flop: Player 3 bet 20, all players called",
    "Turn dealt: 9♠"
  ]
}
```

## データ整合性の重要なポイント

1. **チップの保存則**: `初期チップ(1000) = 現在チップ + 累積ベット額`
2. **ポットの正確性**: `ポット = すべてのプレイヤーの累積ベット額の合計`
3. **to_callの計算**: `最高ベット額 - 自分の現在ベット額`
4. **フェーズ遷移**: 新しいベッティングラウンドでは現在ベットが0にリセット

## 実装例

```python
def get_llm_game_state(game, player_id):
    """LLM用の簡潔なゲーム状態を生成（数値整合性を保証）"""
    player = game.get_player(player_id)
    
    # カードを視覚的な記号に変換
    your_cards = [f"{card.rank}{card.suit_symbol}" for card in player.hole_cards]
    community = [f"{card.rank}{card.suit_symbol}" for card in game.community_cards]
    
    # 他プレイヤーの状態（整合性チェック付き）
    players = []
    for p in game.players:
        if p.id != player_id:
            # チップ + 累積ベット = 初期チップ(2000)になることを確認
            total_invested = p.total_bet_this_hand + p.current_bet
            assert p.chips + total_invested == 2000, f"Player {p.id}: chip inconsistency"
            
            players.append({
                "id": p.id,
                "chips": p.chips,
                "bet": p.current_bet,  # 現在のラウンドのベットのみ
                "status": p.status
            })
    
    # 利用可能なアクション（整合性チェック付き）
    max_bet = max((p.current_bet for p in game.players), default=0)
    to_call = max_bet - player.current_bet
    
    action_list = []
    if game.can_fold(player_id):
        action_list.append("fold")
    if game.can_check(player_id):
        action_list.append("check")
    if to_call > 0 and player.chips >= to_call:
        action_list.append(f"call ({to_call})")
    if game.can_raise(player_id):
        min_raise = max_bet + game.big_blind
        action_list.append(f"raise (min {min_raise})")
    if player.chips > 0:
        action_list.append(f"all-in ({player.chips})")
    
    return {
        "your_id": player_id,
        "phase": game.current_phase,
        "your_cards": your_cards,
        "community": community,
        "your_chips": player.chips,
        "pot": game.total_pot,
        "to_call": to_call,
        "players": players,
        "actions": action_list,
        "history": game.get_recent_action_list()
    }
```

## LLMプロンプト例

```
現在のポーカー状況：
{json.dumps(game_state, ensure_ascii=False, indent=2)}

上記の状況で最適な行動を選択してください。選択肢から一つ選んで理由と共に回答してください。
```

このシンプルなフォーマットにより、LLMは効率的に状況を理解し、戦略的な意思決定を行うことができます。 