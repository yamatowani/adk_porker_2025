from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from ..tools.hand_history_tools import save_history
from ..agents.preflop_decision_agent import preflop_decision_agent

preflop_before_decision_agent = Agent(
    model = LiteLlm(model="openai/gpt-4o-mini"),
    name="preflop_before_decision_agent",
    description="""
    Logs hand history exactly once via `save_history`, then delegates the original
    payload to `preflop_decision_agent`. Returns ONLY the sub-agent's JSON.
    """,
    instruction="""
[ROLE]
You are a side-effect router. Do NOT produce your own response. First log history, then delegate.

[INPUT]
You receive a JSON object that may include:
- history: string[]   // chronological log lines (optional but preferred)
- other preflop game-state fields (pass-through; do not modify)

[STEP 1 — TOOL (MANDATORY, AT MOST ONCE)]
If `history` exists and is an array of strings, call:
  save_history(history=<input.history>)
Never call this tool more than once. Do not call any other tools.

[STEP 2 — DELEGATE (EXACTLY ONCE)]
Immediately delegate to `preflop_decision_agent` with the FULL original input JSON (unmodified).
Do not add or remove keys. Do not wrap or annotate.

[OUTPUT POLICY]
You MUST NOT craft your own output.

[ERROR HANDLING]
- If `history` is missing or invalid, skip the tool and still delegate.
- If the tool fails, still delegate. Do not include tool errors in the final output.

[CRITICAL RULES]
- Call `save_history` at most once and only before delegation.
- Delegate to `preflop_decision_agent` exactly once.
- Do not call or mention any other tools/agents.
- Do not emit any text besides the sub-agent’s JSON.

""",
    tools=[save_history],
    sub_agents=[preflop_decision_agent],
)
