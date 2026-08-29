"""
CLI entry point for starting an independent Edge Robot Agent process.
Usage:
    python -m edge_robot --robot-id AMR-01 --port 5001 --frontend-port 8001
    python -m edge_robot --robot-id AMR-02 --start 18,2 --goal 1,2 --port 5002 --frontend-port 8002
"""

from __future__ import annotations
import argparse
import asyncio
import logging
import signal
import sys
from typing import Tuple, Optional

from edge_robot.config import load_config, RobotConfig
from edge_robot.core.robot import RobotAgent
from edge_robot.gateway.session import FrontendGateway


def setup_logging(robot_id: str, verbose: bool = False) -> None:
    """Configure clean, structured logging."""
    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger("edge_robot")
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)


def parse_coords(val: str) -> Tuple[float, float]:
    """Parse 'x,y' string into float tuple."""
    parts = val.split(",")
    return (float(parts[0].strip()), float(parts[1].strip()))


async def run_robot(config: RobotConfig, goal: Optional[Tuple[float, float]] = None) -> None:
    """Instantiate and run independent robot agent and optional frontend gateway."""
    agent = RobotAgent(config)

    # Initialize Frontend Gateway if frontend_port is configured
    gateway: Optional[FrontendGateway] = None
    if config.frontend_port:
        gateway = FrontendGateway(agent=agent, host=config.broadcast_host, port=config.frontend_port)

    # Signal handlers for clean shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler():
        logging.getLogger("edge_robot").info(f"[{config.robot_id}] Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except NotImplementedError:
            pass

    await agent.start()

    if gateway:
        await gateway.start()

    if goal:
        agent.set_goal(goal)

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        if gateway:
            await gateway.stop()
        await agent.stop()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Autonomous Mobile Robot (AMR) Edge Agent")
    parser.add_argument("--robot-id", type=str, default="AMR-01", help="Robot Identifier (e.g. AMR-01)")
    parser.add_argument("--config", type=str, default=None, help="Path to config file (.json/.yaml)")
    parser.add_argument("--port", type=int, default=None, help="P2P UDP listening port override (e.g. 5001)")
    parser.add_argument("--frontend-port", type=int, default=None, help="WebSocket frontend simulation port (e.g. 8001)")
    parser.add_argument("--start", type=str, default=None, help="Initial position as 'x,y' (e.g. 1.0,2.0)")
    parser.add_argument("--goal", type=str, default=None, help="Navigation destination as 'x,y' (e.g. 18.0,2.0)")
    parser.add_argument("--speed", type=float, default=None, help="Maximum speed (m/s)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config or args.robot_id)

    # Apply CLI overrides
    if args.robot_id:
        config.robot_id = args.robot_id
    if args.port:
        config.network_port = args.port
    if args.frontend_port is not None:
        config.frontend_port = args.frontend_port
    if args.start:
        config.initial_position = parse_coords(args.start)
    if args.speed:
        config.max_speed = args.speed

    goal_coord = parse_coords(args.goal) if args.goal else config.default_goal

    setup_logging(config.robot_id, verbose=args.verbose)

    try:
        asyncio.run(run_robot(config, goal=goal_coord))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
