"""
Fleet Overview REST API Endpoints.
"""

from __future__ import annotations
from typing import Dict, Any, List

from control_center.backend.bridge.robot_bridge import fleet_bridge


def handle_get_fleet() -> Dict[str, Any]:
    """GET /api/fleet"""
    return {
        "status": "success",
        "fleet": fleet_bridge.get_fleet_summary(),
        "system": fleet_bridge.get_system_status(),
    }
