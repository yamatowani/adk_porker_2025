from google.adk.agents import Agent
from .agents.preflop_decision_agent import preflop_decision_agent
from .agents.postflop_agent import postflop_agent
from .tools.parse_suit import parse_suit

root_agent = Agent(
  name="root_agent",
  model="gemini-2.5-flash-lite",
  description="""Normalizes card suits using the parse_suit tool and then delegates the normalized game state to exactly one sub-agent based on phase: preflop_decision_agent for preflop, postflop_agent for flop/turn/river. Returns only the chosen sub-agent’s JSON.""",
  instruction="""
You are the ROOT ROUTER. Do NOT produce any answer. Follow these steps exactly in order.

STEP 1 — NORMALIZE (MUST, exactly once)
Call tool: parse_suit(your_cards=<input.your_cards>, community=<input.community>) once.
If success:true: replace input your_cards/community with the normalized arrays (h/d/c/s).
If success:false: keep originals and add "parse_suit_error" with the tool’s error into the payload.

STEP 2 — ROUTE (choose ONE)
If phase.lower() == "preflop" → call preflop_decision_agent once with the full payload (after STEP 1).
Else ("flop" / "turn" / "river") → call postflop_agent once with the full payload (after STEP 1).

CONSTRAINTS
-Call parse_suit exactly once and before any delegation.
-Delegate to one and only one sub-agent.
-Do not call other tools/agents.
-Do not do any response to client.

SILENT SELF-CHECK (do not include in output)
- Did I call parse_suit once?
- Did I route to exactly one sub-agent based on phase?
  """,
  tools=[parse_suit],
  sub_agents=[preflop_decision_agent, postflop_agent],
)
