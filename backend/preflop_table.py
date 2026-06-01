"""
GTO preflop opening ranges for 6-max No-Limit Hold'em.

These ranges represent standard opening frequencies at a 6-max table
based on widely published GTO solver outputs (e.g. PioSOLVER, GTO+).

Positions: EP (Early / UTG), MP (Middle / HJ), CO (Cutoff), BTN (Button/Late),
           SB (Small Blind), BB (Big Blind).

Actions: 'Raise', 'Call', 'Fold'
- 'Raise'  = open raise (or 3-bet when facing a raise, use judgement)
- 'Call'   = flat call a raise (BB defense) or limp (rare, SB only)
- 'Fold'   = fold preflop

Source: Standard 6-max GTO ranges (approximated from publicly available charts).
Mixed-strategy hands are resolved to the higher-frequency action.
"""

# Map canonical hand notation → {position → action}
# Positions mapped from calculate_position() output:
#   'Early'       → EP
#   'Middle'      → MP
#   'Late'        → CO/BTN combined (BTN range used as it's most common "Late")
#   'Small Blind' → SB
#   'Big Blind'   → BB (facing 1 raise, defense range)

_POSITION_KEY_MAP = {
    "Early":       "EP",
    "Middle":      "MP",
    "Late":        "BTN",
    "Small Blind": "SB",
    "Big Blind":   "BB",
    "Unknown":     "BTN",  # default to loose range if unknown
}

# Action table: hand → (EP, MP, BTN, SB, BB)
# BB column = defence vs a single open raise (Call/Raise/Fold)
_TABLE = {
    # Premiums — open from everywhere
    "AA":  ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "KK":  ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "QQ":  ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "JJ":  ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "TT":  ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "99":  ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "88":  ("Raise", "Raise", "Raise", "Raise", "Call"),
    "77":  ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "66":  ("Fold",  "Fold",  "Raise", "Raise", "Call"),
    "55":  ("Fold",  "Fold",  "Raise", "Raise", "Call"),
    "44":  ("Fold",  "Fold",  "Raise", "Call",  "Call"),
    "33":  ("Fold",  "Fold",  "Raise", "Call",  "Call"),
    "22":  ("Fold",  "Fold",  "Raise", "Call",  "Call"),
    # Suited Broadway
    "AKs": ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "AQs": ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "AJs": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "ATs": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "A9s": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "A8s": ("Fold",  "Fold",  "Raise", "Raise", "Call"),
    "A7s": ("Fold",  "Fold",  "Raise", "Raise", "Call"),
    "A6s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "A5s": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "A4s": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "A3s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "A2s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "KQs": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "KJs": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "KTs": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "K9s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "K8s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "K7s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "K6s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "K5s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "K4s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K3s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K2s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "QJs": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "QTs": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "Q9s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "Q8s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "Q7s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q6s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q5s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q4s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q3s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q2s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "JTs": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "J9s": ("Fold",  "Raise", "Raise", "Raise", "Fold"),
    "J8s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "J7s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "J6s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J5s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J4s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J3s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J2s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T9s": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "T8s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "T7s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "T6s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T5s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T4s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T3s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T2s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "98s": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "97s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "96s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "95s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "94s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "93s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "92s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "87s": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "86s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "85s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "84s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "83s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "82s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "76s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "75s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "74s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "73s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "72s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "65s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "64s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "63s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "62s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "54s": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "53s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "52s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "43s": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "42s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "32s": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    # Offsuit Broadway
    "AKo": ("Raise", "Raise", "Raise", "Raise", "Raise"),
    "AQo": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "AJo": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "ATo": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "A9o": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "A8o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "A7o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "A6o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "A5o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "A4o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "A3o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "A2o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "KQo": ("Raise", "Raise", "Raise", "Raise", "Call"),
    "KJo": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "KTo": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "K9o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "K8o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K7o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K6o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K5o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K4o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K3o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "K2o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "QJo": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "QTo": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "Q9o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "Q8o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q7o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q6o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q5o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q4o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q3o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "Q2o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "JTo": ("Fold",  "Raise", "Raise", "Raise", "Call"),
    "J9o": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "J8o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "J7o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J6o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J5o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J4o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J3o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "J2o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T9o": ("Fold",  "Fold",  "Raise", "Raise", "Fold"),
    "T8o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "T7o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T6o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T5o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T4o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T3o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "T2o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "98o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "97o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "96o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "95o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "94o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "93o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "92o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "87o": ("Fold",  "Fold",  "Fold",  "Raise", "Fold"),
    "86o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "85o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "84o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "83o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "82o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "76o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "75o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "74o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "73o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "72o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "65o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "64o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "63o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "62o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "54o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "53o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "52o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "43o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "42o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
    "32o": ("Fold",  "Fold",  "Fold",  "Fold",  "Fold"),
}

# Column index for each position key
_POS_INDEX = {"EP": 0, "MP": 1, "BTN": 2, "SB": 3, "BB": 4}

# Fallback by hand tier if hand not in table (shouldn't happen for standard 169)
_TIER_FALLBACK = {
    "Premium": "Raise",
    "Strong":  "Raise",
    "Medium":  "Call",
    "Weak":    "Fold",
}


def lookup_preflop_action(hand_canonical: str, position: str) -> str:
    """
    Return the GTO-recommended preflop action for a given hand and position.

    Args:
        hand_canonical: e.g. 'AKs', 'QQ', 'T9o'
        position: output of calculate_position(), e.g. 'Early', 'Late', 'Small Blind'

    Returns:
        'Raise', 'Call', or 'Fold'
    """
    pos_key = _POSITION_KEY_MAP.get(position, "BTN")
    col = _POS_INDEX.get(pos_key, 2)

    row = _TABLE.get(hand_canonical)
    if row is not None:
        return row[col]

    # Fallback: classify by tier
    from backend.hand_strength import classify_starting_hand
    tier = classify_starting_hand(hand_canonical)
    return _TIER_FALLBACK.get(tier, "Fold")


def get_all_hands_for_position(position: str) -> dict:
    """Return {hand: action} for all 169 hands at a given position. Used for testing."""
    pos_key = _POSITION_KEY_MAP.get(position, "BTN")
    col = _POS_INDEX.get(pos_key, 2)
    return {hand: row[col] for hand, row in _TABLE.items()}
