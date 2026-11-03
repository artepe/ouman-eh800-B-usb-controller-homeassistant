"""Ouman Universal configuration constants."""
DOMAIN = "ouman_universal"
CONF_MODEL = "model"
CONF_FIRMWARE = "firmware"
CONF_TRANSPORT = "transport"
CONF_UNIT_ID = "unit_id"
CONF_PROFILE = "profile_json"
CONF_ALLOW_WRITES = "allow_writes"
CONF_BAUDRATE = "baudrate"
CONF_PORT = "port"
CONF_HOST = "host"
CONF_URL = "url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

MODELS = (
    "EH-800", "EH-800B", "A203", "S203", "C203", "H23",
    "Ouflex", "Ouflex A", "Ouflex A XL", "Ouflex AX",
    "Ouflex M", "Ouflex M BA", "Ouflex C",
    "H21", "S105", "EH-203", "EH-105", "EH-686",
    "RU23", "EC-104", "FLEX I/O",
)

CONF_VENDOR = "vendor"
CONF_APPLICATION = "application_key"
CONF_PARITY = "parity"
VENDOR_MODELS = {
    "Ouman": MODELS,
    "Danfoss": ("ECL Comfort 210", "ECL Comfort 296", "ECL Comfort 310", "ECL Comfort 310B", "ECL 120/220"),
    "Regin": ("Corrigo E Ventilation", "Corrigo 5", "Exigo"),
    "Swegon": ("CASA Genius", "CASA Smart", "GOLD"),
    "Enervent": ("eAir", "eWind"),
    "Vallox": ("MyVallox",),
    "Fidelix": ("FX2030", "FX3000"),
    "Siemens": ("Climatix POL6xx",),
    "Produal": ("Proxima",),
    "Koja": ("KojaControl",),
    "NIBE": ("S-series",),
}
