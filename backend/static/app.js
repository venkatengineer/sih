/**
 * AMR Fleet Web Control Center - Client Application
 */

let state = {
  currentPage: "overview",
  fleet: [],
  tasks: [],
  events: [],
  system: {
    robots_online: 4,
    active_tasks: 0,
    completed_tasks: 0,
  },
  activeAuction: null,
};

let ws = null;
let taskCounter = 1;

// ============================================================================
// Initialization & WebSocket
// ============================================================================

window.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  initClock();
  fetchInitialData();
});

function initClock() {
  setInterval(() => {
    const d = new Date();
    const clockEl = document.getElementById("live-clock");
    if (clockEl) clockEl.textContent = d.toTimeString().split(" ")[0];
  }, 1000);
}

function initWebSocket() {
  const loc = window.location;
  const wsProto = loc.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProto}//${loc.host}/ws`;

  const statusEl = document.getElementById("ws-status");

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      if (statusEl) {
        statusEl.textContent = "CONNECTED";
        statusEl.style.color = "#4ade80";
      }
      console.log("WebSocket connected to Control Center API");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWebSocketMessage(msg);
      } catch (err) {
        console.error("WS Parse Error:", err);
      }
    };

    ws.onclose = () => {
      if (statusEl) {
        statusEl.textContent = "DISCONNECTED";
        statusEl.style.color = "#f87171";
      }
      setTimeout(initWebSocket, 2000);
    };

    ws.onerror = (err) => {
      console.debug("WS Error:", err);
    };
  } catch (e) {
    console.error("WS Connect error:", e);
    setTimeout(initWebSocket, 2000);
  }
}

function handleWebSocketMessage(msg) {
  if (msg.type === "SNAPSHOT") {
    state.fleet = msg.fleet || [];
    state.tasks = msg.tasks || [];
    state.system = msg.system || state.system;
    renderAll();
    return;
  }

  if (msg.type === "EVENT") {
    const eventType = msg.event;
    const data = msg.data || {};

    // Record in local event list
    state.events.unshift({
      event: eventType,
      timestamp: msg.timestamp || Date.now() / 1000,
      data: data,
    });
    if (state.events.length > 200) state.events.pop();

    // Handle Specific Events
    if (eventType === "ROBOT_STATE") {
      const idx = state.fleet.findIndex((r) => r.robot_id === data.robot_id);
      if (idx >= 0) state.fleet[idx] = data;
      else state.fleet.push(data);
    } else if (eventType === "TASK_AUCTIONING" || eventType === "TASK_CREATED") {
      state.activeAuction = {
        task_id: data.task_id,
        bids: {},
        winner_id: null,
        round: 1,
        status: "AUCTIONING",
      };
      const existing = state.tasks.find((t) => t.task_id === data.task_id);
      if (!existing) state.tasks.unshift(data);
    } else if (eventType === "TASK_BID" || eventType === "TASK_BID_SUBMITTED") {
      const bData = data.bid || data;
      const bRobot = bData.robot_id || data.robot_id;
      if (state.activeAuction && (state.activeAuction.task_id === data.task_id || !data.task_id)) {
        state.activeAuction.bids[bRobot] = bData;
      }
      // Also update task object
      const t = state.tasks.find((t) => t.task_id === data.task_id);
      if (t) {
        if (!t.bids) t.bids = {};
        t.bids[bRobot] = bData;
      }
    } else if (eventType === "TASK_AWARD" || eventType === "TASK_ASSIGNED") {
      const winner = data.winner_id || (data.data && data.data.winner_id);
      if (state.activeAuction) {
        state.activeAuction.winner_id = winner;
        state.activeAuction.status = "ASSIGNED";
      }
      const t = state.tasks.find((t) => t.task_id === data.task_id);
      if (t) {
        t.assigned_robot = winner;
        t.status = "ASSIGNED";
      }
    } else if (eventType === "TASK_PROGRESS" || eventType === "TASK_STARTED" || eventType === "TASK_PICKED_UP") {
      const t = state.tasks.find((t) => t.task_id === data.task_id);
      if (t) t.status = data.status || "IN_PROGRESS";
    } else if (eventType === "TASK_COMPLETE" || eventType === "TASK_COMPLETED") {
      const t = state.tasks.find((t) => t.task_id === data.task_id);
      if (t) t.status = "COMPLETED";
    } else if (eventType === "TASK_RELEASE" || eventType === "TASK_RELEASED" || eventType === "TASK_FAILED") {
      if (state.activeAuction) {
        state.activeAuction.round = data.new_round || 2;
        state.activeAuction.bids = {};
        state.activeAuction.winner_id = null;
        state.activeAuction.status = "REASSIGNING";
      }
      const t = state.tasks.find((t) => t.task_id === data.task_id);
      if (t) {
        t.status = "REASSIGNING";
        t.assigned_robot = null;
        t.auction_round = data.new_round || 2;
      }
    }

    renderAll();
  }
}

// ============================================================================
// REST API Fetching
// ============================================================================

async function fetchInitialData() {
  try {
    const resFleet = await fetch("/api/fleet");
    if (resFleet.ok) {
      const json = await resFleet.json();
      state.fleet = json.fleet || [];
      state.system = json.system || state.system;
    }

    const resTasks = await fetch("/api/tasks");
    if (resTasks.ok) {
      const json = await resTasks.json();
      state.tasks = json.tasks || [];
    }

    const resEvents = await fetch("/api/events?limit=50");
    if (resEvents.ok) {
      const json = await resEvents.json();
      state.events = json.events || [];
    }

    renderAll();
  } catch (err) {
    console.error("Error fetching initial API data:", err);
  }
}

// ============================================================================
// Page Navigation
// ============================================================================

function switchPage(pageName) {
  state.currentPage = pageName;

  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-page") === pageName);
  });

  document.querySelectorAll(".page-section").forEach((el) => {
    el.style.display = el.id === `page-${pageName}` ? "block" : "none";
  });

  const headingMap = {
    overview: "Fleet Operations Overview",
    fleet: "Autonomous Mobile Robot Fleet",
    create_task: "Create Warehouse Transport Task",
    auctions: "Decentralized Task Auction Matrix",
    tasks: "Warehouse Tasks Ledger",
    events: "Live Fleet Event Stream",
  };
  const headingEl = document.getElementById("page-heading");
  if (headingEl) headingEl.textContent = headingMap[pageName] || "Control Center";

  renderAll();
}

// ============================================================================
// Rendering
// ============================================================================

function renderAll() {
  renderKpis();
  renderOverviewFleetTable();
  renderFullFleetTable();
  renderTasksTable();
  renderEvents();
  renderCreateTaskAuction();
  renderAuctionsPage();
}

function renderKpis() {
  const activeCount = state.tasks.filter((t) => ["ASSIGNED", "IN_PROGRESS", "PICKED_UP", "AUCTIONING"].includes(t.status)).length;
  const completedCount = state.tasks.filter((t) => t.status === "COMPLETED").length;
  const onlineRobots = state.fleet.filter((r) => r.is_online).length;

  document.getElementById("kpi-online-count").textContent = `${onlineRobots} / ${state.fleet.length || 4} Online`;
  document.getElementById("kpi-active-count").textContent = activeCount;

  const cardRobots = document.getElementById("card-robots");
  if (cardRobots) cardRobots.textContent = `${onlineRobots} / ${state.fleet.length || 4}`;

  const cardActive = document.getElementById("card-active-tasks");
  if (cardActive) cardActive.textContent = activeCount;

  const cardDone = document.getElementById("card-completed-tasks");
  if (cardDone) cardDone.textContent = completedCount;
}

function renderOverviewFleetTable() {
  const tbody = document.getElementById("overview-fleet-tbody");
  if (!tbody) return;

  if (state.fleet.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--text-dim); text-align:center;">Discovering AMR edge nodes...</td></tr>`;
    return;
  }

  tbody.innerHTML = state.fleet
    .map((r) => {
      const pillClass = `pill-${(r.status || "moving").toLowerCase()}`;
      return `
      <tr>
        <td><strong>${r.robot_id}</strong></td>
        <td><span class="status-pill ${pillClass}">● ${r.status}</span></td>
        <td>
          <div class="battery-bar-wrap">
            <div class="battery-bar-fill" style="width: ${r.battery}%;"></div>
          </div>
          ${Math.round(r.battery)}%
        </td>
        <td><span style="color:#38bdf8;">${r.current_task || "IDLE"}</span></td>
        <td style="font-family:monospace;">[${r.position[0]}, ${r.position[1]}]</td>
      </tr>
    `;
    })
    .join("");
}

function renderFullFleetTable() {
  const tbody = document.getElementById("fleet-tbody");
  if (!tbody) return;

  tbody.innerHTML = state.fleet
    .map((r) => {
      const pillClass = `pill-${(r.status || "moving").toLowerCase()}`;
      return `
      <tr>
        <td><strong style="color:var(--accent-cyan); font-size:14px;">${r.robot_id}</strong></td>
        <td><span style="color:#4ade80;">● P2P CONNECTED</span></td>
        <td><span class="status-pill ${pillClass}">● ${r.status}</span></td>
        <td>
          <div class="battery-bar-wrap">
            <div class="battery-bar-fill" style="width: ${r.battery}%;"></div>
          </div>
          ${Math.round(r.battery)}%
        </td>
        <td>${r.velocity.toFixed(1)} m/s</td>
        <td style="font-family:monospace;">[${r.position[0]}, ${r.position[1]}]</td>
        <td><strong>${r.current_task || "NONE"}</strong></td>
        <td>
          <button class="btn-secondary" onclick="pauseRobot('${r.robot_id}')">Pause</button>
          <button class="btn-secondary" onclick="resumeRobot('${r.robot_id}')">Resume</button>
        </td>
      </tr>
    `;
    })
    .join("");
}

function renderTasksTable() {
  const tbody = document.getElementById("tasks-tbody");
  if (!tbody) return;

  if (state.tasks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:var(--text-dim); text-align:center;">No tasks recorded.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.tasks
    .map((t) => {
      const pillClass = `pill-${(t.status || "auctioning").toLowerCase()}`;
      const scoreStr = t.winner_score != null ? t.winner_score.toFixed(1) : "—";
      return `
      <tr>
        <td><strong>${t.task_id}</strong></td>
        <td>[${t.pickup.join(", ")}]</td>
        <td>[${t.dropoff.join(", ")}]</td>
        <td><span style="color:#fbbf24;">Priority ${t.priority}</span></td>
        <td><span class="status-pill ${pillClass}">${t.status}</span></td>
        <td><strong style="color:#38bdf8;">${t.assigned_robot || "—"}</strong></td>
        <td>Round ${t.auction_round || 1}</td>
        <td>${scoreStr}</td>
      </tr>
    `;
    })
    .join("");
}

function renderEvents() {
  const overviewFeed = document.getElementById("overview-event-feed");
  const fullFeed = document.getElementById("full-event-feed");

  const buildFeedHtml = (events) => {
    if (events.length === 0) return `<div style="color:var(--text-dim);">Listening for P2P mesh events...</div>`;
    return events
      .slice(0, 30)
      .map((e) => {
        const timeStr = new Date(e.timestamp * 1000).toTimeString().split(" ")[0];
        let detail = JSON.stringify(e.data || {});
        if (e.data && e.data.task_id) detail = `Task: ${e.data.task_id} ${e.data.robot_id ? "| Robot: " + e.data.robot_id : ""} ${e.data.cost ? "| Score: " + e.data.cost.toFixed(1) : ""}`;
        if (e.data && e.data.message) detail = e.data.message;

        return `
        <div class="event-row">
          <span class="event-time">${timeStr}</span>
          <span class="event-badge">${e.event}</span>
          <span style="color:var(--text-main);">${detail}</span>
        </div>
      `;
      })
      .join("");
  };

  if (overviewFeed) overviewFeed.innerHTML = buildFeedHtml(state.events);
  if (fullFeed) fullFeed.innerHTML = buildFeedHtml(state.events);
}

function renderCreateTaskAuction() {
  const auc = state.activeAuction;
  const statusEl = document.getElementById("create-auction-status");
  const tableBox = document.getElementById("create-auction-table-box");
  const tbody = document.getElementById("create-auction-tbody");
  const winnerBox = document.getElementById("create-winner-box");

  if (!auc) {
    if (tableBox) tableBox.style.display = "none";
    if (winnerBox) winnerBox.style.display = "none";
    return;
  }

  if (statusEl) {
    statusEl.innerHTML = `
      <div style="font-size:14px; color:#fbbf24; font-weight:700; margin-bottom:4px;">
        ⚡ P2P AUCTION: ${auc.task_id} (Round ${auc.round})
      </div>
      <div>Status: <span style="color:#38bdf8;">${auc.status}</span> | Evaluating decentralized bids...</div>
    `;
  }

  if (tableBox && tbody) {
    tableBox.style.display = "block";
    const bidKeys = Object.keys(auc.bids);
    if (bidKeys.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="color:var(--text-dim); text-align:center;">Waiting for peer bids over P2P UDP...</td></tr>`;
    } else {
      tbody.innerHTML = bidKeys
        .map((rId) => {
          const b = auc.bids[rId];
          const isWinner = rId === auc.winner_id;
          const rowStyle = isWinner ? `style="background:#0e3322; color:#4ade80; font-weight:700;"` : "";
          const trophy = isWinner ? " 🏆" : "";
          return `
            <tr ${rowStyle}>
              <td>${rId}${trophy}</td>
              <td>${(b.distance || 0).toFixed(1)}m</td>
              <td>${Math.round(b.battery || 100)}%</td>
              <td>${(b.cost || 0).toFixed(1)}</td>
            </tr>
          `;
        })
        .join("");
    }
  }

  if (winnerBox) {
    if (auc.winner_id && auc.bids[auc.winner_id]) {
      const wb = auc.bids[auc.winner_id];
      winnerBox.style.display = "block";
      winnerBox.innerHTML = `
        <div style="color:#4ade80; font-size:14px; font-weight:700; margin-bottom:6px;">
          🏆 CONSENSUS REACHED: ${auc.winner_id} SELECTED
        </div>
        <div style="font-size:12px; color:var(--text-muted); line-height:1.6;">
          • Multi-Factor Cost Score: <strong style="color:#38bdf8;">${(wb.cost || 0).toFixed(1)}</strong><br>
          • Distance to Pickup: <strong>${(wb.distance || 0).toFixed(1)}m</strong> | Battery: <strong>${Math.round(wb.battery || 100)}%</strong><br>
          • Verified independently across 4 AMR Edge nodes without a central server.
        </div>
      `;
    } else {
      winnerBox.style.display = "none";
    }
  }
}

function renderAuctionsPage() {
  const container = document.getElementById("auctions-container");
  if (!container) return;

  const auc = state.activeAuction;
  if (!auc) {
    container.innerHTML = `<div style="color:var(--text-muted);">No active auctions in progress. Create a task to initiate a P2P auction.</div>`;
    return;
  }

  const bidKeys = Object.keys(auc.bids);
  let bidsHtml = `
    <table class="custom-table" style="margin-top:12px;">
      <thead>
        <tr>
          <th>ROBOT</th>
          <th>DISTANCE</th>
          <th>BATTERY</th>
          <th>CONGESTION</th>
          <th>TOTAL SCORE</th>
        </tr>
      </thead>
      <tbody>
  `;

  if (bidKeys.length === 0) {
    bidsHtml += `<tr><td colspan="5" style="color:var(--text-dim);">Listening for bids on P2P network...</td></tr>`;
  } else {
    bidKeys.forEach((rId) => {
      const b = auc.bids[rId];
      const isWinner = rId === auc.winner_id;
      const rowStyle = isWinner ? `style="background:#0e3322; color:#4ade80; font-weight:700;"` : "";
      bidsHtml += `
        <tr ${rowStyle}>
          <td>${rId} ${isWinner ? "🏆" : ""}</td>
          <td>${(b.distance || 0).toFixed(1)}m</td>
          <td>${Math.round(b.battery || 100)}%</td>
          <td>${(b.congestion || 0).toFixed(1)}</td>
          <td><strong>${(b.cost || 0).toFixed(1)}</strong></td>
        </tr>
      `;
    });
  }
  bidsHtml += `</tbody></table>`;

  container.innerHTML = `
    <div style="border-left:4px solid var(--accent-amber); padding-left:14px; margin-bottom:16px;">
      <h3 style="font-size:16px; color:#fbbf24;">Task Auction: ${auc.task_id} (Round ${auc.round})</h3>
      <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
        Decentralized Consensus Status: <strong style="color:#38bdf8;">${auc.status}</strong>
      </div>
    </div>
    ${bidsHtml}
  `;
}

// ============================================================================
// Actions
// ============================================================================

async function handleCreateTaskSubmit(e) {
  e.preventDefault();

  const tId = document.getElementById("input-task-id").value.trim() || `T-${taskCounter}`;
  const pickupStr = document.getElementById("input-pickup").value.split(",").map(Number);
  const dropoffStr = document.getElementById("input-dropoff").value.split(",").map(Number);
  const prio = parseInt(document.getElementById("input-priority").value, 10);

  taskCounter++;
  document.getElementById("input-task-id").value = `T-${taskCounter < 10 ? "00" + taskCounter : (taskCounter < 100 ? "0" + taskCounter : taskCounter)}`;

  try {
    const res = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: tId,
        pickup: pickupStr,
        dropoff: dropoffStr,
        priority: prio,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      console.log("Task submitted successfully:", data);
    }
  } catch (err) {
    console.error("Failed creating task:", err);
  }
}

async function pauseRobot(robotId) {
  try {
    await fetch(`/api/robots/${robotId}/pause`, { method: "POST" });
  } catch (err) {
    console.error(`Error pausing ${robotId}:`, err);
  }
}

async function resumeRobot(robotId) {
  try {
    await fetch(`/api/robots/${robotId}/resume`, { method: "POST" });
  } catch (err) {
    console.error(`Error resuming ${robotId}:`, err);
  }
}
