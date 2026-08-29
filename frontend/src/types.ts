export interface RobotState {
  robot_id: string;
  status: 'MOVING' | 'WAITING' | 'BLOCKED' | 'CHARGING' | 'REROUTING' | 'IDLE';
  battery: number;
  position: [number, number];
  heading: number;
  velocity: number;
  current_task: string | null;
  current_goal: [number, number] | null;
  current_path: [number, number][];
  is_online: boolean;
  last_heartbeat_ago_ms: number;
  task_history: Array<{
    task_id: string;
    status: string;
    timestamp: number;
  }>;
}

export interface TaskItem {
  task_id: string;
  pickup: [number, number];
  dropoff: [number, number];
  priority: number;
  status: 'AUCTIONING' | 'ASSIGNED' | 'IN_PROGRESS' | 'PICKED_UP' | 'COMPLETED' | 'CANCELLED' | 'REASSIGNING';
  assigned_robot: string | null;
  auction_round: number;
  created_at: number;
  started_at: number | null;
  picked_up_at: number | null;
  completed_at: number | null;
  bids: Record<string, BidData>;
  winner_score: number | null;
}

export interface BidData {
  robot_id: string;
  cost: number;
  distance: number;
  battery: number;
  congestion: number;
  is_valid: boolean;
}

export interface SystemStatus {
  mode: string;
  network: string;
  central_server: string;
  robots_total: number;
  robots_online: number;
  active_tasks: number;
  completed_tasks: number;
  auctioning_tasks: number;
  uptime_seconds: number;
}

export interface EventLog {
  event: string;
  timestamp: number;
  data: Record<string, any>;
}
