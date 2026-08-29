"""
Integration test for multiple independent RobotAgents running concurrently.
"""

import unittest
import asyncio
from edge_robot.config import RobotConfig
from edge_robot.core.robot import RobotAgent
from edge_robot.core.enums import RobotStatus


class TestMultiAgentIntegration(unittest.TestCase):
    def test_independent_robot_agents_peer_coordination(self):
        async def _run():
            cfg1 = RobotConfig(
                robot_id="AMR-01",
                initial_position=(1.0, 2.0),
                network_port=5801,
                peer_endpoints=[("127.0.0.1", 5801), ("127.0.0.1", 5802)],
                default_goal=(6.0, 2.0),
                loop_rate_hz=20.0,
                max_speed=2.0,
                safety_distance=0.8,
            )

            cfg2 = RobotConfig(
                robot_id="AMR-02",
                initial_position=(6.0, 2.0),
                network_port=5802,
                peer_endpoints=[("127.0.0.1", 5801), ("127.0.0.1", 5802)],
                default_goal=(1.0, 2.0),
                loop_rate_hz=20.0,
                max_speed=2.0,
                safety_distance=0.8,
            )

            agent1 = RobotAgent(cfg1)
            agent2 = RobotAgent(cfg2)

            await agent1.start()
            await agent2.start()

            try:
                await asyncio.sleep(2.0)

                # Both agents moved along their paths
                self.assertNotEqual(agent1.state.position, (1.0, 2.0))
                self.assertNotEqual(agent2.state.position, (6.0, 2.0))

                # Peer awareness through UDP
                peers_known_by_1 = agent1.peer_table.get_all_active_peers()
                peers_known_by_2 = agent2.peer_table.get_all_active_peers()

                self.assertIn("AMR-02", peers_known_by_1)
                self.assertIn("AMR-01", peers_known_by_2)

            finally:
                await agent1.stop()
                await agent2.stop()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
