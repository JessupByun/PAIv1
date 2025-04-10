import os
import pickle
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from .models import Card, GameState, PlayerInfo, PlayerState

class CookieManager:
    def __init__(self, driver, cookie_path):
        self.driver = driver
        self.cookie_path = cookie_path

    def load_cookies(self):
        print("Entering load_cookies()") # Debug print
        if os.path.exists(self.cookie_path):
            print(f"Loading cookies from {self.cookie_path}") # Debug print
            cookies = pickle.load(open(self.cookie_path, 'rb'))
            current_url = self.driver.current_url
            for cookie in cookies:
                if cookie.get('domain', '') in current_url:
                    print(f"Adding cookie: {cookie}") # Debug print
                    self.driver.add_cookie(cookie)
        else:
            print(f"Cookie file {self.cookie_path} not found, saving new cookies") # Debug print
            self.save_cookies()
        print("Leaving load_cookies()") # Debug print

    def save_cookies(self):
        print("Entering save_cookies()") # Debug print
        pickle.dump(self.driver.get_cookies(), open(self.cookie_path, 'wb'))
        print("Leaving save_cookies()") # Debug print

class GameStateManager:
    def __init__(self, element_helper):
        self.element_helper = element_helper

    def get_game_state(self):
        print("Entering get_game_state()") # Debug print
        game_state = GameState(
            game_type=self.element_helper.get_text('.table-game-type'),
            pot_size=self.parse_stack_value(self.element_helper.get_text('.table-pot-size .main-value')),
            community_cards=self.get_community_cards(),
            players=self.get_players_info(),
            dealer_position=self.get_dealer_position(),
            current_player=self.get_current_player(),
            blinds=self.get_blinds(),
            winners=self.get_winners(),
            is_your_turn=self.is_your_turn(),
            available_actions=self.get_available_actions()
        )
        print("Leaving get_game_state()") # Debug print
        return game_state

    def is_your_turn(self):
        print("Entering is_your_turn()") # Debug print
        try:
            action_signal = self.element_helper.get_element('.action-signal')
            if action_signal and action_signal.text:
                is_your_turn = action_signal.text.strip() == 'Your Turn'
                print(f"is_your_turn: {is_your_turn}") # Debug print
                return is_your_turn
            else:
                print("is_your_turn: False") # Debug print
                return False
        except NoSuchElementException:
            print("is_your_turn: False (NoSuchElementException)") # Debug print
            return False
        finally:
            print("Leaving is_your_turn()") # Debug print

    def get_winners(self):
        print("Entering get_winners()") # Debug print
        winners = []
        try:
            winner_elements = self.element_helper.get_elements('.table-player.winner')
            print(f"Found {len(winner_elements)} winner elements") # Debug print
            for winner_element in winner_elements:
                # Extract the winner's name
                name = self.element_helper.get_text('.table-player-name a', winner_element)
                
                # Extract the stack value which might include winnings
                stack_value = self.parse_stack_value(self.element_helper.get_text('.table-player-stack .chips-value', winner_element))
                
                # Extract the winnings, if there are any
                prize = self.parse_stack_value(self.element_helper.get_text('.table-player-stack-prize .chips-value', winner_element))
                stack_with_prize = f"{stack_value} (+{prize})" if prize else stack_value
                
                # Add the winner's information to the list
                winner_info = {'name': name, 'stack_info': stack_with_prize}
                print(f"Winner: {winner_info}") # Debug print
                winners.append(winner_info)
        except Exception as e:
            print(f"Error getting winners: {e}") # Debug print
        print("Leaving get_winners()") # Debug print
        return winners

    def get_community_cards(self):
        print("Entering get_community_cards()") # Debug print
        card_elements = self.element_helper.get_elements('.table-cards .card-container')
        print(f"Found {len(card_elements)} card elements") # Debug print
        community_cards = [Card.parse_card_class(card.get_attribute('class')) for card in card_elements]
        print(f"Community cards: {community_cards}") # Debug print
        print("Leaving get_community_cards()") # Debug print
        return community_cards

    def get_players_info(self):
        print("Entering get_players_info()")  # Debug print
        players = []
        for player_element in self.element_helper.get_elements('.table-player'):
            hand_message = self.element_helper.get_text('.player-hand-message .name', player_element)

            stack_element = self.element_helper.get_element('.table-player-stack', player_element)
            is_all_in = 'All In' in stack_element.text if stack_element and stack_element.text else False

            name = self.element_helper.get_text('.table-player-name a', player_element)
            stack_value = self.element_helper.get_text('.table-player-stack .chips-value', player_element)
            bet_value = self.element_helper.get_text('.table-player-bet-value .chips-value', player_element)

            player_info = PlayerInfo(
                name=name,
                stack=self.parse_stack_value(stack_value) if not is_all_in else 'All In',
                bet_value=self.parse_stack_value(bet_value),
                cards=self.get_player_cards(player_element),
                status=self.get_player_status(player_element),
                hand_message=hand_message
            )
            print(f"Player info: {player_info}")  # Debug print
            players.append(player_info)
        print("Leaving get_players_info()")  # Debug print
        return players

    def get_player_status(self, player_element):
        print("Entering get_player_status()") # Debug print
        class_list = player_element.get_attribute('class').split()
        if 'decision-current' in class_list:
            status = PlayerState.CURRENT
        elif 'fold' in class_list:
            status = PlayerState.FOLDED
        elif 'offline' in class_list:
            status = PlayerState.OFFLINE
        else:
            status = PlayerState.ACTIVE
        print(f"Player status: {status}") # Debug print
        print("Leaving get_player_status()") # Debug print
        return status

    def get_player_cards(self, player_element):
        print("Entering get_player_cards()") # Debug print
        card_elements = player_element.find_elements(By.CSS_SELECTOR, '.table-player-cards .card-container')
        print(f"Found {len(card_elements)} card elements for player") # Debug print
        player_cards = [Card.parse_card_class(card.get_attribute('class')) for card in card_elements]
        print(f"Player cards: {player_cards}") # Debug print
        print("Leaving get_player_cards()") # Debug print
        return player_cards

    def get_dealer_position(self):
        print("Entering get_dealer_position()") # Debug print
        dealer_button = self.element_helper.get_element('.dealer-button-ctn')
        if dealer_button:
            dealer_position = dealer_button.get_attribute('class').split('-')[-1]
            print(f"Dealer position: {dealer_position}") # Debug print
        else:
            dealer_position = 'unknown'
            print("Dealer position: unknown") # Debug print
        print("Leaving get_dealer_position()") # Debug print
        return dealer_position

    def get_current_player(self):
        print("Entering get_current_player()") # Debug print
        current_player_element = self.element_helper.get_element('.table-player.decision-current')
        if current_player_element:
            current_player = self.element_helper.get_text('.table-player-name a', current_player_element)
            print(f"Current player: {current_player}") # Debug print
        else:
            current_player = 'unknown'
            print("Current player: unknown") # Debug print
        print("Leaving get_current_player()") # Debug print
        return current_player

    def get_blinds(self):
        print("Entering get_blinds()") # Debug print
        blind_values = self.element_helper.get_elements('.blind-value-ctn .chips-value')
        print(f"Found {len(blind_values)} blind value elements") # Debug print
        blinds = [self.parse_stack_value(blind.text) for blind in blind_values]
        print(f"Blinds: {blinds}") # Debug print
        print("Leaving get_blinds()") # Debug print
        return blinds

    def parse_stack_value(self, stack_value):
        print(f"Parsing stack value: {stack_value}") # Debug print
        if '+' in stack_value:
            stack_value = stack_value.split('+')[0]
        parsed_value = stack_value.strip()
        print(f"Parsed stack value: {parsed_value}") # Debug print
        return parsed_value

    def get_available_actions(self):
        print("Entering get_available_actions()") # Debug print
        available_actions = {}
        action_elements = self.element_helper.get_elements('.game-decisions-ctn .button-1')
        for element in action_elements:
            action_text = element.text.strip().lower()
            if action_text in ['fold', 'call', 'raise', 'check']:
                available_actions[action_text] = element
        print(f"Available actions: {available_actions}") # Debug print
        print("Leaving get_available_actions()") # Debug print
        return available_actions

class ActionHelper:
    def __init__(self, element_helper):
        self.element_helper = element_helper

    def get_available_actions(self):
        print("Entering get_available_actions()") # Debug print
        available_actions = {}
        action_elements = self.element_helper.get_elements('.game-decisions-ctn .button-1')
        for element in action_elements:
            action_text = element.text.strip().lower()
            if action_text in ['fold', 'call', 'raise', 'check']:
                available_actions[action_text] = element
        print("Leaving get_available_actions()") # Debug print
        return available_actions

    def perform_action(self, action, amount=None):
        print(f"Entering perform_action({action}, {amount})") # Debug print
        available_actions = self.get_available_actions()
        if action == 'Raise' and available_actions.get('Raise'):
            self.handle_raise(amount)
        elif action in available_actions:
            print(f"Performing action: {action}") # Debug print
            available_actions[action].click()
            if action == 'Fold':
                self.check_and_handle_fold_confirmation()
        else:
            print(f"Action {action} not available.") # Debug print
        print("Leaving perform_action()") # Debug print

    def handle_raise(self, amount):
        print(f"Entering handle_raise({amount})") # Debug print
        raise_button = self.element_helper.get_element('.game-decisions-ctn .button-1.raise')
        if raise_button:
            print("Clicking raise button") # Debug print
            raise_button.click()
            time.sleep(.25)
            raise_input = self.element_helper.get_element('.raise-controller-form .value-input-ctn .value')
            if raise_input:
                print("Clearing and entering raise amount") # Debug print
                raise_input.clear()
                raise_input.send_keys(str(amount))
            confirm_button = self.element_helper.get_element('.raise-controller-form .bet')
            if confirm_button:
                print("Clicking confirm button") # Debug print
                confirm_button.click()
        print("Leaving handle_raise()") # Debug print

    def check_and_handle_fold_confirmation(self):
        print("Entering check_and_handle_fold_confirmation()") # Debug print
        try:
            confirm_button = self.element_helper.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.alert-1-buttons button.middle-gray')))
            print("Clicking fold confirmation button") # Debug print
            confirm_button.click()
        except Exception as e:
            print(f"Error: {e}") # Debug print
        print("Leaving check_and_handle_fold_confirmation()") # Debug print

class ElementHelper:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def wait_for_element(self, selector, timeout=10):
        try:
            print(f"Waiting for element with selector: {selector}") # Debug print
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            print(f"Found element with selector: {selector}") # Debug print
            return True
        except TimeoutException:
            print(f"Element {selector} not found within {timeout} seconds") # Debug print
            return False

    def is_element_present(self, selector):
        try:
            print(f"Checking if element with selector '{selector}' is present") # Debug print
            self.driver.find_element(By.CSS_SELECTOR, selector)
            print(f"Element with selector '{selector}' is present") # Debug print
            return True
        except NoSuchElementException:
            print(f"Element with selector '{selector}' is not present") # Debug print
            return False

    def get_text(self, selector, context=None):
        try:
            if context:
                print(f"Getting text from element with selector '{selector}' in context") # Debug print
                element = context.find_element(By.CSS_SELECTOR, selector)
            else:
                print(f"Getting text from element with selector '{selector}' in driver") # Debug print
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
            text = element.text.strip()
            print(f"Text obtained: '{text}'") # Debug print
            return text
        except NoSuchElementException:
            print(f"Element with selector '{selector}' not found") # Debug print
            return ""

    def get_element(self, selector, context=None):
        try:
            print(f"Trying to find element with selector: {selector}") # Debug print
            if context:
                print(f"Finding element in context: {context}") # Debug print
                element = context.find_element(By.CSS_SELECTOR, selector)
            else:
                print(f"Finding element in driver") # Debug print
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
            print(f"Found element with selector: {selector}") # Debug print
            return element
        except NoSuchElementException:
            print(f"Element with selector '{selector}' not found.") # Debug print
            return None
        except Exception as e:
            print(f"An error occurred while trying to find element with selector '{selector}':") # Debug print
            traceback.print_exc()
            return None

    def get_elements(self, selector):
        try:
            print(f"Trying to find elements with selector: {selector}") # Debug print
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"Found {len(elements)} elements with selector: {selector}") # Debug print
            return elements
        except NoSuchElementException:
            print(f"No elements found with selector '{selector}'") # Debug print
            return []