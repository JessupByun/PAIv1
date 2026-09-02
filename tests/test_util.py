from backend.util import (
    amount_to_call,
    chips,
    has_hole_cards,
    hole_cards,
    is_active,
    local_player,
    local_player_name,
    safe_float,
)


# ── safe_float / chips ───────────────────────────────────────────────────────

def test_safe_float_normal():
    assert safe_float(500) == 500.0
    assert safe_float("250.5") == 250.5
    assert safe_float("1,250") == 1250.0


def test_safe_float_all_in_string():
    assert safe_float("All In") is None
    assert safe_float("all in") is None


def test_safe_float_invalid():
    assert safe_float("N/A") is None
    assert safe_float("") is None
    assert safe_float(None) is None


def test_chips_floors_unparseable_to_zero():
    assert chips("40") == 40.0
    assert chips("All In") == 0.0
    assert chips(None) == 0.0


# ── is_active ────────────────────────────────────────────────────────────────

def test_is_active_handles_stringified_enum():
    assert is_active({"status": "PlayerStatus.ACTIVE"})
    assert not is_active({"status": "PlayerStatus.FOLDED"})
    assert not is_active({"status": "PlayerStatus.OFFLINE"})


def test_is_active_handles_bare_status():
    assert is_active({"status": "Active"})
    assert not is_active({"status": "FOLDED"})


# ── local_player ─────────────────────────────────────────────────────────────

def _hero(name="You", cards=("Ace of Spades", "King of Hearts"), bet=0):
    return {"name": name, "cards": list(cards), "bet": bet, "status": "Active"}


def _villain(name="Alice", cards=("Unknown Card", "Unknown Card"), bet=0):
    return {"name": name, "cards": list(cards), "bet": bet, "status": "Active"}


def test_local_player_prefers_you_name():
    summary = {"you_name": "You", "players": [_villain(), _hero()]}
    assert local_player(summary)["name"] == "You"


def test_local_player_falls_back_to_the_only_visible_hand():
    summary = {"players": [_villain(), _hero()]}
    assert local_player(summary)["name"] == "You"


def test_local_player_gives_up_at_showdown_without_you_name():
    # Both hands face up and no you_name: guessing would pick the wrong player.
    summary = {"players": [_hero("You"), _hero("Alice", ("2 of Clubs", "7 of Hearts"))]}
    assert local_player(summary) is None


def test_local_player_survives_showdown_with_you_name():
    summary = {
        "you_name": "You",
        "players": [_hero("Alice", ("2 of Clubs", "7 of Hearts")), _hero("You")],
    }
    assert hole_cards(summary) == ["Ace of Spades", "King of Hearts"]


def test_local_player_name_falls_back_to_current_player():
    summary = {"current_player": "You", "players": [_villain(), _villain("Bob")]}
    assert local_player_name(summary) == "You"


def test_hole_cards_empty_before_the_deal():
    summary = {"you_name": "You", "players": [{"name": "You", "cards": []}]}
    assert hole_cards(summary) == []
    assert not has_hole_cards({"cards": ["Unknown Card", "Unknown Card"]})


# ── amount_to_call ───────────────────────────────────────────────────────────

def test_amount_to_call_facing_a_bet():
    summary = {"you_name": "You", "players": [_hero(bet=0), _villain(bet=50)]}
    assert amount_to_call(summary) == 50.0


def test_amount_to_call_partially_matched():
    summary = {"you_name": "You", "players": [_hero(bet=20), _villain(bet=50)]}
    assert amount_to_call(summary) == 30.0


def test_amount_to_call_when_checked_to_you():
    summary = {"you_name": "You", "players": [_hero(bet=0), _villain(bet=0)]}
    assert amount_to_call(summary) == 0.0


def test_amount_to_call_never_negative_when_you_lead():
    summary = {"you_name": "You", "players": [_hero(bet=60), _villain(bet=0)]}
    assert amount_to_call(summary) == 0.0

