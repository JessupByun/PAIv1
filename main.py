import os
import sys
import time
import json
import contextlib
from selenium import webdriver
from PokerNow import PokerClient

from backend.hand_strength import evaluate_starting_hand_strength

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_game_summary(game_state):
    summary = {
        "game_type": game_state.game_type,
        "pot_size": game_state.pot_size,
        "community_cards": [str(card) for card in game_state.community_cards],
        "players": [],
        "dealer_position": game_state.dealer_position,
        "current_player": game_state.current_player,
        "blinds": game_state.blinds,
        "winners": [],
        "is_your_turn": game_state.is_your_turn
    }
    for player in game_state.players:
        summary["players"].append({
            "name": player.name,
            "stack": player.stack,
            "bet": player.bet_value,
            "cards": [str(card) for card in player.cards],
            "status": str(player.status),
            "hand_message": player.hand_message
        })
    for winner in game_state.winners:
        summary["winners"].append({
            "name": winner["name"],
            "stack_info": winner["stack_info"]
        })
    return summary

def main():
    driver = webdriver.Chrome()

    try:
        client = PokerClient(driver, cookie_path='cookie_file.pkl')
        client.navigate('https://network.pokernow.club/sessions/new')
        input("Please complete the login process in the browser and press Enter once completed to confirm and continue...")
        client.cookie_manager.save_cookies()

        while True:
            gameLink = input("Please enter the link to your PokerNow table: ")
            if not gameLink.startswith("https://www.pokernow.club/games/"):
                print("Invalid link. Try again")
                continue
            if len(gameLink) != 57:
                print("Invalid link. Try again")
                continue
            break

        client.navigate(gameLink)
        time.sleep(5)

        # Commenting out frontend-related code for now
        # driver.get("http://localhost:3000")

        print("Starting game loop. Press Ctrl+C to exit.\n")
        null_output = open(os.devnull, "w")

        preflop_game_summary = None
        flop_game_summary = None
        turn_game_summary = None
        river_game_summary = None
        prev_game_summary = None

        while True:
            # Silence internal print statements
            with contextlib.redirect_stdout(null_output):
                try:
                    raw_game_state = client.game_state_manager.get_game_state()
                except Exception as e:
                    print("Selenium session browser appears to be closed or exited or crashed:", e)
                    break  # Exit gracefully if session fails
                current_game_summary = get_game_summary(raw_game_state)

            # Commenting out frontend-related code for now
            # driver.execute_script(
            #     "window.latestGameState = arguments[0];",
            #     current_game_summary
            # )

            if current_game_summary != prev_game_summary:
                clear_console()
                print(json.dumps(current_game_summary, indent=2))

                strength = evaluate_starting_hand_strength(current_game_summary)
                print("Starting Hand Strength:", strength)

                num_community = len(current_game_summary["community_cards"])
                if num_community == 0 and preflop_game_summary is None:
                    preflop_game_summary = current_game_summary
                elif num_community == 3 and flop_game_summary is None:
                    flop_game_summary = current_game_summary
                elif num_community == 4 and turn_game_summary is None:
                    turn_game_summary = current_game_summary
                elif num_community == 5 and river_game_summary is None:
                    river_game_summary = current_game_summary

                prev_game_summary = current_game_summary

            if len(current_game_summary["winners"]) > 0:
                print("\nRound Over! Summaries for each stage:")
                print("\nPreflop Stage:")
                print(json.dumps(preflop_game_summary, indent=2) if preflop_game_summary else "N/A")
                print("\nFlop Stage:")
                print(json.dumps(flop_game_summary, indent=2) if flop_game_summary else "N/A")
                print("\nTurn Stage:")
                print(json.dumps(turn_game_summary, indent=2) if turn_game_summary else "N/A")
                print("\nRiver Stage:")
                print(json.dumps(river_game_summary, indent=2) if river_game_summary else "N/A")

                preflop_game_summary = None
                flop_game_summary = None
                turn_game_summary = None
                river_game_summary = None

            time.sleep(2)  # check every 2 seconds

    except KeyboardInterrupt:
        print("\nExited by user.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()