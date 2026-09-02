from backend.hand_strength import canonical_starting_hand
from backend.preflop_table import lookup_preflop_action
from backend.util import chips, hole_cards, is_active, local_player, safe_float


def calculate_position(game_summary):
    """
    dealer_position is the absolute seat number of the dealer button on the full
    PokerNow table (up to 10 seats). Each player dict has a 'seat' field with their
    absolute seat number. We sort active players by seat, rotate so dealer is first,
    then derive position from offset.
    """
    players = game_summary.get("players", [])
    if not players:
        return "Unknown"

    user = local_player(game_summary)
    if user is None:
        return "Unknown"

    dealer_pos_str = str(game_summary.get("dealer_position", "unknown"))
    if dealer_pos_str == "unknown":
        return "Unknown"

    try:
        dealer_seat = int(dealer_pos_str)
    except ValueError:
        return "Unknown"

    user_seat = user.get("seat")
    if user_seat is None:
        return "Unknown"

    # Collect seats of all active players (those with a known seat number)
    active_seats = sorted(p["seat"] for p in players if p.get("seat") is not None)
    n = len(active_seats)
    if n == 0 or dealer_seat not in active_seats or user_seat not in active_seats:
        return "Unknown"

    # Rotate so dealer is at index 0, preserving clockwise order
    dealer_list_idx = active_seats.index(dealer_seat)
    rotated = active_seats[dealer_list_idx:] + active_seats[:dealer_list_idx]
    offset = rotated.index(user_seat)

    if n == 2:
        # Heads-up: dealer = Small Blind (offset 0), other = Big Blind (offset 1)
        return "Small Blind" if offset == 0 else "Big Blind"

    if offset == 0:
        return "Late"        # Button
    if offset == 1:
        return "Small Blind"
    if offset == 2:
        return "Big Blind"

    remaining = n - 3
    if remaining <= 0:
        return "Early"
    pos_offset = offset - 3
    third = max(1, remaining // 3)
    if pos_offset < third:
        return "Early"
    elif pos_offset < 2 * third:
        return "Middle"
    else:
        return "Late"


def calculate_spr(game_summary):
    """Stack-to-pot ratio: user_stack / pot_size. Returns float('inf') if pot is 0."""
    pot = float(game_summary.get("pot_size", 0) or 0)
    user = local_player(game_summary)
    if user is None:
        return float("inf")

    stack = safe_float(user.get("stack"))
    if stack is None:
        return float("inf")  # All In

    if pot == 0:
        return float("inf")

    return round(stack / pot, 2)


def calculate_effective_stack(game_summary):
    """
    Effective stack = min(user_stack, max_opponent_stack).
    Ignores All-In players (they cap the effective stack to 0 beyond their contribution).
    Returns user's stack if no opponents found.
    """
    user = local_player(game_summary)
    if user is None:
        return 0.0

    user_stack = safe_float(user.get("stack"))
    if user_stack is None:
        return 0.0  # user is all-in

    opponent_stacks = []
    for p in game_summary.get("players", []):
        if p.get("name") == user.get("name"):
            continue
        if not is_active(p):
            continue
        s = safe_float(p.get("stack"))
        if s is not None:
            opponent_stacks.append(s)

    if not opponent_stacks:
        return round(user_stack, 2)

    return round(min(user_stack, max(opponent_stacks)), 2)


def recommend_action(game_summary, hand_strength, pot_odds, spr, position, available_actions):
    """
    Return a recommended action string: 'Fold', 'Call', 'Check', or 'Raise'.

    Preflop: uses GTO lookup table by position.
    Postflop: uses heuristic rules based on hand strength, pot odds, SPR.

    available_actions: list of strings, e.g. ['fold', 'call', 'raise'] or ['fold', 'check', 'raise']
    """
    actions_lower = [a.lower() for a in (available_actions or [])]
    can_check = "check" in actions_lower
    can_call = "call" in actions_lower
    can_raise = "raise" in actions_lower

    num_community = len(game_summary.get("community_cards", []))
    is_preflop = num_community == 0

    # --- Preflop: use GTO lookup table ---
    cards = hole_cards(game_summary)
    if is_preflop and cards:
        table_action = lookup_preflop_action(canonical_starting_hand(*cards), position)
        # Never fold for free: if it's checked to us (we have the option), check
        # instead of folding. This must come BEFORE the "table action is available"
        # check, because Fold is always an offered button.
        if table_action == "Fold" and can_check:
            return "Check"
        if table_action.lower() in actions_lower:
            return table_action
        # Fallbacks if the table action isn't directly offered
        if table_action == "Raise" and can_call:
            return "Call"
        if table_action in ("Call", "Raise") and can_check:
            return "Check"

    # --- Postflop heuristic ---
    if can_check:
        # Free to see more cards — never fold, but be selective about raising
        if hand_strength == "Premium":
            return "Raise" if can_raise else "Check"
        elif hand_strength == "Strong":
            return "Raise" if can_raise and spr < 8 else "Check"
        else:
            return "Check"

    # Must call or fold
    if hand_strength == "Premium":
        return "Raise" if can_raise else ("Call" if can_call else "Fold")
    if hand_strength == "Strong":
        if position in ("Late", "Small Blind", "Big Blind") or spr < 5:
            return "Raise" if can_raise else ("Call" if can_call else "Fold")
        return "Call" if can_call else "Fold"
    if hand_strength == "Medium":
        if pot_odds is not None and pot_odds < 30 and spr > 3:
            return "Call" if can_call else "Fold"
        return "Fold"
    if hand_strength == "Playable":
        if pot_odds is not None and pot_odds < 15:
            return "Call" if can_call else "Fold"
        return "Fold"
    # Trash — always fold unless it's free
    return "Fold"


def recommend_bet_size(game_summary, action, position, blinds):
    """
    Preflop raise sizing in chips. Returns an int (the total amount to raise TO)
    or None if not applicable.

    - Unopened pot (RFI / open): 2.5x BB, or 3x BB from the Small Blind (OOP)
    - Facing a raise (3-bet): 3x the largest bet, or 4x out of position (blinds)
    Always capped to the effective stack (never suggest betting more than you have).
    """
    if str(action).lower() not in ("raise", "bet"):
        return None

    bb = safe_float(blinds[1]) if blinds and len(blinds) >= 2 else None
    if not bb or bb <= 0:
        return None

    # Size off the largest OPPONENT bet, never our own — otherwise, right after we
    # raise (e.g. to 60), our own bet would be read as a raise to "3-bet" to 240.
    you_name = game_summary.get("you_name")
    opp_max_bet = 0.0
    for p in game_summary.get("players", []):
        if p.get("name") == you_name:
            continue
        b = chips(p.get("bet"))
        if b > opp_max_bet:
            opp_max_bet = b

    if opp_max_bet <= bb:
        # No opponent has raised beyond the blind — this is an open raise
        size = (3.0 if position == "Small Blind" else 2.5) * bb
    else:
        # Facing an opponent's raise — 3-bet relative to THEIR bet; bigger OOP
        mult = 4.0 if position in ("Small Blind", "Big Blind") else 3.0
        size = mult * opp_max_bet

    eff = calculate_effective_stack(game_summary)
    if eff and size > eff:
        size = eff  # all-in cap
    return round(size)
