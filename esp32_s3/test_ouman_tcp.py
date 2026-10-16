#!/usr/bin/env python3
"""Read-only smoke test for the Ouman EH-800B ESP32-S3 USB/TCP bridge.

Uses only Python standard library. The only device command is MEASUREMENTS.
"""
from __future__ import annotations

import argparse
import re
import socket
import sys
import time

MEASUREMENT = re.compile(r"(-?\d+(?:\.\d+)?)\s*(C|%|dig)\s*$", re.I)


def parse_measurements(response: bytes) -> list[tuple[float, str]]:
    text = response.decode("latin1", errors="replace")
    found: list[tuple[float, str]] = []
    for line in text.replace("\r", "").split("\n"):
        match = MEASUREMENT.search(line.strip())
        if match:
            found.append((float(match.group(1)), match.group(2)))
    return found


def read_measurements(host: str, port: int, timeout: float = 6.0) -> bytes:
    if not 0 < port < 65536:
        raise ValueError("port must be 1..65535")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    received = bytearray()
    with socket.create_connection((host, port), timeout=min(timeout, 5.0)) as connection:
        connection.settimeout(0.35)
        connection.sendall(b"MEASUREMENTS\n")
        deadline = time.monotonic() + timeout
        last_data = time.monotonic()
        while time.monotonic() < deadline:
            try:
                data = connection.recv(4096)
            except socket.timeout:
                if received and time.monotonic() - last_data > 0.9:
                    break
                continue
            if not data:
                break
            received.extend(data)
            last_data = time.monotonic()
            if len(received) > 65536:
                raise RuntimeError("Unusually large response; stopped at 64 KiB")
    return bytes(received)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Ouman USB/TCP bridge check")
    parser.add_argument("--host", required=True, help="ESP32-S3 IP (or local DNS name)")
    parser.add_argument("--port", type=int, default=8880)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--show-raw", action="store_true", help="Print raw device response (may be sensitive)")
    args = parser.parse_args()
    try:
        payload = read_measurements(args.host, args.port, args.timeout)
    except (OSError, RuntimeError, ValueError) as err:
        print(f"Connection failed: {err}", file=sys.stderr)
        return 1
    values = parse_measurements(payload)
    print(f"Connected. Received {len(payload)} bytes, parsed {len(values)} measurement lines.")
    for i, (value, unit) in enumerate(values[:5], start=1):
        print(f"  Sample {i}: {value:g} {unit}")
    if args.show_raw:
        print("--- Raw reply (local debug only) ---")
        print(payload.decode("latin1", errors="replace"))
    if len(values) < 28:
        print("EXPECTED 28 lines on the tested EH-800B. Bridge/protocol needs diagnostics.", file=sys.stderr)
        return 2
    print("PASS: 28 or more measurement lines received. No settings were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
