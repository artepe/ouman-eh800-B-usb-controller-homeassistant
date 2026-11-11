"""Ouman Universal configuration constants."""
DOMAIN = "openlvi"
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
    "H21", "S105", "EH-203", "EH-105", "EH-686", "EC-104",
)

CONF_VENDOR = "vendor"
CONF_APPLICATION = "application_key"
CONF_PARITY = "parity"

# Only devices with a documented local Modbus, BACnet/IP, M-Bus, HTTP or USB
# interface are listed. See docs/DEVICE_SUPPORT.md for sources and for the
# devices that were removed because they need another integration.
VENDOR_MODELS = {
    "Ouman": MODELS + ("WL-BASE 2.1",),
    "Danfoss": ("ECL Comfort 210", "ECL Comfort 296", "ECL Comfort 310", "ECL Comfort 310B", "ECL 120/220", "MCX (site-programmed)"),
    "Regin": ("Corrigo E Ventilation", "Corrigo 5", "Exigo"),
    "Swegon": ("CASA Genius", "CASA Smart", "GOLD"),
    "Enervent": ("eAir", "eWind"),
    "Vallox": ("MyVallox",),
    "Fidelix": ("FX2030", "FX3000"),
    "Siemens": ("Climatix POL6xx", "Desigo PXC4", "Desigo PXC5", "Desigo PXC7", "Desigo DXR2",
                "Desigo PXC4 E16", "Desigo PXC5 E24", "Desigo PXC7 E400"),
    "Produal": ("Proxima",),
    "Jäspi": ("Tehowatti AIR (MODBUS 40)",),
    "Uponor": ("Smatrix Base PRO X-148",),
    "Roth": ("Touchline SL Modbus",),
    "Wavin": ("Sentio",),
    "Tosibox": ("TOSIBOX 175", "TOSIBOX 350", "TOSIBOX 375", "TOSIBOX Lock 500", "TOSIBOX 610", "TOSIBOX 650", "TOSIBOX 670", "TOSIBOX 675", "TOSIBOX 695"),
    "Honeywell": ("CentraLine EAGLEHAWK NX", "EAGLE Controller", "Optimizer VAV", "EAGLEHAWK"),
    "LK Systems": ("ICS.2",),
    "Kamstrup": ("MULTICAL 403", "MULTICAL 603", "MULTICAL 803"),
    "Grundfos": ("MAGNA3 CIM500", "CIM500 / CIU500"),
    "Wilo": ("Stratos MAXO", "Stratos GIGA"),
    "Belimo": ("Modbus actuator", "Modbus VAV"),
    "Schneider Electric": ("SpaceLogic MP-C",),
}

# Models with a built-in driver or read-only point map for the documented
# firmware (marked with ✓ in the setup wizard). Ouflex reads its application
# map from the controller over Modbus TCP/FTP. Every other model needs an
# operator-supplied register map or BACnet/IP object discovery.
BUILTIN_SUPPORT_MODELS = frozenset((
    "EH-800", "EH-800B", "A203", "S203", "C203", "H23", "Ouflex",
    "ECL Comfort 210", "ECL Comfort 296", "ECL Comfort 310", "ECL Comfort 310B",
    "CASA Genius", "Corrigo E Ventilation",
    "Smatrix Base PRO X-148", "Touchline SL Modbus",
    "MULTICAL 403", "MULTICAL 603", "MULTICAL 803",
) + VENDOR_MODELS["Tosibox"])

CONF_BACNET_LOCAL_ADDRESS = "bacnet_local_address"
CONF_BACNET_DEVICE_ID = "bacnet_device_id"
CONF_BACNET_LOCAL_INSTANCE = "bacnet_local_instance"

CONF_DISCOVERY = "discovery_mode"
CONF_PROFILE_CONFIRMED = "profile_confirmed"
