#!/usr/bin/env python3
"""Drive a TAMALAB body from the command line.

    # no hardware at all -- the body is a subprocess speaking the same protocol
    python3 host/cli.py --fake describe
    python3 host/cli.py --fake call set_led --arg on=true

    # a real Raspberry Pi Pico over USB
    uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 describe
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tamabody import BodyClient, BodyError, SerialTransport, SubprocessTransport  # noqa: E402
from tamabody.client import render_result  # noqa: E402


def parse_arg(pair: str) -> tuple[str, object]:
    key, _, raw = pair.partition("=")
    if not _:
        raise SystemExit(f"--arg expects key=value, got {pair!r}")
    try:
        return key, json.loads(raw)
    except json.JSONDecodeError:
        return key, raw  # bare strings need no quoting


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="serial device, e.g. /dev/ttyACM0")
    src.add_argument("--fake", action="store_true", help="run the stub body as a subprocess")
    p.add_argument("--timeout", type=float, default=5.0)

    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("describe", help="print the body's identity, caps and tools")
    c = sub.add_parser("call", help="call one tool")
    c.add_argument("tool")
    c.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE")

    args = p.parse_args()

    if args.fake:
        transport = SubprocessTransport([sys.executable, str(Path(__file__).parent / "fake_body.py")])
    else:
        transport = SerialTransport(args.port)

    try:
        with BodyClient(transport, timeout=args.timeout) as client:
            info = client.describe()

            if args.cmd == "describe":
                print(f"{info.name}  [{info.id}]  fw {info.firmware}")
                print(f"caps: {', '.join(info.caps) or '(none)'}")
                print(f"tools: {len(info.tools)}")
                for t in info.tools:
                    flag = "  !user-only" if t.user_only else ""
                    props = ", ".join((t.input_schema.get("properties") or {}).keys()) or "-"
                    print(f"  - {t.name}({props}){flag}")
                    print(f"      {t.description}")
                return 0

            spec = info.tool(args.tool)
            if spec is None:
                print(f"body advertises no tool named {args.tool!r}", file=sys.stderr)
                print(f"available: {', '.join(t.name for t in info.tools)}", file=sys.stderr)
                return 2
            if spec.user_only:
                print(f"note: {spec.name} is user-only; an agent must not call it autonomously", file=sys.stderr)

            result = client.call(args.tool, dict(parse_arg(a) for a in args.arg))
            print(render_result(result))
            return 1 if result.get("isError") else 0

    except BodyError as exc:
        print(f"body error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
