"""Advisory site safety monitor; never clears native HVAC safety alarms."""
from __future__ import annotations
from .core import finding, optional_number, utc_time, InvalidMeasurement
from datetime import datetime, timezone


def inspect_safety(site, *, now=None):
    if not isinstance(site, dict):
        raise ValueError("site must be a dictionary")
    observed = utc_time(now) if now is not None else datetime.now(timezone.utc)
    issues = []
    if site.get("water_leak") is True:
        issues.append(finding(
            "water_leak", "critical", "Water leak sensor reports active leakage.",
            {"leak_active": True},
            recommendation="Investigate and follow the approved site emergency procedure. No valve command sent."))
    temp = optional_number(site, "water_supply_c", minimum=-50, maximum=200)
    if temp is not None and temp < 4:
        issues.append(finding(
            "water_freeze_risk", "warning",
            "A monitored water line is near freezing temperature.",
            {"water_supply_c": temp},
            recommendation="Check site frost protection and sensor placement; keep independent safety active."))
    co2 = optional_number(site, "co2_ppm", minimum=250, maximum=20000)
    if co2 is not None and co2 > 1500:
        issues.append(finding(
            "elevated_co2", "warning",
            "Elevated indoor CO2 requires ventilation investigation.",
            {"co2_ppm": co2},
            recommendation="Inspect fresh air supply, occupancy and sensor calibration."))
    last_seen = site.get("last_seen")
    if last_seen is not None:
        recorded = utc_time(last_seen)
        seconds = (observed - recorded).total_seconds()
        if seconds > 900:
            issues.append(finding(
                "stale_telemetry", "warning", "Device readings are stale.",
                {"seconds_since_seen": round(seconds)},
                recommendation="Check network, power supply and source timestamp. Do not infer sensor safety state."))
        if seconds < -120:
            issues.append(finding(
                "clock_skew", "warning", "Source timestamp appears to be in the future.",
                {"seconds_ahead": round(-seconds)},
                recommendation="Check gateway NTP and timestamp handling."))
    return {
        "alerts": issues,
        "observed_at": observed.isoformat(),
        "native_safety_bypass": False,
        "alarm_acknowledgments_sent": 0,
        "commands_issued": 0,
    }
