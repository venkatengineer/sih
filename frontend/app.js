// High-Tech Interactive Industrial Warehouse Visualizer Client

const WS_PORT = 8765;
let socket = null;

const canvas = document.getElementById('warehouseCanvas');
const ctx = canvas.getContext('2d');

const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const fleetOverview = document.getElementById('fleetOverview');
const decisionLogs = document.getElementById('decisionLogs');
const instructionBanner = document.getElementById('instructionBanner');

const selectRobot = document.getElementById('selectRobot');
const btnAddMachineInstant = document.getElementById('btnAddMachineInstant');
const btnAddMachine2Click = document.getElementById('btnAddMachine2Click');
const btnRemoveRobot = document.getElementById('btnRemoveRobot');
const btnClearAll = document.getElementById('btnClearAll');

const btnSetStart = document.getElementById('btnSetStart');
const btnSetGoal = document.getElementById('btnSetGoal');
const btnToggleObstacle = document.getElementById('btnToggleObstacle');

const btnSimulateCongestion = document.getElementById('btnSimulateCongestion');
const btnClearCongestion = document.getElementById('btnClearCongestion');
const btnResetMap = document.getElementById('btnResetMap');

// Speed Buttons
const btnSpeedNormal = document.getElementById('btnSpeedNormal');
const btnSpeedFast = document.getElementById('btnSpeedFast');
const btnSpeedTurbo = document.getElementById('btnSpeedTurbo');

// Metrics Labels
const lblCurrentRoute = document.getElementById('lblCurrentRoute');
const lblAlternateRoute = document.getElementById('lblAlternateRoute');

const GRID_SIZE = 30;
const CELL_SIZE = canvas.width / GRID_SIZE;

// Color Palette per Robot
const ROBOT_COLORS = {
    'AMR-01': '#38bdf8', // Cyan
    'AMR-02': '#22c55e', // Neon Green
    'AMR-03': '#f59e0b', // Amber
    'AMR-04': '#a855f7', // Purple
    'AMR-05': '#ef4444', // Crimson
    'AMR-06': '#ec4899', // Pink
    'AMR-07': '#84cc16', // Lime
    'AMR-08': '#f97316'  // Orange
};

function getRobotColor(rId) {
    return ROBOT_COLORS[rId] || '#38bdf8';
}

// UI Placement state
let placementMode = 'START'; // 'START', 'GOAL', 'OBSTACLE', 'ADD_STEP1', 'ADD_STEP2'
let tempStart = null;

let robotMarkers = {};
let fleetState = {};
let segmentCongestion = {};
let staticObstacles = [];
let dynamicObstacles = [];

function initWebSocket() {
    const wsUrl = `ws://${window.location.hostname || 'localhost'}:${WS_PORT}`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        statusDot.className = 'status-dot connected';
        statusText.textContent = 'Connected (WS Live)';
        addLogEntry('Connected to Edge-AI Telemetry Gateway', 'info');
    };

    socket.onclose = () => {
        statusDot.className = 'status-dot disconnected';
        statusText.textContent = 'Disconnected';
        setTimeout(initWebSocket, 2000);
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };
}

function sendAction(actionData) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(actionData));
    } else {
        console.warn('WebSocket not connected');
    }
}

function handleMessage(data) {
    if (data.event === 'CONGESTION_ROUTE_DECISION') {
        const decisionClass = data.decision === 'REROUTE' ? 'reroute' : 'continue';
        
        const currDist = (data.current_route_distance !== null && data.current_route_distance !== undefined) ? `${data.current_route_distance}m` : '0m';
        const altDist = (data.alternate_route_distance !== null && data.alternate_route_distance !== undefined) ? `${data.alternate_route_distance}m` : 'N/A';
        const currTime = data.current_route_time !== null ? `${data.current_route_time}s` : 'N/A';
        const altTime = data.alternate_route_time !== null ? `${data.alternate_route_time}s` : 'N/A';

        const msgText = `[${data.robot_id}] Decision: ${data.decision} (${data.reason}) | Current Path: ${currDist} (ETA ${currTime}) | Alternate Path: ${altDist} (ETA ${altTime})`;
        addLogEntry(msgText, decisionClass);

        // Update Metrics Panel if matching active select
        if (data.robot_id === selectRobot.value) {
            lblCurrentRoute.textContent = `Distance: ${currDist} | ETA: ${currTime}`;
            lblAlternateRoute.textContent = `Distance: ${altDist} | ETA: ${altTime}`;
        }
    } else if (data.event === 'FLEET_STATE') {
        fleetState = data.robots || {};
        segmentCongestion = data.congestion || {};
        staticObstacles = data.obstacles || [];
        dynamicObstacles = data.dynamic_obstacles || [];

        syncRobotDropdown();
        renderWarehouse();
        updateFleetOverview();
    }
}

function syncRobotDropdown() {
    const currentSelection = selectRobot.value;
    const robotKeys = Object.keys(fleetState);

    // Save active dropdown selection
    const prevOptionCount = selectRobot.options.length;
    
    // Only rebuild dropdown if keys changed to avoid flickering selection
    const existingValues = Array.from(selectRobot.options).map(o => o.value).filter(v => v);
    const keysMatch = robotKeys.length === existingValues.length && robotKeys.every(k => existingValues.includes(k));

    if (!keysMatch) {
        selectRobot.innerHTML = '';
        if (robotKeys.length === 0) {
            selectRobot.innerHTML = '<option value="">No machines added yet. Click + Add AMR Machine</option>';
            return;
        }

        robotKeys.forEach((rId) => {
            const opt = document.createElement('option');
            opt.value = rId;
            opt.textContent = `${rId}`;
            selectRobot.appendChild(opt);
        });

        if (robotKeys.includes(currentSelection)) {
            selectRobot.value = currentSelection;
        } else {
            selectRobot.value = robotKeys[0];
        }
    }
}

function addLogEntry(text, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${text}`;
    decisionLogs.appendChild(entry);
    decisionLogs.scrollTop = decisionLogs.scrollHeight;
}

function updateInstructionBanner(htmlText) {
    instructionBanner.innerHTML = `<span>${htmlText}</span>`;
}

function renderWarehouse() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background Floor
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw Metallic Grid Lines
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.6)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= GRID_SIZE; i++) {
        ctx.beginPath();
        ctx.moveTo(i * CELL_SIZE, 0);
        ctx.lineTo(i * CELL_SIZE, canvas.height);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, i * CELL_SIZE);
        ctx.lineTo(canvas.width, i * CELL_SIZE);
        ctx.stroke();
    }

    // Draw Static Warehouse Obstacle Walls
    staticObstacles.forEach((obs) => {
        const [ox, oy] = obs;
        ctx.fillStyle = '#334155';
        ctx.fillRect(ox * CELL_SIZE + 1, oy * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1;
        ctx.strokeRect(ox * CELL_SIZE + 1, oy * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    });

    // Draw Dynamic Obstacle Hazard Cells
    dynamicObstacles.forEach((obs) => {
        const [ox, oy] = obs;
        ctx.fillStyle = 'rgba(168, 85, 247, 0.35)';
        ctx.fillRect(ox * CELL_SIZE, oy * CELL_SIZE, CELL_SIZE, CELL_SIZE);
        ctx.strokeStyle = '#a855f7';
        ctx.lineWidth = 1;
        ctx.strokeRect(ox * CELL_SIZE + 1, oy * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    });

    // Draw Glowing Congestion Segments
    for (const [segId, info] of Object.entries(segmentCongestion)) {
        const parts = segId.split('--');
        if (parts.length === 2) {
            const [x1, y1] = parts[0].split(',').map(Number);
            const [x2, y2] = parts[1].split(',').map(Number);

            ctx.lineWidth = 5;
            ctx.shadowBlur = 8;
            if (info.level === 'HIGH') {
                ctx.strokeStyle = '#ef4444';
                ctx.shadowColor = '#ef4444';
            } else if (info.level === 'MEDIUM') {
                ctx.strokeStyle = '#f59e0b';
                ctx.shadowColor = '#f59e0b';
            } else {
                ctx.strokeStyle = '#22c55e';
                ctx.shadowColor = '#22c55e';
            }

            ctx.beginPath();
            ctx.moveTo(x1 * CELL_SIZE + CELL_SIZE / 2, y1 * CELL_SIZE + CELL_SIZE / 2);
            ctx.lineTo(x2 * CELL_SIZE + CELL_SIZE / 2, y2 * CELL_SIZE + CELL_SIZE / 2);
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    }

    // Draw Active Robot Paths & Positions FOR ALL MACHINES
    for (const [robotId, bot] of Object.entries(fleetState)) {
        const isSelected = (robotId === selectRobot.value);
        const rColor = getRobotColor(robotId);

        // Draw Path Line
        if (bot.current_path && bot.current_path.length > 1) {
            ctx.strokeStyle = rColor;
            ctx.lineWidth = isSelected ? 3 : 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            bot.current_path.forEach((p, idx) => {
                const cx = p[0] * CELL_SIZE + CELL_SIZE / 2;
                const cy = p[1] * CELL_SIZE + CELL_SIZE / 2;
                if (idx === 0) ctx.moveTo(cx, cy);
                else ctx.lineTo(cx, cy);
            });
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Draw Start (S) and Goal (G) Markers for ALL Active Robots
        if (bot.start_position) {
            const sx = bot.start_position[0] * CELL_SIZE + CELL_SIZE / 2;
            const sy = bot.start_position[1] * CELL_SIZE + CELL_SIZE / 2;
            ctx.fillStyle = '#22c55e';
            ctx.beginPath();
            ctx.arc(sx, sy, CELL_SIZE * 0.22, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#0f172a';
            ctx.font = 'bold 8px Inter';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('S', sx, sy);
        }

        if (bot.target_destination) {
            const gx = bot.target_destination[0] * CELL_SIZE + CELL_SIZE / 2;
            const gy = bot.target_destination[1] * CELL_SIZE + CELL_SIZE / 2;
            ctx.fillStyle = '#ef4444';
            ctx.beginPath();
            ctx.arc(gx, gy, CELL_SIZE * 0.22, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 8px Inter';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('G', gx, gy);
        }

        // Draw Robot Circle Body
        if (bot.position) {
            const rx = bot.position[0] * CELL_SIZE + CELL_SIZE / 2;
            const ry = bot.position[1] * CELL_SIZE + CELL_SIZE / 2;

            ctx.shadowBlur = isSelected ? 12 : 4;
            ctx.shadowColor = rColor;

            ctx.fillStyle = rColor;
            ctx.beginPath();
            ctx.arc(rx, ry, CELL_SIZE * 0.4, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;

            ctx.fillStyle = '#0f172a';
            ctx.font = 'bold 9px Inter';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(robotId.replace('AMR-', ''), rx, ry);
        }
    }

    // Draw Temporary Start marker during 2-click creation
    if (tempStart) {
        const tsx = tempStart[0] * CELL_SIZE + CELL_SIZE / 2;
        const tsy = tempStart[1] * CELL_SIZE + CELL_SIZE / 2;
        ctx.shadowBlur = 10;
        ctx.shadowColor = '#22c55e';
        ctx.fillStyle = '#22c55e';
        ctx.beginPath();
        ctx.arc(tsx, tsy, CELL_SIZE * 0.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 10px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('S', tsx, tsy);
    }
}

function updateFleetOverview() {
    fleetOverview.innerHTML = '';
    const robotKeys = Object.keys(fleetState);

    if (robotKeys.length === 0) {
        fleetOverview.innerHTML = '<div class="empty-msg">No active AMRs in fleet. Click "+ Add AMR Machine" to spawn one.</div>';
        return;
    }

    robotKeys.forEach((rId) => {
        const bot = fleetState[rId];
        const item = document.createElement('div');
        item.className = 'robot-item';
        item.innerHTML = `
            <div>
                <span class="robot-id" style="color: ${getRobotColor(rId)}">${rId}</span>
                <span style="color: var(--text-secondary); margin-left: 8px;">Pos: (${bot.position ? bot.position.join(',') : '0,0'})</span>
            </div>
            <span class="badge ${bot.status === 'MOVING' ? 'neon-blue' : ''}">${bot.status || 'ACTIVE'}</span>
        `;
        fleetOverview.appendChild(item);
    });
}

// 1-Click Instant Add Machine Handler
btnAddMachineInstant.addEventListener('click', () => {
    sendAction({ action: 'ADD_ROBOT' });
    const nextNum = Object.keys(fleetState).length + 1;
    const newId = nextNum < 10 ? `AMR-0${nextNum}` : `AMR-${nextNum}`;
    addLogEntry(`Added new crossing machine ${newId}`, 'info');
    updateInstructionBanner(`✅ Added <b>${newId}</b> with crossing path! Click again to add more machines.`);
});

// 2-Click Add Custom Machine Button Handler
btnAddMachine2Click.addEventListener('click', () => {
    placementMode = 'ADD_STEP1';
    tempStart = null;
    btnSetStart.classList.remove('active-mode');
    btnSetGoal.classList.remove('active-mode');
    btnToggleObstacle.classList.remove('active-mode');
    updateInstructionBanner('📍 <b>Step 1:</b> Click on the grid map to place <b>START (S)</b> for the new AMR machine.');
    addLogEntry('Entered 2-Click Add Machine mode: Click map for Start (S)', 'info');
});

btnRemoveRobot.addEventListener('click', () => {
    const activeTarget = selectRobot.value;
    if (activeTarget) {
        sendAction({ action: 'REMOVE_ROBOT', robot_id: activeTarget });
        addLogEntry(`Removed machine ${activeTarget}`, 'info');
    }
});

btnClearAll.addEventListener('click', () => {
    sendAction({ action: 'CLEAR_ALL' });
    robotMarkers = {};
    addLogEntry('Cleared all AMR machines from simulation', 'info');
    updateInstructionBanner('Cleared all machines. Click "+ Add AMR Machine" to start fresh.');
});

// Speed Controls
btnSpeedNormal.addEventListener('click', () => {
    sendAction({ action: 'SET_SPEED', delay: 0.3 });
    btnSpeedNormal.classList.add('active');
    btnSpeedFast.classList.remove('active');
    btnSpeedTurbo.classList.remove('active');
});

btnSpeedFast.addEventListener('click', () => {
    sendAction({ action: 'SET_SPEED', delay: 0.06 });
    btnSpeedFast.classList.add('active');
    btnSpeedNormal.classList.remove('active');
    btnSpeedTurbo.classList.remove('active');
});

btnSpeedTurbo.addEventListener('click', () => {
    sendAction({ action: 'SET_SPEED', delay: 0.02 });
    btnSpeedTurbo.classList.add('active');
    btnSpeedNormal.classList.remove('active');
    btnSpeedFast.classList.remove('active');
});

// Traffic Controls
btnSimulateCongestion.addEventListener('click', () => {
    sendAction({ action: 'SIMULATE_CONGESTION' });
    addLogEntry('Simulated heavy corridor congestion', 'info');
});

btnClearCongestion.addEventListener('click', () => {
    sendAction({ action: 'CLEAR_CONGESTION' });
    addLogEntry('Cleared dynamic corridor traffic', 'info');
});

btnResetMap.addEventListener('click', () => {
    sendAction({ action: 'RESET' });
    addLogEntry('Reset map obstacles and robot paths to start positions', 'info');
    updateInstructionBanner('Reset all machines to their start locations.');
});

// Placement Tool Buttons
btnSetStart.addEventListener('click', () => {
    placementMode = 'START';
    btnSetStart.classList.add('active-mode');
    btnSetGoal.classList.remove('active-mode');
    btnToggleObstacle.classList.remove('active-mode');
    updateInstructionBanner('📍 Click on grid map to place <b>START (S)</b> for selected machine.');
});

btnSetGoal.addEventListener('click', () => {
    placementMode = 'GOAL';
    btnSetGoal.classList.add('active-mode');
    btnSetStart.classList.remove('active-mode');
    btnToggleObstacle.classList.remove('active-mode');
    updateInstructionBanner('🎯 Click on grid map to place <b>END (G)</b> for selected machine.');
});

btnToggleObstacle.addEventListener('click', () => {
    placementMode = 'OBSTACLE';
    btnToggleObstacle.classList.add('active-mode');
    btnSetStart.classList.remove('active-mode');
    btnSetGoal.classList.remove('active-mode');
    updateInstructionBanner('🧱 Click on grid map to draw or erase custom <b>Wall Obstacle</b> blocks.');
});

selectRobot.addEventListener('change', () => {
    renderWarehouse();
});

// Canvas Click Handler
canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    const gridX = Math.floor(clickX / CELL_SIZE);
    const gridY = Math.floor(clickY / CELL_SIZE);

    const clampedX = Math.max(0, Math.min(GRID_SIZE - 1, gridX));
    const clampedY = Math.max(0, Math.min(GRID_SIZE - 1, gridY));

    // 2-Click Add Machine Workflow
    if (placementMode === 'ADD_STEP1') {
        tempStart = [clampedX, clampedY];
        placementMode = 'ADD_STEP2';
        updateInstructionBanner(`🎯 <b>Step 2:</b> Start set at (${clampedX}, ${clampedY}). Now click map to place <b>END (G)</b> for new AMR.`);
        addLogEntry(`Placed Start (S) at (${clampedX}, ${clampedY}). Now click map for End (G)`, 'info');
        renderWarehouse();
        return;
    } else if (placementMode === 'ADD_STEP2') {
        const tempGoal = [clampedX, clampedY];
        const nextNum = Object.keys(fleetState).length + 1;
        const newId = nextNum < 10 ? `AMR-0${nextNum}` : `AMR-${nextNum}`;

        robotMarkers[newId] = { start: tempStart, goal: tempGoal };

        sendAction({
            action: 'ADD_ROBOT',
            start: tempStart,
            goal: tempGoal
        });

        addLogEntry(`Created ${newId}: Start (${tempStart.join(',')}) → Goal (${tempGoal.join(',')})`, 'info');
        updateInstructionBanner(`✅ Created <b>${newId}</b>! Repeat or set tools above to add more machines.`);

        tempStart = null;
        placementMode = 'START';
        btnSetStart.classList.add('active-mode');
        renderWarehouse();
        return;
    }

    // Toggle Obstacle Mode
    if (placementMode === 'OBSTACLE') {
        sendAction({ action: 'TOGGLE_OBSTACLE', cell: [clampedX, clampedY] });
        addLogEntry(`Toggled wall obstacle at (${clampedX}, ${clampedY})`, 'info');
        return;
    }

    // Normal Re-positioning Mode for Active Selected Machine
    const activeRobot = selectRobot.value;
    if (!activeRobot) {
        addLogEntry('No machine selected! Click "+ Add AMR Machine" first.', 'reroute');
        return;
    }

    const currentBot = fleetState[activeRobot];
    const currentStart = currentBot ? currentBot.start_position : [0, 15];
    const currentGoal = currentBot ? currentBot.target_destination : [29, 15];

    let newStart = currentStart;
    let newGoal = currentGoal;

    if (placementMode === 'START') {
        newStart = [clampedX, clampedY];
        addLogEntry(`Updated ${activeRobot} START (S) to (${clampedX}, ${clampedY})`, 'info');
    } else if (placementMode === 'GOAL') {
        newGoal = [clampedX, clampedY];
        addLogEntry(`Updated ${activeRobot} GOAL (G) to (${clampedX}, ${clampedY})`, 'info');
    }

    sendAction({
        action: 'SET_START_GOAL',
        robot_id: activeRobot,
        start: newStart,
        goal: newGoal
    });

    renderWarehouse();
});

document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    renderWarehouse();
});
