# PAIv1 — Claude Code Project Guide

> **PAIv1** is a real-time poker AI assistant that scrapes live game state from PokerNow via Selenium, runs GTO-based analysis, and surfaces decisions through a floating browser overlay powered by an LLM.

---

## Quick Commands

```bash
pytest tests/ -v                          # run full test suite (must pass before any commit)
pytest tests/ -v -s -m "not integration"  # fast tests only (no API call)
pytest tests/test_llm_deployment.py -v -s # LLM integration test (makes real Groq call)
python main.py                            # start the app
```

**Environment:** `cp .env.example .env` → add `GROQ_API_KEY=your_key`
**WS port:** `8765` default, override with `PAI_WS_PORT` env var
**Full roadmap:** [IMPLEMENTATION.md](IMPLEMENTATION.md)

---

## Architecture at a Glance

```
PokerNow browser tab
    └─ Selenium DOM poll (every 2s, local — zero network cost)
           │
           ▼
    main.py game loop
       ├─ get_player_seats()      JS → seat numbers + local player identity
       ├─ get_game_summary()      raw GameState → clean serializable dict
       ├─ build_stats_payload()
       │     ├─ hand_strength.py  Sklansky & Malmuth tier (Premium/Strong/Medium/Playable/Trash)
       │     ├─ eval_best_hand.py best 5-card hand via treys
       │     ├─ pot_odds.py       pot odds %
       │     ├─ preflop_table.py  GTO lookup: 169 hands × 5 positions → Raise/Call/Fold
       │     └─ heuristics.py     position, SPR, effective stack, fallback recommendation
       ├─ WSServer.broadcast()    JSON payload → overlay
       └─ LLM thread (postflop)  Groq API → {action, reason, key_factors, risk_note}
              └─ WSServer.broadcast()   second push once LLM result arrives

WSServer localhost:8765
    └─ WebSocket → content.js (injected into PokerNow tab by Selenium)
           └─ Floating overlay panel rendered in-browser
```

**Decision split:**
| Street | Who decides |
|--------|------------|
| Preflop | GTO lookup table — instant, deterministic |
| Flop / Turn / River | LLM (`llama-3.3-70b-versatile` via Groq) — sees full hand context |

---

## Persistent Development Rules

These rules apply to every session. Claude must follow them without being reminded.

### Never break the test suite
- Run `pytest tests/ -v` before reporting any task complete
- Every new module gets a corresponding test file in `tests/`
- Tests must cover both happy path and edge cases (empty input, "All In" strings, zero-division)
- Current count: **55 tests passing** across 7 files

### Stack values are not always numbers
- Player stacks can be the string `"All In"` — never call `float()` directly
- Always use `_safe_float_stack()` from `backend/heuristics.py`
- Returns `None` for non-numeric values; callers must handle `None` explicitly

### Player identity comes from the DOM, not cards
- The `you-player` CSS class on a `.table-player` element identifies the local player
- This is captured in JS via `get_player_seats()` in `main.py` and stored as `game_summary["you_name"]`
- Do not identify the local player by visible cards — they aren't shown until dealt, and folded players lose them

### Position calculation uses absolute seat numbers
- PokerNow has 10 physical seat slots; players can sit at any of them
- `dealer_position` is the absolute seat number (1–10), not a list index
- Seat numbers are read from the `table-player-N` CSS class via JS
- Algorithm: sort active seats → rotate so dealer is index 0 → count clockwise offset → map to label
- Heads-up special case: dealer offset 0 = Small Blind (dealer posts SB in HU)

### LLM is postflop only
- Preflop: heuristic from GTO lookup table, no LLM call
- Postflop (flop/turn/river): LLM decides AND explains
- **Trigger**: fires when it's your turn at a new decision spot, keyed on `(board, amount_to_call)`. Amount-to-call (not pot) is essential — PokerNow keeps a street's bets in `bet_value` and only sweeps them into `pot_size` at street end, so a check spot and a facing-a-bet spot share the same board AND pot. `_amount_to_call()` distinguishes them so the LLM re-fires for every bet/raise you face.
- LLM runs in a `daemon=True` thread (`_fetch_llm_explanation`) with `try/finally` so `pending` can never get stuck; `llm_broadcast_sent` gates the single result push
- On error: LLM returns `{}`, overlay keeps the heuristic recommendation
- Model: `llama-3.3-70b-versatile` default; override with `PAI_LLM_MODEL` env var (`llama-3.1-8b-instant` ≈ 2× faster). Verify availability via `groq.models.list()` before changing.

### Turn detection
- The PokerNow lib's `is_your_turn()` requires a `.action-signal` element with text exactly `"Your Turn"` — too fragile to rely on alone
- The loop OR's it with `len(available_actions) > 0`: action buttons only render on your turn, so non-empty actions is the reliable signal
- `build_stats_payload()` guards against illogical actions: any recommended action not in `available_actions` is replaced (call → check → fold)

### Game loop must never die
- The inner `while True` body is wrapped in `try/except Exception` — one bad tick never kills the session
- State changes are detected by dict equality: `current_game_summary != prev_game_summary`
- New hand resets all per-hand state (snapshots, `action_history`, `llm_cache`, `last_decision_key`) when community cards return to 0 while in a hand
- `action_history` is diffed per-street: the baseline (`prev_street_summary`) resets at each street change because PokerNow zeroes `bet_value` between streets

### WebSocket caches last state for new connections
- `WSServer._last_message` stores the most recent broadcast payload
- New clients receive it immediately on connect — prevents blank overlay between hand-start and first state change

### No destructive git actions without confirmation
- Never `git push --force`, `git reset --hard`, or delete branches without explicit user approval
- Prefer new commits over amending; always check `git status` before committing

---

## Test Suite Reference

| File | Module | What it covers |
|------|--------|----------------|
| `tests/test_hand_strength.py` | `backend/hand_strength.py` | Card parsing, canonical hand, Sklansky tiers |
| `tests/test_pot_odds.py` | `backend/pot_odds.py` | Pot odds math, zero-division guard |
| `tests/test_eval_best_hand.py` | `backend/eval_best_hand.py` | Best hand from 7 cards, error cases |
| `tests/test_preflop_table.py` | `backend/preflop_table.py` | All 169 hands × 5 positions coverage |
| `tests/test_heuristics.py` | `backend/heuristics.py` | Position calc, SPR, effective stack, All-In guard |
| `tests/test_ws_server.py` | `backend/ws_server.py` | Server start, client connect, broadcast receive |
| `tests/test_llm_deployment.py` | `backend/LLM_deployment.py` | Prompt structure (unit) + live API call (integration) |

**Running integration tests:**
```bash
# Integration test makes a real Groq API call (~1s)
pytest tests/test_llm_deployment.py::test_llm_returns_valid_action -v -s

# Skip API calls in CI or offline:
pytest tests/ -m "not integration" -v
```

### Required assertions per module

**hand_strength**
- `parse_card("Ace of Spades")` → `('A', 'S')`
- `canonical_starting_hand("Ace of Spades", "King of Hearts")` → `'AKo'`
- `canonical_starting_hand("Ace of Spades", "King of Spades")` → `'AKs'`
- `canonical_starting_hand("2 of Hearts", "Ace of Clubs")` → `'A2o'` (order-invariant)
- `classify_starting_hand("AA")` → `"Premium"` | `"99"` → `"Strong"` | `"ATo"` → `"Medium"` | `"44"` → `"Playable"` | `"72o"` → `"Trash"`

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

**preflop_table**
- All 169 canonical hands in `_TABLE`
- Every hand × every position returns one of `{'Raise', 'Call', 'Fold'}`
- `AA`, `KK`, `QQ`, `AKs`, `AKo` → `'Raise'` from all 5 positions
- `72o` → `'Fold'` from all 5 positions

**heuristics**
- `_safe_float_stack(500)` → `500.0` | `"All In"` → `None` | `"N/A"` → `None`
- SPR: pot=100, stack=500 → `5.0` | pot=0 → `inf` | "All In" stack → `inf`
- Effective stack: user=500, opponents=[300,400] → `400.0`
- Effective stack: one "All In" opponent skipped → uses remaining opponent
- Position 6-player: offset 0 → `'Late'` | 1 → `'Small Blind'` | 2 → `'Big Blind'` | 3 → `'Early'`

**ws_server**
- Server starts, loop is not None
- Client connects via WebSocket without error
- `broadcast({"test": 1})` is received by connected client within 2s
- `broadcast()` with no clients does not raise

**llm_deployment** (unit — no API)
- `_players_block()` labels local player with `(YOU)`, hides opponent cards as "hidden"
- `_build_prompt()` output contains: street, hole cards, board, player table, action history entries, available actions

**llm_deployment** (integration — requires `GROQ_API_KEY`)
- Returns non-empty dict with all four keys: `action`, `action_reason`, `key_factors`, `risk_note`
- `action` is one of the `available_actions` (case-insensitive)
- `key_factors` is a list of ≤ 3 strings
- `action_reason` and `risk_note` are non-trivial strings (len > 10)

---

## Known Gotchas

| Gotcha | Fix |
|--------|-----|
| `"All In"` stack crashes `float()` | Use `_safe_float_stack()` — returns `None` |
| `dealer_position` is not a list index | It's an absolute seat number (1–10); sort active seats and rotate |
| `you-player` CSS class may be absent before login | `get_player_seats()` returns `{}` gracefully; position falls back to `"Unknown"` |
| WS `ws://` blocked on `https://` page | Enable `chrome://flags/#allow-insecure-localhost` |
| LLM model decommissioned silently | Verify with `groq.models.list()` before changing; last verified: `llama-3.3-70b-versatile`. Override with `PAI_LLM_MODEL` env var (`llama-3.1-8b-instant` is ~2x faster) |
| Double LLM broadcast every 2s | `llm_broadcast_sent` flag gates the secondary push |
| Overlay blank on new connection | `WSServer._last_message` sends cached state to new connections on connect |
| LLM never fires live; only heuristic "Check" shows | The lib's `is_your_turn()` needs `.action-signal` text == "Your Turn" (fragile). The loop OR's it with `len(available_actions) > 0` — action buttons only render on your turn, so that's the reliable signal |
| Illogical action shown (e.g. "Check" facing a bet) | Usually stale state. `build_stats_payload()` guards: any recommended action not in `available_actions` is replaced by call→check→fold |
| Game loop crash on winner block | Entire inner loop is wrapped in `try/except`; winners are safe to access there |

---

## Code Style Preferences

- **No speculative features** — implement what's needed now, not hypothetical future requirements
- **No defensive error handling for impossible states** — only validate at real boundaries (external API, DOM reads)
- **No comments explaining what code does** — only add comments for non-obvious *why* (workarounds, invariants)
- **Prefer editing existing files** over creating new ones
- **Short responses** — state results and decisions, skip narration
- **Print debug lines use `[PAI]` prefix** — easy to grep; remove before shipping
