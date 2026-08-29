"""
Main Entry Point for Edge-AI Decentralized AMR Congestion-Aware Simulation & Web Server.
Supports simultaneous multi-robot execution, smart crossing path generation,
dynamic robot addition/removal, map obstacles, and instant reset controls.
"""

import os
import sys
import time
import asyncio
import http.server
import socketserver
import threading
import logging
from typing import List, Dict, Any

from config import RobotConfig
from world.grid_map import GridMap
from communication.p2p import P2PCommunicator
from communication.websocket_server import WebSocketServer
from agent.amr_agent import AMRAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MAIN")

# HTTP Static File Server Handler
class HTTPStaticServer(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend')
        super().__init__(*args, directory=frontend_dir, **kwargs)

def start_http_server(port: int = 8080):
    try:
        with socketserver.TCPServer(("", port), HTTPStaticServer) as httpd:
            logger.info(f"HTTP Server serving dashboard at http://localhost:{port}")
            httpd.serve_forever()
    except Exception as e:
        logger.warning(f"HTTP Server start exception: {e}")

async def main():
    logger.info("Initializing Edge-AI Decentralized AMR Congestion-Aware Simulation Server...")
    
    # 1. Start WebSocket Gateway
    ws_server = WebSocketServer(host="0.0.0.0", port=8765)
    await ws_server.start()

    # 2. Start HTTP Server in background thread
    http_thread = threading.Thread(target=start_http_server, args=(8080,), daemon=True)
    http_thread.start()

    # 3. Create Warehouse Grid Map with Map Obstacles
    grid = GridMap(width=30, height=30, cell_size=1.0)
    grid.load_default_warehouse_obstacles()

    # 4. Agent list starts EMPTY - User manually adds robots!
    agents: List[AMRAgent] = []
    step_delay = [0.06]  # Fast step delay = ~16 steps per second!
    
    # WebSocket broadcast helper
    def broadcast_event(event_data: Dict[str, Any]):
        asyncio.create_task(ws_server.broadcast(event_data))

    def wire_p2p_links():
        """Wires in-memory P2P links between all active agents in fleet."""
        for i in range(len(agents)):
            for j in range(len(agents)):
                if i != j:
                    src = agents[i]
                    tgt = agents[j]
                    
                    def make_interceptor(agent_tgt):
                        def intercepted(msg):
                            agent_tgt._handle_p2p_message(msg)
                        return intercepted

                    link_cb = make_interceptor(tgt)
                    prev_bc = src.p2p.broadcast
                    
                    def wrap_bc(msg, p_bc=prev_bc, l_cb=link_cb):
                        p_bc(msg)
                        l_cb(msg)
                        
                    src.p2p.broadcast = wrap_bc

    # Smart Crossing Path Presets for newly added robots
    def get_crossing_path_preset(robot_num: int):
        presets = [
            ((0, 15), (29, 15)),   # AMR-01: Horizontal Main Corridor
            ((15, 0), (15, 29)),   # AMR-02: Vertical Crossing Corridor (Intersects at 15,15!)
            ((0, 14), (29, 16)),   # AMR-03: Diagonal Crossing
            ((29, 15), (0, 15)),   # AMR-04: Reverse Horizontal Corridor
            ((15, 29), (15, 0)),   # AMR-05: Reverse Vertical Corridor
            ((0, 8), (29, 8)),     # AMR-06: Secondary Corridor 1
            ((0, 22), (29, 22)),   # AMR-07: Secondary Corridor 2
            ((8, 0), (8, 29)),     # AMR-08: Vertical Aisle 1
        ]
        if robot_num - 1 < len(presets):
            return presets[robot_num - 1]
        else:
            y = (robot_num * 4) % 30
            return ((0, y), (29, y))

    # Control message callback from Frontend WebSocket UI
    def handle_frontend_command(msg: Dict[str, Any]):
        action = msg.get("action")
        logger.info(f"Received frontend action command: {action} with data: {msg}")
        
        if action == "ADD_ROBOT":
            robot_num = len(agents) + 1
            r_id = f"AMR-0{robot_num}" if robot_num < 10 else f"AMR-{robot_num}"
            
            if "start" in msg and "goal" in msg:
                st = tuple(msg["start"])
                gl = tuple(msg["goal"])
            else:
                st, gl = get_crossing_path_preset(robot_num)
            
            cfg = RobotConfig(robot_id=r_id, reroute_improvement_threshold=0.10)
            p2p_comm = P2PCommunicator(r_id, cfg.p2p_port, cfg.p2p_broadcast_ip)
            agent = AMRAgent(cfg, grid, p2p_communicator=p2p_comm, ws_broadcast_func=broadcast_event)
            agent.set_navigation_goal(destination=gl, start_pos=st)
            agents.append(agent)
            wire_p2p_links()
            logger.info(f"Added new AMR: {r_id} at start {st} -> goal {gl}")

        elif action == "REMOVE_ROBOT":
            target_id = msg.get("robot_id")
            to_remove = [ag for ag in agents if ag.robot_id == target_id]
            for ag in to_remove:
                agents.remove(ag)
            wire_p2p_links()
            logger.info(f"Removed robot: {target_id}")

        elif action == "SET_START_GOAL":
            target_id = msg.get("robot_id")
            st = tuple(msg.get("start", [0, 0]))
            gl = tuple(msg.get("goal", [29, 29]))
            for ag in agents:
                if ag.robot_id == target_id:
                    ag.set_navigation_goal(destination=gl, start_pos=st)
                    ag.planner.last_reroute_time = 0.0
                    logger.info(f"Updated {target_id} Start to {st} and Goal to {gl}")

        elif action == "TOGGLE_OBSTACLE":
            cell = tuple(msg.get("cell", [0, 0]))
            if cell in grid.obstacles:
                grid.set_obstacle(cell[0], cell[1], False)
            else:
                grid.set_obstacle(cell[0], cell[1], True)
                
            # Replan paths for all active agents
            for ag in agents:
                if ag.target_destination:
                    ag.current_path = ag.planner.astar.plan_path(ag.current_position, ag.target_destination) or []
                    ag.current_path_index = 0
            logger.info(f"Toggled map obstacle at {cell}")

        elif action == "SIMULATE_CONGESTION":
            # If no robots exist, spawn AMR-01 and AMR-02 with crossing paths
            if not agents:
                handle_frontend_command({"action": "ADD_ROBOT"})
                handle_frontend_command({"action": "ADD_ROBOT"})
                
            # Simulate Path A corridor crowding (6 peer traffic intent records)
            path_a_corridor = [(x, 15) for x in range(21)]
            for i in range(6):
                peer_id = f"TRAFFIC-0{i+1}"
                for ag in agents:
                    ag.world_model.update_peer(
                        robot_id=peer_id,
                        position=(10, 15),
                        current_path=path_a_corridor,
                        velocity=0.5
                    )
            logger.info("Simulated corridor congestion.")

        elif action == "CLEAR_CONGESTION":
            grid.clear_dynamic_obstacles()
            for ag in agents:
                ag.world_model.peers.clear()
            logger.info("Cleared all dynamic congestion.")

        elif action == "RESET":
            grid.clear_dynamic_obstacles()
            grid.load_default_warehouse_obstacles()
            for ag in agents:
                ag.world_model.peers.clear()
                if ag.target_destination:
                    ag.set_navigation_goal(destination=ag.target_destination, start_pos=ag.start_position)
                    ag.planner.last_reroute_time = 0.0
            logger.info("Reset all map obstacles and AMRs.")

        elif action == "CLEAR_ALL":
            grid.clear_dynamic_obstacles()
            grid.load_default_warehouse_obstacles()
            agents.clear()
            logger.info("Cleared all robots from simulation.")

        elif action == "SET_SPEED":
            spd = float(msg.get("delay", 0.06))
            step_delay[0] = max(0.02, min(1.0, spd))
            logger.info(f"Updated simulation step delay to {step_delay[0]}s")

    ws_server.on_message_callback = handle_frontend_command

    logger.info("Simulation initialized. Ready for user robot additions...")

    # Main Simulation Step Loop
    step_count = 0
    while True:
        step_count += 1
        fleet_telemetry = {}
        segment_telemetry = {}

        # Simultaneously step all active AMRs in parallel
        for agent in agents:
            res = agent.step()
            fleet_telemetry[agent.robot_id] = {
                "position": list(agent.current_position),
                "start_position": list(agent.start_position) if hasattr(agent, 'start_position') else [0, 0],
                "target_destination": list(agent.target_destination) if agent.target_destination else [0, 0],
                "status": agent.status,
                "current_path": [list(p) for p in agent.current_path[agent.current_path_index:]]
            }

            # Collect segment congestion telemetry
            if agent.current_path:
                segments = GridMap.path_to_segments(agent.current_path)
                for seg in segments:
                    seg_info = agent.planner.congestion_estimator.evaluate_segment_congestion(seg, agent.world_model)
                    seg_id = GridMap.undirected_segment_id(seg)
                    segment_telemetry[seg_id] = {
                        "level": seg_info.congestion_level,
                        "robots": seg_info.robot_count
                    }

        # Broadcast fleet status & map static/dynamic obstacles to WebSocket frontend
        await ws_server.broadcast({
            "event": "FLEET_STATE",
            "robots": fleet_telemetry,
            "congestion": segment_telemetry,
            "obstacles": [list(p) for p in grid.obstacles],
            "dynamic_obstacles": [list(p) for p in grid.dynamic_obstacles]
        })

        await asyncio.sleep(step_delay[0])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulation shut down cleanly.")
