"""Transports for the body contract.

The whole point of experiment 001 is that the contract does not know which of
these it is speaking over. Both are newline-delimited JSON in both directions;
one happens to be a USB cable and the other a pipe to a subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Any, Protocol


class Transport(Protocol):
    """Newline-delimited JSON, bidirectional."""

    def open(self) -> None: ...
    def close(self) -> None: ...
    def send(self, obj: dict[str, Any]) -> None: ...
    def recv(self, timeout: float) -> dict[str, Any] | None: ...


class SubprocessTransport:
    """Talk to a body implemented as a local process over its stdin/stdout.

    This is the binding a USB-attached body driver would really use on a
    single-box deployment (Jetson, Pi, mini PC): the daemon spawns the driver
    and speaks the same JSON it would have published to a broker.
    """

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.proc: subprocess.Popen[str] | None = None

    def open(self) -> None:
        self.proc = subprocess.Popen(
            self.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )

    def close(self) -> None:
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None

    def send(self, obj: dict[str, Any]) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout: float) -> dict[str, Any] | None:
        assert self.proc is not None and self.proc.stdout is not None
        # Pipes give us no per-read timeout without threads; the body is
        # expected to answer promptly, and a dead body shows up as EOF.
        line = self.proc.stdout.readline()
        if not line:
            return None
        return json.loads(line)

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None


class SerialTransport:
    """Talk to a body over USB CDC serial (the Raspberry Pi Pico case)."""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self.ser: Any = None

    def open(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - dependency hint
            raise SystemExit(
                "pyserial is required for --port. Try:\n"
                "  uv run --with pyserial python host/cli.py ..."
            ) from exc
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        # A Pico that was already running has buffered output; drop it so the
        # first response we parse is genuinely ours.
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def send(self, obj: dict[str, Any]) -> None:
        assert self.ser is not None
        self.ser.write((json.dumps(obj) + "\n").encode())
        self.ser.flush()

    def recv(self, timeout: float) -> dict[str, Any] | None:
        assert self.ser is not None
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            buf += self.ser.readline()
            if buf.endswith(b"\n"):
                text = buf.decode(errors="replace").strip()
                buf = b""
                if not text:
                    continue
                if not text.startswith("{"):
                    # MicroPython tracebacks and REPL noise land here.
                    print(f"[body stderr] {text}", file=sys.stderr)
                    continue
                return json.loads(text)
        return None

    @property
    def alive(self) -> bool:
        return self.ser is not None and self.ser.is_open
