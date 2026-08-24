"""Finding serial bodies, and surviving them moving.

A numbered device node is not an identity. Unplug a Pico and plug it back in
and `/dev/ttyACM0` becomes `/dev/ttyACM1`, while a host still holding the old
descriptor writes into a node that no longer exists — which is exactly how
experiment 002 lost a session.

Linux publishes stable symlinks under /dev/serial/by-id/ keyed on the USB
serial number. For a Raspberry Pi Pico that serial contains the same board id
the firmware derives its OBP `id` from, so `pico-3f5022` and
`usb-Raspberry_Pi_Pico_E6611C08CB3F5022-if00` identify the same object from
two directions.
"""

from __future__ import annotations

from pathlib import Path

BY_ID = Path("/dev/serial/by-id")


def stable_ports() -> list[str]:
    """Every USB serial device, by a path that survives re-enumeration."""
    if not BY_ID.is_dir():
        return []
    return sorted(str(p) for p in BY_ID.iterdir() if p.is_symlink())


AUTO = "auto"


def expand(specs: list[str]) -> list[str]:
    """Turn a list of port specs into concrete paths.

    `auto` expands to every USB serial device currently attached, which is
    what a host should default to: naming a device node in a config file is
    how experiment 002 ended up pinned to a port the board had left.
    """
    out: list[str] = []
    for spec in specs:
        if spec == AUTO:
            out.extend(stable_ports())
        else:
            out.append(spec)
    return out


def resolve(spec: str) -> str | None:
    """Turn a port spec into a usable path, or None if it is not present.

    Accepts a literal path, a by-id path, or a fragment to match against the
    by-id names — so `--port 3f5022` finds the board whose serial ends that
    way, whichever node it landed on this time.
    """
    p = Path(spec)
    if p.exists():
        return str(p)

    needle = spec.rsplit("/", 1)[-1].lower()
    for candidate in stable_ports():
        if needle in candidate.lower():
            return candidate
    return None


def describe_spec(spec: str) -> str:
    """Human-readable note about what a spec did or did not resolve to."""
    resolved = resolve(spec)
    if resolved is None:
        seen = stable_ports()
        if not seen:
            return f"{spec}: not present, and no USB serial devices are attached"
        listing = "\n".join(f"    {s}" for s in seen)
        return f"{spec}: not present. Attached USB serial devices:\n{listing}"
    if resolved != spec:
        return f"{spec}: resolved to {resolved}"
    return f"{spec}: present"
