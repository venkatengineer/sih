"""
Experience Learning Store for AMR Fleet.
Records historical edge traversal durations and congestion factors,
providing historical cost estimates to the route planner.
"""

from typing import Dict, Tuple, List
from world.grid_map import Point, Segment, GridMap

class ExperienceStore:
    def __init__(self, learning_rate: float = 0.2):
        self.learning_rate = learning_rate
        # Map: undirected_segment_id -> average_traversal_duration (seconds)
        self.edge_durations: Dict[str, float] = {}
        # Map: undirected_segment_id -> historical_congestion_factor (multiplier >= 1.0)
        self.edge_congestion_factors: Dict[str, float] = {}
        # Count of traversals per edge
        self.traversal_counts: Dict[str, int] = {}

    def record_edge_traversal(self, segment: Segment, duration: float, robot_count_during_traversal: int = 1):
        seg_id = GridMap.undirected_segment_id(segment)
        
        # Update traversal count
        self.traversal_counts[seg_id] = self.traversal_counts.get(seg_id, 0) + 1
        
        # Update running average duration
        if seg_id not in self.edge_durations:
            self.edge_durations[seg_id] = duration
        else:
            old_dur = self.edge_durations[seg_id]
            self.edge_durations[seg_id] = old_dur + self.learning_rate * (duration - old_dur)
            
        # Update historical congestion factor
        # Higher robot counts increase the congestion factor multiplier
        factor = 1.0 + max(0, robot_count_during_traversal - 1) * 0.5
        if seg_id not in self.edge_congestion_factors:
            self.edge_congestion_factors[seg_id] = factor
        else:
            old_fac = self.edge_congestion_factors[seg_id]
            self.edge_congestion_factors[seg_id] = old_fac + self.learning_rate * (factor - old_fac)

    def get_historical_cost_penalty(self, segment: Segment, base_duration: float) -> float:
        seg_id = GridMap.undirected_segment_id(segment)
        if seg_id not in self.edge_durations:
            return 0.0  # No prior experience penalty
            
        hist_duration = self.edge_durations[seg_id]
        hist_factor = self.edge_congestion_factors.get(seg_id, 1.0)
        
        # Additional penalty over base travel duration
        extra_duration = max(0.0, hist_duration - base_duration)
        congestion_penalty = base_duration * (hist_factor - 1.0)
        
        return extra_duration + congestion_penalty

    def get_historical_edge_time(self, segment: Segment, base_duration: float) -> float:
        seg_id = GridMap.undirected_segment_id(segment)
        if seg_id not in self.edge_durations:
            return base_duration
        penalty = self.get_historical_cost_penalty(segment, base_duration)
        return base_duration + penalty
