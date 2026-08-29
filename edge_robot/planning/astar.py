"""
Pure Python deterministic A* path planner on 2D grid.
"""

from __future__ import annotations
import heapq
import math
from typing import List, Tuple, Optional, Set, Dict

from edge_robot.world.map import LocalWorldModel


def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Manhattan distance heuristic for grid-aligned 4-directional motion."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_search(
    start: Tuple[int, int],
    goal: Tuple[int, int],
    world: LocalWorldModel,
    avoid_nodes: Optional[Set[Tuple[int, int]]] = None,
) -> Optional[List[Tuple[int, int]]]:
    """
    Deterministic A* path planning.
    Returns list of grid nodes [(x0, y0), (x1, y1), ..., (xN, yN)] from start to goal.
    If no valid path exists, returns None.
    """
    start_node = (int(round(start[0])), int(round(start[1])))
    goal_node = (int(round(goal[0])), int(round(goal[1])))

    if start_node == goal_node:
        return [start_node]

    # Validate start and goal passability
    if not world.is_static_free(goal_node):
        return None

    # Priority queue stores tuples: (f_score, counter, current_node)
    # Counter ensures deterministic tie-breaking without comparing coordinate tuples
    counter = 0
    open_set: List[Tuple[float, int, Tuple[int, int]]] = []
    heapq.heappush(open_set, (heuristic(start_node, goal_node), counter, start_node))

    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start_node: 0.0}
    f_score: Dict[Tuple[int, int], float] = {start_node: heuristic(start_node, goal_node)}
    in_open_set: Set[Tuple[int, int]] = {start_node}

    while open_set:
        _, _, current = heapq.heappop(open_set)
        in_open_set.discard(current)

        if current == goal_node:
            # Reconstruct path from goal to start
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        neighbors = world.get_neighbors(current, avoid_nodes=avoid_nodes)
        for neighbor in neighbors:
            # Step cost is 1.0 for orthogonal steps
            tentative_g = g_score[current] + 1.0

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor, goal_node)
                f_score[neighbor] = f

                if neighbor not in in_open_set:
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))
                    in_open_set.add(neighbor)

    # No path found
    return None
