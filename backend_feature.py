# backend_feature.py

# Ordered list of 169 starting hands from strongest to weakest
# Source: common hand ranking used in poker tools
starting_hands_ranked = [
    'AA', 'KK', 'QQ', 'JJ', 'AKs', 'TT', 'AQs', 'AJs', 'KQs', 'AKo',
    'ATs', 'KJs', 'QJs', '99', 'JTs', 'AQo', 'KTs', 'QTs', 'J9s', '88',
    'QJo', 'T9s', 'KQo', 'A9s', 'K9s', 'T8s', 'AJo', 'JTo', '77', '98s',
    '87s', 'A8s', 'A5s', 'A7s', '66', 'A4s', 'A3s', 'KJo', 'A2s', '76s',
    'K8s', '55', 'J8s', 'T7s', 'K7s', '65s', 'Q9s', '44', 'K6s', 'Q8s',
    '54s', '33', 'Q7s', 'QTo', 'K5s', 'Q6s', '22', 'J7s', '64s', 'K4s',
    'T9o', 'J9o', 'J6s', 'Q5s', '53s', 'J5s', 'K3s', 'Q4s', 'Q3s', '43s',
    'Q2s', 'J4s', 'T8o', 'J3s', 'K2s', 'J2s', '98o', 'J8o', 'T6s', 'J7o',
    '97s', '32s', 'Q9o', 'T5s', 'T4s', '96s', 'T3s', 'T7o', 'T2s', '87o',
    '95s', '86s', '65o', '94s', '75s', '84s', 'T6o', '93s', '54o', '92s',
    '64o', '85s', '76o', '83s', '74s', '82s', '73s', '63s', '52s', '43o',
    '62s', '42s', '53o', '72s', '32o', 'A6s', 'A5o', 'A4o', 'A3o', 'A2o',
    'KTo', 'K9o', 'K8o', 'K7o', 'K6o', 'K5o', 'K4o', 'K3o', 'K2o', 'Q8o',
    'Q7o', 'Q6o', 'Q5o', 'Q4o', 'Q3o', 'Q2o', 'J8o', 'J6o', 'J5o', 'J4o',
    'J3o', 'J2o', 'T8o', 'T7o', 'T5o', 'T4o', 'T3o', 'T2o', '98o', '97o',
    '96o', '95o', '94o', '93o', '92o', '87o', '86o', '85o', '84o', '83o',
    '82o', '76o', '75o', '74o', '73o', '72o', '65o', '64o', '63o', '62o',
    '54o', '53o', '52o', '43o', '42o', '32o'
]

def parse_card(card_str):
    value_str, _, suit = card_str.partition(' of ')
    return value_str[0] if value_str != '10' else 'T', suit[0]

def canonical_starting_hand(card1, card2):
    val1, _ = parse_card(card1)
    val2, _ = parse_card(card2)

    rank_order = '23456789TJQKA'
    i1, i2 = rank_order.index(val1), rank_order.index(val2)

    if i1 == i2:
        return val1 + val2  # e.g., 'QQ'
    suited = card1.split(' of ')[1] == card2.split(' of ')[1]
    high, low = (val1, val2) if i1 > i2 else (val2, val1)
    return high + low + ('s' if suited else 'o')

def rank_starting_hand(hand_str):
    try:
        rank = starting_hands_ranked.index(hand_str) + 1
        percentile = 100 - int((rank - 1) / 168 * 100)
        return f"{rank}/169, {percentile}th Percentile"
    except ValueError:
        return "Unknown Hand"

def evaluate_starting_hand_strength(game_state_dict):
    # Find the first player with known hole cards
    for player in game_state_dict.get("players", []):
        cards = player.get("cards", [])
        if all(card != "Unknown Card" for card in cards) and len(cards) == 2:
            hand = canonical_starting_hand(cards[0], cards[1])
            return rank_starting_hand(hand)
    return "No known cards found"
