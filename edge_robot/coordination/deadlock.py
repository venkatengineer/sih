"""
Wait-For Graph (WFG) Deadlock Detection and Decentralized Resolution.
Constructs directed dependency graphs and deterministically breaks cyclic deadlocks.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, List, Set, Optional, Tuple

from edge_robot.core.enums import ConflictAction
from edge_robot.core.state import RobotState
from edge_robot.coordination.intent import RobotIntentData


@dataclass
class DeadlockReport:
    """Detected cyclic dependency among robots."""
    deadlock_id: str
    cycle: List[str]  # e.g. ["AMR-01", "AMR-02", "AMR-03"]
    victim_robot_id: str  # Lowest-priority robot chosen to yield / reroute
    resolution_action: ConflictAction
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deadlock_id": self.deadlock_id,
            "cycle": self.cycle,
            "victim_robot_id": self.victim_robot_id,
            "resolution_action": self.resolution_action.value,
            "timestamp": self.timestamp,
        }


class DeadlockDetector:
    """
    Constructs a Wait-For Graph (WFG) from observed robot states, intents, and lookaheads.
    Detects directed cycles indicating circular deadlocks.
    """

    @staticmethod
    def build_wait_for_graph(
        self_state: RobotState,
        peer_states: Dict[str, RobotState],
        peer_intents: Optional[Dict[str, RobotIntentData]] = None,
    ) -> Dict[str, str]:
        """
        Builds mapping: waiting_robot_id -> blocking_robot_id.
        Robot A waits for Robot B if A's desired next_node is currently occupied or targeted by B.
        """
        wfg: Dict[str, str] = {}
        all_robots: Dict[str, RobotState] = {self_state.robot_id: self_state, **peer_states}

        # Grid positions of all robots
        robot_positions: Dict[Tuple[int, int], str] = {
            (int(round(r.position[0])), int(round(r.position[1]))): r_id
            for r_id, r in all_robots.items()
        }

        # Targeted next cells
        robot_next_cells: Dict[Tuple[int, int], str] = {
            r.next_node: r_id
            for r_id, r in all_robots.items()
            if r.next_node is not None
        }

        for r_id, r in all_robots.items():
            if r.next_node is not None:
                # 1. Is another robot occupying r's next node?
                blocker = robot_positions.get(r.next_node)
                if blocker and blocker != r_id:
                    wfg[r_id] = blocker
                # 2. Or is another robot also targeting r's next node with lower precedence?
                elif r.next_node in robot_next_cells:
                    peer_targeting = robot_next_cells[r.next_node]
                    if peer_targeting != r_id:
                        wfg[r_id] = peer_targeting

        return wfg

    @staticmethod
    def detect_cycle(wfg: Dict[str, str]) -> Optional[List[str]]:
        """
        Finds a directed cycle in the wait-for graph using depth-first search.
        Returns list of robot IDs forming the cycle if found, else None.
        """
        visited: Set[str] = set()
        rec_stack: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.append(node)

            neighbor = wfg.get(node)
            if neighbor:
                if neighbor in rec_stack:
                    # Cycle detected! Extract cycle sublist
                    idx = rec_stack.index(neighbor)
                    return rec_stack[idx:]
                elif neighbor not in visited:
                    res = dfs(neighbor)
                    if res:
                        return res

            rec_stack.pop()
            return None

        for start_node in list(wfg.keys()):
            if start_node not in visited:
                cycle = dfs(start_node)
                if cycle:
                    return cycle

        return None

    @staticmethod
    def evaluate_deadlock(
        self_state: RobotState,
        peer_states: Dict[str, RobotState],
        peer_intents: Optional[Dict[str, RobotIntentData]] = None,
    ) -> Optional[DeadlockReport]:
        """
        Runs complete deadlock detection cycle and deterministically selects the victim robot to break the cycle.
        """
        wfg = DeadlockDetector.build_wait_for_graph(self_state, peer_states, peer_intents)
        cycle = DeadlockDetector.detect_cycle(wfg)

        if not cycle:
            return None

        all_robots: Dict[str, RobotState] = {self_state.robot_id: self_state, **peer_states}

        # Identify participant with lowest priority (deterministic tie-breaker: highest alphanumeric ID)
        lowest_priority = float("inf")
        victim_id = cycle[0]

        for r_id in cycle:
            robot = all_robots.get(r_id)
            p = robot.priority if robot else 50.0
            if p < lowest_priority:
                lowest_priority = p
                victim_id = r_id
            elif p == lowest_priority:
                # Deterministic tie-breaker: larger ID yields
                if r_id > victim_id:
                    victim_id = r_id

        return DeadlockReport(
            deadlock_id=f"dl-{int(time.time()*1000)}",
            cycle=cycle,
            victim_robot_id=victim_id,
            resolution_action=ConflictAction.REROUTE,
        )
