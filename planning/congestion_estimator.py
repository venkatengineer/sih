"""
Decentralized Congestion Estimator.
Analyzes peer positions, path intents, and segment density to estimate congestion levels and delays.
"""

import time
from typing import Dict, List, Set, Tuple, Optional, Any
from world.grid_map import GridMap, Point, Segment
from world.world_model import LocalWorldModel, PeerState
from config import RobotConfig

class SegmentCongestionInfo:
    def __init__(self, segment_id: str, robot_count: int, robot_ids: List[str],
                 estimated_queue_delay: float, average_velocity: float,
                 congestion_level: str, last_updated: float):
        self.segment_id = segment_id
        self.robot_count = robot_count
        self.robot_ids = robot_ids
        self.estimated_queue_delay = estimated_queue_delay
        self.average_velocity = average_velocity
        self.congestion_level = congestion_level
        self.last_updated = last_updated

class CongestionEstimator:
    def __init__(self, config: RobotConfig):
        self.config = config

    def evaluate_segment_congestion(self, segment: Segment, world_model: LocalWorldModel) -> SegmentCongestionInfo:
        p1, p2 = segment
        seg_id = GridMap.undirected_segment_id(segment)
        now = time.time()
        
        occupying_robots: Set[str] = set()
        incoming_robots: Set[str] = set()
        velocities: List[float] = []

        # Check self position / current segment
        if world_model.current_position in (p1, p2):
            occupying_robots.add(world_model.robot_id)
            velocities.append(world_model.current_velocity)

        # Inspect peer state & path intent (Predictive Congestion)
        peers = world_model.get_all_active_peers()
        for peer in peers:
            # 1. Occupying check
            if peer.position in (p1, p2):
                occupying_robots.add(peer.robot_id)
                velocities.append(peer.velocity)
            elif peer.current_segment:
                peer_seg_id = GridMap.undirected_segment_id(peer.current_segment)
                if peer_seg_id == seg_id:
                    occupying_robots.add(peer.robot_id)
                    velocities.append(peer.velocity)

            # 2. Path Intent overlap check (Predictive incoming robots)
            peer_path = peer.current_path or peer.planned_path
            if peer_path:
                peer_segments = GridMap.path_to_segments(peer_path)
                for ps in peer_segments:
                    if GridMap.undirected_segment_id(ps) == seg_id:
                        incoming_robots.add(peer.robot_id)
                        if peer.velocity not in velocities:
                            velocities.append(peer.velocity)
                        break

            # 3. Reservations check
            if world_model.is_cell_reserved(p1, peer.robot_id) or world_model.is_cell_reserved(p2, peer.robot_id):
                incoming_robots.add(peer.robot_id)

        all_associated_robots = list(occupying_robots.union(incoming_robots))
        total_robot_count = len(all_associated_robots)
        
        avg_vel = sum(velocities) / len(velocities) if velocities else self.config.expected_velocity
        if avg_vel <= 0.05:
            avg_vel = 0.5  # Prevent division by zero

        # Determine Congestion Level
        if total_robot_count >= self.config.congestion_high_threshold:
            congestion_level = "HIGH"
        elif total_robot_count >= self.config.congestion_medium_threshold:
            congestion_level = "MEDIUM"
        else:
            congestion_level = "LOW"

        # Calculate Queue & Congestion Delay Penalty
        # Base traversal time for 1 cell segment
        cell_traversal_time = self.config.cell_size_meters / avg_vel
        
        # Additional queue delay scales deterministically with crowding
        # e.g., 0-1 robot: ~0s delay, 2 robots: 1x cell time, 5+ robots: exponential/linear crowding penalty
        if total_robot_count <= 1:
            estimated_queue_delay = 0.0
        else:
            # Deterministic congestion penalty model:
            # queue delay = (count - 1) * cell_traversal_time * congestion_weight + queueing_wait
            queue_length = total_robot_count - 1
            estimated_queue_delay = (queue_length * cell_traversal_time * 1.5) * self.config.congestion_weight

        return SegmentCongestionInfo(
            segment_id=seg_id,
            robot_count=total_robot_count,
            robot_ids=all_associated_robots,
            estimated_queue_delay=estimated_queue_delay,
            average_velocity=avg_vel,
            congestion_level=congestion_level,
            last_updated=now
        )

    def get_route_congestion_summary(self, path: List[Point], world_model: LocalWorldModel) -> Dict[str, Any]:
        segments = GridMap.path_to_segments(path)
        max_robots = 0
        total_congestion_delay = 0.0
        overall_level = "LOW"

        for seg in segments:
            info = self.evaluate_segment_congestion(seg, world_model)
            if info.robot_count > max_robots:
                max_robots = info.robot_count
            total_congestion_delay += info.estimated_queue_delay
            if info.congestion_level == "HIGH":
                overall_level = "HIGH"
            elif info.congestion_level == "MEDIUM" and overall_level != "HIGH":
                overall_level = "MEDIUM"

        return {
            "max_robots_on_segment": max_robots,
            "total_congestion_delay": total_congestion_delay,
            "overall_congestion_level": overall_level
        }
