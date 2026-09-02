from backend.util import amount_to_call, safe_float


def calculate_pot_odds(game_summary):
    """
    Price of a call as a percentage of the pot you'd be playing for:
    call / (pot + call). Returns 0.0 when there is nothing to call.
    """
    pot_size = safe_float(game_summary.get("pot_size")) or 0.0
    call_amt = amount_to_call(game_summary)

    total_pot = pot_size + call_amt
    if total_pot == 0:
        return 0.0

    return round((call_amt / total_pot) * 100, 2)
