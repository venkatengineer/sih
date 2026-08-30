#!/usr/bin/env bash
# ==============================================================================
# Teardown Script for Decentralized Edge Robot Fleet
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/.logs"

echo "🛑 Stopping all running Edge Robot Agent processes..."

if [ -f "$LOG_DIR/fleet.pid" ]; then
    PIDS=$(cat "$LOG_DIR/fleet.pid")
    for PID in $PIDS; do
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null || true
            echo "Stopped process $PID"
        fi
    done
    rm -f "$LOG_DIR/fleet.pid"
fi

# Fallback pattern kill
pkill -f "python3 -m edge_robot" 2>/dev/null || true

echo "✅ All Edge Robot Agent processes stopped."
