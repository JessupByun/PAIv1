import pytest
from backend.pot_odds import calculate_pot_odds


def _make_summary(pot_size, players):
    return {"pot_size": pot_size, "current_player": "You", "players": players}


def test_basic_pot_odds():
    # pot=100, max_bet=50, player hasn't bet → call_amt=50, total=150 → 33.33%
    summary = _make_summary(100, [
        {"name": "Alice", "bet": "50"},
        {"name": "You",   "bet": "0"},
    ])
    result = calculate_pot_odds(summary)
    assert result == pytest.approx(33.33, abs=0.1)


def test_no_bet_no_divide_by_zero():
    summary = _make_summary(0, [
        {"name": "You", "bet": "0"},
    ])
    result = calculate_pot_odds(summary)
    assert result == 0.0


def test_partial_call():
    # pot=200, max_bet=100, player already bet 50 → call_amt=50, total=250 → 20%
    summary = _make_summary(200, [
        {"name": "Alice", "bet": "100"},
        {"name": "You",   "bet": "50"},
    ])
    result = calculate_pot_odds(summary)
    assert result == pytest.approx(20.0, abs=0.1)


def test_already_matched():
    # Player already matched max bet → call_amt=0 → 0%
    summary = _make_summary(100, [
        {"name": "Alice", "bet": "50"},
        {"name": "You",   "bet": "50"},
    ])
    result = calculate_pot_odds(summary)
    assert result == 0.0
