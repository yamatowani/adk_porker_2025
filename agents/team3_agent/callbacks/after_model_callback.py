from google import genai
from pydantic import BaseModel
import json
import re
from typing import Any, Dict, Optional
from ..tools.hands_eval import evaluate_hands

class PreflopDecision(BaseModel):
    action: str
    amount: int
    reasoning: str

def before_model_callback(callback_context: Any, llm_request: Any) -> Optional[Any]:
    """
    LLMが呼ばれる前にハンド評価を実行するコールバック
    
    Args:
        callback_context: コールバックコンテキスト
        llm_request: LLMリクエスト（入力データを含む）
    
    Returns:
        modified_request: ハンド評価結果を含む修正されたリクエスト
    """
    try:
        # プレフロップ決定エージェントの場合のみ実行
        if hasattr(callback_context, 'agent') and hasattr(callback_context.agent, 'name'):
            agent_name = callback_context.agent.name
            if agent_name != "preflop_decision_agent":
                return None
        
        # LLMリクエストから入力データを取得
        if hasattr(llm_request, 'messages') and llm_request.messages:
            # 最新のメッセージから入力データを取得
            latest_message = llm_request.messages[-1]
            if hasattr(latest_message, 'content'):
                content = latest_message.content
                if isinstance(content, str):
                    try:
                        # JSONとしてパースを試行
                        input_data = json.loads(content)
                    except json.JSONDecodeError:
                        # JSONでない場合は辞書として扱う
                        input_data = {"content": content}
                else:
                    input_data = content
            else:
                return None
        else:
            return None
        
        # 入力データからyour_cardsを取得
        if isinstance(input_data, dict) and 'your_cards' in input_data:
            your_cards = input_data['your_cards']
        else:
            return None
        
        # カードが存在しない場合は何もしない
        if not your_cards or len(your_cards) != 2:
            return None
        
        # カードをJSON配列文字列に変換
        cards_json = json.dumps(your_cards)
        
        # evaluate_handsツールを実行
        hand_evaluation = evaluate_hands(cards_json)
        
        # 入力データにハンド評価結果を追加
        input_data['hand_evaluation'] = hand_evaluation
        
        # 修正されたメッセージを作成
        if hasattr(llm_request, 'messages') and llm_request.messages:
            # 最新のメッセージを更新
            latest_message.content = json.dumps(input_data)
        
        return llm_request
            
    except Exception as e:
        print(f"before_model_callback エラー: {e}")
        return None

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    テキストからJSONを抽出する関数
    """
    # JSONブロックを探す（```json で囲まれたもの）
    json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 単純なJSONオブジェクトを探す
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None

def force_structured_output(response_text: str, expected_schema: type) -> Any:
    """
    レスポンステキストを強制的にstructuredOutputに変換する関数
    
    Args:
        response_text: モデルからのレスポンステキスト
        expected_schema: 期待されるスキーマクラス（Pydanticモデル）
    
    Returns:
        structured_output: パースされたオブジェクト
    """
    # JSONを抽出
    json_data = extract_json_from_text(response_text)
    
    if json_data is None:
        raise ValueError("レスポンスからJSONを抽出できませんでした")
    
    # Pydanticモデルでバリデーション
    try:
        if hasattr(expected_schema, '__origin__') and expected_schema.__origin__ is list:
            # リストの場合
            item_type = expected_schema.__args__[0]
            return [item_type(**item) for item in json_data]
        else:
            # 単一オブジェクトの場合
            return expected_schema(**json_data)
    except Exception as e:
        raise ValueError(f"JSONデータのバリデーションに失敗しました: {e}")

def after_model_callback(callback_context: Any, llm_response: Any) -> Optional[Any]:
    """
    Google ADKのコールバック形式に合わせたafter_model_callback関数
    
    Args:
        callback_context: コールバックコンテキスト
        llm_response: LLMレスポンス
    
    Returns:
        structured_output: パースされたオブジェクト、またはNone
    """
    try:
        # llm_responseからテキストを取得
        if hasattr(llm_response, 'text'):
            response_text = llm_response.text
        elif hasattr(llm_response, 'content'):
            response_text = llm_response.content
        else:
            # レスポンスが既にstructuredOutputの場合はそのまま返す
            return None
        
        # プレフロップ決定エージェントの場合はPreflopDecisionスキーマを使用
        if hasattr(callback_context, 'agent') and hasattr(callback_context.agent, 'name'):
            agent_name = callback_context.agent.name
            if agent_name == "preflop_decision_agent":
                expected_schema = PreflopDecision
            else:
                expected_schema = PreflopDecision
        else:
            expected_schema = PreflopDecision
        
        # 強制的にstructuredOutputに変換
        return force_structured_output(response_text, expected_schema)
        
    except Exception as e:
        # エラーが発生した場合はNoneを返して、デフォルトの処理を継続
        print(f"after_model_callback エラー: {e}")
        return None

