from backend.util import hole_cards

# Sklansky & Malmuth hand groups (from "Hold 'em Poker for Advanced Players")
# Groups 1-2 → Premium, 3-4 → Strong, 5-6 → Medium, 7-8 → Playable, unranked → Trash

HAND_CATEGORIES = {
    "Premium": {
        # Group 1
        'AA', 'KK', 'QQ', 'JJ', 'AKs',
        # Group 2
        'TT', 'AQs', 'AJs', 'KQs', 'AKo',
    },
    "Strong": {
        # Group 3
        '99', 'JTs', 'QJs', 'KJs', 'ATs', 'AQo',
        # Group 4
        '88', 'AJo', 'KQo', 'QTs', 'KTs', 'J9s', 'T9s', '98s',
    },
    "Medium": {
        # Group 5
        '77', '66', 'JTo', 'QJo', 'KJo', 'Q9s', 'T8s', '97s', '87s', '76s',
        'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s',
        # Group 6
        '55', 'ATo', 'KTo', 'QTo', 'J8s', '86s', '75s', '65s', '54s',
    },
    "Playable": {
        # Group 7
        '44', '33', '22',
        'K9s', 'K8s', 'K7s', 'K6s', 'K5s', 'K4s', 'K3s', 'K2s',
        'J9o', 'T9o', '98o', '43s', '64s', '53s',
        # Group 8
        'A9o', 'K9o', 'Q9o', 'J8o', 'T8o', '87o', '76o', '65o', '54o',
        'J7s', '96s', '85s', '74s', '42s', '32s',
    },
}

# The 169 canonical starting hands: 13 pairs plus every high/low combination
# in both suited and offsuit form.
RANKS = "AKQJT98765432"
_ALL_HANDS = {
    high + low + suffix
    for i, high in enumerate(RANKS)
    for low in RANKS[i:]
    for suffix in (("",) if high == low else ("s", "o"))
}

HAND_CATEGORIES["Trash"] = _ALL_HANDS - set().union(*HAND_CATEGORIES.values())


def parse_card(card_str):
    value_str, _, suit = card_str.partition(' of ')
    return value_str[0] if value_str != '10' else 'T', suit[0]


def canonical_starting_hand(card1, card2):
    val1, _ = parse_card(card1)
    val2, _ = parse_card(card2)

    rank_order = '23456789TJQKA'
    i1, i2 = rank_order.index(val1), rank_order.index(val2)

    if i1 == i2:
        return val1 + val2
    suited = card1.split(' of ')[1] == card2.split(' of ')[1]
    high, low = (val1, val2) if i1 > i2 else (val2, val1)
    return high + low + ('s' if suited else 'o')


def classify_starting_hand(hand_str):
    for category, hands in HAND_CATEGORIES.items():
        if hand_str in hands:
            return category
    return "Trash"


def evaluate_starting_hand_strength(game_summary):
    cards = hole_cards(game_summary)
    if not cards:
        return "No known cards found"
    return classify_starting_hand(canonical_starting_hand(*cards))
