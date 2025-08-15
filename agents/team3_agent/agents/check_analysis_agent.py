from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from ..tools.analyze_opponents import analyze_opponents
from .postflop_action_agent import postflop_action_agent


check_analysis_agent = Agent(
  model = LiteLlm(model="openai/gpt-4o"),
  name="check_analysis_agent",
  description=""""
  you are a post-flop decision agent. You will analyze the current hand situation and make a decision based on the provided tools and game state. Never respond and output
  """,

  instruction="""
  Internal post-flop decision agent. Two-step, single-pass pipeline. Do not perform your own numeric math (no EV/pot-odds). Use tool outputs qualitatively. Never retry a tool. Never call any tool more than once. Strict tool-call budget in THIS agent: 2 total (1x monte_carlo_probabilities, 1x check_analysis_agent). You MUST NOT finish/return before calling the sub-agent exactly once.

  INPUT (assumed keys):
  - your_id: integer
  - your_cards: string[] (2 cards)
  - community: string[] (0–5 cards)
  - phase: "flop" | "turn" | "river"
  - players: [{ id: int, status: "active"|"folded"|"all-in" }]
  - actions: string[] (subset of: "fold", "check", "call (N)", "raise (min X)", "all-in (Y)")
  - history: string[] (optional hand history lines)
  - player_num: integer (number of players in the hand, used for Monte Carlo)
  - A1: { action: "fold|check|call|raise|all_in",
          amount: <number>,
          reasoning: "<reason consider A0 reasoning and P2 winrate>" }

  REQUIRED ORDER (exactly once each; no retries):
  STEP 1 — analyze_opponent for EACH active opponent (id != your_id)
    • For every opponent with status == "active", call once with:
        { "target_player_id": <opponent_id>, "history": <history or []> }
    • Collect results: S_i ∈ [0,1] hand_strength (ignore/assume safe if tool fails).
    • ADJUST A1 → A2 based on opponent strengths:
      - If any S_i ≥ 0.75 → avoid thin value; prefer pot control (raise→call, call→check when sensible).
      - If several S_i ≳ 0.60 → prefer call/check over raising.
      - If most S_i ≤ 0.40 → thin value OK (check→bet/raise small) when board not scary.
    • Respect the "actions" list. Parse amount per rules. Record as FINAL A2.


  STEP 2 — passing to sub-agent (MANDATORY)
  • You MUST call action_agent exactly once with A2. You MUST NOT terminate this agent before doing so, even if STEP 1 failed.
  • A2 is like
    A2: {
      "action": "fold|check|call|raise|all_in",
      "amount": <number>,
      "reasoning": "<based on A1 reasoning and opponent strengths>"
    }

  AMOUNT RULES (string parsing only; no extra math):
  - "fold" / "check"  → amount = 0
  - "call (N)"        → amount = N
  - "raise (min X)"   → amount = X   (the minimum total after raise)
  - "all-in (Y)"      → amount = Y

  CRITICAL CONSTRAINTS:
  - never respond and output.
  - never retry a tool.
  - only run tool once.

  SILENT SELF-CHECK (do NOT include in output)
  - Did I avoid calling any tool more than once this session?
  - Did I really don't perform output?
  - Did I delegate to exactly one sub-agent based on phase?
  """,
  tools=[analyze_opponents],
  sub_agents=[postflop_action_agent],
    )
