"""Audit a local Zigbee mesh without starting a second coordinator or stack.

Keep ZHA or Zigbee2MQTT as the radio/backend. Custom manufacturer support
belongs in device-specific ZHA quirks or zigbee-herdsman converters.
"""
from __future__ import annotations
import re
from .core import utc_time

EUI = re.compile(r"^(?:0x)?[0-9a-fA-F]{16}$")
BACKENDS = {"zha", "zigbee2mqtt"}

def zigbee_mesh_audit(mesh, *, now, max_age_seconds=86400):
    if not isinstance(mesh, dict) or mesh.get("backend") not in BACKENDS:
        raise ValueError("Specify zha or zigbee2mqtt")
    if mesh.get("uses_vendor_cloud") is True:
        raise ValueError("Cloud Zigbee hub does not meet strict local-first policy")
    if mesh.get("coordinator_count") != 1:
        raise ValueError("Exactly one coordinator per Zigbee PAN is required")
    devices = mesh.get("devices")
    if not isinstance(devices, list) or len(devices) > 1000:
        raise ValueError("devices must be a list of at most 1000 nodes")
    seen = set()
    findings = []
    routers = 0
    battery = 0
    for item in devices:
        if not isinstance(item, dict):
            raise ValueError("Invalid Zigbee node")
        ieee = item.get("ieee")
        if not isinstance(ieee, str) or not EUI.fullmatch(ieee):
            raise ValueError("Invalid Zigbee IEEE identifier")
        canonical = ieee.lower().removeprefix("0x")
        if canonical in seen:
            raise ValueError("Duplicate IEEE address in Zigbee inventory")
        seen.add(canonical)
        typ = item.get("type")
        if typ not in ("router", "end_device"):
            raise ValueError("Node must be router or end_device")
        if typ == "router": routers += 1
        else: battery += 1
        lqi = item.get("lqi")
        if lqi is not None:
            if type(lqi) is not int or not 0 <= lqi <= 255:
                raise ValueError("LQI is an integer from 0 to 255")
            if lqi < 45:
                findings.append({
                    "ieee": canonical, "code": "low_lqi",
                    "note": "Low reported link quality; assess placement and interference."
                })
        last_seen = item.get("last_seen")
        if last_seen is not None:
            age = (utc_time(now) - utc_time(last_seen)).total_seconds()
            if age > max_age_seconds:
                findings.append({
                    "ieee": canonical, "code": "stale_zigbee_node",
                    "seconds_since_seen": round(age, 0)
                })
    if len(devices) >= 10 and routers == 0:
        findings.append({
            "code": "no_routers",
            "note": "Many end devices without any reported powered Zigbee routers."
        })
    return {
        "backend": mesh["backend"],
        "coordinator_count": 1,
        "nodes": len(devices), "routers": routers, "end_devices": battery,
        "findings": findings,
        "strategy": "Reuse native coordinator and add quirks/external converters only when necessary.",
        "clone_protocol_stack": False,
        "commands_issued": 0,
    }
