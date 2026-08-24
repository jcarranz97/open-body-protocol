"""A host for many bodies at once: USB, MQTT and local fakes, one registry."""

from .client import BodyClient, BodyError, ToolSpec
from .naming import mcp_tool_name, split_tool_name
from .ports import AUTO, describe_spec, expand, resolve, stable_ports
from .registry import Registry
from .transport import BodyUnavailable, SerialTransport, SubprocessTransport

__all__ = [
    "BodyClient", "BodyError", "ToolSpec", "Registry",
    "MqttConnection", "MqttTransport",
    "mcp_tool_name", "split_tool_name",
    "resolve", "stable_ports", "describe_spec", "expand", "AUTO",
    "SerialTransport", "SubprocessTransport", "BodyUnavailable",
]


def __getattr__(name: str):
    """Import the MQTT binding only when it is actually used.

    Experiment 004's Part A runs with no hardware and no broker, and an
    eager `from .mqtt import ...` made that impossible: paho-mqtt is a
    dependency of one binding, not of the host. A binding nobody asked for
    should not be a reason the host will not start.
    """
    if name in ("MqttConnection", "MqttTransport"):
        from . import mqtt
        return getattr(mqtt, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
