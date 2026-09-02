"""
Shared helpers for reading values out of a game summary dict.

A game summary is the flattened, JSON-serializable view of PokerNow's GameState
built by main.get_game_summary(). Its numeric fields arrive as strings straight
from the DOM and are not always numbers: a stack reads "All In" once a player is
committed, and bets can be blank or comma-grouped.
"""

_FOLDED_STATUSES = ("FOLDED", "OFFLINE")


def safe_float(value):
    """
    Parse a DOM-sourced numeric field. Returns None when the value isn't a
    number, which includes the "All In" stack sentinel. Callers must decide
    what None means for them - never call float() on these fields directly.
    """
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def chips(value) -> float:
    """safe_float for bet amounts, where "not a number" means "nothing wagered"."""
    return safe_float(value) or 0.0


def is_active(player: dict) -> bool:
    """
    Whether a player is still contesting the pot. PokerNow reports status as the
    stringified enum ("PlayerStatus.FOLDED"), so this matches on substring.
    """
    status = str(player.get("status", "")).upper()
    return not any(s in status for s in _FOLDED_STATUSES)


def has_hole_cards(player: dict) -> bool:
    cards = player.get("cards", [])
    return len(cards) == 2 and all(c != "Unknown Card" for c in cards)


def local_player(game_summary: dict) -> dict | None:
    """
    The local player's dict, identified by you_name (read from the you-player CSS
    class). Falls back to the one player whose hole cards are visible - which is
    only unambiguous before showdown, so it deliberately gives up when more than
    one player is showing cards rather than guessing wrong.
    """
    players = game_summary.get("players", [])

    you_name = game_summary.get("you_name")
    if you_name:
        for player in players:
            if player.get("name") == you_name:
                return player

    showing = [p for p in players if has_hole_cards(p)]
    return showing[0] if len(showing) == 1 else None


def local_player_name(game_summary: dict):
    """local_player's name, falling back to whoever is on the clock."""
    player = local_player(game_summary)
    if player is not None:
        return player.get("name")
    return game_summary.get("current_player")


def hole_cards(game_summary: dict) -> list:
    """The local player's two hole cards, or [] if they aren't visible."""
    player = local_player(game_summary)
    return list(player["cards"]) if player is not None and has_hole_cards(player) else []


def amount_to_call(game_summary: dict) -> float:
    """
    Chips the local player must add to match the largest bet.

    This is also what identifies a new decision point WITHIN a street: PokerNow
    keeps a street's bets in each player's bet_value and only sweeps them into
    pot_size once the street ends, so the pot alone can't tell a check spot apart
    from facing a bet on the same board.
    """
    hero = local_player_name(game_summary)
    my_bet = 0.0
    max_bet = 0.0
    for player in game_summary.get("players", []):
        bet = chips(player.get("bet"))
        max_bet = max(max_bet, bet)
        if player.get("name") == hero:
            my_bet = bet
    return max(0.0, max_bet - my_bet)
