"""
Path planner orchestrator for RobotAgent.
"""

from typing import List, Tuple, Optional, Set
from edge_robot.world.map import LocalWorldModel
from edge_robot.planning.astar import astar_search
from edge_robot.planning.route import RouteUtils


class PathPlanner:
    """
    Local path planner for the Edge Robot Agent.
    Operates purely on local world representation.
    """

    def __init__(self, world: LocalWorldModel):
        self.world = world

    def plan(
        self,
        start: Tuple[float, float],
        goal: Tuple[float, float],
        avoid_nodes: Optional[Set[Tuple[int, int]]] = None,
    ) -> Optional[List[Tuple[int, int]]]:
        """
        Calculate deterministic A* path between start and goal.
        """
        start_grid = (int(round(start[0])), int(round(start[1])))
        goal_grid = (int(round(goal[0])), int(round(goal[1])))

        return astar_search(
            start=start_grid,
            goal=goal_grid,
            world=self.world,
            avoid_nodes=avoid_nodes,
        )

    def replan_around_obstacle(
        self,
        current_pos: Tuple[float, float],
        goal: Tuple[float, float],
        blocked_nodes: Set[Tuple[int, int]],
    ) -> Optional[List[Tuple[int, int]]]:
        """
        Re-plan path from current position to goal while explicitly avoiding blocked nodes.
        """
        return self.plan(start=current_pos, goal=goal, avoid_nodes=blocked_nodes)
