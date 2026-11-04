"""Hydronic balance suggestions from measured room temperatures and valves."""
from __future__ import annotations
from .core import optional_number


def balance_rooms(rooms):
    if not isinstance(rooms, list) or not 1 <= len(rooms) <= 128:
        raise ValueError("rooms must contain 1..128 measured room objects")
    recommendations = []
    for i, room in enumerate(rooms):
        if not isinstance(room, dict):
            raise ValueError("Every room must be an object")
        label = room.get("name") if isinstance(room.get("name"), str) else f"Room {i+1}"
        label = label[:80]
        temp = optional_number(room, "temperature_c", minimum=-10, maximum=60)
        target = optional_number(room, "target_c", minimum=5, maximum=40)
        valve = optional_number(room, "valve_pct", minimum=0, maximum=100)
        supply = optional_number(room, "supply_c", minimum=-20, maximum=100)
        ret = optional_number(room, "return_c", minimum=-20, maximum=100)
        if temp is None or target is None:
            recommendations.append({
                "room": label, "status": "unavailable",
                "reason": "A trustworthy temperature and setpoint are required.",
                "auto_change": False,
            })
            continue
        deviation = round(target - temp, 2)
        signal = "near_target"
        reason = "The room is close to its selected target."
        if deviation > 1.5:
            signal = "below_target"
            reason = "Room is colder than its target; inspect heat availability."
            if valve is not None and valve >= 90:
                signal = "possible_flow_limitation"
                reason = "Room below target while valve is almost fully open; check balancing/flow before raising supply temperature."
        elif deviation < -1.5:
            signal = "above_target"
            reason = "Room is above target; review valve closing, solar gains and local control."
        delta_t = round(supply - ret, 2) if supply is not None and ret is not None else None
        recommendations.append({
            "room": label,
            "status": signal,
            "temperature_c": temp,
            "target_c": target,
            "deviation_c": deviation,
            "valve_pct": valve,
            "water_delta_t_k": delta_t,
            "reason": reason,
            "auto_change": False,
        })
    priority = {"possible_flow_limitation": 0, "below_target": 1,
                "above_target": 2, "near_target": 3, "unavailable": 4}
    recommendations.sort(key=lambda row: (priority[row["status"]], row["room"]))
    return {
        "rooms": recommendations,
        "disclaimer": "Diagnostic guidance only; room balance requires design flows, hydraulics and site verification.",
        "commands_issued": 0,
    }
