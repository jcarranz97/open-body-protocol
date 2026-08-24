"""A minimal OBP host: registry, MCP-safe naming, and an MCP stdio server.

Self-contained on purpose. Experiments do not import each other, so the
transport and client are copied from 001 rather than shared.
"""

from .client import BodyClient, BodyError, ToolSpec
from .naming import mcp_tool_name, split_tool_name
from .ports import AUTO, describe_spec, expand, resolve, stable_ports
from .registry import Registry
from .transport import BodyUnavailable, SerialTransport, SubprocessTransport

__all__ = [
    "BodyClient", "BodyError", "ToolSpec", "Registry",
    "mcp_tool_name", "split_tool_name",
    "resolve", "stable_ports", "describe_spec", "expand", "AUTO",
    "SerialTransport", "SubprocessTransport", "BodyUnavailable",
]
