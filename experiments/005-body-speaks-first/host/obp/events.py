"""What the host does with an event a body sent unprompted.

Experiments 001-004 are all brain-to-body: every message on the wire answers
something the host asked. `notifications/body/event` is the one message that
does not, and until now the host threw every one away -- `client._request`
skipped anything without an `id`, and the MQTT transport subscribed to the
event topic and dropped what arrived.

Two rules from the specification are implemented here, and both exist for
reasons a Pico demonstrates:

  * **Deduplicate by event id.** "A ULID or UUID, so a host can deduplicate
    across a reconnect." A body that publishes at QoS 1 and a broker that
    redelivers on reconnect will hand the same press over twice; without an
    id the host cannot tell that from two presses.
  * **Distrust the body's clock when it says so.** A Pico has no RTC, so its
    `ts` counts from boot. It sets `clock_confident: false`, and the host then
    orders by arrival instead. A timestamp that is wrong is a nuisance; one
    that is wrong and trusted is a bug in whatever reasons about it.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class Event:
    body_id: str
    type: str
    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    body_ts: str = ""
    clock_confident: bool = True
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_wire(cls, body_id: str, params: dict[str, Any]) -> "Event":
        return cls(
            body_id=body_id,
            type=params.get("type", "unknown"),
            name=params.get("name", ""),
            payload=params.get("payload") or {},
            event_id=params.get("id", ""),
            body_ts=params.get("ts", ""),
            clock_confident=bool(params.get("clock_confident", True)),
        )

    def when(self) -> str:
        """The timestamp to believe, and a note when it is not the body's."""
        if self.clock_confident and self.body_ts:
            return self.body_ts
        return self.received_at.isoformat(timespec="milliseconds") + " (arrival)"

    def describe(self) -> str:
        bits = " ".join(f"{k}={v}" for k, v in self.payload.items())
        name = f" {self.name}" if self.name else ""
        return f"{self.when()}  {self.body_id}  {self.type}{name}" + (f"  {bits}" if bits else "")


class EventLog:
    """Every event every body has sent, newest last, deduplicated by id.

    Bounded on purpose. A body with a loose wire can emit faster than anyone
    reads, and an unbounded log turns that into the host's problem rather
    than the body's.
    """

    def __init__(self, capacity: int = 256,
                 on_event: Callable[[Event], None] | None = None) -> None:
        self._events: deque[Event] = deque(maxlen=capacity)
        self._seen: deque[str] = deque(maxlen=capacity * 4)
        self._seen_set: set[str] = set()
        self._lock = threading.Lock()
        #: Total events ever recorded, so a cursor stays meaningful after the
        #: bounded deque has discarded the oldest ones.
        self._seq = 0
        self._waiters: list[threading.Event] = []
        self.on_event = on_event
        self.dropped_duplicates = 0

    def record(self, body_id: str, params: dict[str, Any]) -> Event | None:
        """Take one event off the wire. Returns None if it is a duplicate."""
        event = Event.from_wire(body_id, params)
        with self._lock:
            if event.event_id:
                if event.event_id in self._seen_set:
                    self.dropped_duplicates += 1
                    return None
                if len(self._seen) == self._seen.maxlen:
                    self._seen_set.discard(self._seen[0])
                self._seen.append(event.event_id)
                self._seen_set.add(event.event_id)
            self._events.append(event)
            self._seq += 1
            waiters, self._waiters = self._waiters, []
        for w in waiters:
            w.set()
        if self.on_event:
            self.on_event(event)
        return event

    def since(self, cursor: int = 0) -> tuple[list[Event], int]:
        """Events after `cursor`, and the cursor to pass next time.

        A cursor rather than a drain: two callers reading the same log must
        not steal each other's events, and an agent that asks twice should
        see the same history both times.
        """
        with self._lock:
            # `_seq` counts every event ever recorded; the deque holds only
            # the last `capacity`. A cursor older than the window silently
            # starts at the oldest event still held rather than failing --
            # the events are gone either way, and refusing to answer helps
            # nobody.
            oldest = self._seq - len(self._events)
            start = max(0, cursor - oldest)
            return list(self._events)[start:], self._seq

    def wait(self, timeout: float, cursor: int = 0) -> tuple[list[Event], int]:
        """Block until an event arrives, or the timeout expires.

        This is how "tell me when someone presses the button" is expressible
        at all over a request/response transport like MCP, which has no way
        for a server to speak first.
        """
        events, now = self.since(cursor)
        if events:
            return events, now
        flag = threading.Event()
        with self._lock:
            self._waiters.append(flag)
        flag.wait(timeout)
        return self.since(cursor)

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)
