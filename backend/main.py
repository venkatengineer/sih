"""
Main entrypoint for AMR Fleet Control Center Backend.

Usage:
    python3 -m control_center.backend.main
"""

import asyncio
import logging
import signal
import sys

from control_center.backend.server import AsyncControlCenterServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("control_center")


async def run_server(port: int = 8000):
    server = AsyncControlCenterServer(host="0.0.0.0", port=port)
    await server.start()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler():
        logger.info("Shutdown signal received...")
        stop_event.set()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, _sig_handler)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        await server.stop()


def main():
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    try:
        asyncio.run(run_server(port=port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
