"""
RobotAgent - Core autonomous Edge Agent representing a single AMR.
Integrates decentralized task allocation, P2P coordination, deterministic A* planning,
safety shields, and experience learning.
"""

from __future__ import annotations
import asyncio
import logging
import math
import time
from typing import List, Tuple, Optional, Dict, Set, Any, Callable

from edge_robot.core.enums import (
    RobotStatus,
    RobotIntent,
    TaskStatus,
    TaskPriority,
    ConflictAction,
    ObstacleType,
    MessageType,
)
from edge_robot.core.state import RobotState
from edge_robot.config import RobotConfig
from edge_robot.hardware.interfaces import MotorInterface, LidarInterface, CameraInterface
from edge_robot.hardware.mock_hardware import MockMotor, MockLidar, MockCamera
from edge_robot.sensors.interfaces import SensorInterface, SensorObservation
from edge_robot.sensors.mock import MockSensor
from edge_robot.localization.localizer import Localizer
from edge_robot.world.map import LocalWorldModel
from edge_robot.world.obstacle import LocalObstacle
from edge_robot.planning.planner import PathPlanner
from edge_robot.planning.route import RouteUtils
from edge_robot.coordination.priority import PriorityCalculator
from edge_robot.coordination.conflict import (
    ConflictDetector,
    ConflictResolver,
    Conflict,
    ConflictResolution,
)
from edge_robot.coordination.intent import RobotIntentData
from edge_robot.coordination.events import CoordinationEvent
from edge_robot.coordination.reservation import ReservationManager, Reservation
from edge_robot.coordination.deadlock import DeadlockDetector
from edge_robot.communication.network import P2PNetworkNode
from edge_robot.communication.peer import PeerTable
from edge_robot.communication.protocol import (
    NetworkMessage,
    create_state_message,
    create_robot_intent_message,
    create_intent_message,
    create_obstacle_message,
    create_heartbeat_message,
    create_conflict_detected_message,
    create_conflict_resolution_message,
    create_reservation_request_message,
    create_reservation_grant_message,
    create_reservation_release_message,
    create_deadlock_detected_message,
    create_task_announcement_message,
    create_task_bid_message,
    create_task_award_message,
    create_task_release_message,
)
from edge_robot.tasks.task import Task
from edge_robot.tasks.bid import TaskBid
from edge_robot.tasks.cost import BidCostCalculator
from edge_robot.tasks.auction import AuctionManager
from edge_robot.tasks.task_manager import TaskManager
from edge_robot.learning.experience import ExperienceStore, TripRecord
from edge_robot.safety.safety_controller import SafetyController
from edge_robot.gateway.frontend_protocol import (
    FrontendCommand,
    CommandAction,
    FrontendDecisionEvent,
    FrontendConflictEvent,
    FrontendNetworkEvent,
)

logger = logging.getLogger("edge_robot")


class RobotAgent:
    """
    Central RobotAgent class.
    Represents ONE autonomous edge robot with its own independent intelligence,
    local world model, decentralized peer communication, planning, tasks, and safety.
    """

    def __init__(
        self,
        config: RobotConfig,
        motor: Optional[MotorInterface] = None,
        lidar: Optional[LidarInterface] = None,
        camera: Optional[CameraInterface] = None,
        sensor: Optional[SensorInterface] = None,
    ):
        self.config = config
        self.robot_id = config.robot_id

        # 1. State
        self.state = RobotState(
            robot_id=self.robot_id,
            position=config.initial_position,
            heading=config.initial_heading,
            battery=config.battery_capacity,
            status=RobotStatus.IDLE,
            intent=RobotIntent.IDLE,
            priority=50.0,
        )

        # 2. Hardware and Abstraction
        self.motor = motor or MockMotor()
        self.lidar = lidar or MockLidar()
        self.camera = camera or MockCamera()
        self.sensor = sensor or MockSensor()

        # 3. Localization
        self.localizer = Localizer(
            initial_x=config.initial_position[0],
            initial_y=config.initial_position[1],
            initial_heading=config.initial_heading,
        )

        # 4. Local World Model
        self.world = LocalWorldModel(
            width=config.grid_width,
            height=config.grid_height,
            static_obstacles=config.static_obstacles,
        )

        # 5. Planning
        self.planner = PathPlanner(self.world)

        # 6. Safety Controller
        self.safety = SafetyController(self.motor, min_safe_distance=config.safety_distance)

        # 7. Coordination & Reservations
        self.reservation_manager = ReservationManager(default_ttl=3.0)

        # 8. Communication & Peer Table
        self.peer_table = PeerTable(heartbeat_timeout=3.0)
        self.network = P2PNetworkNode(
            robot_id=self.robot_id,
            host=config.broadcast_host,
            port=config.network_port,
            peer_endpoints=config.peer_endpoints,
        )

        # 9. Learning
        self.experience_store = ExperienceStore(self.robot_id)

        # 10. Decentralized Task Management
        self.cost_calculator = BidCostCalculator(
            planner=self.planner,
            world=self.world,
            experience_store=self.experience_store,
            minimum_task_battery=20.0,
            nominal_speed=config.max_speed,
        )
        self.task_manager = TaskManager(
            robot_id=self.robot_id,
            cost_calculator=self.cost_calculator,
            auction_manager=AuctionManager(default_timeout_seconds=0.8),
        )
        self.task_manager.on_task_event(self._on_task_event_forwarder)

        # 11. Output Callbacks (for Frontend Gateway and Observers)
        self._command_callbacks: List[Callable[[FrontendCommand], None]] = []
        self._state_callbacks: List[Callable[[RobotState], None]] = []
        self._path_callbacks: List[Callable[[List[Tuple[int, int]]], None]] = []
        self._event_callbacks: List[Callable[[Any], None]] = []

        # Runtime Control Loop Variables
        self.is_running = False
        self._loop_task: Optional[asyncio.Task] = None
        self.trip_start_time: Optional[float] = None
        self.trip_start_pos: Optional[Tuple[int, int]] = None
        self.trip_reroutes: int = 0
        self.trip_obstacles: int = 0
        self.total_waiting_time: float = 0.0
        self.last_step_time: float = time.time()
        self.sequence_number: int = 0
        self.coordination_events: List[CoordinationEvent] = []
        self.latest_conflict: Optional[Conflict] = None
        self.latest_resolution: Optional[ConflictResolution] = None
        self._known_connected_peers: Set[str] = set()
        self._active_auction_timers: Dict[str, asyncio.Task] = {}

        logger.info(f"[{self.robot_id}] INITIALIZED at pos={self.state.position} port={config.network_port}")

    # =========================================================================
    # Callback Registration Hooks
    # =========================================================================

    def on_command(self, callback: Callable[[FrontendCommand], None]) -> None:
        self._command_callbacks.append(callback)

    def on_state(self, callback: Callable[[RobotState], None]) -> None:
        self._state_callbacks.append(callback)

    def on_path(self, callback: Callable[[List[Tuple[int, int]]], None]) -> None:
        self._path_callbacks.append(callback)

    def on_event(self, callback: Callable[[Any], None]) -> None:
        self._event_callbacks.append(callback)

    def _emit_command(self, action: CommandAction, target: Optional[Tuple[float, float]] = None, speed: float = 1.5) -> None:
        cmd = FrontendCommand(robot_id=self.robot_id, action=action, target=target, speed=speed)
        for cb in self._command_callbacks:
            try:
                cb(cmd)
            except Exception as e:
                logger.debug(f"Error in on_command callback: {e}")

    def _emit_state(self) -> None:
        for cb in self._state_callbacks:
            try:
                cb(self.state)
            except Exception as e:
                logger.debug(f"Error in on_state callback: {e}")

    def _emit_path(self, path: List[Tuple[int, int]]) -> None:
        for cb in self._path_callbacks:
            try:
                cb(path)
            except Exception as e:
                logger.debug(f"Error in on_path callback: {e}")

    def _emit_event(self, event: str, reason: str, peer: Optional[str] = None, node: Optional[Tuple[int, int]] = None) -> None:
        evt = FrontendDecisionEvent(
            robot_id=self.robot_id,
            event=event,
            reason=reason,
            peer=peer,
            node=node,
        )
        for cb in self._event_callbacks:
            try:
                cb(evt)
            except Exception as e:
                logger.debug(f"Error in on_event callback: {e}")

    def _emit_conflict_event(self, peer: str, node: Tuple[int, int], resolution: str) -> None:
        evt = FrontendConflictEvent(
            robot_id=self.robot_id,
            peer=peer,
            node=node,
            resolution=resolution,
        )
        for cb in self._event_callbacks:
            try:
                cb(evt)
            except Exception as e:
                logger.debug(f"Error in on_event callback: {e}")

    def _emit_network_event(self, event_type: str, peer: str) -> None:
        evt = FrontendNetworkEvent(
            robot_id=self.robot_id,
            event=event_type,
            peer=peer,
        )
        for cb in self._event_callbacks:
            try:
                cb(evt)
            except Exception as e:
                logger.debug(f"Error in on_event callback: {e}")

    def _on_task_event_forwarder(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Forward task manager event as an explainable decision event."""
        reason = f"Task {payload.get('task_id')}: {event_name}"
        if "winner_id" in payload:
            reason += f" -> Winner: {payload['winner_id']}"
        elif "cost" in payload:
            reason += f" -> Bid: {payload['cost']}"
        self._emit_event(event=event_name, reason=reason)

    # =========================================================================
    # Task Submission & Auction Scheduling
    # =========================================================================

    def submit_task(
        self,
        pickup: Tuple[int, int],
        dropoff: Tuple[int, int],
        priority: int = TaskPriority.NORMAL.value,
        task_id: Optional[str] = None,
        deadline: Optional[float] = None,
    ) -> Task:
        """
        Public API: originate and announce a new transport task to the P2P fleet.
        """
        task = self.task_manager.create_task(
            pickup=pickup,
            dropoff=dropoff,
            priority=priority,
            task_id=task_id,
            deadline=deadline,
        )
        msg = self.task_manager.announce_task(task, auction_round=task.auction_round)
        self.network.broadcast(msg)

        # Self-bid
        _, bid = self.task_manager.handle_task_announcement(
            task_dict=task.to_dict(),
            auction_round=task.auction_round,
            current_position=self.state.position,
            battery_percent=self.state.battery,
            known_peer_positions=[p.position for p in self.peer_table.get_all_active_peers().values()],
        )
        if bid and bid.is_valid:
            bid_msg = create_task_bid_message(self.robot_id, bid)
            self.network.broadcast(bid_msg)

        # Schedule auction finalization
        self._schedule_auction_finalization(task.task_id, task.auction_round)
        return task

    def _schedule_auction_finalization(self, task_id: str, auction_round: int, timeout: float = 0.8) -> None:
        """Schedule an asynchronous timer to finalize task auction and award winner."""
        timer_key = f"{task_id}_{auction_round}"
        if timer_key in self._active_auction_timers:
            return

        async def _finalize_timer():
            await asyncio.sleep(timeout)
            winner_id, task = self.task_manager.finalize_auction(task_id)
            if winner_id:
                logger.info(f"[{self.robot_id}] AUCTION_FINALIZED task={task_id} winner={winner_id} round={auction_round}")
                award_msg = create_task_award_message(self.robot_id, task_id, winner_id, auction_round)
                self.network.broadcast(award_msg)
            self._active_auction_timers.pop(timer_key, None)

        self._active_auction_timers[timer_key] = asyncio.create_task(_finalize_timer())

    def get_current_task(self) -> Optional[Task]:
        return self.task_manager.get_active_task()

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        t = self.task_manager.get_task(task_id)
        return t.status if t else None

    # =========================================================================
    # External Control & Observation Methods (Godot Integration)
    # =========================================================================

    def update_position(self, position: Tuple[float, float], heading: Optional[float] = None) -> None:
        """Receive actual visual robot position observation from Godot simulation."""
        self.state.position = (round(position[0], 2), round(position[1], 2))
        if heading is not None:
            self.state.heading = round(heading, 1)
        self.localizer.set_pose(self.state.position[0], self.state.position[1], self.state.heading)

        # Check if next waypoint was reached
        if self.state.current_path:
            curr_grid = (int(round(self.state.position[0])), int(round(self.state.position[1])))
            if curr_grid == self.state.current_path[0]:
                self.state.current_path.pop(0)
                if self.state.current_path:
                    self.state.next_node = self.state.current_path[0]
                    self._emit_path(self.state.current_path)
                else:
                    self.state.next_node = None
                    if self.state.goal and self.state.distance_to(self.state.goal) < 0.4:
                        self._handle_goal_reached()

    def update_goal(self, goal: Tuple[float, float]) -> None:
        self.set_goal(goal)

    def update_obstacles(self, obstacles: List[Dict[str, Any]]) -> None:
        for obs_dict in obstacles:
            pos = tuple(obs_dict.get("position", (0.0, 0.0)))
            obs = LocalObstacle(
                obstacle_id=str(obs_dict.get("id", f"obs-{int(time.time()*1000)}")),
                obstacle_type=ObstacleType.DYNAMIC_OBSTACLE,
                position=(float(pos[0]), float(pos[1])),
                radius=float(obs_dict.get("radius", 0.5)),
                confidence=float(obs_dict.get("confidence", 1.0)),
                source="godot_observation",
                expires_at=time.time() + 8.0,
            )
            self.world.add_obstacle(obs)
            self.trip_obstacles += 1
            self.experience_store.record_obstacle_encounter(
                (int(round(obs.position[0])), int(round(obs.position[1])))
            )

    def update_world(
        self,
        obstacles: Optional[List[Dict[str, Any]]] = None,
        robots: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if obstacles:
            self.update_obstacles(obstacles)
        if robots:
            for r in robots:
                r_id = r.get("robot_id")
                pos = r.get("position")
                if r_id and pos and r_id != self.robot_id:
                    self.world.update_peer(r_id, (float(pos[0]), float(pos[1])))

    def assign_task(self, task: Task) -> None:
        """Assign a task directly."""
        self.task_manager.assign_task(task)
        self.state.current_task = task.task_id
        self.update_goal(task.pickup)
        self._emit_event(
            event="TASK_ASSIGNED",
            reason=f"Task {task.task_id} assigned (pickup={task.pickup} dropoff={task.dropoff})",
        )

    def reset(
        self,
        initial_position: Optional[Tuple[float, float]] = None,
        initial_heading: Optional[float] = None,
    ) -> None:
        pos = initial_position or self.config.initial_position
        heading = initial_heading if initial_heading is not None else self.config.initial_heading
        self.state.position = pos
        self.state.heading = heading
        self.state.velocity = 0.0
        self.state.battery = self.config.battery_capacity
        self.state.goal = None
        self.state.current_path.clear()
        self.state.next_node = None
        self.state.status = RobotStatus.IDLE
        self.state.intent = RobotIntent.IDLE
        self.state.waiting_time = 0.0
        self.localizer.set_pose(pos[0], pos[1], heading)
        self.world.dynamic_obstacles.clear()
        self._emit_state()
        logger.info(f"[{self.robot_id}] RESET to pos={pos}")

    def set_goal(self, goal: Tuple[float, float]) -> None:
        self.state.goal = (round(goal[0], 2), round(goal[1], 2))
        self.state.current_path.clear()
        self.state.next_node = None
        self.transition_to(RobotStatus.PLANNING, RobotIntent.MOVE)
        logger.info(f"[{self.robot_id}] GOAL_SET goal={self.state.goal}")
        self._emit_event(
            event="GOAL_SET",
            reason=f"Navigating to {self.state.goal}",
            node=(int(round(goal[0])), int(round(goal[1]))),
        )

    def transition_to(self, new_status: RobotStatus, new_intent: Optional[RobotIntent] = None) -> None:
        old_status = self.state.status
        self.state.status = new_status
        if new_intent:
            self.state.intent = new_intent
        self.state.timestamp = time.time()
        if old_status != new_status:
            logger.info(f"[{self.robot_id}] STATE_TRANSITION {old_status.value} -> {new_status.value} (intent={self.state.intent.value})")

    # =========================================================================
    # Continuous Control Loop Pipeline
    # =========================================================================

    async def start(self) -> None:
        if self.is_running:
            return

        self.is_running = True
        await self.network.start()
        self.last_step_time = time.time()

        if self.config.default_goal:
            self.set_goal(self.config.default_goal)

        self._loop_task = asyncio.create_task(self._control_loop())
        logger.info(f"[{self.robot_id}] CONTROL_LOOP STARTED at {self.config.loop_rate_hz} Hz")

    async def stop(self) -> None:
        self.is_running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        for t in self._active_auction_timers.values():
            t.cancel()
        await self.safety.force_stop()
        await self.network.stop()
        self.transition_to(RobotStatus.OFFLINE, RobotIntent.STOP)
        self._emit_command(CommandAction.STOP)
        logger.info(f"[{self.robot_id}] AGENT STOPPED")

    async def _control_loop(self) -> None:
        """
        Asynchronous continuous control loop:
        SENSE -> LOCALIZATION -> WORLD_UPDATE -> COMMUNICATE -> SAFETY -> CONFLICT -> PLAN -> DECIDE -> ACT -> LEARN
        """
        interval = 1.0 / max(1.0, self.config.loop_rate_hz)

        while self.is_running:
            start_time = time.time()
            delta_time = start_time - self.last_step_time
            self.last_step_time = start_time

            try:
                # 1. SENSE
                obs = self.sensor_update()

                # 2. LOCALIZATION
                self.localization_update()

                # 3. WORLD MODEL UPDATE
                self.world_update(obs)

                # 4. COMMUNICATE (Receive peer messages & broadcast state)
                self.receive_peer_messages()
                self.broadcast_state()

                # 5. COORDINATE ACTIVE TASK NAVIGATION GOAL
                self._update_task_navigation()

                # 6. SAFETY CHECK (Deterministic override)
                is_safe = await self.check_safety()

                if is_safe:
                    # 7. CONFLICT PREDICTION & RESOLUTION
                    conflict_action = self.check_conflicts()

                    # 8. PATH PLANNING IF REQUIRED
                    self.plan_if_required()

                    # 9. DECIDE NEXT ACTION
                    action = self.choose_action(conflict_action)

                    # 10. EXECUTE ACTION
                    await self.execute_action(action, delta_time)

                # 11. UPDATE EXPERIENCE & EMIT STATE
                self.update_experience()
                self._emit_state()

            except Exception as e:
                logger.error(f"[{self.robot_id}] Exception in control loop: {e}", exc_info=True)

            elapsed = time.time() - start_time
            sleep_time = max(0.005, interval - elapsed)
            await asyncio.sleep(sleep_time)

    # =========================================================================
    # Step-by-Step Control Pipeline Methods
    # =========================================================================

    def sensor_update(self) -> SensorObservation:
        return self.sensor.get_observation()

    def localization_update(self) -> None:
        x, y, heading = self.localizer.get_pose()
        self.state.position = (x, y)
        self.state.heading = heading

    def world_update(self, obs: SensorObservation) -> None:
        self.world.clean_expired()

        for obs_data in obs.obstacles:
            local_obs = LocalObstacle(
                obstacle_id=obs_data.obstacle_id,
                obstacle_type=obs_data.obstacle_type,
                position=obs_data.position,
                confidence=obs_data.confidence,
                source=obs_data.source,
                expires_at=time.time() + 8.0,
            )
            self.world.add_obstacle(local_obs)
            self.trip_obstacles += 1
            self.experience_store.record_obstacle_encounter(
                (int(round(obs_data.position[0])), int(round(obs_data.position[1])))
            )
            msg = create_obstacle_message(
                robot_id=self.robot_id,
                obstacle_id=obs_data.obstacle_id,
                obstacle_type=obs_data.obstacle_type.value,
                position=obs_data.position,
                distance=obs_data.distance,
            )
            self.network.broadcast(msg)

        dist_to_goal = self.state.distance_to(self.state.goal) if self.state.goal else 10.0
        self.state.priority = PriorityCalculator.calculate_priority(
            task_priority=50,
            waiting_time_s=self.state.waiting_time,
            battery_percent=self.state.battery,
            distance_to_goal=dist_to_goal,
        )

    def receive_peer_messages(self) -> None:
        """Process incoming P2P messages from independent peer processes."""
        incoming = self.network.get_incoming_messages()
        for msg, addr in incoming:
            if msg.sender_id == self.robot_id:
                continue

            if msg.sender_id not in self._known_connected_peers:
                self._known_connected_peers.add(msg.sender_id)
                self._emit_network_event("PEER_CONNECTED", msg.sender_id)
                logger.info(f"[{self.robot_id}] P2P: {self.robot_id} ↔ {msg.sender_id} connected")

            if msg.type == MessageType.ROBOT_STATE:
                try:
                    peer_state = RobotState.from_dict(msg.payload)
                    self.peer_table.update_peer(peer_state, endpoint=addr)
                    self.world.update_peer(
                        robot_id=peer_state.robot_id,
                        position=peer_state.position,
                        next_node=peer_state.next_node,
                    )
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Failed parsing peer state: {e}")

            elif msg.type == MessageType.ROBOT_INTENT or msg.type == MessageType.INTENT:
                try:
                    intent_data = RobotIntentData.from_dict(msg.payload)
                    self.peer_table.update_peer_intent(intent_data, endpoint=addr)
                    self.world.update_peer(
                        robot_id=intent_data.robot_id,
                        position=intent_data.position,
                        next_node=intent_data.next_waypoint,
                    )
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Failed parsing peer intent: {e}")

            elif msg.type in (MessageType.RESERVATION_GRANT, MessageType.RESERVATION_REQUEST):
                try:
                    res = Reservation.from_dict(msg.payload)
                    self.reservation_manager.register_peer_reservation(res)
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Failed parsing reservation: {e}")

            elif msg.type == MessageType.RESERVATION_RELEASE:
                try:
                    node = tuple(msg.payload.get("node", (0, 0)))
                    self.reservation_manager.release_reservation(node, msg.sender_id)
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Failed parsing reservation release: {e}")

            elif msg.type == MessageType.OBSTACLE:
                try:
                    p = msg.payload
                    pos = tuple(p["position"])
                    obs = LocalObstacle(
                        obstacle_id=p["obstacle_id"],
                        obstacle_type=ObstacleType(p.get("obstacle_type", ObstacleType.DYNAMIC_OBSTACLE.value)),
                        position=(float(pos[0]), float(pos[1])),
                        source="peer_broadcast",
                        expires_at=time.time() + 6.0,
                    )
                    self.world.add_obstacle(obs)
                except Exception:
                    pass

            elif msg.type == MessageType.HEARTBEAT:
                self.peer_table.record_heartbeat(msg.sender_id, endpoint=addr)

            # --- Task Auction Protocol Messages ---
            elif msg.type in (MessageType.TASK_ANNOUNCEMENT, MessageType.TASK_ANNOUNCE):
                try:
                    task_dict = msg.payload.get("task", msg.payload)
                    round_num = int(msg.payload.get("auction_round", 1))
                    _, bid = self.task_manager.handle_task_announcement(
                        task_dict=task_dict,
                        auction_round=round_num,
                        current_position=self.state.position,
                        battery_percent=self.state.battery,
                        known_peer_positions=[p.position for p in self.peer_table.get_all_active_peers().values()],
                    )
                    if bid and bid.is_valid:
                        bid_msg = create_task_bid_message(self.robot_id, bid)
                        self.network.broadcast(bid_msg)

                    self._schedule_auction_finalization(task_dict["task_id"], round_num)
                except Exception as e:
                    logger.error(f"[{self.robot_id}] Error handling task announcement: {e}")

            elif msg.type == MessageType.TASK_BID:
                try:
                    self.task_manager.handle_incoming_bid(msg.payload)
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Error handling task bid: {e}")

            elif msg.type in (MessageType.TASK_AWARD, MessageType.TASK_ASSIGN):
                try:
                    t_id = msg.payload["task_id"]
                    w_id = msg.payload["winner_id"]
                    r_num = int(msg.payload.get("auction_round", 1))
                    self.task_manager.handle_task_award(t_id, w_id, r_num)
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Error handling task award: {e}")

            elif msg.type == MessageType.TASK_RELEASE:
                try:
                    t_id = msg.payload["task_id"]
                    new_round = int(msg.payload.get("new_round", 2))
                    task = self.task_manager.get_task(t_id)
                    if task:
                        task.auction_round = new_round
                        task.assigned_robot = None
                        task.transition_to(TaskStatus.REASSIGNING)
                        # Bid in re-auction
                        _, bid = self.task_manager.handle_task_announcement(
                            task_dict=task.to_dict(),
                            auction_round=new_round,
                            current_position=self.state.position,
                            battery_percent=self.state.battery,
                            known_peer_positions=[p.position for p in self.peer_table.get_all_active_peers().values()],
                        )
                        if bid and bid.is_valid:
                            self.network.broadcast(create_task_bid_message(self.robot_id, bid))
                        self._schedule_auction_finalization(t_id, new_round)
                except Exception as e:
                    logger.debug(f"[{self.robot_id}] Error handling task release: {e}")

        # Prune timed-out peers & detect offline peer task recovery
        stale_peers = self.peer_table.prune_stale_peers()
        for p_id in stale_peers:
            logger.warning(f"[{self.robot_id}] PEER_TIMEOUT peer={p_id} marked offline")
            self.world.remove_peer(p_id)
            self.reservation_manager.release_all_for_robot(p_id)
            if p_id in self._known_connected_peers:
                self._known_connected_peers.remove(p_id)
                self._emit_network_event("PEER_TIMEOUT", p_id)

            # Fault Tolerance: Re-auction tasks held by the dead peer
            reassigned = self.task_manager.handle_peer_offline(p_id)
            for r_task in reassigned:
                release_msg = create_task_release_message(
                    robot_id=self.robot_id,
                    task_id=r_task.task_id,
                    reason=f"Peer {p_id} offline",
                    new_round=r_task.auction_round,
                )
                self.network.broadcast(release_msg)
                # Participate in re-auction
                _, bid = self.task_manager.handle_task_announcement(
                    task_dict=r_task.to_dict(),
                    auction_round=r_task.auction_round,
                    current_position=self.state.position,
                    battery_percent=self.state.battery,
                    known_peer_positions=[p.position for p in self.peer_table.get_all_active_peers().values()],
                )
                if bid and bid.is_valid:
                    self.network.broadcast(create_task_bid_message(self.robot_id, bid))
                self._schedule_auction_finalization(r_task.task_id, r_task.auction_round)

    def broadcast_state(self) -> None:
        self.sequence_number += 1
        curr_grid = (int(round(self.state.position[0])), int(round(self.state.position[1])))
        dist_to_next = self.state.distance_to(self.state.next_node) if self.state.next_node else 0.0
        eta = dist_to_next / max(0.5, self.config.max_speed)

        # 1. State broadcast
        msg_state = create_state_message(
            robot_id=self.robot_id,
            position=self.state.position,
            heading=self.state.heading,
            velocity=self.state.velocity,
            battery=self.state.battery,
            status=self.state.status,
            intent=self.state.intent,
            priority=self.state.priority,
            current_path=self.state.current_path,
            next_node=self.state.next_node,
            current_task=self.state.current_task,
        )
        self.network.broadcast(msg_state)

        # 2. Rich Intent broadcast
        vel_2d = (
            self.state.velocity * math.cos(math.radians(self.state.heading)),
            self.state.velocity * math.sin(math.radians(self.state.heading)),
        )
        msg_intent = create_robot_intent_message(
            robot_id=self.robot_id,
            position=self.state.position,
            velocity=vel_2d,
            current_cell=curr_grid,
            path=self.state.current_path,
            next_waypoint=self.state.next_node,
            eta=eta,
            priority=self.state.priority,
            task_id=self.state.current_task,
            status=self.state.status.value,
            sequence=self.sequence_number,
        )
        self.network.broadcast(msg_intent)

    def _update_task_navigation(self) -> None:
        """Synchronize active transport task waypoint transitions."""
        active_task = self.task_manager.get_active_task()
        if active_task:
            self.state.current_task = active_task.task_id
            target = self.task_manager.get_next_navigation_target(self.state.position)
            if target:
                target_f = (float(target[0]), float(target[1]))
                if self.state.goal != target_f:
                    self.set_goal(target_f)
            else:
                # Task completed
                if self.state.goal is None and self.state.status != RobotStatus.IDLE:
                    self.transition_to(RobotStatus.IDLE, RobotIntent.IDLE)
        else:
            if not self.config.default_goal and not self.state.current_path:
                self.state.current_task = None

    async def check_safety(self) -> bool:
        min_dist = self.world.get_nearest_obstacle_distance(self.state.position)
        is_safe = (min_dist > self.config.safety_distance)

        if not is_safe and self.state.status == RobotStatus.MOVING:
            await self.safety.force_stop()
            self.transition_to(RobotStatus.EMERGENCY_STOP, RobotIntent.STOP)
            logger.warning(f"[{self.robot_id}] SAFETY_STOP min_obstacle_distance={min_dist:.2f}m <= {self.config.safety_distance}m")
            self.state.is_safe = False
            self._emit_command(CommandAction.EMERGENCY_STOP)
            self._emit_event(
                event="SAFETY_STOP",
                reason=f"Obstacle dangerously close ({min_dist:.2f}m <= {self.config.safety_distance}m)",
            )
            return False

        self.state.is_safe = is_safe
        return True

    def check_conflicts(self) -> ConflictAction:
        active_peers = self.peer_table.get_all_active_peers()
        active_intents = self.peer_table.get_all_active_intents()

        # 1. Deadlock Detection via Wait-For Graph
        deadlock = DeadlockDetector.evaluate_deadlock(self.state, active_peers, active_intents)
        if deadlock:
            if deadlock.victim_robot_id == self.robot_id:
                logger.warning(f"[{self.robot_id}] DEADLOCK_DETECTED cycle={deadlock.cycle} -> Self is lowest priority victim -> REROUTING")
                if self.state.next_node:
                    self.reservation_manager.release_reservation(self.state.next_node, self.robot_id)
                self._emit_event(
                    event="DEADLOCK_RECOVERY",
                    reason=f"Deadlock cycle {deadlock.cycle} broken -> Rerouting",
                )
                return ConflictAction.REROUTE
            else:
                logger.info(f"[{self.robot_id}] DEADLOCK_DETECTED cycle={deadlock.cycle} -> Victim is {deadlock.victim_robot_id} -> WAITING")
                return ConflictAction.WAIT

        # 2. Check active reservations on next node
        if self.state.next_node:
            peer_res = self.reservation_manager.is_node_reserved_by_other(self.state.next_node, self.robot_id)
            if peer_res and peer_res.priority >= self.state.priority:
                reason = f"Zone {self.state.next_node} reserved by {peer_res.robot_id} (priority {peer_res.priority:.1f} >= {self.state.priority:.1f})"
                logger.info(f"[{self.robot_id}] RESERVATION_WAIT: {reason}")
                self._emit_event(event="WAIT", reason=reason, peer=peer_res.robot_id, node=self.state.next_node)
                return ConflictAction.WAIT

        # 3. Predictive Spatio-Temporal Conflict Detection
        conflicts = ConflictDetector.detect_conflicts(
            self_state=self.state,
            peer_states=active_peers,
            peer_intents=active_intents,
            safe_distance=self.config.safety_distance,
        )

        if not conflicts:
            self.latest_conflict = None
            self.latest_resolution = None
            return ConflictAction.PROCEED

        conflict = conflicts[0]
        resolution = ConflictResolver.resolve_conflict(self.robot_id, conflict)
        self.latest_conflict = conflict
        self.latest_resolution = resolution

        # Manage reservation based on resolution
        if resolution.action == ConflictAction.PROCEED:
            if conflict.contested_node:
                self.reservation_manager.create_reservation(self.robot_id, conflict.contested_node, self.state.priority)
                self.network.broadcast(create_reservation_grant_message(self.robot_id, conflict.contested_node, self.state.priority))
        else:
            if conflict.contested_node:
                self.reservation_manager.release_reservation(conflict.contested_node, self.robot_id)

        logger.info(
            f"[{self.robot_id}] CONFLICT_DETECTED peer={conflict.peer_id} "
            f"type={conflict.conflict_type} node={conflict.contested_node} safe_wait={conflict.safe_wait_node} "
            f"DECISION={resolution.action.value} ({resolution.reason})"
        )

        self._emit_event(
            event=resolution.action.value,
            reason=resolution.reason,
            peer=conflict.peer_id,
            node=conflict.contested_node,
        )
        self._emit_conflict_event(
            peer=conflict.peer_id,
            node=conflict.contested_node,
            resolution=f"{resolution.yielding_id}_YIELDS",
        )

        return resolution.action

    def plan_if_required(self) -> None:
        if not self.state.goal:
            return

        curr_pos = self.state.position
        curr_grid = (int(round(curr_pos[0])), int(round(curr_pos[1])))
        goal_grid = (int(round(self.state.goal[0])), int(round(self.state.goal[1])))

        if self.state.distance_to(self.state.goal) < 0.4:
            if self.state.status != RobotStatus.IDLE:
                self._handle_goal_reached()
            return

        if not self.state.current_path:
            path = self.planner.plan(start=curr_pos, goal=self.state.goal)
            if path:
                self.state.current_path = path
                self.state.next_node = path[1] if len(path) > 1 else path[0]
                self.transition_to(RobotStatus.MOVING, RobotIntent.MOVE)
                self.trip_start_time = time.time()
                self.trip_start_pos = curr_grid
                logger.info(f"[{self.robot_id}] PATH_PLANNED length={len(path)} waypoints={path[:5]}...")
                self._emit_path(self.state.current_path)
            else:
                self.transition_to(RobotStatus.BLOCKED, RobotIntent.WAIT)
                logger.warning(f"[{self.robot_id}] NO_PATH_FOUND from {curr_grid} to {goal_grid}")
                # If active task route is completely blocked, fail and release task
                if self.task_manager.active_task:
                    failed = self.task_manager.fail_current_task(reason=f"No walkable path to {goal_grid}")
                    if failed:
                        self.network.broadcast(create_task_release_message(
                            robot_id=self.robot_id,
                            task_id=failed.task_id,
                            reason="No walkable path",
                            new_round=failed.auction_round,
                        ))
            return

        if not RouteUtils.is_path_valid(self.state.current_path, self.world):
            logger.warning(f"[{self.robot_id}] PATH_INVALIDATED by new obstacle -> Replanning...")
            self.trip_reroutes += 1
            new_path = self.planner.plan(start=curr_pos, goal=self.state.goal)
            if new_path:
                self.state.current_path = new_path
                self.state.next_node = new_path[1] if len(new_path) > 1 else new_path[0]
                self.transition_to(RobotStatus.MOVING, RobotIntent.MOVE)
                logger.info(f"[{self.robot_id}] ROUTE_REPLANNED length={len(new_path)} waypoints={new_path[:5]}...")
                self._emit_path(self.state.current_path)
                self._emit_event(
                    event="REROUTE",
                    reason=f"Path invalidated by obstacle -> replanned to {self.state.goal}",
                    node=self.state.next_node,
                )
            else:
                self.transition_to(RobotStatus.BLOCKED, RobotIntent.WAIT)
                logger.warning(f"[{self.robot_id}] REPLAN_BLOCKED No alternative path to {goal_grid}")
                if self.task_manager.active_task:
                    failed = self.task_manager.fail_current_task(reason="Replanning blocked")
                    if failed:
                        self.network.broadcast(create_task_release_message(
                            robot_id=self.robot_id,
                            task_id=failed.task_id,
                            reason="Replanning blocked",
                            new_round=failed.auction_round,
                        ))

    def choose_action(self, conflict_action: ConflictAction) -> str:
        if self.state.status in (RobotStatus.IDLE, RobotStatus.OFFLINE, RobotStatus.BLOCKED):
            return "STOP"

        if conflict_action == ConflictAction.REROUTE:
            return "REROUTE"
        elif conflict_action == ConflictAction.YIELD:
            return "YIELD"
        elif conflict_action == ConflictAction.WAIT:
            return "WAIT"
        elif conflict_action == ConflictAction.STOP:
            return "STOP"

        return "MOVE"

    async def execute_action(self, action: str, delta_time: float) -> None:
        if action == "STOP":
            await self.safety.force_stop()
            self.state.velocity = 0.0
            self._emit_command(CommandAction.STOP)
            return

        if action in ("YIELD", "WAIT"):
            await self.safety.force_stop()
            self.state.velocity = 0.0
            self.state.waiting_time += delta_time
            self.total_waiting_time += delta_time
            new_status = RobotStatus.YIELDING if action == "YIELD" else RobotStatus.WAITING
            new_intent = RobotIntent.YIELD if action == "YIELD" else RobotIntent.WAIT
            self.transition_to(new_status, new_intent)
            cmd_act = CommandAction.YIELD if action == "YIELD" else CommandAction.WAIT
            self._emit_command(cmd_act, target=self.state.position)
            return

        if action == "REROUTE":
            await self.safety.force_stop()
            self.state.velocity = 0.0
            self.transition_to(RobotStatus.REROUTING, RobotIntent.REROUTE)
            self.trip_reroutes += 1

            avoid_nodes: Set[Tuple[int, int]] = set()
            if self.state.next_node:
                avoid_nodes.add(self.state.next_node)

            new_path = self.planner.plan(
                start=self.state.position,
                goal=self.state.goal or self.state.position,
                avoid_nodes=avoid_nodes,
            )
            if new_path:
                self.state.current_path = new_path
                self.state.next_node = new_path[1] if len(new_path) > 1 else new_path[0]
                self.transition_to(RobotStatus.MOVING, RobotIntent.MOVE)
                logger.info(f"[{self.robot_id}] REROUTE_SUCCESS new_path_len={len(new_path)}")
                self._emit_path(self.state.current_path)
                self._emit_command(
                    CommandAction.MOVE,
                    target=(float(self.state.next_node[0]), float(self.state.next_node[1])),
                    speed=self.config.max_speed,
                )
            else:
                logger.warning(f"[{self.robot_id}] REROUTE_FAILED yielding instead")
                self.transition_to(RobotStatus.YIELDING, RobotIntent.YIELD)
                self._emit_command(CommandAction.YIELD)
            return

        if action == "MOVE" and self.state.current_path:
            target_node = self.state.next_node or self.state.current_path[0]
            target_pos = (float(target_node[0]), float(target_node[1]))

            self._emit_command(CommandAction.MOVE, target=target_pos, speed=self.config.max_speed)

            step = self.config.max_speed * delta_time
            self.localizer.move_towards(target_pos, step)
            self.state.velocity = self.config.max_speed
            self.transition_to(RobotStatus.MOVING, RobotIntent.MOVE)
            self.state.waiting_time = max(0.0, self.state.waiting_time - delta_time)

            self.state.battery = max(0.0, self.state.battery - self.config.battery_drain_rate * delta_time)

            if math.hypot(self.state.position[0] - target_pos[0], self.state.position[1] - target_pos[1]) < 0.2:
                if self.state.current_path and self.state.current_path[0] == target_node:
                    cleared_node = self.state.current_path.pop(0)
                    # Release reservation on traversed node
                    self.reservation_manager.release_reservation(cleared_node, self.robot_id)
                    self.network.broadcast(create_reservation_release_message(self.robot_id, cleared_node))

                if self.state.current_path:
                    self.state.next_node = self.state.current_path[0]
                    self._emit_path(self.state.current_path)
                else:
                    self.state.next_node = None
                    self._handle_goal_reached()

    def _handle_goal_reached(self) -> None:
        travel_time = (time.time() - self.trip_start_time) if self.trip_start_time else 0.0
        logger.info(
            f"[{self.robot_id}] GOAL_REACHED at pos={self.state.position} "
            f"travel_time={travel_time:.2f}s reroutes={self.trip_reroutes} "
            f"obstacles={self.trip_obstacles}"
        )

        self._emit_command(CommandAction.STOP)
        self._emit_event(
            event="GOAL_REACHED",
            reason=f"Reached destination {self.state.goal} in {travel_time:.2f}s",
            node=(int(round(self.state.position[0])), int(round(self.state.position[1]))),
        )

        if self.trip_start_pos and self.state.goal:
            trip = TripRecord(
                trip_id=f"trip-{int(time.time()*1000)}",
                robot_id=self.robot_id,
                start_node=self.trip_start_pos,
                goal_node=(int(round(self.state.goal[0])), int(round(self.state.goal[1]))),
                path=list(self.state.current_path),
                distance=math.hypot(
                    self.trip_start_pos[0] - self.state.goal[0],
                    self.trip_start_pos[1] - self.state.goal[1],
                ),
                travel_time_s=travel_time,
                waiting_time_s=self.total_waiting_time,
                obstacles_encountered=self.trip_obstacles,
                reroutes_count=self.trip_reroutes,
                completed=True,
            )
            self.experience_store.record_trip(trip)

        self.state.goal = None
        self.state.current_path.clear()
        self.state.next_node = None
        self.state.velocity = 0.0

        # Check if active task needs transition (e.g. pickup reached -> advance to dropoff)
        if self.task_manager.active_task:
            next_tgt = self.task_manager.get_next_navigation_target(self.state.position)
            if next_tgt:
                self.set_goal((float(next_tgt[0]), float(next_tgt[1])))
                return

        self.transition_to(RobotStatus.IDLE, RobotIntent.IDLE)

    def update_experience(self) -> None:
        pass
