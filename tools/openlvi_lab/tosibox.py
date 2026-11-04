"""Tosibox/Tosi Gateway read-only diagnostic snapshot and connection plan.

These helpers never initiate a Tosibox VPN, Modbus socket, cloud request,
gateway write, or LAN scan. OpenLVI's existing Modbus driver performs
authorized FC03 reads locally; this module interprets a captured
register snapshot using documented 40001-relative offsets.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from .core import utc_time

REGISTER_MAP = {
    14: ("cellular_rsrp_raw", "raw", (5, 5, 0)),
    15: ("cellular_rssi_raw", "raw", (5, 5, 0)),
    16: ("internet_interface", "enum", (5, 5, 0)),
    17: ("tosi_cloud_connected", "bool", (5, 5, 0)),
    18: ("vpn_tunnel_count", "count", (5, 5, 0)),
    19: ("internet_access_enabled", "bool", (5, 5, 0)),
    20: ("vpn_access_enabled", "bool", (5, 5, 0)),
    21: ("firmware_major", "version", (5, 6, 0)),
    22: ("firmware_minor", "version", (5, 6, 0)),
    23: ("firmware_patch", "version", (5, 6, 0)),
}
INTERFACES = {
    0: "not_connected",
    1: "wan",
    2: "internal_cellular",
    3: "external_cellular",
    4: "lan",
    5: "wlan_client",
    10: "unknown_interface",
}
SUPPORTED_MODELS = {
    "TOSIBOX Lock 150", "TOSIBOX Lock 210", "TOSIBOX Lock 250",
    "TOSIBOX Lock 500", "TOSIBOX 175", "TOSIBOX 350",
    "TOSIBOX 375", "TOSIBOX 610", "TOSIBOX 650",
    "TOSIBOX 670", "TOSIBOX 675", "TOSIBOX 695",
}

def firmware_version(value):
    """Compare gateway firmware numerically, including 26.6.0 releases."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}", value):
        raise ValueError("Tosibox firmware must be major.minor.patch")
    return tuple(int(x) for x in value.split("."))

def interpret_gateway_registers(
    registers, *, gateway_model, firmware, observed_at, now=None,
    max_age_seconds=60, target_reachable=None,
):
    """Interpret a provided authorized FC03 holding register snapshot.

    'registers' keys are MANUFACTURER OFFSETS relative to holding 40001,
    not Modbus 3xxxx/4xxxx absolute addresses. The on-wire PDU offset
    equals the manufacturer offset. OpenLVI generic one-based address
    equals offset + 1.

    No source credentials or device IP addresses are accepted or emitted.
    Never report tunnel count alone as proof of PLC reachability.
    """
    version = firmware_version(firmware)
    if version < (5, 5, 0):
        raise ValueError("Documented Tosibox Modbus requires firmware >= 5.5.0")
    if gateway_model not in SUPPORTED_MODELS:
        raise ValueError("Gateway model must be explicitly supported")
    if not isinstance(registers, dict) or len(registers) > 64:
        raise ValueError("Expected a bounded offset:value register snapshot")
    if target_reachable is not None and type(target_reachable) is not bool:
        raise ValueError("Target reachability must be an observed boolean")
    if type(max_age_seconds) not in (int, float) or not 10 <= max_age_seconds <= 3600:
        raise ValueError("Invalid data freshness interval")
    seen_at = utc_time(observed_at)
    reference = utc_time(now) if now is not None else datetime.now(timezone.utc)
    age = (reference - seen_at).total_seconds()
    quality = "clock_skew" if age < -120 else (
        "stale" if age > max_age_seconds else "fresh")
    clean = {}
    for key, value in registers.items():
        if type(key) is int:
            offset = key
        elif isinstance(key, str) and re.fullmatch(r"\d{1,3}", key):
            offset = int(key)
        else:
            raise ValueError("Register offsets must be small integers")
        if offset not in REGISTER_MAP:
            # Ignore other registers completely, including ICCID and SMS.
            continue
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError("16-bit holding registers must contain integers")
        if offset in clean:
            raise ValueError("Duplicate raw offset")
        clean[offset] = value

    fields = {}
    for offset, (name, kind, introduced) in REGISTER_MAP.items():
        if version < introduced:
            continue
        value = clean.get(offset)
        item = {
            "manufacturer_offset": offset,
            "openlvi_address": offset + 1,
            "quality": "missing" if value is None else quality,
        }
        if value == 0xffff:
            item["quality"] = "unavailable"
        elif value is not None:
            if kind == "bool":
                if value not in (0, 1):
                    item["quality"] = "invalid_value"
                else:
                    item["value"] = bool(value)
            elif kind == "enum":
                if value not in INTERFACES:
                    item["quality"] = "unknown_code"
                    item["raw_value"] = value
                else:
                    item["value"] = INTERFACES[value]
            elif kind == "count":
                item["value"] = value
            elif kind == "raw":
                # Vendor declares unsigned 16 bit "in dBm"; encoding for
                # negative levels must be confirmed on actual gateway.
                item["raw_value"] = value
                item["unit_verified"] = False
            elif kind == "version":
                item["value"] = value
        fields[name] = item

    findings = []
    def current(name):
        item = fields.get(name, {})
        return item.get("value") if item.get("quality") == "fresh" else None

    if current("internet_interface") == "not_connected":
        findings.append({
            "code": "gateway_no_wan",
            "severity": "warning",
            "detail": "Gateway reports no active Internet interface.",
        })
    if current("vpn_access_enabled") is False:
        findings.append({
            "code": "vpn_administration_disabled",
            "severity": "warning",
            "detail": "VPN access flag is off; diagnose locally without attempting Modbus writes.",
        })
    if current("tosi_cloud_connected") is False:
        findings.append({
            "code": "vendor_coordination_unavailable",
            "severity": "info",
            "detail": "Tosi cloud status is down; local HVAC communications may still work.",
        })
    if target_reachable is False:
        findings.append({
            "code": "ot_target_unreachable",
            "severity": "warning",
            "detail": "An external authorized reachability check failed; tunnel count cannot prove plant connectivity.",
        })

    return {
        "manufacturer": "Tosibox",
        "gateway_model": gateway_model,
        "expected_firmware": firmware,
        "protocol": "Modbus TCP FC03 read-only, port 502 on approved LAN",
        "snapshot_quality": quality,
        "age_seconds": round(age, 1),
        "fields": fields,
        "network_findings": findings,
        "vpn_tunnel_count_not_a_reachability_test": True,
        "target_reachable_from_separate_authorized_test": target_reachable,
        "sensitive_identity_registers_ignored": True,
        "modbus_writes_enabled": False,
        "tosi_vpn_connections_established": 0,
        "commands_issued": 0,
    }

def design_connection(*, deployment, gateway_mode, monitoring_location):
    """Advise a deployment mode without VPN provisioning or credentials."""
    if deployment not in ("single_site", "few_sites", "multi_site"):
        raise ValueError("Unknown deployment size")
    if gateway_mode not in ("lock", "client"):
        raise ValueError("Expected Tosibox Lock or Client mode")
    if monitoring_location not in ("on_site", "central"):
        raise ValueError("Monitoring location must be on_site or central")
    return {
        "deployment": deployment,
        "gateway_mode": gateway_mode,
        "monitoring_location": monitoring_location,
        "preferred": ("local_edge_plus_authorized_vpn" if deployment != "multi_site"
                      else "local_edge_plus_licensed_tosi_hub"),
        "plan": [
            "Connect OpenLVI to site automation devices over the authorized local LAN.",
            "Poll Tosibox's own Modbus TCP FC03 status separately on TCP/502.",
            "Enable Tosibox Modbus server only from a restricted trusted management LAN.",
            "Keep Internet/VPN enable and SMS Modbus registers permanently read-only.",
            "Provision authenticated Tosi Key/Client or Tosi Hub outside Home Assistant.",
            "Permit only required destination subnets and TCP/UDP services via the VPN.",
            "For central polling, verify Layer-3 routing, overlapping LAN CIDRs and firewall permissions.",
            "Keep site collector and original HVAC safety controls functional when WAN/VPN is down.",
        ],
        "important": (
            "Client mode does not isolate the connected LAN from the wider network. "
            "Use Lock mode and segmentation when a protected OT subnet is required."
        ),
        "pure_vendor_cloud_independence_unverified": True,
        "unverified_remote_cloudless_claim": (
            "A locally hosted Tosi Hub does not by itself establish that "
            "Tosi matching, licenses or management operate without vendor infrastructure."
        ),
        "commands_issued": 0,
    }
