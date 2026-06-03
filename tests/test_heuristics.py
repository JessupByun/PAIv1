import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.heuristics import (
    calculate_position,
    calculate_spr,
    calculate_effective_stack,
    recommend_action,
    recommend_bet_size,
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


def test_recommend_preflop_checked_to_bb_never_folds():
    # BB with a trash hand, checked around: fold button is present, but checking
    # is free — must Check, never Fold. (Regression: used to return Fold.)
    s = {
        "community_cards": [],
        "players": [{"name": "You", "stack": 100, "cards": ["7 of Spades", "2 of Hearts"],
                     "status": "Active", "bet": 2, "seat": 1}],
        "pot_size": 5, "current_player": "You", "dealer_position": "1", "you_name": "You",
    }
    action = recommend_action(s, "Trash", None, 50.0, "Big Blind", ["fold", "check", "raise"])
    assert action == "Check"


# ── recommend_bet_size ────────────────────────────────────────────────────────

def _size_summary(players, blinds_bb=2):
    return {"players": players, "pot_size": 10, "you_name": "You", "dealer_position": "1"}


def test_bet_size_open_raise():
    # Unopened pot (only blinds posted) → 2.5x BB open
    s = _size_summary([_user_player(stack=200), _make_player("Vil", stack=200, bet=2)])
    size = recommend_bet_size(s, "Raise", "Late", [1, 2])
    assert size == 5  # 2.5 * 2


def test_bet_size_sb_opens_larger():
    s = _size_summary([_user_player(stack=200), _make_player("Vil", stack=200, bet=2)])
    size = recommend_bet_size(s, "Raise", "Small Blind", [1, 2])
    assert size == 6  # 3 * 2


def test_bet_size_three_bet_vs_raise():
    # Villain opened to 6 → 3-bet to 3x = 18 (in position)
    s = _size_summary([_user_player(stack=200), _make_player("Vil", stack=200, bet=6)])
    size = recommend_bet_size(s, "Raise", "Late", [1, 2])
    assert size == 18


def test_bet_size_none_when_not_raising():
    s = _size_summary([_user_player(stack=200)])
    assert recommend_bet_size(s, "Call", "Late", [1, 2]) is None
    assert recommend_bet_size(s, "Fold", "Late", [1, 2]) is None


def test_bet_size_capped_to_effective_stack():
    # Tiny stacks: 3-bet math would exceed stack → cap to effective stack
    s = _size_summary([_user_player(stack=15), _make_player("Vil", stack=15, bet=6)])
    size = recommend_bet_size(s, "Raise", "Late", [1, 2])
    assert size == 15  # capped, not 18


def test_bet_size_ignores_own_raise():
    # Regression: after we raise to 60, our own bet must NOT be read as a raise to
    # 3-bet to ~240. Opponent only has the BB (20) in → treat as an open vs the blind.
    s = {
        "players": [
            _make_player("You", stack=140, bet=60, cards=["Ace of Spades", "King of Hearts"]),
            _make_player("Vil", stack=180, bet=20),
        ],
        "pot_size": 80, "you_name": "You", "dealer_position": "1",
    }
    size = recommend_bet_size(s, "Raise", "Small Blind", [10, 20])
    assert size == 60  # 3x the BB open, not 4x our own 60 (=240)
