"""
Robots REST API Endpoints.
Handles robot telemetry inspection and high-level control commands.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from control_center.backend.bridge.robot_bridge import fleet_bridge


def handle_get_robots() -> Dict[str, Any]:
    """GET /api/robots"""
    return {
        "status": "success",
        "robots": fleet_bridge.get_fleet_summary(),
    }


def handle_get_robot(robot_id: str) -> Dict[str, Any]:
    """GET /api/robots/{robot_id}"""
    robot = fleet_bridge.get_robot(robot_id)
    if not robot:
        return {"status": "error", "message": f"Robot {robot_id} not found"}, 404
    return {
        "status": "success",
        "robot": robot,
    }


def handle_pause_robot(robot_id: str) -> Dict[str, Any]:
    """POST /api/robots/{robot_id}/pause"""
    ok = fleet_bridge.pause_robot(robot_id)
    if not ok:
        return {"status": "error", "message": f"Could not pause {robot_id}"}, 400
    return {"status": "success", "message": f"{robot_id} paused"}


def handle_resume_robot(robot_id: str) -> Dict[str, Any]:
    """POST /api/robots/{robot_id}/resume"""
    ok = fleet_bridge.resume_robot(robot_id)
    if not ok:
        return {"status": "error", "message": f"Could not resume {robot_id}"}, 400
    return {"status": "success", "message": f"{robot_id} resumed"}
