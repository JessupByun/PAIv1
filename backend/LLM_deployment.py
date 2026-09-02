import os
import json
import random
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Importing this module must not require a key - the test suite imports it to
# exercise prompt building, and main.py imports it before the user has a chance
# to see any error. The client is built on the first real call instead.
_client = None

DEBUG = os.getenv("PAI_DEBUG", "").lower() in ("1", "true", "yes")

# How often to nudge the model toward a bluff (postflop). Split into a
# context-driven nudge and a rarer pure-balance ("for no reason") nudge.
# Tune with the PAI_BLUFF_RATE env var (0.0 disables bluffing nudges).
BLUFF_RATE = float(os.getenv("PAI_BLUFF_RATE", "0.35"))

_SYSTEM_PROMPT = """You are a Poker AI assistant. You will be given the current state of a poker hand — the board, the players, their stacks and bets, and the action history. Your job is to decide the best action and explain why.

Respond with valid JSON only, no markdown, no extra keys:
{
  "action": "<one of the exact strings from AVAILABLE ACTIONS>",
  "bet_size": <number — if action is Raise or Bet, the TOTAL chips to make it, sized for the pot and stacks (e.g. ~50-75% of the pot for a value bet, larger on draw-heavy boards). Must be >= the big blind and <= your effective stack. Use 0 for Fold, Check, or Call>,
  "action_reason": "<2-3 sentences explaining the decision using the actual hand details, including why this bet size if raising>",
  "key_factors": ["<short factor 1>", "<short factor 2>", "<short factor 3>"],
  "risk_note": "<1 sentence on what to watch out for next>"
}

Rules:
- Your action MUST be one of the AVAILABLE ACTIONS listed in the prompt.
- Never fold when "check" is available — checking is free, so check (or raise) instead of folding.

Bluffing — poker is not just value betting; bluffing is part of strong, unpredictable play:
- Strong bluff spots: the opponent shows weakness (checks, min-bets, or gives up a street); the board lets you credibly represent a big hand (scary overcards, a completed flush/straight, a paired board); you hold blockers to the hands that would call you; you have position and fold equity; or you missed a draw and have no showdown value (turn the busted draw into a bluff).
- Avoid bluffing: multiway pots, into shown strength, when there is little fold equity (short or committed stacks), or when your hand has showdown value that would rather check/call.
- A bluff is a Raise or Bet (never a "bluff-fold"). Size it to credibly represent the hand you're repping.
- When you bluff, say so plainly in action_reason and name the hand/line you are representing."""

def _groq() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = Groq(api_key=api_key)
    return _client


def _coerce_bet_size(val, effective_stack):
    """Parse the LLM's bet_size to a positive number, clamped to the effective
    stack. Returns None if it's missing, zero, or not a number."""
    try:
        size = float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return None
    try:
        cap = float(effective_stack)
        if cap > 0:
            size = min(size, cap)  # never suggest betting more than you have
    except (TypeError, ValueError):
        pass
    return round(size)


def _bluff_directive():
    """
    Randomly return a coaching note that nudges the model toward a bluff, so the
    assistant mixes in aggression instead of only ever value-betting. Most of the
    time returns "" (play straightforwardly). Frequency is controlled by BLUFF_RATE:
    roughly the bottom third of that rate is a pure "for balance" bluff (even without
    a read), the rest is context-driven (bluff only if a credible line exists).
    """
    roll = random.random()
    if roll < BLUFF_RATE / 3:
        return ("\n\n[Coach note: MIX IN A BLUFF this hand for balance and unpredictability. "
                "Even without a strong read, if you have any fold equity and aren't multiway, "
                "lean toward a bet/raise as a bluff. Don't bluff into obvious strength.]")
    if roll < BLUFF_RATE:
        return ("\n\n[Coach note: a well-timed bluff is on the table this hand. If a credible "
                "bluff line exists given the board and your opponent's actions, take it; "
                "otherwise play straightforwardly.]")
    return ""


def _players_block(players: list, you_name: str) -> str:
    lines = ["Name                 | Stack    | Bet     | Status   | Cards"]
    lines.append("-" * 65)
    for p in players:
        name = p.get("name", "?")
        label = f"{name} (YOU)" if name == you_name else name
        stack  = str(p.get("stack", "?"))
        bet    = str(p.get("bet") or 0)
        status = str(p.get("status", "")).replace("PlayerStatus.", "").replace("_", " ")
        cards  = p.get("cards", [])
        known  = [c for c in cards if c != "Unknown Card"]
        card_str = ", ".join(known) if known else "hidden"
        lines.append(f"{label:<21}| {stack:<9}| {bet:<8}| {status:<9}| {card_str}")
    return "\n".join(lines)


def _build_prompt(stats: dict, game_summary: dict, action_history: list[str]) -> str:
    street    = stats.get("street", "Unknown")
    community = stats.get("community_cards_display", "(none)")
    blinds    = stats.get("blinds", [])
    you_name  = stats.get("you_name", "You")
    pot_size  = stats.get("pot_size", 0)
    pot_odds  = stats.get("pot_odds")
    spr       = stats.get("spr")
    eff_stack = stats.get("effective_stack")
    position  = stats.get("position", "Unknown")
    hole_cards = stats.get("hole_cards_display", "??")
    best_hand  = stats.get("best_hand", "")
    available_actions = stats.get("available_actions", [])
    blinds_str = f"{blinds[0]}/{blinds[1]}" if blinds and len(blinds) >= 2 else "unknown"

    lines = [
        f"Street: {street}",
        f"Blinds: {blinds_str}  |  Pot: {pot_size}  |  Board: {community if community else '(none)'}",
        f"Your cards: {hole_cards}" + (f"  |  Best hand: {best_hand}" if best_hand else ""),
        f"Position: {position}  |  Effective stack: {eff_stack}",
    ]

    if pot_odds and pot_odds > 0:
        lines.append(f"Pot odds: {pot_odds:.1f}%")
    if spr is not None:
        lines.append(f"SPR: {spr}")

    lines += [
        "",
        "Players:",
        _players_block(game_summary.get("players", []), you_name),
    ]

    if action_history:
        lines += ["", "Action history (oldest to newest):"]
        for i, entry in enumerate(action_history, 1):
            lines.append(f"  {i}. {entry}")

    lines += [
        "",
        f"Available actions: {', '.join(available_actions)}",
        "",
        "What is the best action and why?",
    ]

    return "\n".join(lines)


def generate_dashboard_explanation(
    model_name: str,
    stats: dict,
    game_summary: dict,
    action_history: list[str] = None,
) -> dict:
    """
    Called on postflop streets when it is the user's turn.
    Returns {action, action_reason, key_factors, risk_note} or {} on error.
    """
    prompt = _build_prompt(stats, game_summary, action_history or []) + _bluff_directive()
    if DEBUG:
        print(f"[PAI] LLM prompt:\n{prompt}\n")
    try:
        response = _groq().chat.completions.create(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            model=model_name,
            temperature=0.5,  # a bit of variation so bluffs/sizings aren't identical every time
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip() if response.choices else "{}"
        if DEBUG:
            print(f"[PAI] LLM response: {raw}")
        parsed = json.loads(raw)

        # Validate action against available_actions (case-insensitive)
        available = [a.lower() for a in stats.get("available_actions", [])]
        raw_action = parsed.get("action", "").strip().lower()
        if raw_action in available:
            action = raw_action.title()
        elif available:
            # fallback: first available
            action = stats["available_actions"][0].title()
        else:
            action = parsed.get("action", "").strip().title()

        # Bet size only applies when raising/betting
        bet_size = None
        if action.lower() in ("raise", "bet"):
            bet_size = _coerce_bet_size(parsed.get("bet_size"), stats.get("effective_stack"))

        # The model occasionally returns key_factors as a single string.
        factors = parsed.get("key_factors") or []
        if not isinstance(factors, list):
            factors = [str(factors)]

        return {
            "action":        action,
            "bet_size":      bet_size,
            "action_reason": str(parsed.get("action_reason", "")),
            "key_factors":   [str(f) for f in factors[:3]],
            "risk_note":     str(parsed.get("risk_note", "")),
        }
    except Exception as e:
        print(f"[PAI] LLM error: {e}")
        return {}
