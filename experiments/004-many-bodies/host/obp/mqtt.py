"""The MQTT binding: one broker, many bodies, presence for free.

Topic layout, per the specification's bindings page:

    obp/body/<id>/presence     body -> host, RETAINED, cleared by the will
    obp/body/<id>/rpc          host -> body, requests
    obp/body/<id>/rpc/reply    body -> host, replies
    obp/body/<id>/event        body -> host, unsolicited

Presence is the interesting part and costs nothing: a body publishes a
retained message on connect and registers a Last Will with an *empty*
payload on the same topic. When it dies the broker publishes that empty
payload, which clears the retained message. "Which bodies exist" is then
"what is in the retained set" — no heartbeat table, no TTL sweeper, and a
host that restarts is told the truth as soon as it subscribes.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any

TOPIC_ROOT = "obp/body"


def presence_topic(body_id: str) -> str:
    return f"{TOPIC_ROOT}/{body_id}/presence"


def rpc_topic(body_id: str) -> str:
    return f"{TOPIC_ROOT}/{body_id}/rpc"


def reply_topic(body_id: str) -> str:
    return f"{TOPIC_ROOT}/{body_id}/rpc/reply"


def event_topic(body_id: str) -> str:
    return f"{TOPIC_ROOT}/{body_id}/event"


class MqttConnection:
    """One broker connection, shared by every body behind it."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1883,
                 client_id: str = "obp-host") -> None:
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(
                "paho-mqtt is required. Try:\n"
                "  uv run --with paho-mqtt python3 host/obp_cli.py ..."
            ) from exc

        self._mqtt = mqtt
        self.host, self.port = host, port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=client_id)
        self.client.on_message = self._on_message
        #: body id -> queue of decoded reply objects
        self._replies: dict[str, queue.Queue[dict[str, Any]]] = {}
        #: body id -> presence payload, or None when the retained message cleared
        self.present: dict[str, dict[str, Any] | None] = {}
        self._presence_seen = threading.Event()
        self.on_presence_change = None

    # ------------------------------------------------------------ lifecycle

    def connect(self, timeout: float = 5.0) -> None:
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()
        self.client.subscribe(f"{TOPIC_ROOT}/+/presence", qos=1)
        # Retained presence arrives immediately on subscribe; give the broker
        # a moment to deliver whatever it is holding.
        self._presence_seen.wait(timeout=1.0)

    def close(self) -> None:
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception:
            pass

    # -------------------------------------------------------------- routing

    def _on_message(self, client, userdata, msg) -> None:  # noqa: ANN001
        parts = msg.topic.split("/")
        if len(parts) < 4:
            return
        body_id = parts[2]
        kind = "/".join(parts[3:])

        if kind == "presence":
            if not msg.payload:
                # An empty payload is the Last Will clearing the retained
                # message: this body is gone.
                self.present.pop(body_id, None)
            else:
                try:
                    self.present[body_id] = json.loads(msg.payload)
                except ValueError:
                    self.present[body_id] = {}
            self._presence_seen.set()
            if self.on_presence_change:
                self.on_presence_change(body_id, self.present.get(body_id))
            return

        if kind == "rpc/reply":
            try:
                obj = json.loads(msg.payload)
            except ValueError:
                return
            self._replies.setdefault(body_id, queue.Queue()).put(obj)

    # --------------------------------------------------------------- bodies

    def bodies(self) -> list[str]:
        return sorted(self.present)

    def subscribe_body(self, body_id: str) -> None:
        self._replies.setdefault(body_id, queue.Queue())
        self.client.subscribe(reply_topic(body_id), qos=1)
        self.client.subscribe(event_topic(body_id), qos=1)

    def publish(self, body_id: str, obj: dict[str, Any]) -> None:
        self.client.publish(rpc_topic(body_id), json.dumps(obj), qos=1)

    def take_reply(self, body_id: str, timeout: float) -> dict[str, Any] | None:
        q = self._replies.setdefault(body_id, queue.Queue())
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None


class MqttTransport:
    """A Transport for one body, multiplexed over a shared connection."""

    def __init__(self, connection: MqttConnection, body_id: str) -> None:
        self.connection = connection
        self.body_id = body_id
        self.port = f"mqtt://{connection.host}:{connection.port}/{body_id}"

    kind = "mqtt"

    def describe(self) -> str:
        return f"mqtt {self.connection.host}:{self.connection.port}"

    def open(self) -> None:
        self.connection.subscribe_body(self.body_id)

    def close(self) -> None:
        pass                       # the connection outlives any one body

    def send(self, obj: dict[str, Any]) -> None:
        if self.body_id not in self.connection.present:
            raise ConnectionError(f"body {self.body_id} is not present")
        self.connection.publish(self.body_id, obj)

    def recv(self, timeout: float) -> dict[str, Any] | None:
        return self.connection.take_reply(self.body_id, timeout)

    @property
    def alive(self) -> bool:
        return self.body_id in self.connection.present
