(() => {
  // Port is stamped on window by inject_overlay() so PAI_WS_PORT reaches the overlay.
  const WS_URL = `ws://localhost:${window.__PAI_WS_PORT || 8765}`;
  const RECONNECT_DELAY_MS = 3000;

  // ── Build overlay DOM ────────────────────────────────────────────────────
  function createOverlay() {
    const el = document.createElement("div");
    el.id = "pai-overlay";
    el.innerHTML = `
      <div id="pai-header">
        <span id="pai-title">PAIv1</span>
        <span id="pai-turn-badge">waiting...</span>
        <button id="pai-scale-up" title="Larger">🔍</button>
        <button id="pai-scale-down" title="Smaller">🔎</button>
        <button id="pai-toggle" title="Collapse/Expand">−</button>
      </div>
      <div id="pai-body">
        <div class="pai-section">
          <div class="pai-row">
            <span class="pai-label">Starting Hand</span>
            <span class="pai-value" id="pai-hole-cards">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">Hand Strength</span>
            <span class="pai-value" id="pai-starting-hand">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">Best Hand</span>
            <span class="pai-value" id="pai-best-hand">—</span>
          </div>
        </div>
        <div class="pai-divider"></div>
        <div class="pai-section">
          <div class="pai-row">
            <span class="pai-label">Street</span>
            <span class="pai-value" id="pai-street">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">Pot Size</span>
            <span class="pai-value" id="pai-pot">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">Pot Odds</span>
            <span class="pai-value" id="pai-pot-odds">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">Position</span>
            <span class="pai-value" id="pai-position">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">SPR</span>
            <span class="pai-value" id="pai-spr">—</span>
          </div>
          <div class="pai-row">
            <span class="pai-label">Eff. Stack</span>
            <span class="pai-value" id="pai-eff-stack">—</span>
          </div>
        </div>
        <div class="pai-divider"></div>
        <div id="pai-rec-box">
          <span id="pai-rec-label">ACTION</span>
          <span id="pai-rec-action">—</span>
        </div>
        <div class="pai-divider"></div>
        <div id="pai-explain-box">
          <div id="pai-explain-label">AI REASONING</div>
          <div id="pai-explain-reason" class="pai-explain-pending">—</div>
          <ul id="pai-explain-factors"></ul>
          <div id="pai-explain-risk"></div>
        </div>
      </div>
    `;
    document.body.appendChild(el);
    makeDraggable(el);
    setupToggle(el);
    setupScale(el);
    return el;
  }

  // ── Update overlay with payload from Python backend ──────────────────────
  function updateOverlay(data) {
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val ?? "—";
    };

    const isYourTurn = !!data.is_your_turn;
    const overlay = document.getElementById("pai-overlay");
    if (overlay) {
      overlay.classList.toggle("pai-your-turn", isYourTurn);
      overlay.classList.toggle("pai-waiting", !isYourTurn);
    }

    const badge = document.getElementById("pai-turn-badge");
    if (badge) {
      badge.textContent = isYourTurn ? "YOUR TURN" : "";
    }

    set("pai-hole-cards",    data.hole_cards_display || "—");
    set("pai-starting-hand", data.starting_hand
      ? `${data.starting_hand}  [${data.hand_strength}]`
      : "—");
    set("pai-best-hand",     data.best_hand || "—");
    set("pai-street",        data.street || "—");
    set("pai-pot",           data.pot_size != null ? data.pot_size.toFixed(1) : "—");
    set("pai-pot-odds",      (data.pot_odds != null && data.pot_odds > 0) ? `${data.pot_odds.toFixed(1)}%` : "—");
    set("pai-position",      data.position || "—");
    set("pai-spr",           data.spr == null ? "∞" : data.spr.toFixed(2));
    set("pai-eff-stack",     data.effective_stack != null ? data.effective_stack.toFixed(1) : "—");

    const recEl  = document.getElementById("pai-rec-action");
    const hasLLM = data.llm_action_reason || (data.llm_key_factors && data.llm_key_factors.length);

    if (recEl) {
      const action = (data.recommended_action || "").toLowerCase();
      let label = data.recommended_action || "—";
      // Show the size to raise/bet TO, e.g. "RAISE → 45"
      if ((action === "raise" || action === "bet") && data.recommended_bet_size) {
        label = `${label} → ${Math.round(data.recommended_bet_size)}`;
      // Or the amount needed to call, e.g. "CALL 8"
      } else if (action === "call" && data.to_call_amount) {
        label = `${label} ${Math.round(data.to_call_amount)}`;
      }
      recEl.textContent = label;
      recEl.className = "";
      if (data.recommended_action) {
        recEl.classList.add(`pai-rec-${action}`);
      }
    }

    const reasonEl  = document.getElementById("pai-explain-reason");
    const factorsEl = document.getElementById("pai-explain-factors");
    const riskEl    = document.getElementById("pai-explain-risk");

    if (hasLLM) {
      if (reasonEl) {
        reasonEl.textContent = data.llm_action_reason || "";
        reasonEl.classList.remove("pai-explain-pending");
      }
      if (factorsEl) {
        // Model output goes in as text, never markup.
        factorsEl.replaceChildren(...(data.llm_key_factors || []).map(f => {
          const li = document.createElement("li");
          li.textContent = f;
          return li;
        }));
      }
      if (riskEl) {
        riskEl.textContent = data.llm_risk_note ? `⚠ ${data.llm_risk_note}` : "";
      }
    } else {
      if (reasonEl) {
        reasonEl.textContent = isYourTurn ? "AI is analyzing the hand…" : "—";
        reasonEl.classList.toggle("pai-explain-pending", isYourTurn);
      }
      if (factorsEl) factorsEl.replaceChildren();
      if (riskEl)    riskEl.textContent = "";
    }
  }

  // ── WebSocket connection with auto-reconnect ─────────────────────────────
  function connectWS() {
    let ws;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      setTimeout(connectWS, RECONNECT_DELAY_MS);
      return;
    }

    ws.onopen = () => {
      console.log("[PAI] Connected to backend");
      const badge = document.getElementById("pai-turn-badge");
      if (badge) badge.textContent = "";
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        updateOverlay(data);
      } catch (e) {
        console.warn("[PAI] Failed to parse message:", e);
      }
    };

    ws.onclose = () => {
      console.log("[PAI] Disconnected, retrying...");
      const badge = document.getElementById("pai-turn-badge");
      if (badge) badge.textContent = "disconnected";
      setTimeout(connectWS, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => ws.close();
  }

  // ── Drag support ─────────────────────────────────────────────────────────
  function makeDraggable(el) {
    let startX, startY, startLeft, startTop;

    const header = el.querySelector("#pai-header");
    if (!header) return;

    const NON_DRAG = new Set(["pai-toggle", "pai-scale-up", "pai-scale-down"]);
    header.addEventListener("mousedown", (e) => {
      if (NON_DRAG.has(e.target.id)) return;
      startX = e.clientX;
      startY = e.clientY;
      const rect = el.getBoundingClientRect();
      startLeft = rect.left;
      startTop = rect.top;

      const onMove = (e) => {
        el.style.left = `${startLeft + e.clientX - startX}px`;
        el.style.top  = `${startTop  + e.clientY - startY}px`;
        el.style.right = "auto";
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  // ── Collapse / expand toggle ─────────────────────────────────────────────
  function setupToggle(el) {
    const btn  = el.querySelector("#pai-toggle");
    const body = el.querySelector("#pai-body");
    if (!btn || !body) return;

    btn.addEventListener("click", () => {
      const collapsed = body.style.display === "none";
      body.style.display = collapsed ? "" : "none";
      btn.textContent    = collapsed ? "−" : "+";
    });
  }

  // ── Size scale (+ / − buttons) ───────────────────────────────────────────
  function setupScale(el) {
    const btnUp   = el.querySelector("#pai-scale-up");
    const btnDown = el.querySelector("#pai-scale-down");
    if (!btnUp || !btnDown) return;
    const MIN = 0.7, MAX = 1.8, STEP = 0.1;
    let scale = 1.0;

    function applyScale() {
      el.style.transform = `scale(${scale.toFixed(1)})`;
      el.style.transformOrigin = "top right";
    }

    btnUp.addEventListener("click", () => {
      scale = Math.min(MAX, parseFloat((scale + STEP).toFixed(1)));
      applyScale();
    });
    btnDown.addEventListener("click", () => {
      scale = Math.max(MIN, parseFloat((scale - STEP).toFixed(1)));
      applyScale();
    });
  }

  // ── Init ─────────────────────────────────────────────────────────────────
  createOverlay();
  connectWS();
})();
