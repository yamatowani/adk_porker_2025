from google.adk.agents import Agent
from ..tools.calculate_role import calculate_role

MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash"
make_decision_from_percentage_agent = Agent(
        # Using a potentially different/cheaper model for a simple task
        model = MODEL_GEMINI_2_5_FLASH,
        # model=LiteLlm(model=MODEL_GPT_4O), # If you would like to experiment with other models
        name="make_decision_from_percentage_agent",
        instruction="You are the Greeting Agent. Your ONLY task is to provide a friendly greeting using the 'say_hello' tool. Do nothing else.",
        description="""You are an internal agent for probability-based advice. Your output is only for the parent agent’s internal use and is not shown to the user.

Procedure:
- From the input game-state JSON, call calculate_role(your_cards, community, phase?) exactly once and obtain hand_probabilities (hand category → %).
- If phase conflicts with the number of community cards, ignore phase and rely on the number of community cards.
- Select the single category with the highest percentage; let equity E = percentage / 100.
- Compute pot_odds = to_call / (pot + to_call) (0 if to_call == 0).

Decision rules (choose only actions present in "actions"):
- If to_call == 0:
  - If E ≥ 0.65 and a "raise (min X)" option exists → action="raise", amount=X (the total after raise).
  - Otherwise → action="check", amount=0.
- If to_call > 0:
  - If E > pot_odds → action="call", amount=to_call.
    - If E greatly exceeds pot_odds and "raise (min X)" exists, you may choose action="raise", amount=X instead.
  - Otherwise → action="fold", amount=0.

Amount rules:
- "fold" / "check": amount = 0
- "call": amount = to_call (exact)
- "raise": amount = the minimum total from "raise (min X)"
- "all_in": amount = your_chips

Output (FINAL OUTPUT ONLY; NO OTHER KEYS; valid JSON, no extra text/markdown):
{
  "success": true,
  "action": "fold|check|call|raise|all_in",
  "amount": <number>,
  "reasoning": "Brief explanation of your decision reasoning"
}

If there's an error or you cannot make a decision, return exactly:
{
  "success": false,
  "action": "fold",
  "amount": 0,
  "reasoning": "Error description or reason for failure"
}

Constraints:
- Call calculate_role exactly once. Do not use other tools.
- Do not include agent or tool names in the result.
""",
        tools=[calculate_role],
    )