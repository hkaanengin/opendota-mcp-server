"""OpenDota client: the only layer that talks to OpenDota."""

from opendota_mcp.api.client import OpenDotaClient, PlayerNotFoundError

__all__ = ["OpenDotaClient", "PlayerNotFoundError"]
