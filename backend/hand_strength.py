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

# All 169 canonical hands
_ALL_HANDS = {
    'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55', '44', '33', '22',
    'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s',
    'AKo', 'AQo', 'AJo', 'ATo', 'A9o', 'A8o', 'A7o', 'A6o', 'A5o', 'A4o', 'A3o', 'A2o',
    'KQs', 'KJs', 'KTs', 'K9s', 'K8s', 'K7s', 'K6s', 'K5s', 'K4s', 'K3s', 'K2s',
    'KQo', 'KJo', 'KTo', 'K9o', 'K8o', 'K7o', 'K6o', 'K5o', 'K4o', 'K3o', 'K2o',
    'QJs', 'QTs', 'Q9s', 'Q8s', 'Q7s', 'Q6s', 'Q5s', 'Q4s', 'Q3s', 'Q2s',
    'QJo', 'QTo', 'Q9o', 'Q8o', 'Q7o', 'Q6o', 'Q5o', 'Q4o', 'Q3o', 'Q2o',
    'JTs', 'J9s', 'J8s', 'J7s', 'J6s', 'J5s', 'J4s', 'J3s', 'J2s',
    'JTo', 'J9o', 'J8o', 'J7o', 'J6o', 'J5o', 'J4o', 'J3o', 'J2o',
    'T9s', 'T8s', 'T7s', 'T6s', 'T5s', 'T4s', 'T3s', 'T2s',
    'T9o', 'T8o', 'T7o', 'T6o', 'T5o', 'T4o', 'T3o', 'T2o',
    '98s', '97s', '96s', '95s', '94s', '93s', '92s',
    '98o', '97o', '96o', '95o', '94o', '93o', '92o',
    '87s', '86s', '85s', '84s', '83s', '82s',
    '87o', '86o', '85o', '84o', '83o', '82o',
    '76s', '75s', '74s', '73s', '72s',
    '76o', '75o', '74o', '73o', '72o',
    '65s', '64s', '63s', '62s',
    '65o', '64o', '63o', '62o',
    '54s', '53s', '52s',
    '54o', '53o', '52o',
    '43s', '42s',
    '43o', '42o',
    '32s', '32o',
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
