"""
Conflict Detector and Resolution Controller.
Manages spatial-temporal grid cell reservations and resolves peer cross-intersection conflicts.
"""

from typing import Dict, List, Optional, Tuple, Set
from world.grid_map import Point
from world.world_model import LocalWorldModel

class ConflictDetector:
    def __init__(self, robot_id: str):
        self.robot_id = robot_id

    def detect_path_conflicts(
        self,
        my_path: List[Point],
        world_model: LocalWorldModel
    ) -> List[Tuple[Point, str]]:
        """
        Detects grid cells where my path overlaps with peer paths or peer reservations.
        Returns list of (conflict_cell, peer_robot_id).
        """
        conflicts = []
        if not my_path:
            return conflicts

        for idx, cell in enumerate(my_path):
            # Check cell reservations
            if world_model.is_cell_reserved(cell, self.robot_id):
                owner = world_model.reservations.get(cell, "UNKNOWN")
                conflicts.append((cell, owner))
                continue

            # Check peer path overlaps at similar step index
            for peer in world_model.get_all_active_peers():
                peer_path = peer.current_path or peer.planned_path
                if peer_path and idx < len(peer_path):
                    if peer_path[idx] == cell or (idx > 0 and peer_path[idx-1] == cell):
                        conflicts.append((cell, peer.robot_id))

        return conflicts

    def resolve_conflict_priority(self, my_robot_id: str, peer_robot_id: str) -> bool:
        """
        Deterministic tie-breaking priority rule based on robot ID lexicographical order.
        Returns True if my_robot_id has priority, False otherwise.
        """
        return my_robot_id < peer_robot_id
