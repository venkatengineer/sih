"""
Communication Protocol Definitions for P2P UDP and WebSocket Messaging.
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from world.grid_map import Point

# Message Types
MSG_PEER_STATE = "PEER_STATE"
MSG_ROBOT_INTENT = "ROBOT_INTENT"
MSG_RESERVATION_REQ = "RESERVATION_REQUEST"
MSG_RESERVATION_RESP = "RESERVATION_RESPONSE"

# WebSocket Telemetry Events
EVENT_CONGESTION_UPDATE = "CONGESTION_UPDATE"
EVENT_ROUTE_EVALUATION = "ROUTE_EVALUATION"
EVENT_CONGESTION_ROUTE_DECISION = "CONGESTION_ROUTE_DECISION"
EVENT_DECISION_EVENT = "DECISION_EVENT"
EVENT_FLEET_STATE = "FLEET_STATE"

class MessageFactory:
    @staticmethod
    def create_peer_state(robot_id: str, position: Point, velocity: float,
                           current_path: List[Point], planned_path: List[Point],
                           current_segment: Optional[Tuple[Point, Point]] = None,
                           estimated_arrival_times: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        return {
            "type": MSG_PEER_STATE,
            "robot_id": robot_id,
            "position": list(position),
            "velocity": velocity,
            "current_path": [list(p) for p in current_path],
            "planned_path": [list(p) for p in planned_path],
            "current_segment": [list(current_segment[0]), list(current_segment[1])] if current_segment else None,
            "estimated_arrival_times": estimated_arrival_times or {},
            "timestamp": None  # Populated at send
        }

    @staticmethod
    def create_robot_intent(robot_id: str, current_path: List[Point], planned_path: List[Point],
                            current_segment: Optional[Tuple[Point, Point]] = None,
                            estimated_arrival_times: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        return {
            "type": MSG_ROBOT_INTENT,
            "robot_id": robot_id,
            "current_path": [list(p) for p in current_path],
            "planned_path": [list(p) for p in planned_path],
            "current_segment": [list(current_segment[0]), list(current_segment[1])] if current_segment else None,
            "estimated_arrival_times": estimated_arrival_times or {}
        }

    @staticmethod
    def create_congestion_route_decision(
        robot_id: str,
        current_route_time: float,
        alternate_route_time: Optional[float],
        congestion_level: str,
        robots_on_current_route: int,
        decision: str,  # "CONTINUE", "REROUTE", "NO_ALTERNATE"
        reason: str,
        current_route_distance: Optional[float] = None,
        alternate_route_distance: Optional[float] = None
    ) -> Dict[str, Any]:
        return {
            "event": EVENT_CONGESTION_ROUTE_DECISION,
            "robot_id": robot_id,
            "current_route_time": round(current_route_time, 2),
            "alternate_route_time": round(alternate_route_time, 2) if alternate_route_time is not None else None,
            "current_route_distance": round(current_route_distance, 1) if current_route_distance is not None else None,
            "alternate_route_distance": round(alternate_route_distance, 1) if alternate_route_distance is not None else None,
            "congestion_level": congestion_level,
            "robots_on_current_route": robots_on_current_route,
            "decision": decision,
            "reason": reason
        }

    @staticmethod
    def create_decision_event(robot_id: str, decision_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event": EVENT_DECISION_EVENT,
            "robot_id": robot_id,
            "decision_type": decision_type,
            "details": details
        }

    @staticmethod
    def serialize(msg: Dict[str, Any]) -> bytes:
        return json.dumps(msg).encode('utf-8')

    @staticmethod
    def deserialize(data: bytes) -> Dict[str, Any]:
        return json.loads(data.decode('utf-8'))
