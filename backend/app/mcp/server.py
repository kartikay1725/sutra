"""SUTRA MCP Server Instance and Transport Configuration.

Provides the official MCP Python SDK Streamable HTTP server configured for
production integration into FastAPI.
"""
from __future__ import annotations

import logging
from typing import List

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import BaseRoute, Route

from app.mcp.tools import register_sutra_tools

logger = logging.getLogger("sutra.mcp.server")

# 1. Instantiate the official MCP Server
mcp_server = MCPServer(
    name="sutra",
    instructions=(
        "SUTRA is an AI-native engineering control plane that coordinates, audits, "
        "and governs autonomous coding agents. Code cannot be merged into production "
        "branches without satisfying SUTRA's 4-pillar governance policy and human approval. "
        "Always begin your interaction by calling sutra_get_context."
    ),
    version="0.4.0",
)

# 2. Register the 8 curated agent tools
register_sutra_tools(mcp_server)

# 3. Configure transport security settings
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=["*"],
    allowed_origins=["*"],
)

# 4. Generate the official Streamable HTTP Starlette application
_streamable_app = mcp_server.streamable_http_app(
    streamable_http_path="/v1/mcp",
    transport_security=_transport_security,
)


def get_mcp_routes() -> List[BaseRoute]:
    """
    Returns the Starlette routes configured for Streamable HTTP transport.
    Includes both /v1/mcp and /v1/mcp/ to handle all client URL patterns without redirects.
    """
    base_route = _streamable_app.routes[0]
    if not hasattr(base_route.endpoint, "__name__"):
        base_route.endpoint.__name__ = "streamable_http_endpoint"
    return [
        Route("/v1/mcp", endpoint=base_route.endpoint),
        Route("/v1/mcp/", endpoint=base_route.endpoint),
    ]

