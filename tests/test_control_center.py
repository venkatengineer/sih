"""
Unit and Integration Tests for Web-Based AMR Fleet Control Center.
Tests REST APIs, WebSocket live event streaming, task auctions, and decentralized consensus.
"""

import asyncio
import json
import sys
import unittest
import urllib.request
import urllib.parse
import time

# Ensure /data/sih and /data/sih/robot are in path
if "/data/sih" not in sys.path:
    sys.path.insert(0, "/data/sih")
if "/data/sih/robot" not in sys.path:
    sys.path.insert(0, "/data/sih/robot")

from control_center.backend.server import AsyncControlCenterServer
from control_center.backend.bridge.robot_bridge import fleet_bridge


class TestControlCenter(unittest.IsolatedAsyncioTestCase):
    """Test suite for Web Control Center."""

    @classmethod
    def setUpClass(cls):
        cls.port = 8899

    async def asyncSetUp(self):
        self.server = AsyncControlCenterServer(host="127.0.0.1", port=self.port)
        await self.server.start()
        await asyncio.sleep(0.15)

    async def asyncTearDown(self):
        await self.server.stop()
        await asyncio.sleep(0.15)

    async def _async_http_get(self, path: str) -> dict:
        def _get():
            url = f"http://127.0.0.1:{self.port}{path}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=4) as res:
                return json.loads(res.read().decode("utf-8"))
        return await asyncio.to_thread(_get)

    async def _async_http_post(self, path: str, body: dict) -> dict:
        def _post():
            url = f"http://127.0.0.1:{self.port}{path}"
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as res:
                return json.loads(res.read().decode("utf-8"))
        return await asyncio.to_thread(_post)

    async def test_get_fleet_api(self):
        """Verify GET /api/fleet returns 4 online AMRs and decentralized system metadata."""
        data = await self._async_http_get("/api/fleet")
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["fleet"]), 4)
        robot_ids = [r["robot_id"] for r in data["fleet"]]
        self.assertIn("AMR-01", robot_ids)
        self.assertIn("AMR-02", robot_ids)
        self.assertEqual(data["system"]["central_server"], "NONE")
        self.assertEqual(data["system"]["mode"], "DECENTRALIZED")

    async def test_get_robots_and_robot_detail_api(self):
        """Verify GET /api/robots and GET /api/robots/{id}."""
        robots_res = await self._async_http_get("/api/robots")
        self.assertEqual(robots_res["status"], "success")
        self.assertEqual(len(robots_res["robots"]), 4)

        amr2_res = await self._async_http_get("/api/robots/AMR-02")
        self.assertEqual(amr2_res["status"], "success")
        self.assertEqual(amr2_res["robot"]["robot_id"], "AMR-02")
        self.assertTrue(amr2_res["robot"]["is_online"])

    async def test_pause_and_resume_robot_api(self):
        """Verify POST /api/robots/{id}/pause and resume."""
        pause_res = await self._async_http_post("/api/robots/AMR-01/pause", {})
        self.assertEqual(pause_res["status"], "success")

        r = await self._async_http_get("/api/robots/AMR-01")
        self.assertEqual(r["robot"]["status"], "WAITING")

        resume_res = await self._async_http_post("/api/robots/AMR-01/resume", {})
        self.assertEqual(resume_res["status"], "success")

        r2 = await self._async_http_get("/api/robots/AMR-01")
        self.assertEqual(r2["robot"]["status"], "MOVING")

    async def test_create_and_auction_task_api(self):
        """Verify POST /api/tasks submits task to TaskManager and originates P2P auction."""
        task_payload = {
            "task_id": "T-TEST-001",
            "pickup": [3, 16],
            "dropoff": [3, 4],
            "priority": "HIGH",
        }
        res = await self._async_http_post("/api/tasks", task_payload)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["task_id"], "T-TEST-001")
        self.assertEqual(res["task"]["status"], "AUCTIONING")

        # Allow time for P2P UDP auction propagation
        await asyncio.sleep(0.4)

        # Query task detail
        task_detail = await self._async_http_get("/api/tasks/T-TEST-001")
        self.assertEqual(task_detail["status"], "success")
        t = task_detail["task"]
        self.assertEqual(t["task_id"], "T-TEST-001")
        self.assertIn(t["status"], ["ASSIGNED", "IN_PROGRESS", "AUCTIONING"])

    async def test_cancel_task_api(self):
        """Verify POST /api/tasks/{task_id}/cancel."""
        task_payload = {
            "task_id": "T-CANCEL-01",
            "pickup": [2, 5],
            "dropoff": [14, 2],
            "priority": 3,
        }
        await self._async_http_post("/api/tasks", task_payload)
        await asyncio.sleep(0.1)

        cancel_res = await self._async_http_post("/api/tasks/T-CANCEL-01/cancel", {})
        self.assertEqual(cancel_res["status"], "success")
        self.assertEqual(cancel_res["task"]["status"], "CANCELLED")

    async def test_system_status_and_events_api(self):
        """Verify GET /api/system and GET /api/events."""
        sys_res = await self._async_http_get("/api/system")
        self.assertEqual(sys_res["status"], "success")
        self.assertEqual(sys_res["system"]["network"], "P2P UDP")

        events_res = await self._async_http_get("/api/events")
        self.assertEqual(events_res["status"], "success")
        self.assertIsInstance(events_res["events"], list)
        self.assertGreater(len(events_res["events"]), 0)

    async def test_static_ui_serving(self):
        """Verify GET / returns index.html for web browser."""
        def _get_index():
            url = f"http://127.0.0.1:{self.port}/"
            with urllib.request.urlopen(url, timeout=4) as res:
                return res.read().decode("utf-8")

        html = await asyncio.to_thread(_get_index)
        self.assertIn("AMR FLEET OPS", html)
        self.assertIn("Decentralized Edge Hub", html)


if __name__ == "__main__":
    unittest.main()
