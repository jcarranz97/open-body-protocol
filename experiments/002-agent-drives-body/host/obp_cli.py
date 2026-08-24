#!/usr/bin/env python3
"""Drive OBP bodies from the command line.

Any agent that can run a shell command can drive a body this way, with no
MCP and no configuration. It is also how a person checks a new body.

    python3 host/obp_cli.py --fake bodies
    python3 host/obp_cli.py --port /dev/ttyACM0 describe
    python3 host/obp_cli.py --port /dev/ttyACM0 call set_brightness level=40
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from obp import (BodyClient, BodyError, BodyUnavailable, Registry,  # noqa: E402
                 SerialTransport, SubprocessTransport, describe_spec, expand,
                 resolve)
from obp.client import render_result  # noqa: E402
from obp.naming import mcp_tool_name  # noqa: E402


def attach(args) -> Registry:
    reg = Registry()
    for spec in expand(args.port or ([] if args.fake else ['auto'])):
        path = resolve(spec)
        if path is None:
            raise SystemExit(describe_spec(spec))
        client = BodyClient(SerialTransport(path))
        client.transport.open()
        reg.add(client)
    if args.fake:
        client = BodyClient(SubprocessTransport(
            [sys.executable, str(Path(__file__).parent / "fake_body.py")]))
        client.transport.open()
        reg.add(client)
    return reg


def parse_kv(pair: str) -> tuple[str, object]:
    k, _, raw = pair.partition("=")
    if not _:
        raise SystemExit(f"expected key=value, got {pair!r}")
    try:
        return k, json.loads(raw)
    except json.JSONDecodeError:
        return k, raw


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", action="append", default=[],
                   help="'auto' (the default) attaches every USB serial device; "
                        "or give a device path, a /dev/serial/by-id/... path, or "
                        "a fragment of the board serial such as 3f5022. Repeatable.")
    p.add_argument("--fake", action="store_true", help="attach the hardware-free body")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bodies", help="which bodies are present")
    d = sub.add_parser("describe", help="verbs and schemas")
    d.add_argument("body", nargs="?", help="body id, if more than one is present")
    c = sub.add_parser("call", help="invoke a verb")
    c.add_argument("verb")
    c.add_argument("args", nargs="*", metavar="KEY=VALUE")
    c.add_argument("--body", help="body id, if more than one is present")
    args = p.parse_args()

    try:
        reg = attach(args)
    except BodyUnavailable as exc:
        print(exc, file=sys.stderr)
        return 3
    except (BodyError, OSError) as exc:
        print(f"could not attach: {exc}", file=sys.stderr)
        return 3

    try:
        if args.cmd == "bodies":
            for info in reg.bodies:
                verbs = len([t for t in info.tools if not t.user_only])
                print(f"{info.id:<20} {info.name:<38} {verbs} verbs  "
                      f"caps: {', '.join(info.caps) or '-'}")
            return 0

        if args.cmd == "describe":
            for info in reg.bodies:
                if args.body and info.id != args.body:
                    continue
                print(f"{info.name}  [{info.id}]  fw {info.firmware}")
                print(f"caps: {', '.join(info.caps) or '(none)'}")
                for t in info.tools:
                    props = t.input_schema.get("properties") or {}
                    sig = ", ".join(
                        f"{k}:{v.get('type','?')}" + (
                            f"[{v['minimum']}..{v['maximum']}]"
                            if "minimum" in v and "maximum" in v else "")
                        for k, v in props.items())
                    flag = "  !user-only (never offered to an agent)" if t.user_only else ""
                    print(f"  {t.name}({sig}){flag}")
                    print(f"      {t.description}")
                    if not t.user_only:
                        print(f"      mcp: {mcp_tool_name(info.id, t.name)}")
                print()
            return 0

        # call
        target = None
        for info in reg.bodies:
            if args.body and info.id != args.body:
                continue
            if info.tool(args.verb):
                target = info
                break
        if target is None:
            print(f"no present body offers '{args.verb}'", file=sys.stderr)
            return 2
        spec = target.tool(args.verb)
        if spec.user_only:
            print(f"note: {spec.name} is user-only — available here because a "
                  f"person is asking, and never offered to an agent",
                  file=sys.stderr)
        result = reg.call(mcp_tool_name(target.id, args.verb),
                          dict(parse_kv(a) for a in args.args),
                          autonomous=False)
        print(render_result(result))
        return 1 if result.get("isError") else 0
    finally:
        reg.close()


if __name__ == "__main__":
    raise SystemExit(main())
