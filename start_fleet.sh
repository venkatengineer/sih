#!/usr/bin/env bash
# ==============================================================================
# Startup Script for 4 Independent Decentralized Edge Robot Agents
# Each robot runs as an isolated Python process with its own UDP & WebSocket ports.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_DIR="$SCRIPT_DIR/robot"
LOG_DIR="$SCRIPT_DIR/.logs"

mkdir -p "$LOG_DIR"
export PYTHONPATH="$ROBOT_DIR:$SCRIPT_DIR:$PYTHONPATH"

echo "======================================================================"
echo "🚀 STARTING DECENTRALIZED EDGE ROBOT FLEET (AMR 01 - 04)"
echo "======================================================================"

# 1. AMR-01: West Corridor Spawn (Grid: 2, 10)
python3 -u -m edge_robot \
    --robot-id AMR-01 \
    --start 2,10 \
    --port 5001 \
    --frontend-port 8001 \
    --speed 1.5 > "$LOG_DIR/amr01.log" 2>&1 &
PID1=$!
disown $PID1 2>/dev/null || true
echo "✅ AMR-01 started (PID: $PID1, P2P UDP: 5001, WebSocket: 8001, Log: .logs/amr01.log)"

# 2. AMR-02: Central Aisle 1 Spawn (Grid: 8, 3)
python3 -u -m edge_robot \
    --robot-id AMR-02 \
    --start 8,3 \
    --port 5002 \
    --frontend-port 8002 \
    --speed 1.5 > "$LOG_DIR/amr02.log" 2>&1 &
PID2=$!
disown $PID2 2>/dev/null || true
echo "✅ AMR-02 started (PID: $PID2, P2P UDP: 5002, WebSocket: 8002, Log: .logs/amr02.log)"

# 3. AMR-03: Central Aisle 2 Spawn (Grid: 17, 2)
python3 -u -m edge_robot \
    --robot-id AMR-03 \
    --start 17,2 \
    --port 5003 \
    --frontend-port 8003 \
    --speed 1.5 > "$LOG_DIR/amr03.log" 2>&1 &
PID3=$!
disown $PID3 2>/dev/null || true
echo "✅ AMR-03 started (PID: $PID3, P2P UDP: 5003, WebSocket: 8003, Log: .logs/amr03.log)"

# 4. AMR-04: East Parking Bay Spawn (Grid: 20, 16)
python3 -u -m edge_robot \
    --robot-id AMR-04 \
    --start 20,16 \
    --port 5004 \
    --frontend-port 8004 \
    --speed 1.5 > "$LOG_DIR/amr04.log" 2>&1 &
PID4=$!
disown $PID4 2>/dev/null || true
echo "✅ AMR-04 started (PID: $PID4, P2P UDP: 5004, WebSocket: 8004, Log: .logs/amr04.log)"

# Save PIDs to file for easy teardown
echo "$PID1 $PID2 $PID3 $PID4" > "$LOG_DIR/fleet.pid"

echo "======================================================================"
echo "🎯 All 4 Edge Agents are running independently."
echo "Now launch Godot Warehouse Simulation to connect visual AMRs."
echo "To stop fleet: bash $SCRIPT_DIR/stop_fleet.sh"
echo "======================================================================"
