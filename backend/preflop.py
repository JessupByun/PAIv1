import random

# Helper: Convert a card string ("9 of Clubs") into a short value (e.g., "9") and suit shorthand (e.g., "C")
def parse_card(card_str):
    # If card_str is "10 of Diamonds", we'll map it to "T"
    parts = card_str.split(" of ")
    value = parts[0]
    suit = parts[1][0] if len(parts) > 1 else ""
    # Map "10" to "T"
    if value == "10":
        value = "T"
    return value, suit

# Create a canonical starting hand representation:
#   - For pairs: "QQ"
#   - For non-pairs: combine highest card first followed by lower card and append "s" if suited or "o" if offsuit.
def canonical_starting_hand(card1, card2):
    val1, suit1 = parse_card(card1)
    val2, suit2 = parse_card(card2)
    
    rank_order = "23456789TJQKA"
    i1, i2 = rank_order.index(val1), rank_order.index(val2)
    
    if i1 == i2:
        return val1 + val2  # e.g. "QQ"
    suited = (suit1 == suit2)
    high, low = (val1, val2) if i1 > i2 else (val2, val1)
    return high + low + ("s" if suited else "o")

# Example preflop ranges for decision making. (Note: these are sample ranges for illustration.)
# In production, you'd have more granular ranges by position and include mix frequencies.
PREOPEN_RANGE = {
    # Hands recommended for an open raise (first action, no other bets besides blinds)
    "raise": {"AA", "KK", "QQ", "JJ", "AKs", "TT", "AQs", "AJs", "KQs", "AKo", "ATs", "KJs", "QJs", "99", "JTs", "AQo"},
}
RERAISE_RANGE = {
    # Hands recommended for a 3-bet (facing an open raise)
    "3bet": {"AA", "KK", "QQ", "JJ", "AKs", "TT", "AQs", "AJs", "AKo"},
}

# Main function: evaluate preflop decision based on the provided summary dictionary.
def get_preflop_decision(summary):
    # Find our player – assume our cards are the only known cards in summary["players"]
    my_player = None
    for player in summary.get("players", []):
        # Look for the player with known cards (i.e., not "Unknown Card")
        cards = player.get("cards", [])
        if len(cards) == 2 and all("Unknown" not in card for card in cards):
            my_player = player
            break
    if not my_player:
        return {"error": "No valid player with known cards found."}
    
    # Convert our hole cards to canonical form (e.g., "AKs", "JTo", etc.)
    my_cards = my_player["cards"]
    canonical_hand = canonical_starting_hand(my_cards[0], my_cards[1])
    
    # Determine the betting situation:
    # We'll assume that the blinds are provided as strings in summary["blinds"]
    blinds = list(map(int, summary.get("blinds", [])))
    if len(blinds) < 2:
        return {"error": "Blinds not properly provided."}
    big_blind = blinds[1]
    
    # Get the highest bet posted in the current round (convert from string to int)
    # Skip empty strings and assume at least one value.
    bets = [int(player["bet"]) for player in summary.get("players", []) if player.get("bet", "").strip() != ""]
    current_bet = max(bets) if bets else big_blind  # If no bets found, use big blind.
    
    # Determine if it is an "open" situation or if someone has raised.
    # If the highest bet equals the big blind, assume no preflop raise (only forced bets).
    if current_bet == big_blind:
        situation = "open"
    else:
        situation = "re_raise"
    
    # For sizing, determine our recommended multiplier:
    if situation == "open":
        # For open raise, we suggest a raise to, say, 3x the big blind.
        recommended_size = 3 * big_blind
        if canonical_hand in PREOPEN_RANGE["raise"]:
            action = f"Open Raise to {recommended_size}bb"
        else:
            action = "Fold"
    else:
        # If facing a raise (re-raise scenario)
        # Here we assume a 3-bet sizing of 3x the current bet.
        recommended_size = 3 * current_bet
        if canonical_hand in RERAISE_RANGE["3bet"]:
            action = f"3-Bet to {recommended_size}bb"
        else:
            # In some cases, you might choose to call instead of folding.
            # This logic could be extended with additional range data.
            action = "Call or Fold based on pot odds (hand not in 3-bet range)"
    
    # Construct a detailed recommendation dictionary for debugging and clarity.
    recommendation = {
        "action": action,
        "situation": situation,
        "my_hand": canonical_hand,
        "big_blind": big_blind,
        "current_bet": current_bet,
        "recommended_raise_size": recommended_size
    }
    
    return recommendation

# For testing purposes, if you run this script directly:
if __name__ == "__main__":
    # Example summary dictionary (simulate preflop state)
    example_summary = {
        "game_type": "No Limit Texas Hold'em",
        "pot_size": "0",
        "community_cards": [],
        "players": [
            {
                "name": "jessup",
                "stack": "660",
                "bet": "10",
                "cards": ["9 of Clubs", "Queen of Diamonds"],
                "status": "PlayerState.CURRENT",
                "hand_message": ""
            },
            {
                "name": "daniel",
                "stack": "1310",
                "bet": "20",
                "cards": ["Unknown Card", "Unknown Card"],
                "status": "PlayerState.ACTIVE",
                "hand_message": ""
            }
        ],
        "dealer_position": "1",
        "current_player": "jessup",
        "blinds": ["10", "20"],
        "winners": [],
        "is_your_turn": True
    }
    
    decision = get_preflop_decision(example_summary)
    print("Preflop Decision Recommendation:")
    for key, value in decision.items():
        print(f"{key}: {value}")
