from main import _is_pokernow_game_url


def test_accepts_pokernow_game_urls():
    assert _is_pokernow_game_url("https://www.pokernow.club/games/abc123")
    assert _is_pokernow_game_url("https://pokernow.club/games/abc123")
    assert _is_pokernow_game_url("https://www.pokernow.com/games/abc123")


def test_rejects_non_pokernow_urls():
    # The old startswith() check let a lookalike host through as long as the
    # string began with the expected prefix.
    assert not _is_pokernow_game_url("https://pokernow.club.evil.com/games/abc")
    assert not _is_pokernow_game_url("https://www.pokernow.club/sessions/new")
    assert not _is_pokernow_game_url("not a url")


# ── _legal_actions ───────────────────────────────────────────────────────────

def _turn_facing_a_bet():
    """The hand from the README screenshot: 4d6h on 4s Jd 7h 7s, villain bets 20."""
    return {
        "you_name": "pai",
        "community_cards": ["4 of Spades", "Jack of Diamonds",
                            "7 of Hearts", "7 of Spades"],
        "players": [
            {"name": "pai", "stack": 9960, "bet": 0, "status": "PlayerStatus.ACTIVE",
             "cards": ["4 of Diamonds", "6 of Hearts"], "seat": 1},
            {"name": "jes", "stack": 940, "bet": 20, "status": "PlayerStatus.ACTIVE",
             "cards": ["Unknown Card", "Unknown Card"], "seat": 2},
        ],
        "pot_size": 80,
        "dealer_position": "1",
        "current_player": "pai",
        "is_your_turn": True,
        # PokerNow renders the greyed-out Check button, so the scraper reports it.
        "available_actions": ["call", "raise", "check", "fold"],
        "blinds": [10, 20],
    }


def test_check_is_not_offered_while_facing_a_bet():
    from main import _legal_actions
    summary = _turn_facing_a_bet()
    assert "check" not in _legal_actions(summary, summary["available_actions"])


def test_call_is_not_offered_when_checking_is_free():
    from main import _legal_actions
    summary = _turn_facing_a_bet()
    summary["players"][1]["bet"] = 0
    actions = _legal_actions(summary, summary["available_actions"])
    assert "call" not in actions
    assert "check" in actions


def test_unidentified_hero_leaves_actions_untouched():
    from main import _legal_actions
    summary = _turn_facing_a_bet()
    del summary["you_name"]
    summary["players"][1]["cards"] = ["2 of Clubs", "3 of Clubs"]  # showdown, ambiguous
    summary["current_player"] = None
    assert _legal_actions(summary, summary["available_actions"]) == summary["available_actions"]


def test_payload_never_recommends_check_while_facing_a_bet():
    from main import build_stats_payload
    summary = _turn_facing_a_bet()
    # Even when the LLM itself picks Check, as it did in the screenshot.
    stats = build_stats_payload(summary, {"action": "Check"})
    assert stats["recommended_action"].lower() != "check"
    assert "check" not in [a.lower() for a in stats["available_actions"]]
