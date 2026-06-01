import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.eval_best_hand import evaluate_best_hand


def _make_summary(community, hole_cards, current_player="You"):
    return {
        "community_cards": community,
        "current_player": current_player,
        "players": [{"name": "You", "cards": hole_cards}],
    }


def test_royal_flush():
    summary = _make_summary(
        community=["Ace of Spades", "King of Spades", "Queen of Spades",
                   "Jack of Spades", "10 of Spades"],
        hole_cards=["2 of Hearts", "3 of Clubs"],
    )
    result = evaluate_best_hand(summary)
    assert "Straight Flush" in result or "Royal Flush" in result


def test_four_of_a_kind():
    summary = _make_summary(
        community=["Ace of Spades", "Ace of Hearts", "Ace of Diamonds", "2 of Clubs", "3 of Clubs"],
        hole_cards=["Ace of Clubs", "King of Hearts"],
    )
    result = evaluate_best_hand(summary)
    assert result.startswith("Four of a Kind")


def test_full_house():
    summary = _make_summary(
        community=["King of Spades", "King of Hearts", "King of Diamonds", "2 of Clubs", "3 of Hearts"],
        hole_cards=["2 of Hearts", "2 of Spades"],
    )
    result = evaluate_best_hand(summary)
    assert result.startswith("Full House")


def test_preflop_not_enough_cards():
    summary = _make_summary(
        community=[],
        hole_cards=["Ace of Spades", "King of Hearts"],
    )
    result = evaluate_best_hand(summary)
    assert "Not enough" in result


def test_unknown_card_returns_error():
    summary = _make_summary(
        community=["Ace of Spades", "King of Hearts", "Queen of Clubs"],
        hole_cards=["Unknown Card", "Jack of Diamonds"],
    )
    result = evaluate_best_hand(summary)
    assert "Unknown" in result or "error" in result.lower()
