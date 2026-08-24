"""Transports for the body contract.

The whole point of experiment 001 is that the contract does not know which of
these it is speaking over. Both are newline-delimited JSON in both directions;
one happens to be a USB cable and the other a pipe to a subprocess.
"""

from __future__ import annotations

import json
import queue
import threading
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

    def __init__(self, argv: list[str], env: dict[str, str] | None = None) -> None:
        self.argv = argv
        self.env = env
        self.proc: subprocess.Popen[str] | None = None
        self._inbox: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._reader: threading.Thread | None = None

    kind = "local"

    def describe(self) -> str:
        import os.path
        return f"a subprocess ({os.path.basename(self.argv[-1])})"

    def open(self) -> None:
        self.proc = subprocess.Popen(
            self.argv,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

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
        # A reader thread, which the original comment here predicted would be
        # needed: "pipes give us no per-read timeout without threads".
        #
        # A blocking readline() was fine while every message answered a
        # question -- the body was about to speak, so waiting cost nothing.
        # Polling for events breaks that: "has anything happened?" is asked
        # when the usual answer is no, and a blocking read makes that a hang.
        #
        # select() on the pipe is the obvious fix and is WRONG here, which
        # cost an hour. readline() on a buffered stream can pull several lines
        # into Python's buffer in one syscall, so the kernel pipe reads as
        # empty while a complete message is already in hand -- select says
        # "nothing there", and the reply times out five seconds later. The
        # queue holds decoded messages, so nothing can hide below it.
        try:
            return self._inbox.get(timeout=timeout) if timeout > 0 \
                else self._inbox.get_nowait()
        except queue.Empty:
            return None

    def _read_loop(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._inbox.put(json.loads(line))
            except ValueError:
                continue          # a body that printed debug output, not JSON

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None


class BodyUnavailable(RuntimeError):
    """A body could not be attached. The message is written for a person."""


def _explain_open_failure(port: str, exc: Exception) -> str:
    """Turn an unhelpful OS error into the thing the caller has to do.

    A permission failure on a tty is the first obstacle between a person and
    a working body, and the message the OS gives mentions neither groups nor
    the fix. Both runs of experiment 002 lost time here.
    """
    import errno
    import grp
    import os

    if getattr(exc, "errno", None) != errno.EACCES:
        return f"could not open {port}: {exc}"

    try:
        owner_group = grp.getgrgid(os.stat(port).st_gid).gr_name
    except (OSError, KeyError):
        owner_group = "dialout"

    in_process = owner_group in (grp.getgrgid(g).gr_name for g in os.getgroups())
    lines = [f"Permission denied opening {port}.", ""]

    if in_process:
        lines += [f"This process is in '{owner_group}', so the cause is something else —",
                  "another program may be holding the port (ModemManager is a common one)."]
    else:
        lines += [
            f"{port} is owned by group '{owner_group}' and this process is not in it.",
            "",
            f"  sudo usermod -aG {owner_group} $USER      # once, permanently",
            "",
            "That does NOT affect a shell that is already open: supplementary",
            "groups are fixed at login. Until you log out and back in, use:",
            "",
            f"  sg {owner_group} -c '<command>'           # one command, non-interactive",
            f"  newgrp {owner_group}                      # a new interactive shell",
            "",
            "Scripts and agents want 'sg': 'newgrp' starts an interactive shell",
            "and waits for input, so a non-interactive caller hangs or loses the",
            "command.",
        ]
    return "\n".join(lines)


class SerialTransport:
    """Talk to a body over USB CDC serial (the Raspberry Pi Pico case)."""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self.ser: Any = None

    kind = "usb"

    def describe(self) -> str:
        import os.path
        return f"usb {os.path.basename(self.port)}"

    def open(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - dependency hint
            # NOT SystemExit. This is one binding's optional dependency, and
            # raising SystemExit from inside a transport killed the whole MCP
            # server -- M9 says a host must stay available when a body cannot
            # be reached, because a server that exits is indistinguishable
            # from a broken one. It also printed the hint into the JSON-RPC
            # stream on the way out. Same shape as the eager paho-mqtt import
            # in experiment 004: a binding nobody asked for should not be a
            # reason the host will not start.
            raise BodyUnavailable(
                "pyserial is required to talk to a USB body. Try:\n"
                "  uv run --with pyserial python3 host/obp_mcp.py ..."
            ) from exc
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        except serial.SerialException as exc:
            raise BodyUnavailable(_explain_open_failure(self.port, exc)) from exc
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
