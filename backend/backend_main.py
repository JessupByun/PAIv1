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

# 1. Example usage to get hand_strength

print(hand_strength.evaluate_starting_hand_strength(sample_summary))

# 2. Example usage to get pot-odds strategy

print(pot_odds.calculate_pot_odds(sample_summary))

# 3. Example usage to get your hand classification

print(eval_best_hand.evaluate_best_hand(sample_summary))

# 4. Example usage to to deploy LLM for explanations
def run_llm_deployment():
    model_name = "llama-3.3-70b-versatile"
    game_summary = sample_summary
    recommended_decision = "Open raise to 10 BB"
    print(f"Generating data with {model_name}...")
    response = LLM_deployment.generate_response(model_name, game_summary, recommended_decision)
    print(f"Generated response for {model_name}:\n{response}\n")

run_llm_deployment()

# 5. Example usage to get preflop strategy

# 6. Example usage to get preflop strategy

# 7. Example usage to get equity calculation

# 8. Example usage to estimate opponent ranges

# 9. Example usage to get player profiling (VPIP (voluntarily put money in pot), PFR (pre-flop raise), AF (agression factor))

# 10. Hand replayer 

"""
    Potential Features	                        Why it matters
Decision Confidence Scoring	    Help users interpret recommendations
Session Summary Stats	        Show win/loss rate, best hands, total EV gained
Bluff Catching Helper	        Use logic like: missed draws, overbets, opponent profile
LLM Explainer Mode	            Option to get detailed reasoning for each decision
GTO Deviation Visualizer	    Highlight how your play compares to GTO baseline
"""

class PokerDecisionEngine:
    def __init__(self):
        # Reference functions through their module names
        self.hand_strength_evaluator = hand_strength.evaluate_starting_hand_strength
        self.best_hand_evaluator = eval_best_hand.evaluate_best_hand
        self.pot_odds_calculator = pot_odds.calculate_pot_odds
        self.llm_generator = LLM_deployment.generate_response
        self.pluribus = PluribusIntegration()
        
    def make_decision(self, game_state):
        # Combine all factors
        hand_strength = self.hand_strength_evaluator(game_state)
        pot_odds = self.pot_odds_calculator(game_state)
        best_hand = self.best_hand_evaluator(game_state)
        
        # Get decision from Pluribus
        pluribus_decision = self.pluribus.get_decision(game_state)
        
        # Get explanation from LLM
        explanation = self.llm_generator(
            "llama-3.3-70b-versatile",
            game_state, 
            pluribus_decision["action"]
        )
        
        return {
            'decision': pluribus_decision["action"],
            'confidence': pluribus_decision["confidence"],
            'explanation': explanation,
            'metrics': {
                'hand_strength': hand_strength,
                'pot_odds': pot_odds,
                'best_hand': best_hand
            }
        }


