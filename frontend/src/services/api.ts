import { RobotState, TaskItem, SystemStatus, EventLog } from '../types';

export async function fetchFleet(): Promise<{ fleet: RobotState[]; system: SystemStatus }> {
  const res = await fetch('/api/fleet');
  return res.json();
}

export async function fetchTasks(): Promise<{ tasks: TaskItem[] }> {
  const res = await fetch('/api/tasks');
  return res.json();
}

export async function fetchEvents(limit = 50): Promise<{ events: EventLog[] }> {
  const res = await fetch(`/api/events?limit=${limit}`);
  return res.json();
}

export async function createTask(taskData: {
  task_id: string;
  pickup: [number, number];
  dropoff: [number, number];
  priority: number;
}): Promise<{ status: string; task: TaskItem }> {
  const res = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData),
  });
  return res.json();
}

export async function pauseRobot(robotId: string): Promise<void> {
  await fetch(`/api/robots/${robotId}/pause`, { method: 'POST' });
}

export async function resumeRobot(robotId: string): Promise<void> {
  await fetch(`/api/robots/${robotId}/resume`, { method: 'POST' });
}
