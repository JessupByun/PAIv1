import os
import time
import json
import threading
import contextlib
from selenium import webdriver
from PokerNow import PokerClient

from backend.hand_strength import evaluate_starting_hand_strength, canonical_starting_hand
from backend.eval_best_hand import evaluate_best_hand
from backend.pot_odds import calculate_pot_odds
from backend.heuristics import calculate_position, calculate_spr, calculate_effective_stack, recommend_action, recommend_bet_size
from backend.ws_server import WSServer
from backend.LLM_deployment import generate_dashboard_explanation

# Model is configurable via env var. Defaults to the 70B (best decisions, ~1s).
# For a faster demo set:  PAI_LLM_MODEL=llama-3.1-8b-instant  (~0.6s)
LLM_MODEL = os.environ.get("PAI_LLM_MODEL", "llama-3.3-70b-versatile")
WS_PORT = int(os.environ.get("PAI_WS_PORT", 8765))

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_player_seats(driver) -> dict:
    """
    Returns {player_name: seat_number} from 'table-player-N' CSS class,
    and also flags which player is 'you' via the 'you-player' class.
    Result includes a special key '__you__' with the local player's name.
    """
    try:
        result = driver.execute_script("""
            var result = {};
            var youName = null;
            var players = document.querySelectorAll('.table-player');
            for (var i = 0; i < players.length; i++) {
                var el = players[i];
                var nameEl = el.querySelector('.table-player-name a');
                if (!nameEl) continue;
                var name = nameEl.textContent.trim();
                var classes = el.className.split(' ');
                for (var j = 0; j < classes.length; j++) {
                    var c = classes[j].trim();
                    if (/^table-player-\d+$/.test(c)) {
                        result[name] = parseInt(c.split('-')[2], 10);
                    }
                    if (c === 'you-player') {
                        youName = name;
                    }
                }
            }
            if (youName) result['__you__'] = youName;
            return result;
        """)
        return result if result else {}
    except Exception:
        return {}


def get_game_summary(game_state, player_seats=None):
    seats = player_seats or {}
    summary = {
        "game_type": game_state.game_type,
        "pot_size": game_state.pot_size,
        "community_cards": [str(card) for card in game_state.community_cards],
        "players": [],
        "dealer_position": game_state.dealer_position,
        "current_player": game_state.current_player,
        "blinds": game_state.blinds,
        "winners": [],
        "is_your_turn": game_state.is_your_turn,
        "available_actions": list(game_state.available_actions.keys()) if game_state.available_actions else [],
        "you_name": seats.get("__you__"),
    }
    for player in game_state.players:
        summary["players"].append({
            "name": player.name,
            "stack": player.stack,
            "bet": player.bet_value,
            "cards": [str(card) for card in player.cards],
            "status": str(player.status),
            "hand_message": player.hand_message,
            "seat": seats.get(player.name),
        })
    for winner in game_state.winners:
        summary["winners"].append({
            "name": winner["name"],
            "stack_info": winner["stack_info"]
        })
    return summary

def _format_cards_display(card_list: list) -> str:
    rank_map = {
        '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
        '7': '7', '8': '8', '9': '9', '10': 'T', 'Jack': 'J',
        'Queen': 'Q', 'King': 'K', 'Ace': 'A'
    }
    suit_map = {'Spades': '♠', 'Hearts': '♥', 'Diamonds': '♦', 'Clubs': '♣'}
    parts = []
    for card in card_list:
        try:
            rank_str, suit_str = card.strip().split(' of ')
            parts.append(rank_map.get(rank_str, '?') + suit_map.get(suit_str, '?'))
        except Exception:
            parts.append('??')
    return ' '.join(parts)


def inject_overlay(driver):
    css_path = os.path.join(os.path.dirname(__file__), "frontend", "overlay.css")
    js_path  = os.path.join(os.path.dirname(__file__), "frontend", "content.js")

    with open(css_path, "r") as f:
        css = f.read()
    with open(js_path, "r") as f:
        js = f.read()

    driver.execute_script("""
        if (!document.getElementById('pai-style')) {
            const style = document.createElement('style');
            style.id = 'pai-style';
            style.textContent = arguments[0];
            document.head.appendChild(style);
        }
    """, css)

    driver.execute_script("""
        if (!window.__pai_injected) {
            window.__pai_injected = true;
            """ + js + """
        }
    """)


def _get_street(num_community: int) -> str:
    return {0: "Preflop", 3: "Flop", 4: "Turn", 5: "River"}.get(num_community, "Unknown")


def _get_user_cards(game_summary: dict) -> list:
    for p in game_summary.get("players", []):
        cards = p.get("cards", [])
        if len(cards) == 2 and all(c != "Unknown Card" for c in cards):
            return cards
    return []


def _safe_json_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f == float('inf') or f == float('-inf') or f != f) else round(f, 2)
    except (TypeError, ValueError):
        return None


def build_stats_payload(game_summary: dict, llm_result: dict = None) -> dict:
    num_community = len(game_summary.get("community_cards", []))
    community_cards = game_summary.get("community_cards", [])
    user_cards = _get_user_cards(game_summary)
    starting_hand = ""
    hand_strength = "Unknown"
    if len(user_cards) == 2:
        starting_hand = canonical_starting_hand(user_cards[0], user_cards[1])
        hand_strength = evaluate_starting_hand_strength(game_summary)

    best_hand = None
    if num_community >= 3 and len(user_cards) == 2:
        result = evaluate_best_hand(game_summary)
        best_hand = result if result not in (
            "Unknown cards in player hand", "Card conversion error", "Not enough cards to evaluate hand"
        ) else None

    pot_odds = _safe_json_float(calculate_pot_odds(game_summary))
    position = calculate_position(game_summary)
    spr = _safe_json_float(calculate_spr(game_summary))
    effective_stack = _safe_json_float(calculate_effective_stack(game_summary))
    available_actions = game_summary.get("available_actions", [])
    active_players = [p for p in game_summary.get("players", [])
                      if "FOLDED" not in str(p.get("status", "")) and
                         "OFFLINE" not in str(p.get("status", ""))]

    heuristic_rec = recommend_action(
        game_summary, hand_strength, pot_odds, spr, position, available_actions
    )

    llm = llm_result or {}
    # LLM action overrides heuristic when available; heuristic is the fallback
    recommended_action = llm.get("action") or heuristic_rec

    # Only surface a recommendation when it's actually our turn to act. Otherwise
    # the overlay would show a stale/meaningless action (e.g. right after we raise,
    # while the opponent is deciding). Stats (pot, position, hand strength) still show.
    is_my_turn = game_summary.get("is_your_turn", False)
    if not is_my_turn:
        recommended_action = ""

    # Defensive: never surface an action that isn't actually available right now.
    # (Guards against stale state showing "Check" while facing a bet, etc.)
    if available_actions:
        valid = {a.lower() for a in available_actions}
        if recommended_action and recommended_action.lower() not in valid:
            # Prefer a sensible substitute: call > check > fold among what's offered
            for sub in ("call", "check", "fold"):
                if sub in valid:
                    recommended_action = sub.title()
                    break
        # Never fold when checking is free — covers both the heuristic and the LLM,
        # preflop (checked to you) and postflop (checked to you on any street).
        if recommended_action.lower() == "fold" and "check" in valid:
            recommended_action = "Check"

    # Bet sizing + call amount for the overlay
    action_l = recommended_action.lower() if recommended_action else ""
    to_call = _amount_to_call(game_summary)
    recommended_bet_size = None
    if action_l in ("raise", "bet"):
        if num_community == 0:
            recommended_bet_size = recommend_bet_size(
                game_summary, recommended_action, position, game_summary.get("blinds", [])
            )
        else:
            recommended_bet_size = llm.get("bet_size")
    to_call_amount = round(to_call) if (action_l == "call" and to_call > 0) else None

    return {
        "is_your_turn": game_summary.get("is_your_turn", False),
        "street": _get_street(num_community),
        "hole_cards_display": _format_cards_display(user_cards),
        "starting_hand": starting_hand,
        "hand_strength": hand_strength,
        "best_hand": best_hand,
        "pot_size": _safe_json_float(game_summary.get("pot_size", 0)),
        "pot_odds": pot_odds,
        "position": position,
        "spr": spr,
        "effective_stack": effective_stack,
        "available_actions": available_actions,
        "recommended_action": recommended_action,
        "recommended_bet_size": recommended_bet_size,
        "to_call_amount": to_call_amount,
        "num_players": len(active_players),
        "community_cards_display": _format_cards_display(community_cards),
        "blinds": game_summary.get("blinds", []),
        "you_name": game_summary.get("you_name", ""),
        # LLM fields — empty until LLM responds, then overlay re-broadcasts
        "llm_action_reason": llm.get("action_reason", ""),
        "llm_key_factors": llm.get("key_factors", []),
        "llm_risk_note": llm.get("risk_note", ""),
        "llm_bet_size": llm.get("bet_size"),
    }


def _amount_to_call(game_summary: dict) -> float:
    """
    Chips the local player must add to call. This is the key signal for a NEW
    decision point WITHIN a street: PokerNow keeps each street's bets in the
    players' bet_value (not pot_size) until the street ends, so pot_size alone
    can't tell a check spot apart from a facing-a-bet spot.
    """
    you_name = game_summary.get("you_name")
    my_bet = 0.0
    max_bet = 0.0
    for p in game_summary.get("players", []):
        b = _bet_of(p)
        if p.get("name") == you_name:
            my_bet = b
        if b > max_bet:
            max_bet = b
    return max(0.0, max_bet - my_bet)


def _fetch_llm_explanation(stats: dict, game_summary: dict, action_history: list, cache: dict):
    try:
        cache["result"] = generate_dashboard_explanation(LLM_MODEL, stats, game_summary, action_history)
    except Exception as e:
        print(f"[PAI] LLM thread error: {type(e).__name__}: {e}")
        cache["result"] = {}
    finally:
        cache["pending"] = False  # guarantee we never get stuck "pending"


def _new_hand_state():
    return {
        "preflop": None,
        "flop": None,
        "turn": None,
        "river": None,
    }


def _bet_of(player: dict) -> float:
    try:
        return float(str(player.get("bet") or 0).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _build_action_history(prev: dict, curr: dict, street: str, you_name: str) -> list[str]:
    """
    Diff two consecutive game summaries (from the SAME street) and return any new
    action strings, e.g. 'Flop: Villain bet 12' or 'Preflop: You called 6'.

    PokerNow's per-player bet_value is the amount wagered ON THE CURRENT STREET only
    and resets to 0 when a new street begins. This function must therefore only be
    called when prev and curr are on the same street — the caller resets the action
    baseline at each street change. See main loop.

    Detects: folds, opening bets, raises, and calls. (Checks are inferred separately
    by the caller via turn rotation, since a check leaves bet_value unchanged.)
    """
    if prev is None:
        return []

    prev_players = {p["name"]: p for p in prev.get("players", [])}
    curr_players = {p["name"]: p for p in curr.get("players", [])}

    prev_max = max((_bet_of(p) for p in prev.get("players", [])), default=0.0)

    events = []
    for name, curr_p in curr_players.items():
        prev_p = prev_players.get(name, {})
        label = "You" if name == you_name else name

        curr_status = str(curr_p.get("status", ""))
        prev_status = str(prev_p.get("status", ""))
        if "FOLDED" in curr_status and "FOLDED" not in prev_status:
            events.append(f"{street}: {label} folded")
            continue

        curr_bet = _bet_of(curr_p)
        prev_bet = _bet_of(prev_p)
        if curr_bet <= prev_bet:
            continue  # no new chips committed by this player

        if prev_max == 0:
            events.append(f"{street}: {label} bet {curr_bet:.0f}")
        elif curr_bet > prev_max:
            events.append(f"{street}: {label} raised to {curr_bet:.0f}")
        else:
            events.append(f"{street}: {label} called {curr_bet:.0f}")

    return events


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--allow-insecure-localhost")
    driver = webdriver.Chrome(options=options)

    ws_server = WSServer(port=WS_PORT)
    ws_server.start()

    try:
        client = PokerClient(driver, cookie_path='cookie_file.pkl')
        client.navigate('https://network.pokernow.club/sessions/new')
        input("Please complete the login process in the browser and press Enter once completed to confirm and continue...")
        client.cookie_manager.save_cookies()

        while True:
            gameLink = input("Please enter the link to your PokerNow table: ")
            if not (gameLink.startswith("https://www.pokernow.club/games/") or
                    gameLink.startswith("https://www.pokernow.com/games/")):
                print("Invalid link. Must be a pokernow.club or pokernow.com game URL.")
                continue
            break

        client.navigate(gameLink)
        time.sleep(5)

        inject_overlay(driver)
        print("Overlay injected. Starting game loop. Press Ctrl+C to exit.\n")

        null_output = open(os.devnull, "w")

        # ── Per-session state ────────────────────────────────────────────────
        prev_game_summary = None       # last tick's summary (for diffing)
        prev_street_summary = None     # last tick's summary on the SAME street (action baseline)
        hand_snapshots = _new_hand_state()
        action_history: list[str] = []
        current_street = None          # None until first preflop tick of a hand
        in_hand = False                # True once a hand is underway
        hand_saved = False

        # LLM trigger state — fires once per unique (board, pot) decision spot
        llm_cache = {"result": {}, "pending": False}
        llm_broadcast_sent = False
        last_decision_key = None       # (board, pot) of the last spot we fired on

        while True:
            try:
                with contextlib.redirect_stdout(null_output):
                    raw_game_state = client.game_state_manager.get_game_state()
                player_seats = get_player_seats(driver)
                current_game_summary = get_game_summary(raw_game_state, player_seats)
            except Exception as e:
                print(f"[PAI] Game state error (retrying): {type(e).__name__}: {e}")
                time.sleep(2)
                continue

            try:
                num_community = len(current_game_summary["community_cards"])
                new_street = _get_street(num_community)
                you_name = current_game_summary.get("you_name")
                user_cards = _get_user_cards(current_game_summary)
                available_actions = current_game_summary.get("available_actions", [])
                current_player = current_game_summary.get("current_player")

                # "My turn" detection. The authoritative signal is the player with
                # the .decision-current class (current_player). When we can identify
                # both who must act and who we are, compare them directly — this
                # avoids false positives where action buttons or the .action-signal
                # element linger for a tick AFTER we've already acted (which caused
                # the overlay to re-recommend a raise on our own bet). Only fall back
                # to the noisier signals when identity is unknown.
                if you_name and current_player and current_player != "unknown":
                    is_your_turn = (current_player == you_name)
                else:
                    is_your_turn = (
                        current_game_summary.get("is_your_turn", False)
                        or len(available_actions) > 0
                    )
                current_game_summary["is_your_turn"] = is_your_turn  # normalize for overlay

                # ── New hand detection ──────────────────────────────────────
                # A new hand starts when we're back to 0 community cards AND we
                # were previously in a hand (or just have fresh hole cards we
                # haven't seen). Reset all per-hand state.
                is_new_hand = (
                    num_community == 0
                    and len(user_cards) == 2
                    and (not in_hand or current_street not in (None, "Preflop"))
                )
                if is_new_hand:
                    hand_snapshots = _new_hand_state()
                    action_history = []
                    current_street = "Preflop"
                    in_hand = True
                    hand_saved = False
                    llm_cache = {"result": {}, "pending": False}
                    llm_broadcast_sent = False
                    last_decision_key = None
                    prev_street_summary = None

                state_changed = current_game_summary != prev_game_summary

                if state_changed:
                    clear_console()

                    # ── Street change: reset the action-history baseline ─────
                    # PokerNow resets per-player bet_value at each new street, so
                    # we must not diff bets across a street boundary.
                    street_changed = (new_street != current_street)
                    if street_changed:
                        current_street = new_street
                        prev_street_summary = None

                    # ── Accumulate action history (same-street diff only) ────
                    if prev_street_summary is not None:
                        new_events = _build_action_history(
                            prev_street_summary, current_game_summary, current_street, you_name
                        )
                        action_history.extend(new_events)
                    prev_street_summary = current_game_summary

                    # ── Capture first snapshot of each street ────────────────
                    key = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(num_community)
                    if key and hand_snapshots.get(key) is None:
                        hand_snapshots[key] = current_game_summary

                    # ── Build stats and broadcast to overlay ─────────────────
                    stats = build_stats_payload(current_game_summary, llm_cache["result"])
                    ws_server.broadcast(stats)

                    # Console debug
                    print(f"\n── {current_street} | community={num_community} | "
                          f"your_turn={is_your_turn} | actions={available_actions}")
                    print(f"   Hand: {stats['hole_cards_display']} ({stats['hand_strength']}) | "
                          f"Pos: {stats['position']} | Pot: {stats['pot_size']} | "
                          f"PotOdds: {stats['pot_odds']}% | SPR: {stats['spr']}")
                    if action_history:
                        print(f"   History: {action_history}")
                    if is_your_turn:
                        print(f"   >>> YOUR TURN — heuristic says: {stats['recommended_action']}")

                    prev_game_summary = current_game_summary

                # ── LLM trigger: postflop, when it's your turn at a NEW spot ─
                # A "spot" is identified by (board, amount-to-call). Using
                # amount-to-call (not pot) is what lets a fresh check spot be told
                # apart from facing a bet/raise on the SAME board — PokerNow doesn't
                # sweep bets into the pot until the street ends. This re-fires on
                # every street AND every bet/raise you face. Preflop uses the GTO table.
                is_postflop = num_community >= 3
                to_call = _amount_to_call(current_game_summary)
                decision_key = (
                    tuple(current_game_summary.get("community_cards", [])),
                    round(to_call, 2),
                )
                new_spot = decision_key != last_decision_key
                if is_your_turn and is_postflop and new_spot and not llm_cache["pending"]:
                    last_decision_key = decision_key
                    llm_cache["pending"] = True
                    llm_cache["result"] = {}
                    llm_broadcast_sent = False
                    fresh_stats = build_stats_payload(current_game_summary, {})
                    print(f"[PAI] 🔥 Firing LLM ({LLM_MODEL}) for {current_street} "
                          f"decision (to_call={to_call:.0f})...")
                    threading.Thread(
                        target=_fetch_llm_explanation,
                        args=(fresh_stats, current_game_summary, list(action_history), llm_cache),
                        daemon=True,
                    ).start()
                elif (is_your_turn and is_postflop and not new_spot
                      and not llm_cache["pending"] and not llm_cache["result"]):
                    # Your turn, postflop, same spot as before, not pending, and no
                    # result — means the LLM call errored. Surface it for the demo.
                    print(f"[PAI] ⚠ your turn ({current_street}, to_call={to_call:.0f}) "
                          f"but LLM returned no result (check earlier [PAI] LLM error)")

                # ── Push LLM result to overlay once it arrives ───────────────
                if (not llm_broadcast_sent
                        and not llm_cache["pending"]
                        and llm_cache["result"]):
                    stats = build_stats_payload(current_game_summary, llm_cache["result"])
                    ws_server.broadcast(stats)
                    llm_broadcast_sent = True
                    print(f"[PAI] LLM decision broadcast: {llm_cache['result'].get('action')}")

                # ── Round-over summary (once) ────────────────────────────────
                if current_game_summary.get("winners") and not hand_saved:
                    hand_saved = True
                    in_hand = False
                    print("\n=== Round Over ===")
                    for label, snap in [
                        ("Preflop", hand_snapshots["preflop"]),
                        ("Flop",    hand_snapshots["flop"]),
                        ("Turn",    hand_snapshots["turn"]),
                        ("River",   hand_snapshots["river"]),
                    ]:
                        print(f"\n{label}:")
                        print(json.dumps(snap, indent=2) if snap else "N/A")

            except Exception as e:
                print(f"[PAI] Loop error (continuing): {type(e).__name__}: {e}")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nExited by user.")
    finally:
        null_output.close()
        ws_server.stop()
        driver.quit()


if __name__ == "__main__":
    main()
