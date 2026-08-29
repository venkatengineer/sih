"""
Enumerations for Robot State Machine, Actions, Tasks, and Communication.
"""

from enum import Enum


class RobotStatus(str, Enum):
    """Lifecycle and operational state of the AMR."""
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    MOVING = "MOVING"
    WAITING = "WAITING"
    YIELDING = "YIELDING"
    REROUTING = "REROUTING"
    BLOCKED = "BLOCKED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    CHARGING = "CHARGING"
    OFFLINE = "OFFLINE"


class RobotIntent(str, Enum):
    """Predictive intent shared with peer robots."""
    IDLE = "IDLE"
    MOVE = "MOVE"
    YIELD = "YIELD"
    WAIT = "WAIT"
    REROUTE = "REROUTE"
    STOP = "STOP"
    CHARGE = "CHARGE"


class ConflictType(str, Enum):
    """Explicit classification of multi-robot spatial and temporal conflicts."""
    HEAD_ON_SWAP = "HEAD_ON_SWAP"
    SAME_NEXT_NODE = "SAME_NEXT_NODE"
    HEAD_ON = "HEAD_ON_SWAP"
    SAME_CELL = "SAME_NEXT_NODE"
    INTERSECTION = "INTERSECTION"
    FOLLOWING = "FOLLOWING"
    CHOKE_POINT = "CHOKE_POINT"
    OVERLAPPING_PATH = "OVERLAPPING_PATH"
    PROXIMITY = "PROXIMITY"


class TaskStatus(str, Enum):
    """Status of an assigned or auctioned warehouse task."""
    CREATED = "CREATED"
    AUCTIONING = "AUCTIONING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PICKED_UP = "PICKED_UP"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REASSIGNING = "REASSIGNING"

    # Backward compatibility aliases
    PENDING = "CREATED"
    BIDDING = "AUCTIONING"


class TaskPriority(int, Enum):
    """Priority levels for warehouse transport tasks."""
    LOW = 1
    NORMAL = 3
    HIGH = 5
    CRITICAL = 10


class ConflictAction(str, Enum):
    """Action resulting from decentralized conflict resolution."""
    PROCEED = "PROCEED"
    YIELD = "YIELD"
    WAIT = "WAIT"
    REROUTE = "REROUTE"
    STOP = "STOP"
    SLOW = "WAIT"


class ObstacleType(str, Enum):
    """Type of detected obstacle."""
    PERSON = "PERSON"
    FORKLIFT = "FORKLIFT"
    PALLET = "PALLET"
    BOX = "BOX"
    WALL = "WALL"
    DYNAMIC_OBSTACLE = "DYNAMIC_OBSTACLE"


class MessageType(str, Enum):
    """P2P network message types."""
    ROBOT_STATE = "ROBOT_STATE"
    INTENT = "INTENT"
    ROBOT_INTENT = "ROBOT_INTENT"
    OBSTACLE = "OBSTACLE"
    RESERVATION_REQUEST = "RESERVATION_REQUEST"
    RESERVATION_GRANT = "RESERVATION_GRANT"
    RESERVATION_RELEASE = "RESERVATION_RELEASE"
    RESERVATION_DENIED = "RESERVATION_DENIED"
    CONFLICT = "CONFLICT"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    DEADLOCK_DETECTED = "DEADLOCK_DETECTED"
    DEADLOCK_RESOLVED = "DEADLOCK_RESOLVED"
    HEARTBEAT = "HEARTBEAT"
    YIELD = "YIELD"
    PROCEED = "PROCEED"
    REROUTE = "REROUTE"

    # Decentralized Task Auction Messages
    TASK_ANNOUNCEMENT = "TASK_ANNOUNCEMENT"
    TASK_BID = "TASK_BID"
    TASK_AWARD = "TASK_AWARD"
    TASK_ACCEPT = "TASK_ACCEPT"
    TASK_REJECT = "TASK_REJECT"
    TASK_PROGRESS = "TASK_PROGRESS"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_FAILED = "TASK_FAILED"
    TASK_RELEASE = "TASK_RELEASE"

    # Legacy aliases
    TASK_ANNOUNCE = "TASK_ANNOUNCEMENT"
    TASK_ASSIGN = "TASK_AWARD"
    TASK_STATUS = "TASK_PROGRESS"
    EXPERIENCE_SYNC = "EXPERIENCE_SYNC"
