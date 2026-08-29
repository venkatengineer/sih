"""
System Status & Event Logs REST API Endpoints.
"""

from __future__ import annotations
from typing import Dict, Any, List

from control_center.backend.bridge.robot_bridge import fleet_bridge


def handle_get_system() -> Dict[str, Any]:
    """GET /api/system"""
    return {
        "status": "success",
        "system": fleet_bridge.get_system_status(),
    }


def handle_get_events(limit: int = 50) -> Dict[str, Any]:
    """GET /api/events"""
    return {
        "status": "success",
        "events": fleet_bridge.get_events(limit=limit),
    }
