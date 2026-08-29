"""
Robot Configuration Module for Edge-AI AMR Fleet.
Defines parameters for decentralized P2P communication, motion, A* path planning,
congestion estimation, reroute thresholds, and experience weights.
"""

from dataclasses import dataclass, field
from typing import Tuple

@dataclass
class RobotConfig:
    # Robot Identification
    robot_id: str = "AMR-01"
    
    # Grid & World Parameters
    grid_width: int = 30
    grid_height: int = 30
    cell_size_meters: float = 1.0
    
    # Motion & Kinematics
    expected_velocity: float = 1.0       # meters/second
    max_velocity: float = 1.5            # meters/second
    reroute_overhead_seconds: float = 2.0  # Time delay penalty associated with switching routes
    
    # P2P Communication
    p2p_port: int = 5005
    p2p_broadcast_ip: str = "255.255.255.255"
    p2p_heartbeat_interval: float = 0.5   # seconds
    
    # WebSocket Visualization Server
    ws_port: int = 8765
    http_port: int = 8080
    
    # Congestion Avoidance & Estimation
    congestion_enabled: bool = True
    congestion_medium_threshold: int = 3   # 3-4 robots -> MEDIUM
    congestion_high_threshold: int = 5     # 5+ robots -> HIGH
    
    # Rerouting Decision & Stability Rules
    reroute_improvement_threshold: float = 0.10  # 10% minimum travel time improvement to trigger reroute
    reroute_cooldown_seconds: float = 5.0        # Cooldown timer to prevent route oscillation
    congestion_update_interval: float = 1.0      # Evaluation loop frequency in seconds
    
    # Cost Estimator Weighting Parameters
    congestion_weight: float = 1.0
    historical_cost_weight: float = 1.0
    reservation_delay_weight: float = 1.0
    conflict_penalty_weight: float = 1.0
    obstacle_penalty_weight: float = 5.0
    
    # Safety & Collision Avoidance
    safety_margin_meters: float = 1.0
    emergency_stop_distance: float = 0.5
    
    # Experience Learning
    learning_rate: float = 0.2
    max_historical_records: int = 100
