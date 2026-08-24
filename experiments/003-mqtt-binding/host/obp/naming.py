"""MCP-safe tool names (conformance M1-M3).

MCP clients constrain tool names to ^[a-zA-Z0-9_-]{1,64}$ — notably no dots,
so the `body.<id>.<verb>` form used casually elsewhere is not a legal tool
name. The rules here are normative and must produce the same output on every
host and every run: an agent that cached a prompt containing a tool name
must not find it renamed after a restart.
"""

from __future__ import annotations

import hashlib
import re

MAX_LEN = 64
SEP = "__"
_ILLEGAL = re.compile(r"[^a-zA-Z0-9_-]")


def sanitise(part: str) -> str:
    """Replace anything MCP will not accept with an underscore."""
    return _ILLEGAL.sub("_", part)


def mcp_tool_name(body_id: str, verb: str) -> str:
    """Build a deterministic, MCP-legal tool name for a body's verb.

    >>> mcp_tool_name("pico-3f5022", "set_brightness")
    'pico-3f5022__set_brightness'

    When the budget runs out the *body id* is truncated, never the verb —
    the verb is what the model reasons about — and a short hash of the
    original pair keeps distinct bodies distinct.
    """
    sid, sverb = sanitise(body_id), sanitise(verb)
    name = f"{sid}{SEP}{sverb}"
    if len(name) <= MAX_LEN:
        return name

    digest = hashlib.sha256(f"{body_id}{SEP}{verb}".encode()).hexdigest()[:6]
    # room for: <id> SEP <verb> "_" <6-char digest>
    keep = MAX_LEN - len(SEP) - len(sverb) - 1 - len(digest)
    if keep < 1:
        # A verb long enough to fill the budget alone; truncate it too, but
        # only as a last resort, and keep the hash so it stays unique.
        keep_verb = MAX_LEN - 1 - len(digest)
        return f"{sverb[:keep_verb]}_{digest}"
    return f"{sid[:keep]}{SEP}{sverb}_{digest}"


def split_tool_name(name: str) -> tuple[str, str]:
    """Best-effort inverse, for routing a call back to a body.

    Truncated names cannot be inverted, so a host routes by lookup rather
    than by parsing. This exists for logs and error messages.
    """
    head, sep, tail = name.partition(SEP)
    return (head, tail) if sep else ("", name)
