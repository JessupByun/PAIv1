import pytest
from backend.hand_strength import (
    parse_card,
    canonical_starting_hand,
    classify_starting_hand,
    evaluate_starting_hand_strength,
)


def test_parse_card_ace_spades():
    rank, suit = parse_card("Ace of Spades")
    assert rank == "A"
    assert suit == "S"


def test_parse_card_ten():
    rank, suit = parse_card("10 of Hearts")
    assert rank == "T"


def test_canonical_offsuit():
    assert canonical_starting_hand("Ace of Spades", "King of Hearts") == "AKo"


def test_canonical_suited():
    assert canonical_starting_hand("Ace of Spades", "King of Spades") == "AKs"


def test_canonical_pair():
    assert canonical_starting_hand("Queen of Hearts", "Queen of Clubs") == "QQ"


def test_canonical_order_invariant():
    assert canonical_starting_hand("2 of Hearts", "Ace of Clubs") == "A2o"


def test_classify_premium():
    assert classify_starting_hand("AA") == "Premium"
    assert classify_starting_hand("KK") == "Premium"
    assert classify_starting_hand("AKs") == "Premium"
    assert classify_starting_hand("AKo") == "Premium"
    assert classify_starting_hand("AJs") == "Premium"


def test_classify_strong():
    assert classify_starting_hand("99") == "Strong"
    assert classify_starting_hand("88") == "Strong"
    assert classify_starting_hand("JTs") == "Strong"


def test_classify_medium():
    assert classify_starting_hand("ATo") == "Medium"
    assert classify_starting_hand("55") == "Medium"
    assert classify_starting_hand("QJo") == "Medium"


def test_classify_playable():
    assert classify_starting_hand("44") == "Playable"
    assert classify_starting_hand("22") == "Playable"


def test_classify_trash():
    assert classify_starting_hand("72o") == "Trash"
    assert classify_starting_hand("83o") == "Trash"


def test_evaluate_starting_hand_finds_user_cards():
    game_summary = {
        "players": [
            {"name": "Alice", "cards": ["Unknown Card", "Unknown Card"], "status": "Active"},
            {"name": "You",   "cards": ["Ace of Spades", "King of Hearts"], "status": "Current"},
        ]
    }
    result = evaluate_starting_hand_strength(game_summary)
    assert result == "Premium"


def test_evaluate_starting_hand_no_cards():
    game_summary = {"players": [
        {"name": "Alice", "cards": ["Unknown Card", "Unknown Card"]},
    ]}
    result = evaluate_starting_hand_strength(game_summary)
    assert "No known" in result


def test_evaluate_starting_hand_at_showdown_uses_you_name():
    # At showdown every hand is face up; you_name must decide whose it is.
    game_summary = {
        "you_name": "You",
        "players": [
            {"name": "Alice", "cards": ["7 of Spades", "2 of Hearts"], "status": "Active"},
            {"name": "You",   "cards": ["Ace of Spades", "Ace of Hearts"], "status": "Active"},
        ],
    }
    assert evaluate_starting_hand_strength(game_summary) == "Premium"
