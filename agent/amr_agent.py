"""
Edge-AI Autonomous Mobile Robot (AMR) Agent.
Executes decentralized lifecycle loop:
Sense -> Localize -> World Update -> P2P Comm -> Safety Check -> Conflict Prediction ->
Congestion Estimation -> Candidate Routes -> Time Estimation -> Decision -> Act -> Learn.
"""

import time
import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Any, Callable
from config import RobotConfig
from world.grid_map import GridMap, Point, Segment
from world.world_model import LocalWorldModel
from communication.protocol import MessageFactory
from communication.p2p import P2PCommunicator
from learning.experience import ExperienceStore
from planning.planner import RoutePlanner
from coordination.safety import SafetyController
from coordination.conflict import ConflictDetector
from coordination.deadlock import DeadlockDetector

logger = logging.getLogger(__name__)

class AMRAgent:
    def __init__(
        self,
        config: RobotConfig,
        grid_map: GridMap,
        p2p_communicator: Optional[P2PCommunicator] = None,
        ws_broadcast_func: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.config = config
        self.grid_map = grid_map
        self.robot_id = config.robot_id
        
        # Subsystems
        self.world_model = LocalWorldModel(grid_map, self.robot_id)
        self.experience_store = ExperienceStore(learning_rate=config.learning_rate)
        self.safety = SafetyController(config)
        self.conflict_detector = ConflictDetector(self.robot_id)
        self.deadlock_detector = DeadlockDetector(self.robot_id)
        
        self.planner = RoutePlanner(
            grid_map=grid_map,
            config=config,
            experience_store=self.experience_store,
            safety_checker=self.safety
        )
        
        self.p2p = p2p_communicator or P2PCommunicator(self.robot_id, config.p2p_port, config.p2p_broadcast_ip)
        self.ws_broadcast_func = ws_broadcast_func
        
        # State
        self.start_position: Point = (0, 0)
        self.current_position: Point = (0, 0)
        self.target_destination: Optional[Point] = None
        self.current_path: List[Point] = []
        self.current_path_index: int = 0
        self.status: str = "IDLE"  # IDLE, MOVING, WAITING, STOPPED
        self.auto_loop: bool = True
        
        self.wait_start_time: float = 0.0
        self.last_step_time: float = time.time()
        self.running: bool = False

        # Setup P2P callback
        self.p2p.message_callback = self._handle_p2p_message

    def _handle_p2p_message(self, msg: Dict[str, Any]):
        msg_type = msg.get("type")
        if msg_type == "PEER_STATE" or msg_type == "ROBOT_INTENT":
            peer_id = msg.get("robot_id")
            if peer_id and peer_id != self.robot_id:
                pos = tuple(msg.get("position", [0, 0]))
                vel = msg.get("velocity", 1.0)
                curr_p = [tuple(p) for p in msg.get("current_path", [])]
                plan_p = [tuple(p) for p in msg.get("planned_path", [])]
                curr_seg = tuple(tuple(p) for p in msg.get("current_segment")) if msg.get("current_segment") else None
                
                self.world_model.update_peer(
                    robot_id=peer_id,
                    position=pos,
                    velocity=vel,
                    current_path=curr_p,
                    planned_path=plan_p,
                    current_segment=curr_seg,
                    estimated_arrival_times=msg.get("estimated_arrival_times", {})
                )

    def set_navigation_goal(self, destination: Point, start_pos: Optional[Point] = None):
        if start_pos is not None:
            self.start_position = start_pos
            self.current_position = start_pos
        elif not hasattr(self, 'start_position') or self.start_position == (0, 0):
            self.start_position = self.current_position

        self.target_destination = destination
        self.world_model.target_destination = destination
        
        # Initial Path Planning
        self.current_path = self.planner.astar.plan_path(self.current_position, destination) or []
        self.current_path_index = 0
        self.status = "MOVING" if self.current_path else "IDLE"
        self._broadcast_intent()

    def _broadcast_intent(self):
        curr_segment = None
        if self.current_path and self.current_path_index < len(self.current_path) - 1:
            curr_segment = (self.current_path[self.current_path_index], self.current_path[self.current_path_index + 1])
            
        msg = MessageFactory.create_peer_state(
            robot_id=self.robot_id,
            position=self.current_position,
            velocity=self.config.expected_velocity,
            current_path=self.current_path,
            planned_path=self.current_path[self.current_path_index:],
            current_segment=curr_segment
        )
        self.p2p.broadcast(msg)

    def step(self) -> Dict[str, Any]:
        """
        Executes one discrete perception-planning-action iteration cycle.
        Returns execution result summary.
        """
        now = time.time()
        
        # 1. SENSE & LOCALIZE
        self.world_model.current_position = self.current_position
        self.world_model.current_velocity = self.config.expected_velocity
        self.world_model.prune_stale_peers()

        if not self.target_destination or self.current_position == self.target_destination:
            if self.auto_loop and self.target_destination and self.start_position != self.target_destination:
                # Loop back to start position and re-navigate continuously
                self.current_position = self.start_position
                self.current_path = self.planner.astar.plan_path(self.current_position, self.target_destination) or []
                self.current_path_index = 0
                self.status = "MOVING"
                self._broadcast_intent()
                return {"status": "LOOP_RESTART", "position": self.current_position}
            else:
                self.status = "IDLE"
                self._broadcast_intent()
                return {"status": "ARRIVED", "position": self.current_position}

        # 2. SAFETY CHECK
        if self.safety.emergency_stop_triggered:
            self.status = "STOPPED"
            return {"status": "EMERGENCY_STOP", "position": self.current_position}

        # 3. CONGESTION-AWARE LEAST-TIME ROUTE SELECTION
        already_waited = (now - self.wait_start_time) if self.status == "WAITING" else 0.0
        
        route_decision = self.planner.select_best_route(
            start=self.current_position,
            goal=self.target_destination,
            current_route=self.current_path,
            current_index=self.current_path_index,
            world_model=self.world_model,
            already_waited_time=already_waited
        )

        decision_type = route_decision["decision"]
        if decision_type == "REROUTE":
            self.current_path = route_decision["best_route"]
            self.current_path_index = 0
            self.status = "MOVING"
            self.wait_start_time = 0.0

        # Broadcast Explainable WebSocket Event
        ws_event = MessageFactory.create_congestion_route_decision(
            robot_id=self.robot_id,
            current_route_time=route_decision["current_route_time"],
            alternate_route_time=route_decision["alternate_route_time"],
            current_route_distance=route_decision.get("current_route_distance"),
            alternate_route_distance=route_decision.get("alternate_route_distance"),
            congestion_level=route_decision["congestion_level"],
            robots_on_current_route=route_decision["robots_on_current_route"],
            decision=decision_type,
            reason=route_decision["reason"]
        )
        if self.ws_broadcast_func:
            self.ws_broadcast_func(ws_event)

        # 4. CONFLICT & DEADLOCK PREDICTION
        if self.current_path and self.current_path_index < len(self.current_path) - 1:
            next_cell = self.current_path[self.current_path_index + 1]
            
            # Check collision or spatial conflict on next cell
            if self.safety.is_collision_imminent(self.current_position, next_cell, self.world_model):
                if self.status != "WAITING":
                    self.status = "WAITING"
                    self.wait_start_time = now
                    
                # Check for Deadlock condition
                if self.deadlock_detector.check_deadlock(self.current_position, has_goal=True):
                    # Force route replan if stalled too long
                    alt_path = self.planner.astar.plan_path(self.current_position, self.target_destination, ignore_dynamic=False)
                    if alt_path and alt_path != self.current_path:
                        self.current_path = alt_path
                        self.current_path_index = 0
                        
                self._broadcast_intent()
                return {"status": "WAITING_CONFLICT", "position": self.current_position, "decision": route_decision}

        # 5. ACT - Advance along path
        if self.current_path and self.current_path_index < len(self.current_path) - 1:
            prev_cell = self.current_position
            self.current_path_index += 1
            self.current_position = self.current_path[self.current_path_index]
            self.status = "MOVING"
            self.wait_start_time = 0.0
            
            step_duration = now - self.last_step_time
            self.last_step_time = now
            
            # 6. LEARN - Record historical edge traversal duration & congestion
            traversal_segment = (prev_cell, self.current_position)
            cong_info = self.planner.congestion_estimator.evaluate_segment_congestion(traversal_segment, self.world_model)
            self.experience_store.record_edge_traversal(
                segment=traversal_segment,
                duration=max(0.5, step_duration),
                robot_count_during_traversal=cong_info.robot_count
            )

        self._broadcast_intent()
        return {"status": self.status, "position": self.current_position, "decision": route_decision}

    async def run_loop(self, update_interval: float = 0.5):
        self.running = True
        while self.running:
            self.step()
            await asyncio.sleep(update_interval)

    def stop(self):
        self.running = False
