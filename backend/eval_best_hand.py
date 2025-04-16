from treys import Card, Evaluator
import itertools

def convert_card_to_treys(card_str):
    rank_str, suit_str = card_str.strip().split(' of ')
    rank_map = {'2':'2', '3':'3', '4':'4', '5':'5', '6':'6',
                '7':'7', '8':'8', '9':'9', '10':'T', 'Jack':'J',
                'Queen':'Q', 'King':'K', 'Ace':'A'}
    suit_map = {'Spades':'s', 'Hearts':'h', 'Diamonds':'d', 'Clubs':'c'}
    return Card.new(rank_map[rank_str] + suit_map[suit_str])

def evaluate_best_hand(game_summary):
    community = game_summary.get("community_cards", [])
    current_player_name = game_summary.get("current_player", "")
    player_cards = None

    for p in game_summary.get("players", []):
        if p.get("name") == current_player_name:
            player_cards = p.get("cards", [])
            break

    if not player_cards or len(player_cards) != 2 or any(c == "Unknown Card" for c in player_cards):
        return "Unknown cards in player hand"

    if len(community + player_cards) < 5:
        return "Not enough cards to evaluate hand"

    try:
        all_cards = [convert_card_to_treys(c) for c in community + player_cards]
    except Exception:
        return "Card conversion error"

    evaluator = Evaluator()
    best_score = 9999
    best_class = "High Card"

    for combo in itertools.combinations(all_cards, 5):
        score = evaluator.evaluate([], list(combo))
        if score < best_score:
            best_score = score
            best_class = evaluator.class_to_string(evaluator.get_rank_class(score))

    return best_class

