#!/usr/bin/env python3
"""Drive OBP bodies over USB or MQTT — the same commands either way.

    uv run --with paho-mqtt python3 host/obp_cli.py --mqtt bodies
    uv run --with paho-mqtt python3 host/obp_cli.py --mqtt describe
    uv run --with paho-mqtt python3 host/obp_cli.py --mqtt call blink times=5

    # both bindings at once, which is the point of the experiment
    uv run --with paho-mqtt --with pyserial python3 host/obp_cli.py --mqtt --port auto bodies
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from obp import (BodyClient, BodyError, BodyUnavailable, MqttConnection,  # noqa: E402
                 MqttTransport, Registry, SerialTransport, describe_spec, expand,
                 resolve)
from obp.client import render_result  # noqa: E402
from obp.naming import mcp_tool_name  # noqa: E402


def parse_kv(pair: str) -> tuple[str, object]:
    k, _, raw = pair.partition("=")
    if not _:
        raise SystemExit(f"expected key=value, got {pair!r}")
    try:
        return k, json.loads(raw)
    except json.JSONDecodeError:
        return k, raw


def attach(args) -> tuple[Registry, MqttConnection | None]:
    reg = Registry()
    conn = None

    if args.mqtt:
        conn = MqttConnection(args.broker, args.broker_port)
        conn.connect()
        for body_id in conn.bodies():
            client = BodyClient(MqttTransport(conn, body_id))
            client.transport.open()
            try:
                reg.add(client)
            except BodyError as exc:
                print(f"{body_id}: {exc}", file=sys.stderr)

    # `auto` means every attached USB serial device, so it has to be expanded
    # before resolving -- resolve() only matches one spec to one path and has
    # no idea 'auto' is a word. Experiment 002 does this; this CLI did not, so
    # --port auto quietly found nothing while reporting devices were attached.
    for spec in expand(args.port):
        path = resolve(spec)
        if path is None:
            print(describe_spec(spec), file=sys.stderr)
            continue
        try:
            client = BodyClient(SerialTransport(path))
            client.transport.open()
            reg.add(client)
        except (BodyUnavailable, BodyError, OSError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)

    return reg, conn


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mqtt", action="store_true", help="discover bodies on a broker")
    p.add_argument("--broker", default="127.0.0.1")
    p.add_argument("--broker-port", type=int, default=1883)
    p.add_argument("--port", action="append", default=[],
                   help="'auto' for every USB serial device, or a path or "
                        "serial fragment; repeatable")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bodies")
    d = sub.add_parser("describe"); d.add_argument("body", nargs="?")
    c = sub.add_parser("call")
    c.add_argument("verb"); c.add_argument("args", nargs="*", metavar="KEY=VALUE")
    c.add_argument("--body")
    args = p.parse_args()

    if not args.mqtt and not args.port:
        args.mqtt = True                       # the point of this experiment

    reg, conn = attach(args)
    try:
        if not reg.bodies:
            print("no bodies present", file=sys.stderr)
            return 2

        if args.cmd == "bodies":
            for info in reg.bodies:
                verbs = len([t for t in info.tools if not t.user_only])
                via = "mqtt" if info.id in (conn.bodies() if conn else []) else "usb"
                print(f"{info.id:<20} {info.name:<34} {verbs} verbs  via {via}  "
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
                    sig = ", ".join(f"{k}:{v.get('type','?')}" for k, v in props.items())
                    flag = "  !user-only" if t.user_only else ""
                    print(f"  {t.name}({sig}){flag}\n      {t.description}")
                print()
            return 0

        target = next((i for i in reg.bodies
                       if (not args.body or i.id == args.body) and i.tool(args.verb)), None)
        if target is None:
            print(f"no present body offers '{args.verb}'", file=sys.stderr)
            return 2
        result = reg.call(mcp_tool_name(target.id, args.verb),
                          dict(parse_kv(a) for a in args.args), autonomous=False)
        print(render_result(result))
        return 1 if result.get("isError") else 0
    finally:
        reg.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
