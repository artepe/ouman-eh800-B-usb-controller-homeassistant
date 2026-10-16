from __future__ import annotations
import logging
import re
import threading
import time
import serial

_LOGGER = logging.getLogger(__name__)

_PORT_LOCKS: dict[str, threading.RLock] = {}
_PORT_LOCKS_GUARD = threading.Lock()

PROP_RE = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'([^']+)'\(([^)]*)\)\s*=\s*(-?\d+)",
    re.I,
)

def _port_lock(port: str) -> threading.RLock:
    with _PORT_LOCKS_GUARD:
        return _PORT_LOCKS.setdefault(port, threading.RLock())

class OumanUSB:
    def __init__(self, port: str):
        self.port = port
        self.lock = _port_lock(port)

    def _open_port(self):
        """Open either the tested local USB port or an opt-in raw TCP bridge.

        The ESP32-S3 serves one USB CDC-ACM device over an IP-restricted
        socket:// endpoint. Do not use RFC2217 URLs: the bridge is raw TCP.
        """
        if self.port.startswith("socket://"):
            return serial.serial_for_url(
                self.port,
                timeout=0.22,
                write_timeout=1.0,
            )
        return serial.Serial(
            self.port,
            timeout=0.22,
            write_timeout=1.0,
            exclusive=True,
        )

    def _command(self, command: str, wait: float = 0.18, retries: int = 3) -> str:
        last = ""
        with self.lock:
            for attempt in range(1, retries + 1):
                with self._open_port() as s:
                    time.sleep(0.06)
                    s.reset_input_buffer()
                    s.write((command + "\n").encode("ascii"))
                    s.flush()
                    time.sleep(wait)

                    out = bytearray()
                    quiet_reads = 0
                    deadline = time.monotonic() + 1.8
                    while time.monotonic() < deadline:
                        chunk = s.read(4096)
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
                    command,
                    attempt,
                    retries,
                )
                time.sleep(0.12)

        return last

    def measurements(self) -> list[tuple[float, str]]:
        text = self._command("MEASUREMENTS", 0.22)
        result = []
        for line in text.replace("\r", "").split("\n"):
            m = re.search(r"(-?\d+(?:\.\d+)?)\s*(C|%|dig)\s*$", line.strip(), re.I)
            if m:
                result.append((float(m.group(1)), m.group(2)))
        if not result:
            raise RuntimeError(f"Unexpected EH-800 MEASUREMENTS response: {text!r}")
        return result

    def property(self, prop_id: int, value: int) -> tuple[int, str, int, int, int]:
        command = f"SET PROPERTY {prop_id} {value}"
        last = ""

        for attempt in range(1, 4):
            text = self._command(command, 0.18, retries=1)
            last = text
            m = PROP_RE.search(text)
            if m:
                returned_id = int(m.group(1))
                name = m.group(2)
                range_text = m.group(3).strip()
                returned_value = int(m.group(4))
                rmin = rmax = 0
                rm = re.match(r"\s*(\d+)\s*-\s*(\d+)\s*$", range_text)
                if rm:
                    rmin, rmax = int(rm.group(1)), int(rm.group(2))

                if returned_id != prop_id:
                    _LOGGER.warning(
                        "EH-800 replied for property %s while writing %s: %r",
                        returned_id,
                        prop_id,
                        text,
                    )
                    time.sleep(0.12)
                    continue

                return returned_id, name, rmin, rmax, returned_value

            _LOGGER.warning(
                "Unexpected EH-800 property response (attempt %s/3): %r",
                attempt,
                text,
            )
            time.sleep(0.15)

        raise RuntimeError(f"Unexpected EH-800 response to {command!r}: {last!r}")
