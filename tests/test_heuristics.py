import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.heuristics import (
    calculate_position,
    calculate_spr,
    calculate_effective_stack,
    recommend_action,
    _safe_float_stack,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_summary(dealer_pos, players, community_cards=None, pot_size=100,
                  current_player=None, available_actions=None, you_name="You"):
    if current_player is None and players:
        current_player = players[0]["name"]
    return {
        "dealer_position": str(dealer_pos),
        "players": players,
        "community_cards": community_cards or [],
        "pot_size": pot_size,
        "current_player": current_player,
        "available_actions": available_actions or ["fold", "call", "raise"],
        "you_name": you_name,
    }


def _make_player(name, stack=500, cards=None, status="Active", bet=0, seat=None):
    return {
        "name": name,
        "stack": stack,
        "cards": cards or ["Unknown Card", "Unknown Card"],
        "status": status,
        "bet": bet,
        "seat": seat,
    }


def _user_player(stack=500, cards=None, seat=None):
    return _make_player("You", stack=stack,
                        cards=cards or ["Ace of Spades", "King of Hearts"],
                        seat=seat)


# ── _safe_float_stack ─────────────────────────────────────────────────────────

def test_safe_float_normal():
    assert _safe_float_stack(500) == 500.0
    assert _safe_float_stack("250.5") == 250.5


def test_safe_float_all_in_string():
    assert _safe_float_stack("All In") is None
    assert _safe_float_stack("all in") is None


def test_safe_float_invalid():
    assert _safe_float_stack("N/A") is None


# ── calculate_spr ─────────────────────────────────────────────────────────────

def test_spr_normal():
    players = [_user_player(stack=500)]
    summary = _make_summary(1, players, pot_size=100)
    assert calculate_spr(summary) == pytest.approx(5.0)


def test_spr_zero_pot():
    players = [_user_player(stack=500)]
    summary = _make_summary(1, players, pot_size=0)
    assert calculate_spr(summary) == float("inf")


def test_spr_all_in_user():
    players = [_make_player("You", stack="All In",
                            cards=["Ace of Spades", "King of Hearts"])]
    summary = _make_summary(1, players, pot_size=100)
    assert calculate_spr(summary) == float("inf")


# ── calculate_effective_stack ─────────────────────────────────────────────────

def test_effective_stack_basic():
    players = [
        _user_player(stack=500),
        _make_player("Alice", stack=300),
        _make_player("Bob",   stack=400),
    ]
    summary = _make_summary(1, players)
    # min(500, max(300, 400)) = min(500, 400) = 400
    assert calculate_effective_stack(summary) == pytest.approx(400.0)


def test_effective_stack_skips_all_in():
    players = [
        _user_player(stack=500),
        _make_player("Alice", stack="All In"),
        _make_player("Bob",   stack=300),
    ]
    summary = _make_summary(1, players)
    assert calculate_effective_stack(summary) == pytest.approx(300.0)


def test_effective_stack_no_opponents():
    players = [_user_player(stack=500)]
    summary = _make_summary(1, players)
    assert calculate_effective_stack(summary) == pytest.approx(500.0)


# ── calculate_position ────────────────────────────────────────────────────────

def _six_player_summary(dealer_pos_1based, user_seat_0based):
    # Seats are 1-based; list index i → seat i+1
    names = ["P1", "P2", "P3", "P4", "P5", "P6"]
    players = [_make_player(n, seat=i+1) for i, n in enumerate(names)]
    user_name = names[user_seat_0based]
    players[user_seat_0based] = _user_player(seat=user_seat_0based + 1)
    players[user_seat_0based]["name"] = user_name
    return _make_summary(
        dealer_pos_1based,
        players,
        current_player=user_name,
        you_name=user_name,
    )


def test_position_button():
    # dealer=seat1 (1-based), user=seat0 → offset=0 → Late (Button)
    summary = _six_player_summary(dealer_pos_1based=1, user_seat_0based=0)
    assert calculate_position(summary) == "Late"


def test_position_small_blind():
    # dealer=seat1, user=seat1 (0-based) → offset=1 → Small Blind
    summary = _six_player_summary(dealer_pos_1based=1, user_seat_0based=1)
    assert calculate_position(summary) == "Small Blind"


def test_position_big_blind():
    # dealer=seat1, user=seat2 → offset=2 → Big Blind
    summary = _six_player_summary(dealer_pos_1based=1, user_seat_0based=2)
    assert calculate_position(summary) == "Big Blind"


def test_position_early():
    # dealer=seat1, user=seat3 → offset=3, first post-blind seat → Early
    summary = _six_player_summary(dealer_pos_1based=1, user_seat_0based=3)
    assert calculate_position(summary) == "Early"


def test_position_unknown_dealer():
    players = [_user_player()]
    summary = _make_summary("unknown", players)
    assert calculate_position(summary) == "Unknown"


# ── recommend_action ──────────────────────────────────────────────────────────

def _rec_summary(community_cards=None):
    return {
        "community_cards": community_cards or [],
        "players": [_user_player()],
        "pot_size": 100,
        "current_player": "You",
        "dealer_position": "1",
    }


def test_recommend_premium_raise():
    s = _rec_summary()
    action = recommend_action(s, "Premium", 20.0, 5.0, "Late", ["fold", "call", "raise"])
    assert action == "Raise"


def test_recommend_check_available_premium():
    s = _rec_summary(community_cards=["Ace of Spades", "King of Hearts", "2 of Clubs"])
    action = recommend_action(s, "Premium", 0.0, 5.0, "Late", ["check", "raise"])
    assert action == "Raise"


def test_recommend_trash_fold():
    s = _rec_summary(community_cards=["Ace of Spades", "King of Hearts", "2 of Clubs"])
    action = recommend_action(s, "Trash", 35.0, 5.0, "Early", ["fold", "call", "raise"])
    assert action == "Fold"


def test_recommend_check_when_trash_and_free():
    s = _rec_summary(community_cards=["Ace of Spades", "King of Hearts", "2 of Clubs"])
    action = recommend_action(s, "Trash", 0.0, 5.0, "Early", ["fold", "check", "raise"])
    assert action == "Check"
