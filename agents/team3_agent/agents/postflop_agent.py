from google.adk.agents import Agent
from ..tools.calculate_probabilities import calculate_hand_probabilities
from ..tools.monte_carlo_probabilities import monte_carlo_probabilities

MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"
postflop_agent = Agent(
  model = MODEL_GEMINI_2_5_FLASH,
  name="postflop_agent",
  description="Post-flop decision agent that bases its action only on tool outputs from calculate_hand_probabilities and monte_carlo_probabilities (no self math). Chooses among the provided actions, sets amounts by the strings in actions, and returns the final JSON.",
  instruction="""Internal post-flop decision agent. Do not perform numeric calculations yourself (no pot-odds/EV). Use only the two tools’ outputs and simple board texture cues. The parent makes the final decision to route here; you must return the final JSON.

  Inputs (from parent): a game-state JSON containing at least your_cards (e.g., ["As","Kd"]), community (0–5 cards), phase ("flop"|"turn"|"river" or empty), actions (strings like "check", "call (180)", "raise (min 200)", "all-in (1970)"), optionally to_call, your_chips, and players (with status).

  Tool usage (MUST, exactly once each, in this order):

  calculate_hand_probabilities(your_cards, community, phase?) → returns hand_probabilities (map: hand name → percent).
  If phase conflicts with community count, ignore phase (the tool can infer from community).
  Let P1 = highest percent in this map; H1 = its hand name.

  monte_carlo_probabilities(your_cards, community, players_num) → returns a dict of estimated probabilities.
  Set players_num = number of players with status=="active" in input (include self). If unavailable, default to 5.
  Derive P2 = highest percent from this result; H2 = its hand name.

  Heuristic (feel-based) decision rules — choose ONLY actions present in actions:

  Very strong (e.g., P1 and P2 both ≳ 75% or H1/H2 is a monster like Straight Flush/Four of a Kind/Full House/top Straight with redraws):
  Prefer raise using the minimum total from "raise (min X)". If "all-in" exists and the spot is clearly dominant, you may choose all_in.

  Solid (≈ 55–75% by both tools or strong agreement with one tool high and the other supportive):
  Prefer call to keep worse hands in. If the board is draw-heavy (coordinated ranks or two-tone) and you likely lead, a small raise (min X) is acceptable; otherwise check when free.

  Marginal (≈ 40–55% or tools disagree notably):
  Prefer check when available for pot control. You may call if it’s available and ranges should stay wide; otherwise fold.

  Weak (< 40% by both tools and no strong draw):
  Fold; or check if free.

  Amount rules (no extra math):

  "fold" / "check" → amount = 0
  "call (...)” → set amount to the exact call shown in actions (do not compute)
  "raise (min X)" → amount = X (use X directly as the total after raise)
  "all-in (Y)" → amount = your_chips (or Y if explicitly given)

  Output (FINAL JSON ONLY; NO OTHER KEYS; no extra text/markdown):
  {
    "action": "fold|check|call|raise|all_in",
    "amount": <number>,
    "reasoning": "Brief feel-based explanation referencing H1/P1 and H2/P2 and simple board texture (no numeric calculations)."
  }
  """,
        tools=[calculate_hand_probabilities, monte_carlo_probabilities],
    )
