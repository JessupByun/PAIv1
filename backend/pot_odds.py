def calculate_pot_odds(game_summary):
    try:
        pot_size = float(game_summary.get("pot_size", 0))
        current_player_name = game_summary.get("current_player")
        players = game_summary.get("players", [])

        current_bet = 0
        all_bets = []

        for player in players:
            raw_bet = player.get("bet", 0)
            bet = float(str(raw_bet).strip() or 0)
            all_bets.append(bet)
            if player.get("name") == current_player_name:
                current_bet = bet

        # Get the highest bet made by any player
        max_bet = max(all_bets)

        # The call amount is the difference between max bet and the current player's bet
        call_amt = max(0, max_bet - current_bet)

        total_pot = pot_size + call_amt

        if total_pot == 0:
            return 0.0

        pot_odds = (call_amt / total_pot) * 100
        return round(pot_odds, 2)

    except Exception as e:
        print(f"Error calculating pot odds: {e}")
        return None
