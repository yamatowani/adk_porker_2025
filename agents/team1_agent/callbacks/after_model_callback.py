from google import genai
from pydantic import BaseModel
import json
import re
from typing import Any, Dict, Optional

class PreflopDecision(BaseModel):
    action: str
    amount: int
    reasoning: str

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

