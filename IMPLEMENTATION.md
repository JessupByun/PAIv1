# PAIv1 — Implementation Roadmap

## Project Summary

**PAIv1** is a real-time poker AI assistant for [PokerNow](https://www.pokernow.club). It scrapes live game state from the PokerNow DOM via Selenium, runs GTO-based preflop lookup + postflop heuristics, explains decisions via LLM, and surfaces everything as a floating overlay injected into the browser tab.

**Stack:** Python 3.10, Selenium, asyncio WebSocket server, Groq LLM API (Llama 3), Chrome content script overlay.

---

## Architecture Overview

```
PokerNow DOM (browser)
    ↓  Selenium DOM read (every 2s, local — no network cost)
GameState dict  ←  PokerNow Python library (PokerClient)
    ↓
main.py game loop
    ├── get_player_seats()       JS → absolute seat numbers + you-player name
    ├── get_game_summary()       flattens GameState → serializable dict
    ├── build_stats_payload()    calls all analysis modules
    │     ├── hand_strength.py   Sklansky & Malmuth tier classification
    │     ├── eval_best_hand.py  best 5-card hand from 7 cards
    │     ├── pot_odds.py        pot odds %
    │     ├── preflop_table.py   GTO preflop lookup (169 hands × 5 positions)
    │     └── heuristics.py      position, SPR, effective stack, recommend_action
    ├── WSServer.broadcast()     sends JSON payload to overlay
    └── LLM thread               Groq API → structured JSON explanation
          ↓ (async, fires once per decision point)
     ws_server.broadcast()       pushes LLM result when ready

WSServer (localhost:8765)
    ↓  WebSocket
frontend/content.js              injected into PokerNow tab by main.py via Selenium
    ↓  updates DOM
Floating overlay panel           visible to user in browser
```

---

## Phase Status

### Phase 0 — Scraper Foundation  ✅ COMPLETE

**What was built:**
- Selenium + PokerNow library integration to read live game state (cards, stacks, pot, blinds, community cards, dealer position, player statuses, available actions)
- `main.py` game loop with 2s polling, state-change detection, console debug output
- Cookie-based session persistence for PokerNow login

**Key files:** `main.py`, `PokerNow/` (library, not modified)

---

### Phase 1 — Analysis Engine  ✅ COMPLETE

**What was built:**

| Module | Purpose |
|--------|---------|
| `backend/hand_strength.py` | Parses card strings, computes canonical hand (AKs/AKo/QQ), classifies using Sklansky & Malmuth groups into 5 tiers: Premium / Strong / Medium / Playable / Trash |
| `backend/eval_best_hand.py` | Evaluates best 5-card hand from hole cards + community cards using `treys` library; returns detailed string e.g. "Full House (Ks over 3s)" |
| `backend/pot_odds.py` | Calculates pot odds % given pot size, max bet, current player bet contribution |
| `backend/preflop_table.py` | Hardcoded GTO preflop lookup table for all 169 canonical hands × 5 positions (Early/Middle/Late/Small Blind/Big Blind) → Raise/Call/Fold |
| `backend/heuristics.py` | `calculate_position()`, `calculate_spr()`, `calculate_effective_stack()`, `recommend_action()`; uses absolute seat numbers; handles "All In" strings |

**Hand tiers (Sklansky & Malmuth):**
- **Premium** (Groups 1-2): AA, KK, QQ, JJ, TT, AKs, AQs, AJs, ATs, KQs, AKo, AQo
- **Strong** (Groups 3-4): 99, 88, JTs, QJs, KJs, QTs, KTs, J9s, T9s, 98s, AJo, KQo
- **Medium** (Groups 5-6): 77, 66, 55, A2s-A9s, K9s-KQs, Q9s-QJs, J8s, T8s, 97s, 86s, 75s, 64s, 53s, ATo, KJo-KQo, QJo, JTo
- **Playable** (Groups 7-8): 44, 33, 22, K2s-K8s, Q2s-Q8s, J2s-J7s, T2s-T7s, 52s-96s (suited connectors), A2o-A9o, K9o-KTo
- **Trash** (unranked): everything else including 72o, 32o, 83o

**Position algorithm:**
1. `get_player_seats()` in `main.py` runs JS to extract `table-player-N` seat numbers and `you-player` name
2. `calculate_position()` sorts active seat numbers, rotates list so dealer is index 0, computes user's clockwise offset
3. Offset → label: 0=Late (Button), 1=Small Blind, 2=Big Blind, 3+=Early/Middle
4. Heads-up: offset 0 = Small Blind (dealer posts SB), offset 1 = Big Blind

**Key gotchas resolved:**
- PokerNow has 10 physical seats; active players can be at any arbitrary seat numbers — must use absolute seat numbers, not list index
- `"All In"` is a string in player stack field — guard with `isinstance` before `float()` conversion
- `you-player` CSS class is the only reliable way to identify the local player (cards aren't visible until dealt)

---

### Phase 2 — Live Browser Overlay  ✅ COMPLETE

**What was built:**

| Component | Purpose |
|-----------|---------|
| `backend/ws_server.py` | asyncio WebSocket server on localhost:8765; `broadcast()` sends JSON to all clients; caches `_last_message` so new connections get current state immediately |
| `frontend/content.js` | Injected into PokerNow tab via Selenium (`inject_overlay()` in main.py); creates floating draggable panel; connects to WS; renders all stat fields |
| `frontend/overlay.css` | Styles for the overlay panel; z-index 99999 to float above PokerNow modals |

**Overlay UI sections:**
- Header: "PAI" title + turn badge (glows gold when your turn)
- Street + hole cards display (e.g. "As Kh — AKs Premium")
- Best hand (postflop only)
- Stats grid: Pot, Pot Odds %, Position, SPR, Effective Stack
- Recommended action (bold, colored)
- LLM explain section: action reason (2-3 sentences), 3 key factor bullets, risk note
- Scale buttons (🔍/🔎, 0.7x–1.8x) + minimize toggle

**How injection works:** `main.py` reads CSS and JS files from disk, injects via `driver.execute_script()`. Overlay is re-injected on each startup; `window.__pai_injected` guard prevents double-injection.

**Known requirement:** Chrome needs "Allow insecure localhost" enabled at `chrome://flags/#allow-insecure-localhost` for `ws://localhost` to work on an `https://` page.

---

### Phase 3 — LLM Decision + Explanation Layer  ✅ COMPLETE

**What was built:**

`backend/LLM_deployment.py` — Groq API integration. LLM **decides the action AND explains it** for postflop streets only.

**Architecture split:**
| Street | Decision source |
|--------|----------------|
| Preflop | GTO preflop lookup table (`backend/preflop_table.py`) — instant, no LLM |
| Flop / Turn / River | LLM (`llama-3.3-70b-versatile`) — sees full hand context, decides + explains |

**Why this split:** Preflop decisions are deterministic from GTO charts (169 canonical hands × 5 positions). Postflop is where context — board texture, opponent behavior, stack depth, pot odds — matters most and where LLM reasoning adds value. Running LLM preflop would waste ~3s on a decision that a lookup table gets right instantly.

**What the LLM receives (via `_build_prompt()`):**
- Full player table: every player's name, current stack, amount bet this street, status (active/folded/all-in), and any visible cards
- Board cards, pot size, street
- Pot odds % with equity framing ("need >X% equity to call profitably")
- SPR with interpretation (low/medium/high)
- Effective stack in BB with depth label (SHORT/MID/DEEP)
- Blinds
- Full chronological action history list (one entry per event: fold/bet/raise/call)

**Response schema (`response_format={"type": "json_object"}`):**
```json
{
  "action": "Raise",
  "action_reason": "2-3 sentences citing actual numbers from the hand",
  "key_factors": ["hand/board factor", "positional factor", "stack/math factor"],
  "risk_note": "1 sentence: forward-looking risk on next street"
}
```

**Action validation:** LLM `action` is validated against `available_actions` (case-insensitive). Falls back to substring match, then first available action if LLM returns something invalid.

**Overlay behavior:**
- While LLM is pending: overlay shows heuristic action + "analyzing…" source badge
- After LLM returns: overlay updates with LLM action + "AI" source badge (purple)
- Preflop: overlay shows heuristic action + "heuristic" source badge, no explanation text

**Deduplication:** `hash((tuple(hole_cards), tuple(community_cards)))` → fires LLM only once per new board state. `llm_broadcast_sent` flag prevents re-broadcasting every 2s tick.

**Threading:** LLM runs in `daemon=True` thread; result stored in `llm_cache["result"]`; pushed to overlay once when ready.

---

### Phase 4 — Action History Tracking  ✅ COMPLETE

**What was built:** `_build_action_history()` in `main.py` diffs consecutive game summaries to detect all player actions.

**Detected events (per tick):**
- Fold: player status changed to FOLDED → `"Flop: Alice folded"`
- Open bet: bet increased from 0 when table max bet was also 0 → `"Flop: You bet 60"`
- Raise: bet increased above prior table max bet → `"Turn: Alice raised to 120"`
- Call: bet increased to match (not exceed) prior table max bet → `"River: You called 40"`

**Key details:**
- Returns a list of strings per tick (multiple players can act between 2s polls)
- `action_history.extend(new_events)` accumulates into a flat chronological list
- Labels "You" for `you_name`, real name for opponents
- Entire list is passed to LLM prompt verbatim, numbered 1→N
- `action_history` resets on each new hand

---

## Phase 5 — Future Work  🔲 NOT STARTED

### 5A — Equity Calculator
Real-time Monte Carlo equity estimation (% to win vs. opponent range) using `treys` or `eval7`. Run in background thread, display as win% bar in overlay.

**Libraries:** `treys` (already in project), or `eval7` for faster range equity.

### 5B — Opponent Profiling
Track per-opponent stats within a session: VPIP (voluntarily put money in pot), PFR (preflop raise %), aggression frequency. Display as tags next to player names in overlay.

**Implementation:** Dict keyed by player name, updated each `_build_action_history()` call. Reset on browser refresh.

### 5C — Session Bankroll Tracker
Track stack size at hand start and end, compute session P&L. Display running graph (could be ASCII in console or a small chart in overlay).

**Implementation:** Record `user_stack` at hand start; diff with hand end; append to session log.

### 5D — Bet Sizing Advisor
Given SPR, street, hand strength, recommend a specific bet size (e.g. "Bet 60% pot = 45") rather than just "Raise". Currently `recommend_action` only returns a direction.

### 5E — GTO Blueprint (Future)
Replace heuristic `recommend_action` with a trained CFR solver blueprint.
- **fedden/poker_ai**: Python CFR implementation; requires ~8 days of cloud training to generate blueprint
- **Slumbot API**: Near-GTO but heads-up only; public HTTP API

### 5F — Hand History & Replay
Save full hand snapshots (preflop/flop/turn/river) to JSON/SQLite. Load and replay past hands in overlay for review.

**Note:** Explicitly deferred by user. The `hand_snapshots` dict structure in `main.py` already captures the data; persistence layer is the only missing piece.

---

## Technical Documentation

| Resource | URL | Relevant to |
|----------|-----|-------------|
| PokerNow game client | https://www.pokernow.club | Target site |
| PokerNow Python library | (bundled in `PokerNow/` dir) | DOM scraping, GameState API |
| Groq API docs | https://console.groq.com/docs/openai | LLM inference |
| Groq JSON mode | https://console.groq.com/docs/structured-outputs | Structured LLM output |
| Groq model list | https://console.groq.com/docs/models | Available models (llama3, mixtral, etc.) |
| websockets library | https://websockets.readthedocs.io | WS server (`backend/ws_server.py`) |
| treys (hand evaluator) | https://github.com/ihendley/treys | `backend/eval_best_hand.py` |
| Selenium Python | https://selenium-python.readthedocs.io | DOM scraping + overlay injection |
| Chrome Manifest V3 | https://developer.chrome.com/docs/extensions/mv3 | If extension is ever separated from injection |
| Sklansky & Malmuth groups | https://www.pokerstarschool.com/poker-hands-ranked | Hand tier reference |
| pytest docs | https://docs.pytest.org | Test suite |
| python-dotenv | https://pypi.org/project/python-dotenv | `.env` for `GROQ_API_KEY` |

---

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=your_key_here

# Run tests
pytest tests/ -v

# Run app
python main.py
# → opens Chrome, prompts for PokerNow login, then game URL
# → inject overlay into browser tab
# → poll game state every 2s
```

**Chrome flag required for WS on HTTPS:**
Go to `chrome://flags/#allow-insecure-localhost` and enable "Allow invalid certificates for resources loaded from localhost."

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Selenium DOM polling (not API) | PokerNow has no public API; DOM is the only source of truth |
| 2s polling interval | Fast enough for meaningful decisions; low enough to avoid browser CPU spikes |
| Overlay injected via Selenium JS | Avoids Chrome extension install friction; works immediately with `python main.py` |
| LLM decides + explains postflop | Preflop is deterministic (lookup table); postflop needs context — LLM runs async so overlay is never blocked |
| Groq (not OpenAI) | Free tier, faster inference than OpenAI for Llama models |
| Preflop lookup table (not solver) | Near-zero latency, no training required; accurate for preflop decisions |
| `you-player` CSS class for identity | Only reliable player identification method before cards are dealt |
| Absolute seat numbers for position | PokerNow has 10 physical seats, players sit at arbitrary positions — list index is meaningless |
