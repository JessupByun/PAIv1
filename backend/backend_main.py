import LLM_deployment

#Testing dictionary
sample_summary = {
    "game_type": "No Limit Texas Hold'em",
    "pot_size": "50",
    "community_cards": ["9 of Diamonds", "2 of Clubs", "K of Hearts"],
    "players": [
        {
            "name": "jessup",
            "stack": "1000",
            "bet": "20",
            "cards": ["Ace of Spades", "King of Clubs"],
            "status": "PlayerState.CURRENT",
            "hand_message": ""
        },
        {
            "name": "daniel",
            "stack": "900",
            "bet": "30",
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

# Main function to get hand_strength



# Main function to get preflop strategy




# Main function to deploy LLM
def run_llm_deployment():
    model_name = "llama-3.3-70b-versatile"
    game_summary = sample_summary
    recommended_decision = "Open raise to 10 BB"
    print(f"Generating data with {model_name}...")
    response = LLM_deployment.generate_response(model_name, game_summary, recommended_decision)
    print(f"Generated response for {model_name}:\n{response}\n")

print(run_llm_deployment())