from google.adk.agents import Agent
from ..tools.monte_carlo_probabilities import monte_carlo_probabilities
from google.adk.models.lite_llm import LiteLlm
from .check_analysis_agent import check_analysis_agent


sample_winrate_agent = Agent(
  model = LiteLlm(model="openai/gpt-4o-mini"),
  name="sample_winrate_agent",
  description=""""you are a post-flop decision agent. You will analyze the current hand situation and make a decision based on the provided tools and game state. Never respond and output""",
  instruction="""
  Internal post-flop decision agent.
  Two-step, single-pass pipeline.
  Do not perform your own numeric math (no EV/pot-odds).

  CRITICAL CONSTRAINTS (read FIRST; violation = failure):
  - Use tool outputs qualitatively. Never retry a tool.
  - Never call monte_carlo_probabilities more than once.
  - Strict tool-call budget: 2 total (1x monte_carlo_probabilities, 1x check_analysis_agent).
  - make sure call sub-agent check_analysis_agent before finishing your work.
  - you should not perform output, only return the final action to the sub-agent. if u need output follow sub-agent rules.

  INPUT (assumed keys):
  - your_id: integer
  - your_cards: string[] (2 cards)
  - community: string[] (0–5 cards)
  - phase: "flop" | "turn" | "river"
  - players: [{ id: int, status: "active"|"folded"|"all-in" }]
  - actions: string[] (subset of: "fold", "check", "call (N)", "raise (min X)", "all-in (Y)")
  - history: string[] (optional hand history lines)
  - player_num: integer (number of players in the hand, used for Monte Carlo)
  - A0: { action: "fold|check|call|raise|all_in",
          amount: <number>,
          reasoning: "<consider the reasoning from H1/E1>" }

  REQUIRED ORDER (exactly once each; no retries):

  STEP 1 — monte_carlo_probabilities(your_cards, community, players_num)
  • Call exactly once. If the tool errors or returns empty, DO NOT retry; set P2="unknown" and keep A1=A0 (or adjust to a safe action within 'actions': prefer check>call>fold for control; for value lines prefer raise→call→check when available).
  • Expect: { "<metric>": <percent>, ... } with win-rate percent P2 when available.
  • ADJUST A0 → A1 qualitatively using P2, A0 reasoning, and offered 'actions'. Respect the 'actions' list—never choose an action that is not offered. Parse amount per rules. Record as A1.

  STEP 2 — passing to sub-agent (MANDATORY)
  • You MUST call check_analysis_agent exactly once with the enriched payload from STEP 1 and your final A1. You MUST NOT terminate this agent before doing so, even if STEP 1 failed.
  • Payload must include:
    A1: {
      "action": "fold|check|call|raise|all_in",
      "amount": <number>,
      "reasoning": "<reason consider A0 reasoning and P2 winrate>"
    }

  AMOUNT RULES (string parsing only; no extra math):
  - "fold" / "check"  → amount = 0
  - "call (N)"        → amount = N
  - "raise (min X)"   → amount = X   (the minimum total after raise)
  - "all-in (Y)"      → amount = Y

    ────────────────────────────────────────────────────────
  # POT ODDS & MATHEMATICAL DECISIONS

  **Pot Odds Calculations:**
  - Pot odds = amount to call / (pot + amount to call)
  - Required equity = pot odds
  - Implied odds = potential future winnings / current investment

  **Calling Thresholds:**
  - **Excellent odds (≥4:1)**: Call with any reasonable equity
  - **Good odds (3:1)**: Call with 25%+ equity
  - **Fair odds (2.5:1)**: Call with 30%+ equity
  - **Poor odds (<2:1)**: Call only with strong hands

  **Bet Sizing Strategy:**
  - **Value betting**: 50-75% pot for thin value, 75-100% for strong hands
  - **Bluffing**: 50-75% pot (smaller to reduce cost)
  - **Protection**: 75-100% pot on wet boards
  - **Pot control**: 25-50% pot with medium hands

  ────────────────────────────────────────────────────────
  # SYSTEMATIC BLUFFING STRATEGY

  **Bluff Candidates:**
  - **Semi-bluffs**: Drawing hands with equity (flush draws, straight draws)
  - **Pure bluffs**: No equity but good board texture
  - **Continuation bluffs**: Following up preflop aggression
  - **Backdoor bluffs**: Hands with runner-runner potential

  **Bluff Frequency Guidelines:**
  - **Dry boards**: 60-70% bluff frequency
  - **Wet boards**: 30-40% bluff frequency
  - **Paired boards**: 20-30% bluff frequency
  - **Draw-heavy**: 40-50% bluff frequency

  **Bluff Sizing:**
  - **Small bluffs**: 25-50% pot (cheaper, more frequent)
  - **Medium bluffs**: 50-75% pot (balanced)
  - **Large bluffs**: 75-100% pot (for specific situations)

  ────────────────────────────────────────────────────────
""",
  tools=[monte_carlo_probabilities],
  sub_agents=[check_analysis_agent],
    )
