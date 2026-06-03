"""
Integration test for LLM deployment — makes a real Groq API call.
Requires GROQ_API_KEY in environment or .env file.
Run with: pytest tests/test_llm_deployment.py -v -s
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.LLM_deployment as LLM
from backend.LLM_deployment import (
    generate_dashboard_explanation, _build_prompt, _players_block, _coerce_bet_size,
    _bluff_directive,
)

MODEL = "llama-3.3-70b-versatile"


# ── _coerce_bet_size (unit) ──────────────────────────────────────────────────

def test_coerce_bet_size_normal():
    assert _coerce_bet_size(30, 100) == 30
    assert _coerce_bet_size("45", 100) == 45

def test_coerce_bet_size_clamps_to_stack():
    # Never suggest betting more than the effective stack
    assert _coerce_bet_size(500, 80) == 80

def test_coerce_bet_size_invalid():
    assert _coerce_bet_size(0, 100) is None
    assert _coerce_bet_size(-10, 100) is None
    assert _coerce_bet_size("lots", 100) is None
    assert _coerce_bet_size(None, 100) is None


# ── _bluff_directive (unit) ──────────────────────────────────────────────────

def test_bluff_directive_disabled(monkeypatch):
    monkeypatch.setattr(LLM, "BLUFF_RATE", 0.0)
    assert all(_bluff_directive() == "" for _ in range(50))

def test_bluff_directive_always_on(monkeypatch):
    monkeypatch.setattr(LLM, "BLUFF_RATE", 1.0)
    # rate 1.0 → every roll yields a (non-empty) bluff nudge
    assert all(_bluff_directive() != "" for _ in range(50))

def test_bluff_directive_mentions_bluff(monkeypatch):
    monkeypatch.setattr(LLM, "BLUFF_RATE", 1.0)
    assert any("bluff" in _bluff_directive().lower() for _ in range(20))

# ── Shared fixtures ───────────────────────────────────────────────────────────

def _make_flop_hand():
    stats = {
        "street": "Flop",
        "hole_cards_display": "A♠ K♥",
        "starting_hand": "AKo",
        "hand_strength": "Premium",
        "best_hand": "Top Pair (Aces)",
        "pot_size": 120,
        "pot_odds": 33.3,
        "spr": 4.2,
        "effective_stack": 380,
        "position": "Late",
        "num_players": 2,
        "community_cards_display": "A♦ 7♣ 2♥",
        "blinds": [5, 10],
        "you_name": "paiv1",
        "available_actions": ["fold", "call", "raise"],
    }
    game_summary = {
        "players": [
            {
                "name": "paiv1",
                "stack": 380,
                "bet": 40,
                "status": "Active",
                "cards": ["Ace of Spades", "King of Hearts"],
            },
            {
                "name": "jess",
                "stack": 420,
                "bet": 40,
                "status": "Active",
                "cards": ["Unknown Card", "Unknown Card"],
            },
        ],
        "community_cards": ["Ace of Diamonds", "7 of Clubs", "2 of Hearts"],
    }
    action_history = [
        "Preflop: jess bet 20",
        "Preflop: paiv1 called 20",
        "Flop: jess bet 40",
    ]
    return stats, game_summary, action_history


# ── Unit tests (no API call) ──────────────────────────────────────────────────

def test_players_block_shows_you_label():
    players = [
        {"name": "paiv1", "stack": 500, "bet": 20, "status": "Active", "cards": ["Ace of Spades", "King of Hearts"]},
        {"name": "jess",  "stack": 400, "bet": 20, "status": "Active", "cards": ["Unknown Card", "Unknown Card"]},
    ]
    block = _players_block(players, you_name="paiv1")
    assert "paiv1 (YOU)" in block
    assert "jess" in block
    assert "Ace of Spades" in block
    assert "hidden" in block


def test_build_prompt_contains_key_fields():
    stats, game_summary, action_history = _make_flop_hand()
    prompt = _build_prompt(stats, game_summary, action_history)

    assert "Flop" in prompt
    assert "A♠ K♥" in prompt
    assert "A♦ 7♣ 2♥" in prompt
    assert "paiv1 (YOU)" in prompt
    assert "jess" in prompt
    assert "fold, call, raise" in prompt
    assert "Preflop: jess bet 20" in prompt
    assert "Flop: jess bet 40" in prompt


def test_build_prompt_empty_action_history():
    stats, game_summary, _ = _make_flop_hand()
    prompt = _build_prompt(stats, game_summary, [])
    assert "Action history" not in prompt or "oldest" not in prompt


# ── Integration test (real API call) ─────────────────────────────────────────

@pytest.mark.integration
def test_llm_returns_valid_action():
    """Real Groq API call — requires GROQ_API_KEY."""
    stats, game_summary, action_history = _make_flop_hand()
    result = generate_dashboard_explanation(MODEL, stats, game_summary, action_history)

    assert result, "LLM returned empty dict — likely API error or model issue"
    assert "action" in result, f"Missing 'action' key in: {result}"
    assert "action_reason" in result, f"Missing 'action_reason' key in: {result}"
    assert "key_factors" in result, f"Missing 'key_factors' key in: {result}"
    assert "risk_note" in result, f"Missing 'risk_note' key in: {result}"

    available = [a.lower() for a in stats["available_actions"]]
    assert result["action"].lower() in available, (
        f"LLM returned action '{result['action']}' not in {stats['available_actions']}"
    )
    assert isinstance(result["key_factors"], list)
    assert len(result["key_factors"]) <= 3
    assert isinstance(result["action_reason"], str) and len(result["action_reason"]) > 10
    assert isinstance(result["risk_note"], str) and len(result["risk_note"]) > 5

    # bet_size is present; a positive number when raising/betting, else None
    assert "bet_size" in result, f"Missing 'bet_size' key in: {result}"
    if result["action"].lower() in ("raise", "bet"):
        assert result["bet_size"] is None or result["bet_size"] > 0
    else:
        assert result["bet_size"] is None

    print("\n--- LLM output ---")
    print(f"Action      : {result['action']}")
    print(f"Bet size    : {result['bet_size']}")
    print(f"Reason      : {result['action_reason']}")
    print(f"Key factors : {result['key_factors']}")
    print(f"Risk note   : {result['risk_note']}")
