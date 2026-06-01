from treys import Card, Evaluator
from collections import Counter
import itertools

RANK_CHARS = '23456789TJQKA'

def convert_card_to_treys(card_str):
    rank_str, suit_str = card_str.strip().split(' of ')
    rank_map = {'2':'2', '3':'3', '4':'4', '5':'5', '6':'6',
                '7':'7', '8':'8', '9':'9', '10':'T', 'Jack':'J',
                'Queen':'Q', 'King':'K', 'Ace':'A'}
    suit_map = {'Spades':'s', 'Hearts':'h', 'Diamonds':'d', 'Clubs':'c'}
    return Card.new(rank_map[rank_str] + suit_map[suit_str])


def _rank_name(r):
    return {'T': '10', 'J': 'J', 'Q': 'Q', 'K': 'K', 'A': 'A'}.get(r, r)


def _describe_hand(hand_class, best_combo):
    """Return a detailed string like 'Full House (8s full of 2s)'."""
    ranks = [Card.int_to_str(c)[0] for c in best_combo]
    rank_counts = Counter(ranks)
    by_count = sorted(rank_counts.items(),
                      key=lambda x: (-x[1], -RANK_CHARS.index(x[0])))

    if hand_class == "Full House":
        t, p = by_count[0][0], by_count[1][0]
        return f"Full House ({_rank_name(t)}s full of {_rank_name(p)}s)"
    if hand_class == "Four of a Kind":
        return f"Four of a Kind ({_rank_name(by_count[0][0])}s)"
    if hand_class == "Three of a Kind":
        return f"Three of a Kind ({_rank_name(by_count[0][0])}s)"
    if hand_class == "Two Pair":
        pairs = sorted([x[0] for x in by_count if x[1] == 2],
                       key=lambda r: RANK_CHARS.index(r), reverse=True)
        return f"Two Pair ({_rank_name(pairs[0])}s & {_rank_name(pairs[1])}s)"
    if hand_class == "Pair":
        return f"Pair of {_rank_name(by_count[0][0])}s"
    if hand_class == "High Card":
        high = max(ranks, key=lambda r: RANK_CHARS.index(r))
        return f"High Card ({_rank_name(high)})"
    # Flush, Straight, Straight Flush, Royal Flush
    high = max(ranks, key=lambda r: RANK_CHARS.index(r))
    return f"{hand_class} ({_rank_name(high)}-high)"


def evaluate_best_hand(game_summary):
    community = game_summary.get("community_cards", [])
    player_cards = None

    for p in game_summary.get("players", []):
        cards = p.get("cards", [])
        if len(cards) == 2 and all(c != "Unknown Card" for c in cards):
            player_cards = cards
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
    best_combo = None

    for combo in itertools.combinations(all_cards, 5):
        score = evaluator.evaluate([], list(combo))
        if score < best_score:
            best_score = score
            best_class = evaluator.class_to_string(evaluator.get_rank_class(score))
            best_combo = combo

    return _describe_hand(best_class, best_combo)
