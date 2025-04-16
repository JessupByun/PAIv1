import LLM_deployment
import hand_strength
import pot_odds
import eval_best_hand

#Testing dictionary
sample_summary = {
    "game_type": "No Limit Texas Hold'em",
    "pot_size": "70",
    "community_cards": ["2 of Spades", "3 of Spades", "Ace of Spades"],
    "players": [
        {
            "name": "jessup",
            "stack": "1000",
            "bet": "20",
            "cards": ["8 of Spades", "9 of Spades"],
            "status": "PlayerState.CURRENT",
            "hand_message": ""
        },
        {
            "name": "daniel",
            "stack": "900",
            "bet": "50",
            "cards": ["Unknown Card", "Unknown Card"],
            "status": "PlayerState.ACTIVE",
            "hand_message": ""
        }
    ],
    "dealer_position": "1",
    "current_player": "jessup",
    "blinds": ["10", "20"],
    "winners": [],
    "is_your_turn": True
}

# Example usage to get hand_strength

print(hand_strength.evaluate_starting_hand_strength(sample_summary))

# Example usage to get pot-odds strategy

print(pot_odds.calculate_pot_odds(sample_summary))

# Example usage to get your hand classification

print(eval_best_hand.evaluate_best_hand(sample_summary))

# Example usage to to deploy LLM for explanations
def run_llm_deployment():
    model_name = "llama-3.3-70b-versatile"
    game_summary = sample_summary
    recommended_decision = "Open raise to 10 BB"
    print(f"Generating data with {model_name}...")
    response = LLM_deployment.generate_response(model_name, game_summary, recommended_decision)
    print(f"Generated response for {model_name}:\n{response}\n")

run_llm_deployment()

# Example usage to get preflop strategy

