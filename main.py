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
from backend.heuristics import calculate_position, calculate_spr, calculate_effective_stack, recommend_action
from backend.ws_server import WSServer
from backend.LLM_deployment import generate_dashboard_explanation

LLM_MODEL = "llama-3.3-70b-versatile"
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
        "num_players": len(active_players),
        "community_cards_display": _format_cards_display(community_cards),
        "blinds": game_summary.get("blinds", []),
        "you_name": game_summary.get("you_name", ""),
        # LLM fields — empty until LLM responds, then overlay re-broadcasts
        "llm_action_reason": llm.get("action_reason", ""),
        "llm_key_factors": llm.get("key_factors", []),
        "llm_risk_note": llm.get("risk_note", ""),
    }


def _fetch_llm_explanation(stats: dict, game_summary: dict, action_history: list, cache: dict):
    result = generate_dashboard_explanation(LLM_MODEL, stats, game_summary, action_history)
    cache["result"] = result
    cache["pending"] = False


def _new_hand_state():
    return {
        "preflop": None,
        "flop": None,
        "turn": None,
        "river": None,
    }


def _build_action_history(prev: dict, curr: dict, street: str, you_name: str) -> list[str]:
    """
    Compare previous and current game summaries to detect all actions that occurred.
    Returns a list of action strings (may be empty). Each entry is a full sentence
    like 'Flop: Alice raised to 60' or 'Preflop: You called 20'.

    Detects: folds, bets/raises (bet increased), calls (bet matched villain's bet),
    and checks (turn passed with no bet change when current player changed).
    """
    if prev is None:
        return []

    prev_players = {p["name"]: p for p in prev.get("players", [])}
    curr_players = {p["name"]: p for p in curr.get("players", [])}

    # Max bet on the table this tick (used to distinguish call vs. check)
    curr_bets = [float(str(p.get("bet") or 0)) for p in curr.get("players", [])]
    max_curr_bet = max(curr_bets) if curr_bets else 0

    events = []
    for name, curr_p in curr_players.items():
        prev_p = prev_players.get(name, {})
        label = "You" if name == you_name else name

        try:
            curr_bet = float(str(curr_p.get("bet") or 0))
            prev_bet = float(str(prev_p.get("bet") or 0))
        except (ValueError, TypeError):
            curr_bet = prev_bet = 0

        curr_status = str(curr_p.get("status", ""))
        prev_status = str(prev_p.get("status", ""))

        # Fold
        if "FOLDED" in curr_status and "FOLDED" not in prev_status:
            events.append(f"{street}: {label} folded")
            continue

        bet_delta = curr_bet - prev_bet
        if bet_delta <= 0:
            continue

        # Bet increased — distinguish raise vs. call vs. open
        prev_max_bets = [float(str(p.get("bet") or 0)) for p in prev.get("players", [])]
        prev_max_bet = max(prev_max_bets) if prev_max_bets else 0

        if prev_bet == 0 and prev_max_bet == 0:
            # Opening bet / raise from nothing
            events.append(f"{street}: {label} bet {curr_bet}")
        elif curr_bet > prev_max_bet:
            # Raised above the table's prior max bet
            events.append(f"{street}: {label} raised to {curr_bet}")
        else:
            # Matched the prior max bet — it's a call
            events.append(f"{street}: {label} called {bet_delta:.0f}")

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

        prev_game_summary = None
        hand_snapshots = _new_hand_state()
        hand_saved = False

        llm_cache = {"result": {}, "pending": False}
        last_turn_hash = None
        llm_broadcast_sent = False
        action_history: list[str] = []
        current_street = "Preflop"

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
                state_changed = current_game_summary != prev_game_summary

                if state_changed:
                    clear_console()
                    num_community = len(current_game_summary["community_cards"])
                    new_street = _get_street(num_community)
                    you_name = current_game_summary.get("you_name")

                    # Reset per-hand state on new hand
                    if num_community == 0 and hand_snapshots["preflop"] is None:
                        hand_snapshots = _new_hand_state()
                        llm_cache = {"result": {}, "pending": False}
                        last_turn_hash = None
                        hand_saved = False
                        llm_broadcast_sent = False
                        action_history = []
                        current_street = "Preflop"

                    # Track action history: detect bets/folds/calls between ticks
                    if prev_game_summary is not None:
                        new_events = _build_action_history(prev_game_summary, current_game_summary, current_street, you_name)
                        action_history.extend(new_events)

                    # Update current street tracker
                    current_street = new_street

                    # Capture first snapshot of each street
                    if num_community == 0 and hand_snapshots["preflop"] is None:
                        hand_snapshots["preflop"] = current_game_summary
                    elif num_community == 3 and hand_snapshots["flop"] is None:
                        hand_snapshots["flop"] = current_game_summary
                    elif num_community == 4 and hand_snapshots["turn"] is None:
                        hand_snapshots["turn"] = current_game_summary
                    elif num_community == 5 and hand_snapshots["river"] is None:
                        hand_snapshots["river"] = current_game_summary

                    # Build stats and broadcast
                    stats = build_stats_payload(current_game_summary, llm_cache["result"])
                    ws_server.broadcast(stats)
                    llm_broadcast_sent = False

                    # Fire LLM only on postflop streets when it's our turn
                    # Preflop uses the GTO lookup table (heuristic) instead
                    is_postflop = num_community >= 3
                    if current_game_summary.get("is_your_turn") and is_postflop:
                        user_cards = _get_user_cards(current_game_summary)
                        community = current_game_summary.get("community_cards", [])
                        turn_hash = hash((tuple(user_cards), tuple(community)))
                        if turn_hash != last_turn_hash and not llm_cache["pending"]:
                            last_turn_hash = turn_hash
                            llm_cache["pending"] = True
                            llm_cache["result"] = {}
                            llm_broadcast_sent = False
                            threading.Thread(
                                target=_fetch_llm_explanation,
                                args=(stats, current_game_summary, list(action_history), llm_cache),
                                daemon=True,
                            ).start()

                    # Console debug
                    print(json.dumps(current_game_summary, indent=2))
                    print("Starting Hand Strength:", stats["hand_strength"])
                    if current_game_summary.get("is_your_turn"):
                        print(f"[YOUR TURN] Rec: {stats['recommended_action']} | "
                              f"Pos: {stats['position']} | "
                              f"PotOdds: {stats['pot_odds']}% | "
                              f"SPR: {stats['spr']}")

                    prev_game_summary = current_game_summary

                # Push LLM result to overlay exactly once after it arrives
                elif (not llm_broadcast_sent
                      and not llm_cache["pending"]
                      and llm_cache["result"]):
                    stats = build_stats_payload(current_game_summary, llm_cache["result"])
                    ws_server.broadcast(stats)
                    llm_broadcast_sent = True

                # Print round summary once when winners are decided
                if current_game_summary.get("winners") and not hand_saved:
                    hand_saved = True
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
