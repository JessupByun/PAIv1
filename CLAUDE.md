# PAIv1 - Claude Code Project Guide

> **PAIv1** is a real-time poker assistant that scrapes live game state from PokerNow via Selenium, runs GTO-based analysis, and surfaces decisions through a floating browser overlay powered by an LLM.

---

## Quick Commands

```bash
pytest                                    # full suite; integration tests are deselected by default
pytest -m integration                     # live Groq call (needs GROQ_API_KEY)
python main.py                            # start the app
```

**Environment:** `cp .env.example .env` then add `GROQ_API_KEY=your_key`
**WS port:** `8765` default, override with `PAI_WS_PORT`
**Verbose LLM logging:** `PAI_DEBUG=1`

---

## Architecture at a Glance

```
PokerNow browser tab
    └─ Selenium DOM poll (every 2s, local, zero network cost)
           │
           ▼
    main.py game loop
       ├─ get_player_seats()      JS → seat numbers + local player identity
       ├─ get_game_summary()      raw GameState → clean serializable dict
       ├─ build_stats_payload()
       │     ├─ util.py           safe_float / chips / local_player / amount_to_call
       │     ├─ hand_strength.py  Sklansky & Malmuth tier (Premium/Strong/Medium/Playable/Trash)
       │     ├─ eval_best_hand.py best 5-card hand via treys
       │     ├─ pot_odds.py       pot odds %
       │     ├─ preflop_table.py  GTO lookup: 169 hands x 5 positions → Raise/Call/Fold
       │     └─ heuristics.py     position, SPR, effective stack, fallback recommendation
       ├─ WSServer.broadcast()    JSON payload → overlay
       └─ LLM thread (postflop)   Groq API → {action, bet_size, reason, key_factors, risk_note}
              └─ WSServer.broadcast()   second push once LLM result arrives

WSServer localhost:8765
    └─ WebSocket → content.js (injected into PokerNow tab by Selenium)
           └─ Floating overlay panel rendered in-browser
```

**Decision split:**

| Street | Who decides |
|--------|-------------|
| Preflop | GTO lookup table, instant and deterministic |
| Flop / Turn / River | LLM (`openai/gpt-oss-120b` via Groq), sees full hand context |

---

## Persistent Development Rules

These rules apply to every session.
Claude must follow them without being reminded.

### Never break the test suite
- Run `pytest` before reporting any task complete.
- Every new module gets a corresponding test file in `tests/`.
- Tests must cover both happy path and edge cases (empty input, "All In" strings, zero division).
- Current count: **87 tests passing** across 9 files, plus 1 opt-in integration test.

### Never parse DOM values by hand
- Everything numeric off the PokerNow DOM arrives as a string and is not always a number.
  A stack reads `"All In"` once a player is committed, bets can be blank or comma-grouped.
- Use `safe_float()` from `backend/util.py`.
  It returns `None` for anything unparseable, and callers must handle `None` explicitly.
- Use `chips()` for bet amounts, where "not a number" means "nothing wagered" and 0.0 is correct.
- Never call `float()` on these fields directly, and never re-implement the parsing locally.

### Player identity comes from the DOM, not cards
- The `you-player` CSS class on a `.table-player` element identifies the local player.
  This is captured in JS by `get_player_seats()` in `main.py` and stored as `game_summary["you_name"]`.
- Resolve the local player through `util.local_player()` / `util.hole_cards()`, never by scanning for
  the first player with visible cards.
  That heuristic breaks at showdown, when PokerNow flips the opponents' hands and the first match can
  be an opponent.
- `local_player()` falls back to the single player showing cards, and deliberately returns `None` when
  more than one is showing rather than guessing.

### Player status is a stringified enum
- `str(player.status)` reads `"PlayerStatus.FOLDED"`, not `"FOLDED"`.
- Use `util.is_active()` for "still contesting the pot"; equality checks against `"FOLDED"` silently
  never match.

### Position calculation uses absolute seat numbers
- PokerNow has 10 physical seat slots; players can sit at any of them.
- `dealer_position` is the absolute seat number (1-10), not a list index.
- Seat numbers are read from the `table-player-N` CSS class via JS.
- Algorithm: sort active seats → rotate so dealer is index 0 → count clockwise offset → map to label.
- Heads-up special case: dealer offset 0 is the Small Blind, since the dealer posts SB heads-up.

### LLM is postflop only
- Preflop uses the GTO lookup table, with no LLM call.
- Postflop (flop/turn/river) the LLM decides and explains.
- **Trigger:** fires when it is your turn at a new decision spot, keyed on `(board, amount_to_call)`.
  Amount-to-call rather than pot is essential: PokerNow keeps a street's bets in `bet_value` and only
  sweeps them into `pot_size` at street end, so a check spot and a facing-a-bet spot share the same
  board AND pot.
  `util.amount_to_call()` distinguishes them so the LLM re-fires for every bet or raise you face.
- The decision key is computed before the state broadcast, and the previous spot's result is dropped
  as soon as the key changes, so a new board is never paired with the old street's reasoning.
- The LLM runs in a `daemon=True` thread (`_fetch_llm_explanation`) with `try/finally`, so `pending`
  can never get stuck; `llm_broadcast_sent` gates the single result push.
- On error the LLM returns `{}` and the overlay keeps the heuristic recommendation.
- The Groq client is built lazily by `_groq()`.
  Importing the module must never require a key.
- Model: `LLM_deployment.DEFAULT_MODEL` (`openai/gpt-oss-120b`), override with `PAI_LLM_MODEL`
  (`qwen/qwen3.8-27b` is roughly 2x faster).
  Verify availability via `groq.models.list()` before changing.
- `MAX_TOKENS` is 1500, not a tight budget: reasoning models spend part of it before emitting any
  JSON, and at 400 the API rejected the empty completion outright.

### Turn detection
- The authoritative signal is `current_player` (the `.decision-current` element) compared against
  `you_name`.
  This avoids false positives where action buttons linger for a tick after we have already acted.
- Only when identity is unknown does the loop fall back to OR-ing the library's `is_your_turn()` with
  `len(available_actions) > 0`.
- `build_stats_payload()` guards against illogical actions: any recommended action not in
  `available_actions` is replaced (call → check → fold), and fold is never recommended when checking
  is free.

### Game loop must never die
- The inner `while True` body is wrapped in `try/except Exception`, so one bad tick never kills the
  session.
- State changes are detected by dict equality: `current_game_summary != prev_game_summary`.
- A new hand resets all per-hand state (`action_history`, `llm_cache`, `last_decision_key`) when
  community cards return to 0 while in a hand.
- `action_history` is diffed per street: the baseline (`prev_street_summary`) resets at each street
  change, because PokerNow zeroes `bet_value` between streets.

### WebSocket caches last state for new connections
- `WSServer._last_message` stores the most recent broadcast payload.
- New clients receive it immediately on connect, which prevents a blank overlay between hand start and
  the first state change.
- `PAI_WS_PORT` reaches the overlay because `inject_overlay()` stamps `window.__PAI_WS_PORT` before
  injecting `content.js`.
  Do not hardcode the port in the frontend.

### No destructive git actions without confirmation
- Never `git push --force`, `git reset --hard`, or delete branches without explicit user approval.
- Prefer new commits over amending; always check `git status` before committing.

---

## Test Suite Reference

| File | Module | What it covers |
|------|--------|----------------|
| `tests/test_util.py` | `backend/util.py` | safe_float/chips, is_active, local player resolution, amount_to_call |
| `tests/test_hand_strength.py` | `backend/hand_strength.py` | Card parsing, canonical hand, Sklansky tiers, 169-hand coverage |
| `tests/test_pot_odds.py` | `backend/pot_odds.py` | Pot odds math, zero-division guard |
| `tests/test_eval_best_hand.py` | `backend/eval_best_hand.py` | Best hand from 7 cards, showdown disambiguation, error cases |
| `tests/test_preflop_table.py` | `backend/preflop_table.py` | All 169 hands x 5 positions coverage |
| `tests/test_heuristics.py` | `backend/heuristics.py` | Position calc, SPR, effective stack, bet sizing |
| `tests/test_ws_server.py` | `backend/ws_server.py` | Server start, client connect, broadcast receive |
| `tests/test_llm_deployment.py` | `backend/LLM_deployment.py` | Prompt structure, response coercion, missing-key error, live API call |
| `tests/test_main.py` | `main.py` | Game URL validation |

### Required assertions per module

**util**
- `safe_float(500)` → `500.0` | `"1,250"` → `1250.0` | `"All In"` → `None` | `"N/A"` → `None`
- `chips("All In")` → `0.0`
- `is_active({"status": "PlayerStatus.FOLDED"})` → `False`
- `local_player` prefers `you_name`, falls back to the single visible hand, returns `None` at a
  showdown with no `you_name`
- `amount_to_call` handles facing a bet, partial match, checked-to-you, and never returns negative

**hand_strength**
- `parse_card("Ace of Spades")` → `('A', 'S')`
- `canonical_starting_hand("Ace of Spades", "King of Hearts")` → `'AKo'`
- `canonical_starting_hand("Ace of Spades", "King of Spades")` → `'AKs'`
- `canonical_starting_hand("2 of Hearts", "Ace of Clubs")` → `'A2o'` (order-invariant)
- `classify_starting_hand("AA")` → `"Premium"` | `"99"` → `"Strong"` | `"ATo"` → `"Medium"` | `"44"` → `"Playable"` | `"72o"` → `"Trash"`
- `_ALL_HANDS` is 169 hands: 13 pairs, 78 suited, 78 offsuit

**pot_odds**
- pot=100, max_bet=50, player_bet=0 → `33.33%`
- pot=0, max_bet=0 → `0.0` (no crash)
- pot=200, max_bet=100, player_bet=50 → `20.0%`

**eval_best_hand**
- Royal flush combo → `"Royal Flush"` or `"Straight Flush"` in result
- Four of a kind → result `startswith("Four of a Kind")`
- Full house → result `startswith("Full House")`
- Preflop (no community cards) → `"Not enough cards to evaluate hand"`
- Unknown card → `"Unknown cards in player hand"` or `"Card conversion error"`
- At showdown with `you_name` set, evaluates the local player's hand, not an opponent's

**preflop_table**
- All 169 canonical hands in `_TABLE`
- Every hand x every position returns one of `{'Raise', 'Call', 'Fold'}`
- `AA`, `KK`, `QQ`, `AKs`, `AKo` → `'Raise'` from all 5 positions
- `72o` → `'Fold'` from all 5 positions

**heuristics**
- SPR: pot=100, stack=500 → `5.0` | pot=0 → `inf` | "All In" stack → `inf`
- Effective stack: user=500, opponents=[300,400] → `400.0`
- Effective stack: one "All In" opponent skipped → uses remaining opponent
- Position 6-player: offset 0 → `'Late'` | 1 → `'Small Blind'` | 2 → `'Big Blind'` | 3 → `'Early'`
- Bet sizing: 2.5x BB open, 3x BB from the SB, 3x the opponent's bet as a 3-bet, capped to the
  effective stack

**ws_server**
- Server starts, loop is not None
- Client connects via WebSocket without error
- `broadcast({"test": 1})` is received by connected client within 2s
- `broadcast()` with no clients does not raise

**llm_deployment** (unit, no API)
- `_players_block()` labels the local player with `(YOU)` and hides opponent cards as "hidden"
- `_build_prompt()` output contains street, hole cards, board, player table, action history entries,
  available actions
- `_coerce_bet_size` clamps to the effective stack and rejects zero/negative/non-numeric
- `_bluff_directive` respects `BLUFF_RATE` at both 0.0 and 1.0
- `key_factors` returned as a bare string is coerced to a one-element list
- `_groq()` without `GROQ_API_KEY` raises a `RuntimeError` naming the variable

**llm_deployment** (integration, requires `GROQ_API_KEY`)
- Returns a non-empty dict with `action`, `bet_size`, `action_reason`, `key_factors`, `risk_note`
- `action` is one of the `available_actions` (case-insensitive)
- `key_factors` is a list of at most 3 strings
- `action_reason` and `risk_note` are non-trivial strings

---

## Known Gotchas

| Gotcha | Fix |
|--------|-----|
| `"All In"` stack crashes `float()` | Use `util.safe_float()`, which returns `None` |
| Folded players not excluded | `str(status)` is `"PlayerStatus.FOLDED"`; use `util.is_active()` |
| Overlay shows an opponent's hand at showdown | Resolve the player via `util.local_player()`, not by scanning for visible cards |
| `dealer_position` is not a list index | It is an absolute seat number (1-10); sort active seats and rotate |
| `you-player` CSS class may be absent before login | `get_player_seats()` returns `{}` gracefully; position falls back to `"Unknown"` |
| WS `ws://` blocked on `https://` page | Enable `chrome://flags/#allow-insecure-localhost` |
| LLM model decommissioned silently | Groq retired the whole llama-3.x line under this project. Verify with `groq.models.list()`; last verified `openai/gpt-oss-120b` and `qwen/qwen3.8-27b` |
| Double LLM broadcast every 2s | `llm_broadcast_sent` gates the secondary push |
| Overlay blank on new connection | `WSServer._last_message` sends cached state to new connections |
| Illogical action shown, e.g. "Check" facing a bet | `build_stats_payload()` replaces any action not in `available_actions` with call → check → fold |
| Overlay stuck on port 8765 after `PAI_WS_PORT` | `inject_overlay()` must stamp `window.__PAI_WS_PORT`; the frontend reads it |

---

## Code Style Preferences

- **No speculative features**, implement what is needed now, not hypothetical future requirements.
- **No defensive error handling for impossible states**, only validate at real boundaries
  (external API, DOM reads).
- **No comments explaining what code does**, only add comments for non-obvious *why*
  (workarounds, invariants).
- **Prefer editing existing files** over creating new ones.
- **Short responses**, state results and decisions, skip narration.
- **Print debug lines use the `[PAI]` prefix**, and anything verbose sits behind `PAI_DEBUG`.
