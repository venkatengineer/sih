"""
Configuration loader and definitions for independent Edge Robot Agents.
Aligned with Godot 3D Warehouse Digital Twin grid coordinates.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json
import os
from typing import List, Optional, Tuple, Dict, Any, Set


def generate_godot_warehouse_obstacles(width: int = 25, height: int = 20) -> List[Tuple[int, int]]:
    """
    Computes static obstacles matching Godot's WarehouseGridManager:
    - Perimeter boundary walls
    - Storage rack footprints
    """
    obstacles: Set[Tuple[int, int]] = set()

    # 1. Perimeter Walls
    for x in range(width):
        obstacles.add((x, 0))
        obstacles.add((x, height - 1))
    for z in range(height):
        obstacles.add((0, z))
        obstacles.add((width - 1, z))

    # 2. Storage Racks
    rack_x_ranges = [
        (4, 7),    # rx = -14.0
        (9, 12),   # rx = -4.0
        (13, 16),  # rx = 4.0
        (18, 21),  # rx = 14.0
    ]
    rack_z_ranges = [
        (3, 4),    # rz = -12.0
        (6, 7),    # rz = -6.0
        (10, 11),  # rz = 2.0
        (13, 14),  # rz = 8.0
    ]

    for (min_x, max_x) in rack_x_ranges:
        for (min_z, max_z) in rack_z_ranges:
            for x in range(min_x, max_x + 1):
                for z in range(min_z, max_z + 1):
                    if 0 <= x < width and 0 <= z < height:
                        obstacles.add((x, z))

    return sorted(list(obstacles))


@dataclass
class RobotConfig:
    """Configuration parameters for a single RobotAgent instance."""
    robot_id: str = "AMR-01"
    initial_position: Tuple[float, float] = (2.0, 10.0)
    initial_heading: float = 0.0
    network_port: int = 5001
    frontend_port: Optional[int] = 8001  # WebSocket port for Godot / external frontend
    broadcast_host: str = "127.0.0.1"
    peer_endpoints: List[Tuple[str, int]] = field(default_factory=lambda: [
        ("127.0.0.1", 5001),
        ("127.0.0.1", 5002),
        ("127.0.0.1", 5003),
        ("127.0.0.1", 5004),
    ])
    max_speed: float = 1.5  # m/s
    battery_capacity: float = 100.0  # Percentage
    battery_drain_rate: float = 0.04  # % per second of movement
    safety_distance: float = 1.2  # meters / grid units
    loop_rate_hz: float = 10.0  # Control loop frequency
    grid_width: int = 25
    grid_height: int = 20
    static_obstacles: List[Tuple[int, int]] = field(default_factory=lambda: generate_godot_warehouse_obstacles(25, 20))
    default_goal: Optional[Tuple[float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "initial_position": list(self.initial_position),
            "initial_heading": self.initial_heading,
            "network_port": self.network_port,
            "frontend_port": self.frontend_port,
            "broadcast_host": self.broadcast_host,
            "peer_endpoints": [list(ep) for ep in self.peer_endpoints],
            "max_speed": self.max_speed,
            "battery_capacity": self.battery_capacity,
            "battery_drain_rate": self.battery_drain_rate,
            "safety_distance": self.safety_distance,
            "loop_rate_hz": self.loop_rate_hz,
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "static_obstacles": [list(obs) for obs in self.static_obstacles],
            "default_goal": list(self.default_goal) if self.default_goal else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RobotConfig:
        pos = tuple(data.get("initial_position", (2.0, 10.0)))
        peers = [tuple(p) for p in data.get("peer_endpoints", [("127.0.0.1", 5001)])]
        obs = [tuple(o) for o in data.get("static_obstacles", generate_godot_warehouse_obstacles(25, 20))]
        goal = tuple(data["default_goal"]) if data.get("default_goal") else None

        return cls(
            robot_id=data.get("robot_id", "AMR-01"),
            initial_position=(float(pos[0]), float(pos[1])),
            initial_heading=float(data.get("initial_heading", 0.0)),
            network_port=int(data.get("network_port", 5001)),
            frontend_port=int(data["frontend_port"]) if data.get("frontend_port") else None,
            broadcast_host=data.get("broadcast_host", "127.0.0.1"),
            peer_endpoints=peers,
            max_speed=float(data.get("max_speed", 1.5)),
            battery_capacity=float(data.get("battery_capacity", 100.0)),
            battery_drain_rate=float(data.get("battery_drain_rate", 0.04)),
            safety_distance=float(data.get("safety_distance", 1.2)),
            loop_rate_hz=float(data.get("loop_rate_hz", 10.0)),
            grid_width=int(data.get("grid_width", 25)),
            grid_height=int(data.get("grid_height", 20)),
            static_obstacles=obs,
            default_goal=(float(goal[0]), float(goal[1])) if goal else None,
        )


def get_default_configs() -> Dict[str, RobotConfig]:
    """Default configurations for 4 independent robots in Godot warehouse."""
    common_peers = [
        ("127.0.0.1", 5001),
        ("127.0.0.1", 5002),
        ("127.0.0.1", 5003),
        ("127.0.0.1", 5004),
    ]

    return {
        "AMR-01": RobotConfig(
            robot_id="AMR-01",
            initial_position=(2.0, 10.0),    # West Corridor (X=-20, Z=0)
            network_port=5001,
            frontend_port=8001,
            peer_endpoints=common_peers,
            default_goal=(22.0, 10.0),       # Move East along central crossway
        ),
        "AMR-02": RobotConfig(
            robot_id="AMR-02",
            initial_position=(22.0, 10.0),   # East Corridor (X=20, Z=0)
            initial_heading=180.0,
            network_port=5002,
            frontend_port=8002,
            peer_endpoints=common_peers,
            default_goal=(2.0, 10.0),        # Move West (direct head-on / intersection conflict with AMR-01!)
        ),
        "AMR-03": RobotConfig(
            robot_id="AMR-03",
            initial_position=(12.0, 2.0),    # North Central Corridor (X=0, Z=-16)
            initial_heading=90.0,
            network_port=5003,
            frontend_port=8003,
            peer_endpoints=common_peers,
            default_goal=(12.0, 17.0),       # Move South across central intersection (12, 10)
        ),
        "AMR-04": RobotConfig(
            robot_id="AMR-04",
            initial_position=(22.0, 17.0),   # East Corridor South (X=20, Z=14)
            initial_heading=270.0,
            network_port=5004,
            frontend_port=8004,
            peer_endpoints=common_peers,
            default_goal=(22.0, 2.0),        # Move North towards charging bays
        ),
    }


def load_config(robot_id_or_path: str) -> RobotConfig:
    """
    Load RobotConfig either by preset name (e.g. 'AMR-01') or file path (.json/.yaml).
    """
    defaults = get_default_configs()
    if robot_id_or_path.upper() in defaults:
        return defaults[robot_id_or_path.upper()]

    if os.path.exists(robot_id_or_path):
        with open(robot_id_or_path, "r", encoding="utf-8") as f:
            content = f.read()
            if robot_id_or_path.endswith(".json"):
                data = json.loads(content)
                return RobotConfig.from_dict(data)
            elif robot_id_or_path.endswith((".yaml", ".yml")):
                try:
                    import yaml
                    data = yaml.safe_load(content)
                    return RobotConfig.from_dict(data)
                except ImportError:
                    data = json.loads(content)
                    return RobotConfig.from_dict(data)

    cfg = RobotConfig(robot_id=robot_id_or_path)
    return cfg
