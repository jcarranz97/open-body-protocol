"""A host for the MQTT binding: discovery, presence, and the same registry."""

from .client import BodyClient, BodyError, ToolSpec
from .mqtt import MqttConnection, MqttTransport
from .naming import mcp_tool_name, split_tool_name
from .ports import describe_spec, resolve, stable_ports
from .registry import Registry
from .transport import BodyUnavailable, SerialTransport, SubprocessTransport

__all__ = [
    "BodyClient", "BodyError", "ToolSpec", "Registry",
    "MqttConnection", "MqttTransport",
    "mcp_tool_name", "split_tool_name",
    "resolve", "stable_ports", "describe_spec",
    "SerialTransport", "SubprocessTransport", "BodyUnavailable",
]
