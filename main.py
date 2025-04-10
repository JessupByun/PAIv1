import os
import sys
import time
import contextlib
from selenium import webdriver
from PokerNow import PokerClient

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_state_summary(game_state):
    players_summary = [
        f"{p.name}-{p.stack}-{p.bet_value}-{p.status}-{p.hand_message}" 
        for p in game_state.players
    ]
    summary = (
        f"Game Type: {game_state.game_type}\n"
        f"Pot Size: {game_state.pot_size}\n"
        f"Community Cards: {[str(card) for card in game_state.community_cards]}\n"
        f"Dealer Position: {game_state.dealer_position}\n"
        f"Current Player: {game_state.current_player}\n"
        f"Blinds: {game_state.blinds}\n"
        f"Winners: {game_state.winners}\n"
        f"Players: {players_summary}\n"
        f"Is Your Turn: {game_state.is_your_turn}"
    )
    return summary

def main():
    driver = webdriver.Chrome()

    try:
        client = PokerClient(driver, cookie_path='cookie_file.pkl')
        client.navigate('https://network.pokernow.club/sessions/new')
        input("Please complete the login process in the browser and press Enter to continue...")
        client.cookie_manager.save_cookies()

        while True:
            gameLink = input("Please enter the link to your PokerNow table: ")
            if not gameLink.startswith("https://www.pokernow.club/games/"):
                print("Invalid link.")
                continue
            if len(gameLink) != 57:
                print("Invalid link.")
                continue
            break

        client.navigate(gameLink)
        time.sleep(5)

        print("Starting game loop. Press Ctrl+C to exit.\n")

        prev_state_summary = ""
        null_output = open(os.devnull, "w")

        while True:
            # Silence internal print statements
            with contextlib.redirect_stdout(null_output):
                game_state = client.game_state_manager.get_game_state()
                curr_state_summary = get_state_summary(game_state)

            if curr_state_summary != prev_state_summary:
                clear_console()
                print(curr_state_summary)
                prev_state_summary = curr_state_summary

            time.sleep(2)  # check every 2 seconds

    except KeyboardInterrupt:
        print("\nExited by user.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()