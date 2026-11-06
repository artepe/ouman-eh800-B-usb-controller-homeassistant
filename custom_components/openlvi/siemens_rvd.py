"""Siemens RVD120/RVD140 read-only P2510 Modbus RTU point lists.

Source: Siemens CE1P2510en, 2018-04-30, pp. 69-86, Modbus V1.0.
Manufacturer table addresses are zero-based wire offsets. The OpenLVI driver
subtracts one from Register.address, therefore the model stores offset + 1.
All points are FC03 holding registers, signed 16-bit and NON-writable.
"""
SOURCE = "https://sid.siemens.com/api/khub/documents/K2sQQXzf6QS87HzaOTu9xQ/content"
MODELS = ("RVD120", "RVD140")
MODEL_CODES = {"RVD120": 140, "RVD140": 142}


def make_profile(Register, model):
    """Return a separate, documented, strictly read-only profile."""
    if model not in MODELS:
        raise ValueError("Unknown Siemens RVD controller")

    def r(key, name, wire_address, unit=None, scale=1.0):
        return Register(
            key=key, name=name, address=wire_address + 1,
            kind="s16", decimals=0, unit=unit, writable=False,
            area="holding", read_scale=scale,
        )

    points = [
        r("unit_address", "Modbus slave address", 1015),
        r("modbus_version", "Modbus object version", 1019, scale=0.1),
        r("software_version", "Software version", 1020, scale=0.1),
        r("controller_model_code", "Controller model code", 1021),
        r("plant_type", "Configured plant type", 1022),
        r("manual_operation", "Manual operation (0=on)", 1030),
        r("fault_code", "Controller fault code", 1031),
        r("active_limit_code", "Active limitation code", 1032),
        r("hardware_write_lock", "Hardware write lock", 1033),
        r("valve_relay_y1", "Valve relay Y1 energised", 1034),
        r("valve_relay_y2", "Valve relay Y2 energised", 1035),
        r("heating_pump_q1", "Heating circuit pump Q1 energised", 1036),
        r("outdoor_temp", "Outside temperature B9", 1044, "°C", 1 / 64),
        r("flow_temp", "Flow temperature B1", 1045, "°C", 1 / 64),
        r("dhw_temp", "DHW / storage temperature B3", 1046, "°C", 1 / 64),
        r("room_temp", "Room temperature A6", 1047, "°C", 1 / 64),
        r("primary_return_temp", "Primary return temperature B7", 1048, "°C", 1 / 64),
        r("attenuated_outdoor_temp", "Attenuated outside temperature", 1054, "°C", 1 / 64),
        r("composite_outdoor_temp", "Composite outside temperature", 1055, "°C", 1 / 64),
        r("room_target", "Current room temperature target", 1057, "°C", 1 / 64),
        r("dhw_target", "Current DHW temperature target", 1058, "°C", 1 / 64),
        r("flow_target", "Resulting flow temperature target", 1064, "°C", 1 / 64),
        r("heating_target", "Heating circuit temperature target", 1066, "°C", 1 / 64),
        r("dhw_resulting_target", "Resulting DHW target", 1068, "°C", 1 / 64),
    ]
    if model == "RVD140":
        points += [
            r("universal_temp", "Universal temperature B71", 1049, "°C", 1 / 64),
            r("tank_2_temp", "Storage tank 2 temperature B32", 1050, "°C", 1 / 64),
            r("collector_temp", "Solar collector temperature B6", 1051, "°C", 1 / 64),
            r("secondary_pressure", "Secondary pressure U1", 1052, "bar", 1 / 50),
            r("primary_pressure", "Primary pressure U2", 1053, "bar", 1 / 50),
        ]
    return points
