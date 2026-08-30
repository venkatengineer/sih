"""
Launch System - Single-command launcher for SIH Decentralized Multi-AMR Fleet & Control Center.
Starts 4 isolated Python Edge Robot Agents + Web Control Center backend.
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("launch_system")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROBOT_DIR = os.path.join(BASE_DIR, "robot")
CONTROL_DIR = os.path.join(BASE_DIR, "control_center")
LOG_DIR = os.path.join(BASE_DIR, ".logs")

os.makedirs(LOG_DIR, exist_ok=True)


def spawn_processes():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROBOT_DIR}:{BASE_DIR}:{env.get('PYTHONPATH', '')}"

    processes = {}

    logger.info("=" * 70)
    logger.info("🚀 LAUNCHING DECENTRALIZED MULTI-AMR FLEET & WEB CONTROL CENTER")
    logger.info("=" * 70)

    # Launch Web Control Center Daemon (Hosts 4 Edge Agents, P2P UDP 5001-5004, WebSocket 8001-8004, Web 8000)
    cc_log = open(os.path.join(LOG_DIR, "control_center.log"), "w")
    cc_cmd = [sys.executable, "-u", "-m", "control_center.backend.main", "8000"]
    cc_p = subprocess.Popen(cc_cmd, stdout=cc_log, stderr=subprocess.STDOUT, env=env, cwd=BASE_DIR)
    processes["CONTROL_CENTER"] = (cc_p, cc_log)

    logger.info(f"✅ AMR-01 Started (P2P UDP: 5001 | Godot WebSocket: 8001)")
    logger.info(f"✅ AMR-02 Started (P2P UDP: 5002 | Godot WebSocket: 8002)")
    logger.info(f"✅ AMR-03 Started (P2P UDP: 5003 | Godot WebSocket: 8003)")
    logger.info(f"✅ AMR-04 Started (P2P UDP: 5004 | Godot WebSocket: 8004)")
    logger.info(f"✅ Web Control Center Started (PID {cc_p.pid} | HTTP: 8000 | ws://localhost:8000/ws)")

    logger.info("=" * 70)
    logger.info("🎯 All 4 Decentralized Edge Agents & Control Center are RUNNING!")
    logger.info("🌐 Web Control Center:  http://localhost:8000")
    logger.info("🎮 Godot 3D Twin:       godot --path warehouse scenes/main.tscn")
    logger.info("=" * 70)

    return processes


def main():
    processes = spawn_processes()

    def _shutdown(signum, frame):
        logger.info("\n🛑 Stopping all processes...")
        for name, (p, f) in processes.items():
            try:
                p.terminate()
                p.wait(timeout=2.0)
            except Exception:
                p.kill()
            try:
                f.close()
            except Exception:
                pass
            logger.info(f"  • Stopped {name}")
        logger.info("✅ All systems cleanly shutdown.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Monitor loop
    while True:
        time.sleep(1.0)
        for name, (p, _) in list(processes.items()):
            ret = p.poll()
            if ret is not None:
                logger.warning(f"⚠️ Process {name} exited with code {ret}")


if __name__ == "__main__":
    main()
