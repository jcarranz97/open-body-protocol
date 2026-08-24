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

from obp import BodyClient, BodyError, Registry, SerialTransport, SubprocessTransport  # noqa: E402
from obp.mcp import McpServer  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", action="append", default=[], help="serial device; repeatable")
    p.add_argument("--fake", action="store_true", help="also attach the hardware-free body")
    p.add_argument("--log", type=Path, help="append the MCP conversation here")
    args = p.parse_args()

    registry = Registry()
    server = McpServer(registry, log_path=args.log)

    for port in args.port:
        try:
            client = BodyClient(SerialTransport(port))
            client.transport.open()
            info = registry.add(client)
            print(f"attached {info.name} [{info.id}] on {port}", file=sys.stderr)
        except (BodyError, OSError) as exc:
            print(f"could not attach {port}: {exc}", file=sys.stderr)

    if args.fake or not args.port:
        client = BodyClient(SubprocessTransport(
            [sys.executable, str(Path(__file__).parent / "fake_body.py")]))
        client.transport.open()
        info = registry.add(client)
        print(f"attached {info.name} [{info.id}]", file=sys.stderr)

    if not registry.bodies:
        print("no bodies attached; exiting", file=sys.stderr)
        return 1

    print(f"serving {len(registry.tools())} tools over MCP on stdio", file=sys.stderr)
    try:
        server.serve()
    except KeyboardInterrupt:
        pass
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
