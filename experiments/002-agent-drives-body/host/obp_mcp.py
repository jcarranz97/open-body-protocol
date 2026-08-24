#!/usr/bin/env python3
"""Expose OBP bodies to an MCP client over stdio.

    claude mcp add obp -- python3 /abs/path/host/obp_mcp.py --port /dev/ttyACM0
    claude mcp add obp -- python3 /abs/path/host/obp_mcp.py --fake
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from obp import (BodyClient, BodyError, BodyUnavailable, Registry,  # noqa: E402
                 SerialTransport, SubprocessTransport, describe_spec, resolve)
from obp.mcp import McpServer  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", action="append", default=[],
                   help="device path, /dev/serial/by-id/... path, or a fragment "
                        "of the board serial such as 3f5022; repeatable")
    p.add_argument("--fake", action="store_true", help="also attach the hardware-free body")
    p.add_argument("--log", type=Path, help="append the MCP conversation here")
    args = p.parse_args()

    registry = Registry()
    problems: list[str] = []

    def attach() -> list[str]:
        """Attach whatever is reachable. Never fatal: an MCP server that
        exits because a cable is unplugged looks to the agent exactly like a
        broken server, and the user learns nothing."""
        problems.clear()
        attached = {b.id for b in registry.bodies}
        for spec in args.port:
            path = resolve(spec)
            if path is None:
                problems.append(describe_spec(spec))
                continue
            if any(path == getattr(e.client.transport, "port", None)
                   for e in registry._bodies.values()):
                continue
            try:
                client = BodyClient(SerialTransport(path))
                client.transport.open()
                info = registry.add(client)
                print(f"attached {info.name} [{info.id}] on {path}", file=sys.stderr)
            except BodyUnavailable as exc:
                problems.append(f"{path}:\n{exc}")
            except (BodyError, OSError) as exc:
                problems.append(f"{path}: {exc}")
        if (args.fake or not args.port) and not any(
                b.id.startswith("fake-") for b in registry.bodies):
            try:
                client = BodyClient(SubprocessTransport(
                    [sys.executable, str(Path(__file__).parent / "fake_body.py")]))
                client.transport.open()
                info = registry.add(client)
                print(f"attached {info.name} [{info.id}]", file=sys.stderr)
            except (BodyError, OSError) as exc:
                problems.append(f"fake body: {exc}")
        return list(problems)

    server = McpServer(registry, log_path=args.log, attach=attach)
    attach()
    server.problems = list(problems)

    for p in problems:
        print(p, file=sys.stderr)
    print(f"serving {len(registry.bodies)} bodies over MCP on stdio", file=sys.stderr)

    try:
        server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
