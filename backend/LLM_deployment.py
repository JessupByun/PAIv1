import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

_SYSTEM_PROMPT = """You are a Poker AI assistant. You will be given the current state of a poker hand — the board, the players, their stacks and bets, and the action history. Your job is to decide the best action and explain why.

Respond with valid JSON only, no markdown, no extra keys:
{
  "action": "<one of the exact strings from AVAILABLE ACTIONS>",
  "action_reason": "<2-3 sentences explaining the decision using the actual hand details>",
  "key_factors": ["<short factor 1>", "<short factor 2>", "<short factor 3>"],
  "risk_note": "<1 sentence on what to watch out for next>"
}"""

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
    prompt = _build_prompt(stats, game_summary, action_history or [])
    print(f"[PAI] LLM prompt:\n{prompt}\n")
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            model=model_name,
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip() if response.choices else "{}"
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

        return {
            "action":        action,
            "action_reason": parsed.get("action_reason", ""),
            "key_factors":   parsed.get("key_factors", [])[:3],
            "risk_note":     parsed.get("risk_note", ""),
        }
    except Exception as e:
        print(f"[PAI] LLM error: {e}")
        return {}
