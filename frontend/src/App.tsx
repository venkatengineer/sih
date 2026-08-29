import React, { useState, useEffect } from 'react';
import { RobotState, TaskItem, SystemStatus, EventLog } from './types';
import { fetchFleet, fetchTasks, fetchEvents, createTask, pauseRobot, resumeRobot } from './services/api';
import { wsClient } from './services/websocket';

export function App() {
  const [currentPage, setCurrentPage] = useState<'overview' | 'fleet' | 'create_task' | 'auctions' | 'tasks' | 'events'>('overview');
  const [fleet, setFleet] = useState<RobotState[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [events, setEvents] = useState<EventLog[]>([]);
  const [system, setSystem] = useState<SystemStatus>({
    mode: 'DECENTRALIZED',
    network: 'P2P UDP',
    central_server: 'NONE',
    robots_total: 4,
    robots_online: 4,
    active_tasks: 0,
    completed_tasks: 0,
    auctioning_tasks: 0,
    uptime_seconds: 0,
  });

  // Task creation form state
  const [taskId, setTaskId] = useState('T-001');
  const [pickup, setPickup] = useState<[number, number]>([3, 16]);
  const [dropoff, setDropoff] = useState<[number, number]>([3, 4]);
  const [priority, setPriority] = useState<number>(5);

  useEffect(() => {
    // Initial fetch
    fetchFleet().then((data) => {
      if (data.fleet) setFleet(data.fleet);
      if (data.system) setSystem(data.system);
    });
    fetchTasks().then((data) => {
      if (data.tasks) setTasks(data.tasks);
    });
    fetchEvents().then((data) => {
      if (data.events) setEvents(data.events);
    });

    // WebSocket subscription
    wsClient.connect();
    const unsub = wsClient.subscribe((msg) => {
      if (msg.type === 'SNAPSHOT') {
        if (msg.fleet) setFleet(msg.fleet);
        if (msg.tasks) setTasks(msg.tasks);
        if (msg.system) setSystem(msg.system);
      } else if (msg.type === 'EVENT') {
        const { event, data } = msg;
        setEvents((prev) => [{ event, timestamp: Date.now() / 1000, data }, ...prev.slice(0, 100)]);

        if (event === 'ROBOT_STATE') {
          setFleet((prev) => {
            const idx = prev.findIndex((r) => r.robot_id === data.robot_id);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = data;
              return updated;
            }
            return [...prev, data];
          });
        } else if (event === 'TASK_CREATED' || event === 'TASK_AUCTIONING') {
          setTasks((prev) => {
            if (prev.some((t) => t.task_id === data.task_id)) return prev;
            return [data, ...prev];
          });
        } else if (event === 'TASK_BID' || event === 'TASK_BID_SUBMITTED') {
          const b = data.bid || data;
          setTasks((prev) =>
            prev.map((t) => {
              if (t.task_id === data.task_id) {
                return {
                  ...t,
                  bids: { ...t.bids, [b.robot_id || data.robot_id]: b },
                };
              }
              return t;
            })
          );
        } else if (event === 'TASK_AWARD' || event === 'TASK_ASSIGNED') {
          setTasks((prev) =>
            prev.map((t) => {
              if (t.task_id === data.task_id) {
                return {
                  ...t,
                  assigned_robot: data.winner_id,
                  status: 'ASSIGNED',
                  winner_score: data.score,
                };
              }
              return t;
            })
          );
        } else if (event === 'TASK_PROGRESS' || event === 'TASK_STARTED' || event === 'TASK_PICKED_UP') {
          setTasks((prev) =>
            prev.map((t) => (t.task_id === data.task_id ? { ...t, status: data.status || 'IN_PROGRESS' } : t))
          );
        } else if (event === 'TASK_COMPLETE' || event === 'TASK_COMPLETED') {
          setTasks((prev) =>
            prev.map((t) => (t.task_id === data.task_id ? { ...t, status: 'COMPLETED' } : t))
          );
        }
      }
    });

    return unsub;
  }, []);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    await createTask({ task_id: taskId, pickup, dropoff, priority });
    const nextNum = parseInt(taskId.replace(/\D/g, '') || '1', 10) + 1;
    setTaskId(`T-${String(nextNum).padStart(3, '0')}`);
  };

  const activeAuctionTask = tasks.find((t) => t.status === 'AUCTIONING' || t.status === 'ASSIGNED');

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', background: '#070b12', color: '#f1f5f9', fontFamily: 'sans-serif' }}>
      {/* Sidebar */}
      <aside style={{ width: 240, background: '#0d1524', borderRight: '1px solid #1e3352', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px 16px', borderBottom: '1px solid #1e3352', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ fontSize: 24 }}>🏭</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700 }}>AMR FLEET OPS</div>
            <div style={{ fontSize: 11, color: '#38bdf8' }}>Decentralized Edge Hub</div>
          </div>
        </div>

        <ul style={{ listStyle: 'none', padding: '16px 8px', flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {[
            { id: 'overview', label: 'Overview', icon: '📊' },
            { id: 'fleet', label: 'Fleet Status', icon: '🤖' },
            { id: 'create_task', label: 'Create Task', icon: '📦' },
            { id: 'auctions', label: 'Live Auctions', icon: '⚡' },
            { id: 'tasks', label: 'All Tasks', icon: '📋' },
            { id: 'events', label: 'Live Events', icon: '📡' },
          ].map((item) => (
            <li
              key={item.id}
              onClick={() => setCurrentPage(item.id as any)}
              style={{
                padding: '10px 14px',
                borderRadius: 6,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                fontWeight: 500,
                background: currentPage === item.id ? '#1e3a5f' : 'transparent',
                color: currentPage === item.id ? '#38bdf8' : '#94a3b8',
                borderLeft: currentPage === item.id ? '3px solid #38bdf8' : 'none',
              }}
            >
              <span>{item.icon}</span> {item.label}
            </li>
          ))}
        </ul>

        <div style={{ padding: 16, borderTop: '1px solid #1e3352', fontSize: 11, color: '#64748b' }}>
          <div><strong>P2P NETWORK:</strong> <span style={{ color: '#4ade80' }}>● ACTIVE</span></div>
          <div style={{ marginTop: 4 }}><strong>CENTRAL SERVER:</strong> <span style={{ color: '#38bdf8' }}>NONE</span></div>
        </div>
      </aside>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <header style={{ height: 56, background: '#0d1524', borderBottom: '1px solid #1e3352', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <h1 style={{ fontSize: 16, fontWeight: 700, textTransform: 'capitalize' }}>{currentPage.replace('_', ' ')}</h1>
            <div style={{ background: '#0f233a', border: '1px solid #1e3e6b', padding: '4px 10px', borderRadius: 12, fontSize: 11, color: '#38bdf8' }}>
              ● Decentralized Autonomous Fleet
            </div>
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>
            Robots Online: <strong style={{ color: '#4ade80' }}>{fleet.filter((r) => r.is_online).length} / 4</strong>
          </div>
        </header>

        <main style={{ flex: 1, padding: 24, overflowY: 'auto' }}>
          {currentPage === 'overview' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 16 }}>
                  <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>ACTIVE EDGE ROBOTS</div>
                  <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>{fleet.filter((r) => r.is_online).length} / 4</div>
                  <div style={{ fontSize: 11, color: '#38bdf8', marginTop: 4 }}>P2P Mesh Connected</div>
                </div>
                <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 16 }}>
                  <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>ACTIVE TASKS</div>
                  <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>{tasks.filter((t) => ['ASSIGNED', 'IN_PROGRESS', 'PICKED_UP', 'AUCTIONING'].includes(t.status)).length}</div>
                  <div style={{ fontSize: 11, color: '#38bdf8', marginTop: 4 }}>Executing in Warehouse</div>
                </div>
                <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 16 }}>
                  <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>COMPLETED JOBS</div>
                  <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>{tasks.filter((t) => t.status === 'COMPLETED').length}</div>
                  <div style={{ fontSize: 11, color: '#38bdf8', marginTop: 4 }}>Delivered Successfully</div>
                </div>
                <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 16 }}>
                  <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600 }}>COORDINATION</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#38bdf8', marginTop: 4 }}>P2P UDP</div>
                  <div style={{ fontSize: 11, color: '#4ade80', marginTop: 4 }}>Zero Central Allocator</div>
                </div>
              </div>

              {/* Live Fleet Snapshot */}
              <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 20, marginBottom: 24 }}>
                <h3 style={{ fontSize: 14, marginBottom: 12 }}>🤖 Active AMR Fleet Telemetry</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                  <thead>
                    <tr style={{ color: '#64748b', borderBottom: '1px solid #1e3352' }}>
                      <th style={{ padding: '8px 12px' }}>ROBOT</th>
                      <th style={{ padding: '8px 12px' }}>STATUS</th>
                      <th style={{ padding: '8px 12px' }}>BATTERY</th>
                      <th style={{ padding: '8px 12px' }}>TASK</th>
                      <th style={{ padding: '8px 12px' }}>POSITION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fleet.map((r) => (
                      <tr key={r.robot_id} style={{ borderBottom: '1px solid rgba(30,51,82,0.5)' }}>
                        <td style={{ padding: '10px 12px', fontWeight: 700 }}>{r.robot_id}</td>
                        <td style={{ padding: '10px 12px', color: '#4ade80' }}>● {r.status}</td>
                        <td style={{ padding: '10px 12px' }}>{Math.round(r.battery)}%</td>
                        <td style={{ padding: '10px 12px', color: '#38bdf8' }}>{r.current_task || 'IDLE'}</td>
                        <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>[{r.position[0]}, {r.position[1]}]</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {currentPage === 'create_task' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24 }}>
              <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 20 }}>
                <h3 style={{ fontSize: 14, marginBottom: 16 }}>📦 Create Warehouse Transport Job</h3>
                <form onSubmit={handleCreateTask}>
                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Task ID</label>
                    <input
                      type="text"
                      value={taskId}
                      onChange={(e) => setTaskId(e.target.value)}
                      style={{ width: '100%', background: '#0d1524', border: '1px solid #1e3352', color: '#fff', padding: '8px 12px', borderRadius: 6 }}
                      required
                    />
                  </div>

                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Pickup Location</label>
                    <select
                      value={`${pickup[0]},${pickup[1]}`}
                      onChange={(e) => setPickup(e.target.value.split(',').map(Number) as [number, number])}
                      style={{ width: '100%', background: '#0d1524', border: '1px solid #1e3352', color: '#fff', padding: '8px 12px', borderRadius: 6 }}
                    >
                      <option value="3,16">Inbound Pickup Station A3 [3, 16]</option>
                      <option value="2,10">Loading Dock L2 [2, 10]</option>
                      <option value="2,5">Loading Dock L1 [2, 5]</option>
                      <option value="5,17">Aisle 01 North [5, 17]</option>
                      <option value="10,17">Aisle 02 North [10, 17]</option>
                    </select>
                  </div>

                  <div style={{ marginBottom: 14 }}>
                    <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Dropoff Destination</label>
                    <select
                      value={`${dropoff[0]},${dropoff[1]}`}
                      onChange={(e) => setDropoff(e.target.value.split(',').map(Number) as [number, number])}
                      style={{ width: '100%', background: '#0d1524', border: '1px solid #1e3352', color: '#fff', padding: '8px 12px', borderRadius: 6 }}
                    >
                      <option value="3,4">Outbound Dropoff Station D8 [3, 4]</option>
                      <option value="14,2">Aisle 03 South [14, 2]</option>
                      <option value="19,2">Aisle 04 South [19, 2]</option>
                      <option value="21,4">Charging Dock C3 [21, 4]</option>
                    </select>
                  </div>

                  <div style={{ marginBottom: 16 }}>
                    <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Priority</label>
                    <select
                      value={priority}
                      onChange={(e) => setPriority(Number(e.target.value))}
                      style={{ width: '100%', background: '#0d1524', border: '1px solid #1e3352', color: '#fff', padding: '8px 12px', borderRadius: 6 }}
                    >
                      <option value={5}>HIGH (Priority: 5)</option>
                      <option value={10}>CRITICAL (Priority: 10)</option>
                      <option value={3}>NORMAL (Priority: 3)</option>
                      <option value={1}>LOW (Priority: 1)</option>
                    </select>
                  </div>

                  <div style={{ background: '#0f2038', border: '1px solid #1e3a5f', padding: 12, borderRadius: 6, marginBottom: 16, fontSize: 12, color: '#93c5fd' }}>
                    🤖 <strong>Decentralized Allocation:</strong> Robot is selected automatically via P2P auction.
                  </div>

                  <button type="submit" style={{ width: '100%', background: '#0284c7', color: '#fff', border: 'none', padding: '10px 16px', borderRadius: 6, fontWeight: 700, cursor: 'pointer' }}>
                    🚀 BROADCAST & AUCTION TASK
                  </button>
                </form>
              </div>

              {/* Auction Matrix Card */}
              <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 20 }}>
                <h3 style={{ fontSize: 14, marginBottom: 12 }}>⚡ Live Auction Monitor</h3>
                {activeAuctionTask ? (
                  <div>
                    <div style={{ fontSize: 13, color: '#fbbf24', fontWeight: 700 }}>P2P AUCTION: {activeAuctionTask.task_id}</div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 12, marginTop: 12 }}>
                      <thead>
                        <tr style={{ color: '#64748b' }}>
                          <th style={{ padding: '6px 8px' }}>ROBOT</th>
                          <th style={{ padding: '6px 8px' }}>DIST</th>
                          <th style={{ padding: '6px 8px' }}>BATT</th>
                          <th style={{ padding: '6px 8px' }}>SCORE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(activeAuctionTask.bids || {}).map(([rId, b]) => {
                          const isWinner = rId === activeAuctionTask.assigned_robot;
                          return (
                            <tr key={rId} style={{ background: isWinner ? '#0e3322' : 'transparent', color: isWinner ? '#4ade80' : '#fff' }}>
                              <td style={{ padding: '6px 8px', fontWeight: isWinner ? 700 : 400 }}>{rId} {isWinner ? '🏆' : ''}</td>
                              <td style={{ padding: '6px 8px' }}>{(b.distance || 0).toFixed(1)}m</td>
                              <td style={{ padding: '6px 8px' }}>{Math.round(b.battery || 100)}%</td>
                              <td style={{ padding: '6px 8px', fontWeight: 700 }}>{(b.cost || 0).toFixed(1)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ color: '#64748b', fontSize: 13 }}>Create a task to observe real-time bids.</div>
                )}
              </div>
            </div>
          )}

          {currentPage === 'fleet' && (
            <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 16 }}>🤖 Autonomous Mobile Robot Fleet</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                <thead>
                  <tr style={{ color: '#64748b', borderBottom: '1px solid #1e3352' }}>
                    <th style={{ padding: '10px 12px' }}>ROBOT ID</th>
                    <th style={{ padding: '10px 12px' }}>NETWORK</th>
                    <th style={{ padding: '10px 12px' }}>STATUS</th>
                    <th style={{ padding: '10px 12px' }}>BATTERY</th>
                    <th style={{ padding: '10px 12px' }}>VELOCITY</th>
                    <th style={{ padding: '10px 12px' }}>POSITION</th>
                    <th style={{ padding: '10px 12px' }}>TASK</th>
                    <th style={{ padding: '10px 12px' }}>CONTROLS</th>
                  </tr>
                </thead>
                <tbody>
                  {fleet.map((r) => (
                    <tr key={r.robot_id} style={{ borderBottom: '1px solid rgba(30,51,82,0.5)' }}>
                      <td style={{ padding: '12px 12px', fontWeight: 700, color: '#38bdf8' }}>{r.robot_id}</td>
                      <td style={{ padding: '12px 12px', color: '#4ade80' }}>● P2P CONNECTED</td>
                      <td style={{ padding: '12px 12px' }}>● {r.status}</td>
                      <td style={{ padding: '12px 12px' }}>{Math.round(r.battery)}%</td>
                      <td style={{ padding: '12px 12px' }}>{r.velocity.toFixed(1)} m/s</td>
                      <td style={{ padding: '12px 12px', fontFamily: 'monospace' }}>[{r.position[0]}, {r.position[1]}]</td>
                      <td style={{ padding: '12px 12px', fontWeight: 700 }}>{r.current_task || 'NONE'}</td>
                      <td style={{ padding: '12px 12px' }}>
                        <button onClick={() => pauseRobot(r.robot_id)} style={{ background: '#1e293b', color: '#fff', border: '1px solid #334155', padding: '4px 8px', borderRadius: 4, marginRight: 6, cursor: 'pointer' }}>Pause</button>
                        <button onClick={() => resumeRobot(r.robot_id)} style={{ background: '#1e293b', color: '#fff', border: '1px solid #334155', padding: '4px 8px', borderRadius: 4, cursor: 'pointer' }}>Resume</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {currentPage === 'tasks' && (
            <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 16 }}>📋 Warehouse Tasks Ledger</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                <thead>
                  <tr style={{ color: '#64748b', borderBottom: '1px solid #1e3352' }}>
                    <th style={{ padding: '10px 12px' }}>TASK ID</th>
                    <th style={{ padding: '10px 12px' }}>PICKUP</th>
                    <th style={{ padding: '10px 12px' }}>DROPOFF</th>
                    <th style={{ padding: '10px 12px' }}>PRIORITY</th>
                    <th style={{ padding: '10px 12px' }}>STATUS</th>
                    <th style={{ padding: '10px 12px' }}>ASSIGNED AMR</th>
                    <th style={{ padding: '10px 12px' }}>SCORE</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t) => (
                    <tr key={t.task_id} style={{ borderBottom: '1px solid rgba(30,51,82,0.5)' }}>
                      <td style={{ padding: '12px 12px', fontWeight: 700 }}>{t.task_id}</td>
                      <td style={{ padding: '12px 12px' }}>[{t.pickup.join(', ')}]</td>
                      <td style={{ padding: '12px 12px' }}>[{t.dropoff.join(', ')}]</td>
                      <td style={{ padding: '12px 12px', color: '#fbbf24' }}>P{t.priority}</td>
                      <td style={{ padding: '12px 12px' }}>{t.status}</td>
                      <td style={{ padding: '12px 12px', fontWeight: 700, color: '#38bdf8' }}>{t.assigned_robot || '—'}</td>
                      <td style={{ padding: '12px 12px' }}>{t.winner_score ? t.winner_score.toFixed(1) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {currentPage === 'events' && (
            <div style={{ background: '#131f33', border: '1px solid #1e3352', borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 16 }}>📡 Real-Time Fleet & Consensus Event Feed</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {events.map((e, idx) => (
                  <div key={idx} style={{ background: '#0d1524', borderLeft: '3px solid #38bdf8', padding: '8px 12px', borderRadius: 4, fontSize: 12 }}>
                    <span style={{ fontFamily: 'monospace', color: '#64748b', marginRight: 12 }}>{new Date(e.timestamp * 1000).toTimeString().split(' ')[0]}</span>
                    <strong style={{ color: '#38bdf8', marginRight: 12 }}>{e.event}</strong>
                    <span>{JSON.stringify(e.data || {})}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
