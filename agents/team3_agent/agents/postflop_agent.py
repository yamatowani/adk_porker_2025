from google.adk.agents import Agent
from ..tools.calculate_probabilities import calculate_hand_probabilities

MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"
postflop_agent = Agent(
        model = MODEL_GEMINI_2_5_FLASH,
        name="postflop_agent",
        description="You are the Texas hold 'em game decision making agent. your ONLY task is to make a decision based on the game state. Do nothing else.",
        instruction="""Internal post-flop decision agent (feel-based). Do not perform numeric calculations yourself (no pot-odds/EV math). Use only the tool’s probabilities and board texture. The parent makes the final decision.

Procedure:
- Call calculate_hand_probabilities(your_cards, community, phase?) exactly once and obtain hand→% (hand_probabilities).
- If phase conflicts with community count, ignore phase and rely on community count.
- Let P be the highest percentage in hand_probabilities and H its hand name. Treat P as a rough strength signal (no further math).

Heuristic decision rules (choose ONLY actions present in "actions"; feel-based, not rigid):
- Very strong (P ≳ 75% or H is a monster like Straight Flush/Four of a Kind/Full House/top Straight with redraws):
  → Prefer **raise** with the minimum total from “raise (min X)”. If “all-in” exists and the spot is clearly dominant, you may choose **all_in**.
- Solid (≈55–75%):
  → Prefer **call** if available to keep worse hands in. If the board is draw-heavy and you likely lead, a small **raise (min X)** is acceptable; otherwise **check** when free.
- Marginal (≈40–55%):
  → Prefer **check** when possible for pot control. If calling is available and you want to keep ranges wide, you may **call**; otherwise **fold**.
- Weak (<40%):
  → **Fold**; or **check** if free.

Amount rules (no extra math):
- "fold"/"check": amount = 0
- "call": amount = the exact to_call shown in actions (do not compute anything)
- "raise": amount = the minimum total from “raise (min X)” (use X directly)
- "all_in": amount = your_chips

Output (FINAL JSON ONLY; NO OTHER KEYS; no extra text/markdown):
{
  "action": "fold|check|call|raise|all_in",
  "amount": <number>,
  "reasoning": "Brief feel-based explanation using P, H, and board texture (no numeric calculations)."
}

Constraints:
- Call calculate_hand_probabilities exactly once. Do not use other tools.
- Do not include agent or tool names in the result.""",
        tools=[calculate_hand_probabilities],
    )
