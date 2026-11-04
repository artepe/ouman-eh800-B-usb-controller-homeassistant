"""Ouman EH-800B USB service-shell client used by OpenHVAC Bridge.

Same serial framing as the physically tested legacy driver
(custom_components/ouman_eh800/ouman.py, v0.1.2): newline-terminated ASCII
commands, a short quiet period as the reply delimiter and an exclusive
port open per command. Copied here so OpenHVAC Bridge no longer imports
another integration's private code and can be installed on its own (HACS).

Only MEASUREMENTS and caller-validated SET PROPERTY commands are sent.
pyserial is imported lazily so the module loads without it in unit tests.
"""
from __future__ import annotations

import logging
import re
import threading
import time

_LOGGER = logging.getLogger(__name__)

_PORT_LOCKS: dict[str, threading.RLock] = {}
_PORT_LOCKS_GUARD = threading.Lock()

_MEASUREMENT_LINE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(C|%|dig)\s*$", re.I)


def _port_lock(port: str) -> threading.RLock:
    with _PORT_LOCKS_GUARD:
        return _PORT_LOCKS.setdefault(port, threading.RLock())


class OumanUSB:
    """Blocking client; call from an executor thread."""

    def __init__(self, port: str):
        self.port = port
        self.lock = _port_lock(port)

    def command(self, command: str, wait: float = 0.18, retries: int = 3) -> str:
        """Send one shell command and return the raw reply text.

        `retries` re-sends only when the reply is completely empty. Callers
        that write settings pass retries=1 so an ambiguous write is never
        repeated.
        """
        import serial

        last = ""
        with self.lock:
            for attempt in range(1, retries + 1):
                with serial.Serial(
                    self.port,
                    timeout=0.22,
                    write_timeout=1.0,
                    exclusive=True,
                ) as port:
                    time.sleep(0.06)
                    port.reset_input_buffer()
                    port.write((command + "\n").encode("ascii"))
                    port.flush()
                    time.sleep(wait)

                    out = bytearray()
                    quiet_reads = 0
                    deadline = time.monotonic() + 1.8
                    while time.monotonic() < deadline:
                        chunk = port.read(4096)
                        if chunk:
                            out.extend(chunk)
                            quiet_reads = 0
                        else:
                            quiet_reads += 1
                            if out and quiet_reads >= 2:
                                break

                    last = bytes(out).decode("latin1", errors="replace")
                    if last.strip():
                        return last

                _LOGGER.warning(
                    "Empty EH-800 response for %r (attempt %s/%s)",
                    command, attempt, retries,
                )
                time.sleep(0.12)
        return last

    def measurements(self) -> list[tuple[float, str]]:
        """Parse MEASUREMENTS into (value, unit) rows in controller order."""
        text = self.command("MEASUREMENTS", 0.22)
        result = []
        for line in text.replace("\r", "").split("\n"):
            match = _MEASUREMENT_LINE.search(line.strip())
            if match:
                result.append((float(match.group(1)), match.group(2)))
        if not result:
            raise RuntimeError(f"Unexpected EH-800 MEASUREMENTS response: {text!r}")
        return result
