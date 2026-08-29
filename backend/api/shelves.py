"""
Shelves REST API Endpoints.
Provides machine-readable inventory of functional warehouse shelves for web UI and external systems.
"""

from __future__ import annotations
from typing import Dict, Any, List

from edge_robot.world.shelf_registry import shelf_registry


def handle_get_shelves() -> Dict[str, Any]:
    """GET /api/shelves"""
    shelves = shelf_registry.get_all_shelves()
    return {
        "status": "success",
        "total_shelves": len(shelves),
        "shelves": [s.to_dict() for s in shelves],
    }


def handle_get_shelf(shelf_id: str) -> Tuple[Dict[str, Any], int]:
    """GET /api/shelves/{shelf_id}"""
    shelf = shelf_registry.get_shelf(shelf_id)
    if not shelf:
        return {"status": "error", "message": f"Shelf '{shelf_id}' not found"}, 404
    return {
        "status": "success",
        "shelf": shelf.to_dict(),
    }, 200
