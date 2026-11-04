"""OpenHVAC Bridge configuration constants."""
DOMAIN = "openhvac"
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
    "Ouman": MODELS + ("WL-BASE 2.1", "Oulink ETH", "M-LINK"),  # EC-104 is already in MODELS
    "Danfoss": ("ECL Comfort 210", "ECL Comfort 296", "ECL Comfort 310", "ECL Comfort 310B", "ECL 120/220", "Icon2", "Ally Gateway"),
    "Regin": ("Corrigo E Ventilation", "Corrigo 5", "Exigo"),
    "Swegon": ("CASA Genius", "CASA Smart", "GOLD"),
    "Enervent": ("eAir", "eWind"),
    "Vallox": ("MyVallox",),
    "Fidelix": ("FX2030", "FX3000"),
    "Siemens": ("Climatix POL6xx", "Desigo PXC4", "Desigo PXC5", "Desigo PXC7", "Desigo DXR2", "Synco OZW672", "Synco RMU7xx"),
    "Produal": ("Proxima",),
    "Koja": ("KojaControl",),
    "NIBE": ("S-series",),
    "Uponor": ("Smatrix Base PRO X-148", "Smatrix Base PRO X-147 KNX", "Smatrix Pulse R-208"),
    "Roth": ("Touchline SL Modbus", "Touchline SL WiFi"),
    "Wavin": ("Sentio",),
    "Tosibox": ("TOSIBOX 175", "TOSIBOX 350", "TOSIBOX 375", "TOSIBOX Lock 500", "TOSIBOX 610", "TOSIBOX 650", "TOSIBOX 670", "TOSIBOX 675", "TOSIBOX 695"),
    "Honeywell": ("CentraLine EAGLEHAWK NX", "EAGLE Controller", "Optimizer VAV", "EAGLEHAWK"),
    "Resideo": ("Evohome", "HCC100", "HCC80", "HCE80"),
    "LK Systems": ("ICS.2",),
    "SALUS": ("Smart Home UG600",),
    "OJ Electronics": ("WLM3", "WLM2"),

}

CONF_BACNET_LOCAL_ADDRESS = "bacnet_local_address"
CONF_BACNET_DEVICE_ID = "bacnet_device_id"
CONF_BACNET_LOCAL_INSTANCE = "bacnet_local_instance"
VENDOR_MODELS["Kamstrup"] = ("MULTICAL 403", "MULTICAL 603", "MULTICAL 803")
VENDOR_MODELS["Grundfos"] = ("MAGNA3 CIM500", "CIM500 / CIU500")
VENDOR_MODELS["Wilo"] = ("Stratos MAXO", "Stratos GIGA")
VENDOR_MODELS["Belimo"] = ("Modbus actuator", "Modbus VAV", "BACnet actuator")
VENDOR_MODELS["Schneider Electric"] = ("SpaceLogic MP-C",)
VENDOR_MODELS["Siemens"] += ("Desigo PXC4 E16", "Desigo PXC5 E24", "Desigo PXC7 E400")
