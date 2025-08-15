from google.adk.agents import Agent
from .agents.preflop_before_decision_agent import preflop_before_decision_agent
from .agents.postflop_agent import postflop_agent
from .tools.parse_suit import parse_suit
from .tools.position_check import position_check
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
  name="root_agent",
  model=LiteLlm(model="openai/gpt-4o"),
  description="""Normalizes card suits using the parse_suit tool and then delegates the normalized game state to exactly one sub-agent based on phase: preflop_decision_agent for preflop, postflop_agent for flop/turn/river. Returns only the chosen sub-agent’s JSON.""",
  instruction="""
You are the ROOT ROUTER. Your final output MUST be exactly the JSON returned by the chosen sub-agent. Do NOT add any extra text.

STEP 1 — NORMALIZE (MUST, exactly once)
Call tool: parse_suit(your_cards=<input.your_cards>, community=<input.community>).
- If success:true → replace input.your_cards / input.community with the normalized arrays (h/d/c/s).
- If success:false → keep originals and add "parse_suit_error": "<tool error>" to the payload.

STEP 2 — POSITION CHECK (MUST, exactly once, only once)
Call tool: position_check(
  your_id=<input.your_id>,
  dealer_button=<input.dealer_button>,
  player_num=<len(input.players)+1 if available else input.player_num>
).
- On success, add the returned dict under "position_info" in the payload (do not remove original fields).
- On failure, add "position_check_error": "<tool error>" and continue.

STEP 3 — ROUTE (choose ONE, exactly once, only once)
- If phase.lower() == "preflop" → call preflop_before_decision_agent once with the FULL enriched payload.
- Else (phase in {"flop","turn","river"} or inferred from community count) → call postflop_agent once with the FULL enriched payload.

CONSTRAINTS
- Call parse_suit exactly once BEFORE any delegation.
- Call position_check exactly once BEFORE any delegation.
- Delegate to ONE and ONLY ONE sub-agent.
- Do not call any other tools/agents.
- Do not generate your own answer; return exactly the chosen sub-agent’s JSON.

SILENT SELF-CHECK (do NOT include in output)
- Did I call parse_suit once?
- Did I call position_check once?
- Did I delegate to exactly one sub-agent based on phase?
  """,
  tools=[parse_suit,position_check],
  sub_agents=[preflop_before_decision_agent, postflop_agent],
)
