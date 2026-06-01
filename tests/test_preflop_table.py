import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.preflop_table import lookup_preflop_action, get_all_hands_for_position, _TABLE
from backend.hand_strength import _ALL_HANDS as starting_hands_ranked

POSITIONS = ["Early", "Middle", "Late", "Small Blind", "Big Blind"]
VALID_ACTIONS = {"Raise", "Call", "Fold"}


def test_all_169_hands_in_table():
    for hand in starting_hands_ranked:
        assert hand in _TABLE, f"Hand {hand} missing from preflop table"


def test_all_hands_all_positions_return_valid_action():
    for hand in starting_hands_ranked:
        for pos in POSITIONS:
            action = lookup_preflop_action(hand, pos)
            assert action in VALID_ACTIONS, \
                f"Invalid action '{action}' for {hand} at {pos}"


def test_premium_hands_raise_from_all_positions():
    for hand in ("AA", "KK", "QQ", "AKs", "AKo"):
        for pos in POSITIONS:
            action = lookup_preflop_action(hand, pos)
            assert action == "Raise", f"{hand} should Raise from {pos}, got {action}"


def test_trash_hands_fold_from_early():
    for hand in ("72o", "32o", "27o"):
        # 27o is not canonical — only test hands in table
        if hand in _TABLE:
            action = lookup_preflop_action(hand, "Early")
            assert action == "Fold", f"{hand} from Early should Fold, got {action}"


def test_72o_folds_everywhere():
    for pos in POSITIONS:
        assert lookup_preflop_action("72o", pos) == "Fold"


def test_aks_raises_from_early():
    assert lookup_preflop_action("AKs", "Early") == "Raise"


def test_get_all_hands_returns_dict():
    result = get_all_hands_for_position("Late")
    assert isinstance(result, dict)
    assert len(result) == len(_TABLE)
    for action in result.values():
        assert action in VALID_ACTIONS
