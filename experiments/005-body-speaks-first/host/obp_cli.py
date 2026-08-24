#!/usr/bin/env python3
"""Drive many OBP bodies at once — USB, MQTT and local fakes, one registry.

    uv run --with paho-mqtt python3 host/obp_cli.py --mqtt bodies
    uv run python3 host/obp_cli.py --fake 4 bodies          # four local bodies
    uv run python3 host/obp_cli.py --fake-id twin --fake-id twin bodies
    uv run --with paho-mqtt python3 host/obp_cli.py --mqtt describe
    uv run --with paho-mqtt python3 host/obp_cli.py --mqtt call blink times=5

    # both bindings at once, which is the point of the experiment
    uv run --with paho-mqtt --with pyserial python3 host/obp_cli.py --mqtt --port auto bodies
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from obp import (BodyClient, BodyError, BodyUnavailable, Registry,  # noqa: E402
                 SerialTransport, SubprocessTransport, describe_spec, expand,
                 resolve)
from obp.registry import DuplicateBodyId  # noqa: E402
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


FAKE = Path(__file__).parent / "fake_body.py"


def fake_ids(args) -> list[str]:
    """Explicit --fake-id values, plus --fake N generated ones."""
    ids = list(args.fake_id)
    ids += [f"{i:04d}" for i in range(1, args.fake + 1)]
    return ids


def attach(args) -> tuple[Registry, MqttConnection | None]:
    reg = Registry()
    conn = None

    for i, oid in enumerate(fake_ids(args)):
        env = dict(os.environ, OBP_ID=oid)
        # Give them different hardware, so a multi-body list is not four
        # copies of one thing -- every other body gets a servo, and the
        # third of each trio cannot dim.
        env["OBP_SERVO"] = "1" if i % 2 else "0"
        env["OBP_DIMMABLE"] = "0" if i % 3 == 2 else "1"
        client = BodyClient(SubprocessTransport([sys.executable, str(FAKE)], env=env))
        client.transport.open()
        try:
            reg.add(client)
        except DuplicateBodyId as exc:
            print(f"refused: {exc}", file=sys.stderr)
        except BodyError as exc:
            print(f"fake-{oid}: {exc}", file=sys.stderr)

    if args.mqtt:
        from obp import MqttConnection, MqttTransport
        conn = MqttConnection(args.broker, args.broker_port)
        conn.connect()
        for body_id in conn.bodies():
            client = BodyClient(MqttTransport(conn, body_id))
            client.transport.open()
            try:
                reg.add(client)
            except DuplicateBodyId as exc:
                print(f"refused: {exc}", file=sys.stderr)
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
        except DuplicateBodyId as exc:
            print(f"refused: {exc}", file=sys.stderr)
        except (BodyUnavailable, BodyError, OSError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)

    return reg, conn


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mqtt", action="store_true", help="discover bodies on a broker")
    p.add_argument("--fake", type=int, default=0, metavar="N",
                   help="spawn N local fake bodies, no hardware needed")
    p.add_argument("--fake-id", action="append", default=[], metavar="ID",
                   help="spawn a fake body with this id; repeat it to collide two")
    p.add_argument("--broker", default="127.0.0.1")
    p.add_argument("--broker-port", type=int, default=1883)
    p.add_argument("--port", action="append", default=[],
                   help="'auto' for every USB serial device, or a path or "
                        "serial fragment; repeatable")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bodies")
    sub.add_parser("events")
    w = sub.add_parser("watch")
    w.add_argument("--seconds", type=float, default=60.0)
    d = sub.add_parser("describe"); d.add_argument("body", nargs="?")
    c = sub.add_parser("call")
    c.add_argument("verb"); c.add_argument("args", nargs="*", metavar="KEY=VALUE")
    c.add_argument("--body")
    args = p.parse_args()

    # Selection is per-shell, in the environment, exactly as adb does it with
    # $ANDROID_SERIAL plus -s. Deliberately NOT a state file: kubectl's
    # current-context is one global mutable pointer shared by every terminal,
    # so the same command means different things in two windows -- the shape
    # behind a documented three-hour production incident. An environment
    # variable is scoped to the shell that set it, dies with it, and shows up
    # in `env` where a person can see it.
    ambient = os.environ.get("OBP_BODY")

    # Inherited from 003, where defaulting to the broker was the point. Here
    # --fake and --fake-id are sources of bodies too, so only fall back to the
    # broker when the user named no source at all.
    if not args.mqtt and not args.port and not args.fake and not args.fake_id:
        args.mqtt = True

    reg, conn = attach(args)
    if ambient:
        reg.select(ambient)
    try:
        if not reg.bodies:
            print("no bodies present", file=sys.stderr)
            return 2

        if args.cmd == "bodies":
            for info in reg.bodies:
                verbs = len([t for t in info.tools if not t.user_only])
                # Ask the transport where it is, rather than guessing from
                # whether the broker happens to know the id -- with fakes,
                # USB and MQTT in one list, guessing labelled every
                # subprocess "usb".
                via = reg.transport_of(info.id)
                print(f"{info.id:<20} {info.name:<30} {verbs} verbs  via {via:<6} "
                      f"caps: {', '.join(info.caps) or '-'}")
            return 0

        if args.cmd == "events":
            reg.poll_events(0.3)
            evs, cursor = reg.events.since(0)
            for e in evs:
                print(e.describe())
            if not evs:
                print("nothing reported", file=sys.stderr)
            return 0

        if args.cmd == "watch":
            # A person watching a body, which is the quickest way to know the
            # return path works: press the button, see a line.
            print(f"watching {len(reg.bodies)} bodies for {args.seconds:g}s — "
                  f"press the button", file=sys.stderr)
            reg.events.on_event = lambda e: print(e.describe(), flush=True)
            end = time.monotonic() + args.seconds
            while time.monotonic() < end:
                reg.poll_events(0.2)
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

        body_id, note = reg.resolve(args.verb, args.body)
        if body_id is None:
            print(note, file=sys.stderr)
            return 2
        if note:
            # The implicit path narrates itself; a body named explicitly does
            # not need a running commentary.
            print(f"({note})", file=sys.stderr)
        result = reg.call(mcp_tool_name(body_id, args.verb),
                          dict(parse_kv(a) for a in args.args), autonomous=False)
        print(render_result(result))
        # Anything the body said while doing it. A fake body lives and dies
        # with this process, so a separate `events` run would find an empty
        # log and report nothing -- true, and misleading. A real board
        # outlives the CLI, which is what `watch` is for.
        reg.poll_events(0.2)
        for e in reg.events.since(0)[0]:
            print(f"  event: {e.describe()}", file=sys.stderr)
        return 1 if result.get("isError") else 0
    finally:
        reg.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
