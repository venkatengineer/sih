"""
Tasks REST API Endpoints.
Handles task creation, querying, and cancellation through the decentralized RobotFleetBridge.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional

from control_center.backend.models.api_models import TaskCreateRequest
from control_center.backend.bridge.robot_bridge import fleet_bridge


def handle_get_tasks() -> Dict[str, Any]:
    """GET /api/tasks"""
    return {
        "status": "success",
        "tasks": fleet_bridge.get_tasks(),
    }


def handle_get_task(task_id: str) -> Dict[str, Any]:
    """GET /api/tasks/{task_id}"""
    task = fleet_bridge.get_task(task_id)
    if not task:
        return {"status": "error", "message": f"Task {task_id} not found"}, 404
    return {
        "status": "success",
        "task": task,
    }


def handle_create_task(body: Dict[str, Any]) -> Dict[str, Any]:
    """POST /api/tasks"""
    try:
        req = TaskCreateRequest.from_dict(body)
        task_summary = fleet_bridge.submit_task(req)
        return {
            "status": "success",
            "task_id": task_summary.task_id,
            "task": task_summary.to_dict(),
        }, 201
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


def handle_cancel_task(task_id: str) -> Dict[str, Any]:
    """POST /api/tasks/{task_id}/cancel"""
    cancelled = fleet_bridge.cancel_task(task_id)
    if not cancelled:
        return {"status": "error", "message": f"Task {task_id} not found"}, 404
    return {
        "status": "success",
        "task": cancelled.to_dict(),
    }
