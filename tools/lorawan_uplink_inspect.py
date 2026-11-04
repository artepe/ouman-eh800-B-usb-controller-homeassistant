#!/usr/bin/env python3
"""Inspect already-decrypted LoRaWAN MQTT uplink JSON offline.

Supported envelopes: Milesight UG65 embedded NS, ChirpStack v4 and TTS v3.
No broker, HTTP, network, radio, downlink or controller write functionality.
Raw LoRaWAN bytes are NOT interpreted as sensor values.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
from pathlib import Path
import re
import sys

_MAX_JSON_BYTES = 65536
_MAX_PAYLOAD_BYTES = 255
_EUI = re.compile(r"^[0-9a-fA-F]{16}$")


def _object(value):
    return value if isinstance(value, dict) else {}


def _numeric(value):
    if type(value) in (int, float):
        return value
    return None


def _decoded(value):
    """Pass through a bounded set of vendor-decoded fields, without guessing."""
    if not isinstance(value, dict) or len(value) > 64:
        return {}
    result = {}
    for key, data in value.items():
        if (isinstance(key, str) and 1 <= len(key) <= 64
                and type(data) in (str, int, float, bool)
                and (not isinstance(data, str) or len(data) <= 200)):
            result[key] = data
    return result


def _payload(encoded):
    if not isinstance(encoded, str):
        raise ValueError("Uplink has no base64 payload string")
    if len(encoded) > 400:
        raise ValueError("Base64 payload is too long")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid uplink base64 data") from exc
    if not data:
        raise ValueError("Empty LoRaWAN application payload")
    if len(data) > _MAX_PAYLOAD_BYTES:
        raise ValueError("Payload exceeds LoRaWAN 255-byte limit")
    return data.hex()


def inspect_uplink(message: dict) -> dict:
    """Normalize one application-server uplink. Reject ambiguous envelopes."""
    if not isinstance(message, dict):
        raise ValueError("Expected a JSON object")
    if isinstance(message.get("end_device_ids"), dict):
        flavor = "the_things_stack_v3"
        ids = message["end_device_ids"]
        eui = ids.get("dev_eui")
        frame = _object(message.get("uplink_message"))
        encoded = frame.get("frm_payload")
        port = frame.get("f_port")
        count = frame.get("f_cnt")
        info = frame.get("rx_metadata")
        info = info[0] if isinstance(info, list) and info else {}
        info = _object(info)
        decoded = frame.get("decoded_payload")
        device_name = ids.get("device_id")
    elif isinstance(message.get("deviceInfo"), dict):
        flavor = "chirpstack_v4"
        ids = message["deviceInfo"]
        eui = ids.get("devEui")
        encoded = message.get("data")
        port = message.get("fPort")
        count = message.get("fCnt")
        info = message.get("rxInfo")
        info = info[0] if isinstance(info, list) and info else {}
        info = _object(info)
        decoded = message.get("object")
        device_name = ids.get("deviceName")
    elif "devEUI" in message:
        flavor = "milesight_embedded_ns"
        eui = message.get("devEUI")
        encoded = message.get("data")
        port = message.get("fPort")
        count = message.get("fCnt")
        info = message.get("rxInfo")
        info = info[0] if isinstance(info, list) and info else {}
        info = _object(info)
        decoded = message.get("object")
        device_name = message.get("deviceName")
    else:
        raise ValueError("Unknown LoRaWAN application-server envelope")

    if not isinstance(eui, str) or not _EUI.fullmatch(eui):
        raise ValueError("Missing or invalid 16-hex-digit DevEUI")
    if type(port) is not int or not 1 <= port <= 223:
        raise ValueError("Uplink FPort must be an integer between 1 and 223")
    if count is not None and (type(count) is not int or count < 0):
        raise ValueError("Invalid frame counter")

    return {
        "format": flavor,
        "dev_eui": eui.lower(),
        "device_name": device_name if isinstance(device_name, str) else None,
        "f_port": port,
        "frame_counter": count,
        "rssi_dbm": _numeric(info.get("rssi")),
        "snr_db": _numeric(info.get("loRaSNR", info.get("snr"))),
        "payload_hex": _payload(encoded),
        "decoded_fields": _decoded(decoded),
        "note": (
            "Raw payload is shown as hex only; sensor fields require "
            "a device-and-firmware-specific verified payload codec. "
            "No downlink or controller command was issued."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, nargs="?",
                        help="JSON message from a local MQTT subscription; stdin if omitted")
    args = parser.parse_args(argv)
    try:
        if args.file:
            if args.file.stat().st_size > _MAX_JSON_BYTES:
                raise ValueError("JSON file too large")
            content = args.file.read_text(encoding="utf-8")
        else:
            content = sys.stdin.read(_MAX_JSON_BYTES + 1)
            if len(content.encode("utf-8")) > _MAX_JSON_BYTES:
                raise ValueError("JSON input too large")
        normalized = inspect_uplink(json.loads(content))
        print(json.dumps(normalized, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"OpenLVI: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
