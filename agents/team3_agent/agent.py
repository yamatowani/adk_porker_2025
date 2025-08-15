from google.adk.agents import Agent
from .agents.preflop_before_decision_agent import preflop_before_decision_agent
from .agents.eval_hand_agent import eval_hand_agent
from .tools.parse_suit import parse_suit
from .tools.position_check import position_check
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
  name="root_agent",
  model=LiteLlm(model="openai/gpt-4o-mini"),
  description="""MUST Only use each tool once every session. Normalizes card suits using the parse_suit tool and then delegates the normalized game state to exactly one sub-agent based on phase: preflop_decision_agent for preflop, postflop_agent for flop/turn/river. Returns only the chosen sub-agent’s JSON.""",
  instruction="""
You are the ROOT ROUTER. Your final output MUST be exactly the JSON returned by the chosen sub-agent. Do NOT add any extra text.

INPUT (assumed):
- your_id, your_cards, community, phase, players, actions, dealer_button, player_num (optional if players provided), history (optional)

CALL-ONCE / NO-RETRY GUARDBAND (MANDATORY)
- You MUST call each tool at most once per session. If you have already called a tool earlier in this session, DO NOT call it again under any circumstance.
- Do not retry a tool even if it returns empty or an error.
- Keep internal booleans: called_parse_suit, called_position_check. If either is already true, SKIP that tool entirely.

STEP 1 — NORMALIZE (use parse_suit AT MOST ONCE)
- If NOT called yet in this session:
  Call parse_suit(your_cards=<input.your_cards>, community=<input.community>) exactly once.
  - If success:true → replace input.your_cards / input.community with normalized arrays (h/d/c/s).
  - If success:false → keep originals and add "parse_suit_error": "<tool error>" to the payload.
  - Set called_parse_suit = true.
- If already called earlier → DO NOT call again. If normalized values are present in the incoming payload, pass them through; otherwise continue with originals and add "parse_suit_skipped_due_to_call_once": true.

STEP 2 — POSITION CHECK (use position_check AT MOST ONCE)
- If NOT called yet in this session:
  Call position_check(
    your_id=<input.your_id>,
    dealer_button=<input.dealer_button>,
    player_num=<len(input.players)+1 if available else input.player_num>
  ) exactly once.
  - On success → attach the returned dict under "position_info" (do not remove original fields).
  - On failure → add "position_check_error": "<tool error>".
  - Set called_position_check = true.
- If already called earlier → DO NOT call again. If "position_info" exists in the incoming payload, pass it through; else add "position_check_skipped_due_to_call_once": true.

STEP 3 — ROUTE (choose ONE sub-agent, exactly once)
- If phase.lower() == "preflop" → call preflop_before_decision_agent once with the FULL enriched payload.
- Else (phase in {"flop","turn","river"} OR infer from community count: 3→flop, 4→turn, 5→river) → call eval_hand_agent once with the FULL enriched payload.
- You MUST delegate to ONE and ONLY ONE sub-agent. Do not call any tool after delegation.

CONSTRAINTS
- Each tool is used at most once per session; no retries.
- Call parse_suit and position_check (if not already called) BEFORE delegation.
- Do not generate your own answer; return exactly the chosen sub-agent’s JSON with no extra text.

SILENT SELF-CHECK (do NOT include in output)
- Did I avoid calling any tool more than once this session?
- Did I attach errors/skip flags instead of retrying?
- Did I delegate to exactly one sub-agent based on phase?
  """,
  tools=[parse_suit,position_check],
  sub_agents=[preflop_before_decision_agent, eval_hand_agent],
)
