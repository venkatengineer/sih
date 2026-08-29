#!/usr/bin/env bash
# =============================================================================
# AMR FLEET WEB CONTROL CENTER - STARTUP SCRIPT
# =============================================================================
# Launches the Python Control Center API and Web Dashboard on http://localhost:8000
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="/data/sih:/data/sih/robot:$PYTHONPATH"

echo "========================================================================"
echo "🏭 STARTING AMR FLEET WEB CONTROL CENTER"
echo "========================================================================"
echo "  • Web Dashboard URL: http://localhost:8000"
echo "  • REST API:         http://localhost:8000/api"
echo "  • WebSocket Stream: ws://localhost:8000/ws"
echo "  • Coordination:     Decentralized P2P UDP Mesh"
echo "  • Central Server:   NONE"
echo "========================================================================"

cd "$SCRIPT_DIR"
exec python3 -m backend.main 8000
