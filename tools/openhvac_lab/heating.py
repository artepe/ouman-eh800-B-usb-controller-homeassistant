"""Cost-aware heat storage scheduling simulator; never controls a heat pump.

This simplified storage model ignores direct heat supply, thermal inertia,
defrost, stratification, hydraulic limits and compressor minimum on/off time.
Its output is a decision-support forecast, NOT a valid plant control schedule.
"""
from __future__ import annotations
from math import floor
from .core import number


def plan_buffer_heating(config, forecast):
    """Discretized cost-minimizing dispatch with hard model energy bounds."""
    if not isinstance(config, dict) or not isinstance(forecast, list):
        raise ValueError("Expected configuration object and forecast list")
    if not 1 <= len(forecast) <= 96:
        raise ValueError("Forecast must have 1-96 chronological slots")
    volume = number(config.get("tank_volume_l"), "tank_volume_l", minimum=10, maximum=100000)
    minimum = number(config.get("tank_min_c"), "tank_min_c", minimum=0, maximum=95)
    maximum = number(config.get("tank_max_c"), "tank_max_c", minimum=0, maximum=95)
    current = number(config.get("tank_current_c"), "tank_current_c", minimum=0, maximum=95)
    if not minimum < maximum or not minimum <= current <= maximum:
        raise ValueError("Require tank_min_c <= tank_current_c <= tank_max_c")
    heat_kw_max = number(config.get("heatpump_max_thermal_kw"), "heatpump_max_thermal_kw",
                         minimum=.01, maximum=250)
    loss = number(config.get("building_loss_kw_per_k"), "building_loss_kw_per_k",
                  minimum=0, maximum=100)
    indoor = number(config.get("indoor_target_c"), "indoor_target_c",
                    minimum=5, maximum=35)
    reserve = number(config.get("final_reserve_kwh", 0), "final_reserve_kwh",
                     minimum=0, maximum=10000)
    capacity = volume * 0.001163 * (maximum - minimum)
    if reserve > capacity:
        raise ValueError("Final reserve exceeds buffer energy capacity")
    stored = volume * 0.001163 * (current - minimum)
    step = max(.05, capacity / 240)
    initial_bin = min(int(stored / step), int(capacity / step))
    max_bin = int(capacity / step)
    options = (0, .25, .5, .75, 1.0)

    # Keep one least-cost path per discrete storage bin.
    paths = {initial_bin: (0.0, [])}
    for index, slot in enumerate(forecast):
        if not isinstance(slot, dict):
            raise ValueError("Each slot must be an object")
        hours = number(slot.get("hours", 1), "slot.hours", minimum=.05, maximum=4)
        outdoor = number(slot.get("outdoor_c"), "slot.outdoor_c", minimum=-60, maximum=50)
        price = number(slot.get("electricity_eur_per_kwh"), "electricity_eur_per_kwh",
                       minimum=-2, maximum=10)
        cop = number(slot.get("expected_cop"), "expected_cop", minimum=1, maximum=9)
        demand_kwh = max(0.0, indoor - outdoor) * loss * hours
        nxt = {}
        for stored_bin, (cost, plan) in paths.items():
            remaining = stored_bin * step
            for fraction in options:
                produced = heat_kw_max * fraction * hours
                end = remaining + produced - demand_kwh
                # Respect physical energy bounds *before* discretization.
                if end < -1e-8 or end > capacity + 1e-8:
                    continue
                next_bin = min(max_bin, floor((end + 1e-9) / step))
                elec = produced / cop
                total = cost + elec * price
                old = nxt.get(next_bin)
                if old is None or total < old[0]:
                    nxt[next_bin] = (total, plan + [{
                        "index": index,
                        "hours": hours,
                        "outdoor_c": outdoor,
                        "demand_kwh_estimate": round(demand_kwh, 3),
                        "heatpump_thermal_kw_suggested": round(heat_kw_max * fraction, 3),
                        "electricity_price_eur_kwh": price,
                        "expected_cop": cop,
                        "buffer_kwh_after_estimate": round(next_bin * step, 3),
                        "buffer_c_after_estimate": round(
                            minimum + next_bin * step / (volume * .001163), 2),
                    }])
        paths = nxt
        if not paths:
            return {
                "feasible": False,
                "failed_at_slot": index,
                "reason": "No schedule satisfies the simplified buffer balance and capacity constraints.",
                "commands_issued": 0,
            }
    finals = [(cost, plan, stored_bin * step)
              for stored_bin, (cost, plan) in paths.items()
              if stored_bin * step + step >= reserve]
    if not finals:
        return {
            "feasible": False,
            "reason": "No simulated schedule meets the configured final energy reserve.",
            "commands_issued": 0,
        }
    cost, schedule, final = min(finals, key=lambda item: item[0])
    return {
        "feasible": True,
        "method": "discrete_store_and_forward_dynamic_programming",
        "buffer_capacity_kwh": round(capacity, 3),
        "initial_buffer_kwh": round(stored, 3),
        "final_buffer_kwh_estimate": round(final, 3),
        "estimated_electricity_cost_eur": round(cost, 3),
        "slots": schedule,
        "limitations": [
            "Simplified single-buffer model: ignores direct heat flow, frost/defrost and building thermal mass.",
            "Does not enforce heat pump start/stop, minimum compressor frequency or auxiliary heat.",
            "Electrical cost and COP are forecasts. A qualified controller must retain all native protections.",
        ],
        "commands_issued": 0,
    }
