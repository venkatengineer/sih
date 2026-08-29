"""
Peer discovery mechanisms for P2P edge network.
"""

from typing import List, Tuple, Set


class PeerDiscovery:
    """Helper to manage and discover peer robot endpoints."""

    def __init__(self, static_endpoints: List[Tuple[str, int]]):
        self.known_endpoints: Set[Tuple[str, int]] = set(static_endpoints)

    def add_endpoint(self, host: str, port: int) -> None:
        self.known_endpoints.add((host, port))

    def get_endpoints(self) -> List[Tuple[str, int]]:
        return list(self.known_endpoints)
