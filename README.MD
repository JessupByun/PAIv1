# PAIv1 — Real-Time Online Poker Assistant

> A live poker AI that watches your PokerNow game, analyzes the hand, and tells you what to do — with reasoning.

Built by the **Data Science Union** at UCLA.

---

## Demo

The assistant runs alongside a live [PokerNow](https://www.pokernow.club) game. A floating overlay appears directly in the browser tab showing real-time hand analysis and AI-generated decisions.

- **Preflop** → GTO lookup table instantly recommends Raise / Call / Fold based on your hand and position
- **Flop / Turn / River** → LLM analyzes the full hand state (stacks, bets, board, action history) and outputs a decision with a written explanation

---

## How It Works

```
PokerNow browser tab
    └─ Selenium polls the DOM every 2 seconds (local — zero network cost)
           ↓
    main.py game loop
       ├─ Extracts: hole cards, community cards, pot, stacks, blinds, position, available actions
       ├─ Computes: hand strength tier, best hand, pot odds %, SPR, effective stack, position
       ├─ Preflop  → GTO lookup table (169 hands × 5 positions) → Raise / Call / Fold
       ├─ Broadcasts stats to overlay via WebSocket
       └─ Postflop → fires LLM in background thread
              └─ Groq API (llama-3.3-70b-versatile) receives full hand context
                     └─ Returns: action + 2-3 sentence explanation + key factors + risk note
                            └─ Overlay updates with AI decision

Overlay: injected directly into the PokerNow tab via Selenium — no Chrome extension needed
```

**Decision split:**

| Street | Who decides | Why |
|--------|-------------|-----|
| Preflop | GTO lookup table | Deterministic, instant — 169 canonical hands × 5 positions |
| Flop / Turn / River | LLM (`llama-3.3-70b-versatile`) | Context-dependent — board texture, stacks, history all matter |

---

## Project Structure

```
PAIv1/
├── main.py                  # Entry point: game loop, overlay injection, WS broadcast, LLM thread
├── backend/
│   ├── hand_strength.py     # Card parsing, canonical notation (AKs/AKo/QQ), Sklansky tier classification
│   ├── eval_best_hand.py    # Best 5-card hand from 7 cards (uses treys)
│   ├── pot_odds.py          # Pot odds % calculation
│   ├── heuristics.py        # Position, SPR, effective stack, preflop fallback recommender
│   ├── preflop_table.py     # GTO preflop ranges: all 169 hands × 5 positions → Raise/Call/Fold
│   ├── ws_server.py         # asyncio WebSocket server — broadcasts JSON payload to overlay
│   └── LLM_deployment.py    # Groq API — receives full hand state, decides action + explains it
├── frontend/
│   ├── content.js           # Overlay UI — WebSocket client, updates DOM on each message
│   └── overlay.css          # Floating panel styles (draggable, resizable, z-index 99999)
├── tests/                   # 55 pytest tests across 7 files — all passing
├── CLAUDE.md                # AI dev guidelines, persistent rules, gotchas
├── IMPLEMENTATION.md        # Full architecture + phase history + future roadmap
├── requirements.txt
└── .env.example             # Copy to .env and add your GROQ_API_KEY
```

---

## Setup

**Requirements:** Python 3.10+, Google Chrome

```bash
# 1. Clone the repo
git clone https://github.com/the-data-science-union/DSU-S2026-PAIv1-Real-time-Online-Poker-Assistant.git
cd DSU-S2026-PAIv1-Real-time-Online-Poker-Assistant

# 2. Create and activate a virtual environment
python3.10 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your Groq API key
cp .env.example .env
# Edit .env and set: GROQ_API_KEY=your_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

**Chrome flag (one-time setup):**
Go to `chrome://flags/#allow-insecure-localhost` and enable it. This lets the overlay's WebSocket connect to the Python backend on an `https://` page.

---

## Running

```bash
source venv/bin/activate
python main.py
```

1. Chrome opens → log into PokerNow when prompted
2. Press Enter in the terminal once logged in
3. Paste your game URL: `https://www.pokernow.club/games/pgl...`
4. The overlay appears top-right in the browser tab
5. Stats update every 2s — overlay glows green when it's your turn

---

## Tests

```bash
pytest tests/ -v                           # all 55 tests
pytest tests/ -v -m "not integration"      # skip live API call
pytest tests/test_llm_deployment.py -v -s  # live Groq API test (needs key)
```

| Test file | What it covers |
|-----------|----------------|
| `test_hand_strength.py` | Card parsing, canonical hand notation, Sklansky tier classification |
| `test_pot_odds.py` | Pot odds math, zero-division guard |
| `test_eval_best_hand.py` | Best hand from 7 cards, error cases |
| `test_preflop_table.py` | All 169 hands × 5 positions return valid actions |
| `test_heuristics.py` | Position calc, SPR, effective stack, "All In" string guard |
| `test_ws_server.py` | Server start, client connect, broadcast receive |
| `test_llm_deployment.py` | Prompt structure (unit) + live Groq API call (integration) |

---

## Contributing

**Branch strategy:**
```
main           ← stable, demo-ready
feature/xyz    ← your work — PR into main when ready
```

**To add a feature:**
```bash
git pull origin main
git checkout -b feature/your-name-feature
# write code + tests
pytest tests/ -v   # must pass
git push origin feature/your-name-feature
# open a PR on GitHub
```

**Open areas for contribution:**

| Area | Location | Notes |
|------|----------|-------|
| Overlay UI improvements | `frontend/content.js`, `frontend/overlay.css` | Layout, colors, animations |
| Opponent profiling | `backend/heuristics.py` | Track VPIP, PFR, aggression per opponent |
| Bet sizing advisor | `backend/heuristics.py` | Recommend specific bet sizes ("Bet 60% pot = 45") |
| Equity calculator | `backend/` | Monte Carlo win % vs. opponent range using `treys` |
| Session bankroll tracker | `main.py` | Track P&L across hands within a session |
| Hand history persistence | `main.py` | Save hand snapshots to JSON/SQLite for review |
| LLM prompt tuning | `backend/LLM_deployment.py` | Improve postflop decision quality |

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for full architecture details and phased development history.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Game scraping | Python 3.10, Selenium 4, PokerNow client library |
| Hand analysis | `treys` (hand evaluator), custom GTO preflop table |
| LLM inference | Groq API — `llama-3.3-70b-versatile` (~1s latency) |
| Overlay transport | asyncio WebSocket server (`websockets` library) |
| Overlay UI | Vanilla JS + CSS, injected via `driver.execute_script()` |
| Tests | pytest, 55 cases |
