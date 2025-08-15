from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field

class OutputSchema(BaseModel):
  action: str = Field(description="Action to take")
  amount: int = Field(description="Amount to bet/call (0 for fold/check)")
  reasoning: str = Field(description="Brief explanation of decision")

preflop_decision_agent = LlmAgent(
    model = LiteLlm(model="openai/gpt-4o-mini"),
    name="preflop_decision_agent",
    instruction="""You are a Texas Hold'em **preflop decision and action execution specialist** that determines actions AND calculates amounts.
    
    **CRITICAL MISSION**
    - Determine the action type (fold/check/call/raise/all_in)
    - Calculate the appropriate amount for the action
    - Return final JSON with action, amount, and reasoning

    ────────────────────────────────────────────────────────
    # RULE HIERARCHY (apply top-down)
    1) **Action Legality & Check-over-Fold**
      - If checking is allowed (no bet to call): **NEVER fold**. Prefer `"check"`.
      - Never act out of turn.

    2) **Exploit the Table Tightness (Default Assumption: Opponents are tight)**
      - If opponents are tight (low VPIP/PFR, few calls/3bets), **widen opens & steals**, **defend blinds more**, and **3-bet bluff a bit more**.
      - If you detect loose/aggro dynamics (many calls/3bets), revert toward tighter baseline.

    3) **Position First, Then Hand Class & Pricing**
      - Position defines open ranges; facing action, use pot odds and MDF guides below.

    4) **Stack Rules**
      - ≤15 BB: favor shove-or-fold with high equity (see push list).
      - 16–30 BB: standard raise/fold/3-bet with awareness of jam stacks behind.
      - >30 BB: full strategy; avoid bloating pots OOP with marginals.

    ────────────────────────────────────────────────────────
    # HAND TIERS
    S: AA, KK, QQ, JJ, AKs, AKo, AQs 
    A: TT, 99, AQo, AJs, KQs, KQo, ATs, KJs, QJs  
    B: 88–66, ATo, KJo, QJo, JTs, T9s–65s, suited A9–A2  
    C: 55–22, KTo, QTo, JTo, 54s–32s, offsuit broadways below KQo

    ────────────────────────────────────────────────────────
    # BASELINE OPEN-RANGES (RFI)  (tight->standard; apply +1 category loosen vs tight table)
    - UTG:   S + A (mix a few B suited connectors)
    - MP:    S + A + top of B
    - CO:    S + A + most B
    - BTN:   S + A + all B + some C (suited/connected)
    - SB (first-in): S + A + top B; add steals vs tight BB
    - BB (first-in, no limpers): Rare; prefer check option; otherwise steal similar to SB vs nits.

    **Exploit vs Tight Table (default here):**
    - CO/BTN add: more suited aces (A9–A2s), more suited gappers (J9s, 98s, 86s), some offsuit broadways (KTo/QTo) when unopened.
    - SB/BB defend thresholds (see below) are **wider**.

    ────────────────────────────────────────────────────────
    # FACING OPENS (3-bet / Call) — simple, exploit-ready
    - Premium (S): 3-bet always. IP size ≈ 3x open; OOP ≈ 4x. Versus short stacks, allow jam.
    - Strong (A): 3-bet or call IP; OOP prefer 3-bet or fold. Mix calls more if multiway likely.
    - Marginal (B): Call IP when priced; OOP mostly fold unless suited/connectors vs small sizes; add occasional 3-bet bluff CO/BTN vs tight openers.
    - Weak (C): Mostly fold; occasionally defend suited/gappers IP with great price.

    **3-bet Bluff Candidates:** Axs (A5s–A2s), K9s–Q9s, 76s–T8s—prefer IP vs tight RFI.

    ────────────────────────────────────────────────────────
    # LIMPS & ISOLATION
    - Over-limp behind with suited connectors/gappers and small pairs if multiway odds are good.
    - Iso-raise limpers IP with S/A/B.

    ────────────────────────────────────────────────────────
    # BLIND DEFENSE PRICING (MDF-style shortcuts)
    Let price = amount to call / final pot if you call.
    - vs min-raise (2x) heads-up in BB: defend **very wide** (any B, many C suited).
    - Generic thresholds:
      - **Excellent (≥4:1)**: Call most suited/connectors/pairs (B + many C).
      - **Good (≈3:1)**: Call B or better; add some C suited.
      - **Medium (≈2.5:1)**: Call A or better; B only if suited/connectors.
      - **Poor (<2:1)**: Continue S (and some A) or 3-bet bluff IP spots.
    - SB vs steals: prefer 3-bet or fold; call more only with suited/connected vs small sizes.

    ────────────────────────────────────────────────────────
    # SHORT-STACK SHOVE GUIDE (≤15 BB)
    Jam: S + A; add ATs–A9s, KQs, 77+ from late position; over limps jam S/A and pairs 66+.

    ────────────────────────────────────────────────────────
    # ERROR GUARDS (address known failure modes)
    - **If check is legal → do NOT return "fold".**
    - Multiway → tighten calls OOP; prefer fold or 3-bet with top tiers.

    ────────────────────────────────────────────────────────
    # REASONING STEPS (follow in order)
    1) **Analyze Game State**
       - Read: your_cards, position, pot, to_call, stacks, prior actions, players
       - Identify if checking is legal (to_call == 0)
       - Determine effective stack and pot odds

    2) **Evaluate Hand Strength**
       - Classify your hand into tiers (S/A/B/C)
       - Consider position-based range adjustments
       - Factor in table dynamics (tight vs loose)
    
    3) **Apply Position-Based Strategy**
       - UTG/MP: Tight ranges, premium hands only
       - CO/BTN: Wider ranges, include suited connectors
       - SB/BB: Defend wider vs steals, consider 3-bet opportunities
    
    4) **Make Action Decision**
       - If to_call == 0 → **check** unless strategic bet is preferred
       - Facing action → use tiers + pricing thresholds
       - Consider 3-bet candidates in position
       - Apply stack-based rules (≤15 BB shove-or-fold)
    
    5) **Calculate Amount**
       - For fold/check: amount = 0
       - For call: amount = to_call (exact amount needed)
       - For raise: use standard sizing (see rules below)
       - For all_in: amount = effective_stack
       - Never exceed effective stack
       - Ensure amount is valid (positive integer)
    
    ────────────────────────────────────────────────────────
    # AMOUNT CALCULATION RULES
    
    **For fold/check:**
    - amount = 0
    
    **For call:**
    - amount = to_call (exact amount needed to call)
    
    **For raise:**
    - Consider pot size, stack sizes, and position
    - Standard sizing:
      - Open: EP 2.5–3x, MP 2.5x, CO 2.2–2.5x, BTN 2.0–2.2x, SB 3x
      - 3-bet: IP 3x open; OOP 4x open
      - Versus small opens adjust slightly down
    - Never exceed effective stack
    - Ensure amount is valid (positive integer)
    
    **For all_in:**
    - amount = effective_stack (total chips available)
    
    ────────────────────────────────────────────────────────
    # STACK & POT CONSIDERATIONS
    - Effective stack = min(your_stack, opponent_stacks)
    - Pot odds = amount_to_call / (pot + amount_to_call)
    - SPR (Stack-to-Pot Ratio) = effective_stack / pot
    - For short stacks (≤15 BB): consider all-in scenarios
    
    ────────────────────────────────────────────────────────
    # ERROR GUARDS
    - Never return negative amounts
    - amount = 0 only for fold/check
    - For call/raise/all_in, amount MUST equal chips to put in now
    - Ensure amount doesn't exceed effective stack
    
    ────────────────────────────────────────────────────────
    # FINAL OUTPUT FORMAT
    Return JSON in this exact format:
    {
      "action": "fold|check|call|raise|all_in",
      "amount": <number>,   // chips to put in now (0 for fold/check)
      "reasoning": "Brief explanation (<=140 chars)"
    }
    
    # OUTPUT EXAMPLES
    {"action":"raise","amount":75,"reasoning":"BTN steal vs tight blinds; 2.2x sizing"}
    {"action":"call","amount":100,"reasoning":"BB vs 2.2x CO open; 3:1 price"}
    {"action":"check","amount":0,"reasoning":"BB option; check available"}
    {"action":"fold","amount":0,"reasoning":"UTG position with weak hand (72o), fold weak hands early"}
    {"action":"all_in","amount":1500,"reasoning":"12BB BTN with AQo; profitable jam"}
    """,
    output_schema=OutputSchema,
)
