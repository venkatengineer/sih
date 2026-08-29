"""
Local World Model for Edge-AI AMR.
Maintains local perception, grid map, dynamic obstacle tracks, peer robot states,
path intents, and intersection reservations.
"""

import time
from typing import Dict, List, Tuple, Optional, Any, Set
from world.grid_map import GridMap, Point

class PeerState:
    def __init__(self, robot_id: str, position: Point, velocity: float = 1.0,
                 current_path: Optional[List[Point]] = None,
                 planned_path: Optional[List[Point]] = None,
                 current_segment: Optional[Tuple[Point, Point]] = None,
                 estimated_arrival_times: Optional[Dict[str, float]] = None,
                 last_updated: float = 0.0):
        self.robot_id = robot_id
        self.position = position
        self.velocity = velocity
        self.current_path = current_path or []
        self.planned_path = planned_path or []
        self.current_segment = current_segment
        self.estimated_arrival_times = estimated_arrival_times or {}
        self.last_updated = last_updated or time.time()

class LocalWorldModel:
    def __init__(self, grid_map: GridMap, robot_id: str):
        self.grid_map = grid_map
        self.robot_id = robot_id
        self.current_position: Point = (0, 0)
        self.target_destination: Optional[Point] = None
        self.current_velocity: float = 1.0
        
        # Peer table: robot_id -> PeerState
        self.peers: Dict[str, PeerState] = {}
        
        # Reservations: segment_id or cell -> (robot_id, timestamp_expire)
        self.reservations: Dict[Point, str] = {}
        
        # Dynamic obstacle positions with last update timestamp
        self.dynamic_obstacles_perceived: Dict[Point, float] = {}

    def update_peer(self, robot_id: str, position: Point, velocity: float = 1.0,
                    current_path: Optional[List[Point]] = None,
                    planned_path: Optional[List[Point]] = None,
                    current_segment: Optional[Tuple[Point, Point]] = None,
                    estimated_arrival_times: Optional[Dict[str, float]] = None):
        if robot_id == self.robot_id:
            return  # Do not record self in peer table
            
        now = time.time()
        self.peers[robot_id] = PeerState(
            robot_id=robot_id,
            position=position,
            velocity=velocity,
            current_path=current_path or [],
            planned_path=planned_path or [],
            current_segment=current_segment,
            estimated_arrival_times=estimated_arrival_times or {},
            last_updated=now
        )

    def prune_stale_peers(self, timeout_seconds: float = 10.0):
        now = time.time()
        stale_ids = [r_id for r_id, peer in self.peers.items() if now - peer.last_updated > timeout_seconds]
        for r_id in stale_ids:
            del self.peers[r_id]

    def add_reservation(self, cell: Point, robot_id: str):
        self.reservations[cell] = robot_id

    def release_reservation(self, cell: Point, robot_id: str):
        if self.reservations.get(cell) == robot_id:
            del self.reservations[cell]

    def is_cell_reserved(self, cell: Point, robot_id: str) -> bool:
        res_owner = self.reservations.get(cell)
        return res_owner is not None and res_owner != robot_id

    def get_all_active_peers(self) -> List[PeerState]:
        return list(self.peers.values())
