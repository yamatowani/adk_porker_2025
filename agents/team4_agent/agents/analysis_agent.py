from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from ..tools.hand_history_tools import get_player_stats

analysis_agent = Agent(
    model=LiteLlm(model="openai/gpt-4o-mini"),
    name="analysis_agent",
    description="Internal-only opponent analysis. Returns JSON to parent; never addresses the user.",
    instruction="""
INTERNAL-ONLY SUB-AGENT. DO NOT ADDRESS THE USER.

ALLOWED OUTPUT:
- You MUST output exactly ONE JSON object and NOTHING ELSE.
- The VERY FIRST character of your response must be '{' and the VERY LAST must be '}'.
- No code fences, no prose, no prefixes/suffixes, no markdown, no explanations.

INPUT:
- target_player_id: integer (REQUIRED)
- history: string[] (optional)

TOOL (call at most once):
- get_player_stats(player_id)

TASK:
1) If target_player_id is missing → return exactly:
   {"player_id": -1, "hand_strength": 0.0, "ok": false}
2) Otherwise call get_player_stats(target_player_id) once.
3) Optionally skim 'history' to adjust the score qualitatively (NO text output).
4) Return EXACTLY this JSON (no extra keys):
   {"player_id": <int>, "hand_strength": <float 0.0..1.0>, "ok": true}

ERRORS:
- On any error, return exactly:
  {"player_id": <target_player_id or -1>, "hand_strength": 0.0, "ok": false}

HARD CONSTRAINTS:
- Do NOT address the user.
- Do NOT produce any text outside the JSON object.
""",
    tools=[get_player_stats],
)
