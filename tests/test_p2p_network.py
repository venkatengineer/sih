"""
Unit tests for P2P network messaging and peer table.
"""

import unittest
import asyncio
from edge_robot.core.enums import RobotStatus, RobotIntent
from edge_robot.communication.protocol import (
    create_state_message,
    create_obstacle_message,
    NetworkMessage,
)
from edge_robot.communication.network import P2PNetworkNode
from edge_robot.communication.peer import PeerTable


class TestP2PNetwork(unittest.TestCase):
    def test_udp_p2p_communication(self):
        async def _run():
            node1 = P2PNetworkNode(
                robot_id="AMR-01",
                host="127.0.0.1",
                port=5901,
                peer_endpoints=[("127.0.0.1", 5902)],
            )
            node2 = P2PNetworkNode(
                robot_id="AMR-02",
                host="127.0.0.1",
                port=5902,
                peer_endpoints=[("127.0.0.1", 5901)],
            )

            await node1.start()
            await node2.start()

            try:
                msg = create_state_message(
                    robot_id="AMR-01",
                    position=(5.0, 5.0),
                    heading=0.0,
                    velocity=1.0,
                    battery=90.0,
                    status=RobotStatus.MOVING,
                    intent=RobotIntent.MOVE,
                    priority=55.0,
                    current_path=[(5, 5), (6, 5)],
                    next_node=(6, 5),
                )

                node1.broadcast(msg)
                await asyncio.sleep(0.05)

                received = node2.get_incoming_messages()
                self.assertGreaterEqual(len(received), 1)
                recv_msg, _ = received[0]
                self.assertEqual(recv_msg.sender_id, "AMR-01")
                self.assertEqual(recv_msg.payload["position"], [5.0, 5.0])

            finally:
                await node1.stop()
                await node2.stop()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
