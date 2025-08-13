# ADK Poker - テキサスホールデム ポーカーゲーム

LLMプレイヤー対応のWebアプリ（Flet）/CLIのテキサスホールデムポーカーです。観戦用Viewerやログビューワーも付属します。

## 特徴

- **UI**: デフォルトはWeb（Flet）。必要に応じてCLIも利用可
- **観戦ビューア**: 別ポートでリアルタイム観戦（全員のホールカードを公開）
- **LLM対応**: `docs/game_state_format.md`のJSON仕様でLLMプレイヤーと連携（インプロセス/外部APIの2方式）
- **完全実装**: No-Limit、ハンド評価、ショーダウンまで実装
- **デフォルト4人対戦**: 人間1 + CPU3（設定で変更可）
- **CPU専用モード**: 全員CPUの自動進行（テスト・統計用途）

## ゲーム仕様

- **形式**: テキサスホールデム（No-Limit）
- **初期チップ**: 2000
- **ブラインド**: SB 10 / BB 20

### ハンドランキング（強い順）

1. ロイヤルフラッシュ
2. ストレートフラッシュ
3. フォーカード
4. フルハウス
5. フラッシュ
6. ストレート
7. スリーカード
8. ツーペア
9. ワンペア
10. ハイカード

## インストール・実行

### 必要なもの

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)

### セットアップ

1. まず、リポジトリをforkしてください．
2. 次にリポジトリをcloneしてください．

   ```bash
   # フォークしたリポジトリをクローン
   git clone <repository-url>
   cd adk_porker_2025
   ```

3. 次に、uvをインストールしてください

   ```bash
   # uvが未インストールの場合
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

#### 環境変数の設定

[.env.example](.env.example)を参考にして.envファイルをリポジトリルートに作成し、各チームに配布しているAPIキーを書き込んでください．

#### Webアプリモード（デフォルト・推奨）

uv runでwebブラウザとagentを起動してください．

```bash
# ブラウザでアクセス可能なWebアプリケーション（デフォルト）
uv run python main.py
# ブラウザで http://localhost:8551 にアクセス

# エージェントの起動
cd agents && uv run adk api_server --port 8000
```

- **観戦ビューア同時起動**（別ウィンドウで自動起動）

  ```bash
  uv run python main.py --with-viewer       # Viewer: http://localhost:8552
  uv run python main.py --with-viewer --viewer-port 9000
  ```

- **CLIモード**

  ```bash
  uv run python main.py --cli
  ```

- **CPU専用モード（CLI限定）**

  ```bash
  uv run python main.py --cli --cpu-only                      # 10ハンド、毎ハンド表示
  uv run python main.py --cli --cpu-only --max-hands 20       # 20ハンド
  uv run python main.py --cli --cpu-only --max-hands 100 --display-interval 10
  ```

#### 利用可能なオプション

```bash
uv run python main.py --help
```

- `--cli`: CLI（コマンドライン）モードで実行（デフォルトはWeb）
- `--with-viewer`: 観戦ビューアを別ポートで同時起動（デフォルト: 8552）
- `--viewer-port <port>`: 観戦ビューアのポート指定
- `--cpu-only`: CPU専用モード（CLI限定）
- `--max-hands <N>`: CPU専用モードの最大ハンド数（デフォルト: 10）
- `--display-interval <N>`: 何ハンドおきに詳細表示するか（デフォルト: 1）
- `--llm-mode`: 予約（現在未使用）

## 使い方（Web）

1. `uv run python main.py` を実行し、`http://localhost:8551` を開く
2. 最初に表示される設定画面で、プレイヤー構成を選択
   - プレイヤータイプ: `human` / `random` / `llm` / `llm_api`
   - `llm` の場合はモデルを、`llm_api` の場合は利用するエージェント等を設定
3. ゲーム開始後、画面下部のボタンでアクションを選択
   - フォールド（赤）/ チェック（青）/ コール（緑）/ レイズ（オレンジ）/ オールイン（紫）
   - レイズはダイアログで金額を入力
4. ベッティングラウンド終了時は「次のフェーズへ」ボタンで進行
5. ショーダウン結果はテーブル上に表示され、「次のハンドへ」で継続

## LLMプレイヤー

### JSON状態フォーマット

`docs/game_state_format.md`で定義された構造化フォーマットでゲーム状態を提供：

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

### LLMプレイヤーの実装方法

1. `poker/models.py`の`LLMPlayer`クラスを拡張
2. `make_decision()`メソッドでLLMクライアントと連携
3. JSONフォーマットでゲーム状態を受け取り、構造化された決定を返す

#### LLMプレイヤーの出力フォーマット

LLMプレイヤーは、意思決定の際に**必ず次のJSON形式**で出力してください。

```json
{
  "action": "fold|check|call|raise|all_in",
  "amount": <数値>,
  "reasoning": "戦略分析から導出された決定と戦略的理由の詳細な説明"
}
```

### 実行方式

- **インプロセス LLM（`llm`）**: ADKエージェントをプロセス内で実行します。`GOOGLE_API_KEY` 等の環境変数が未設定の場合はランダム行動にフォールバックします。
- **外部API LLM（`llm_api`）**: `http://localhost:8000` のADK APIサーバーに接続します（デフォルト）。
  - 必要なエンドポイント（例）: `/apps/{agent}/users/{user}/sessions/{session}`, `/run`
  - Setup画面でエージェント（例: `team1_agent`）を選択してください
  - Viewer に「LLMエージェントの最新判断」が表示されます

### デバッグモード

```bash
# デバッグモード有効（ターミナルとファイル両方に出力）
uv run python main.py --debug

# CLI + デバッグモード
uv run python main.py --cli --debug

# CPU専用 + デバッグモード
uv run python main.py --cpu-only --debug --max-hands 5
```

## ログ出力

- 実行ごとに `logs/` にタイムスタンプ付きログを自動保存（例: `poker_game_20250101_123456.log`）
- ターミナルにはINFO、ファイルにはDEBUGレベルで詳細記録（プロンプトや判定も含む）

## ログビューワー

ゲームの進行状況を可視化する簡易ログビューワーが利用可能です。

### 起動方法

```bash
# 基本的な起動（ブラウザで http://localhost:8553 にアクセス）
uv run python log_viewer.py

# ポート番号を指定して起動
uv run python log_viewer.py --port 8554

# ヘルプを表示
uv run python log_viewer.py --help
```

### 機能

- **ログファイル選択**: 日時順でログファイルを一覧表示
- **視覚的な表示**: アイコンと色分けで見やすく表示
- **統計情報**: ハンド数、アクション数などの概要を表示

### 使い方

1. ログビューワーを起動
2. 左側のパネルからログファイルを選択
3. メインパネルでゲームの進行を確認

## プロジェクト構造（主要）

```md
adk-porker/
├── main.py
├── poker/
│   ├── game.py               # ゲーム進行の中核
│   ├── game_models.py        # 型付きゲーム状態/フェーズ等
│   ├── player_models.py      # Human/Random/LLM/LLM API プレイヤー
│   ├── evaluator.py          # ハンド評価
│   ├── flet_ui.py            # Fletエントリ/統合
│   ├── setup_ui.py           # 設定画面
│   ├── game_ui.py            # 対局画面
│   ├── viewer_ui.py          # 観戦ビューア
│   ├── state_server.py       # JSON状態HTTPサーバー（:8765/state）
│   └── shared_state.py       # ゲーム共有状態
├── agents/                   # ADK Agent の例
├── log_viewer.py             # ログ可視化アプリ
└── docs/
    ├── game_state_format.md
    ├── design.md
    └── requirements.md
```
