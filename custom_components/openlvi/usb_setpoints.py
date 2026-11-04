"""EH-800B USB allowlist. Never write PID 56/57/58 or valve override 92."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

@dataclass(frozen=True)
class UsbSetpoint:
    property_id: int
    key: str
    name: str
    raw_min: int
    raw_max: int
    raw_step: int
    scale: int
    unit: str | None = None

    @property
    def minimum(self):
        return self.raw_min / self.scale

    @property
    def maximum(self):
        return self.raw_max / self.scale

    @property
    def step(self):
        return self.raw_step / self.scale

    @property
    def decimals(self):
        return 1 if self.scale == 10 else 0

# Approved L1 property IDs from the legacy EH-800B USB project. These are
# manually triggered setpoints, never sent during installation or startup.
USB_SAFE_SETPOINTS = (
    UsbSetpoint(54, "l1_supply_minimum", "L1 supply minimum", 50, 950, 10, 10, "°C"),
    UsbSetpoint(55, "l1_supply_maximum", "L1 supply maximum", 50, 950, 10, 10, "°C"),
    UsbSetpoint(67, "l1_curve_minus_20c", "L1 heating curve -20 °C", 0, 1000, 10, 10, "°C"),
    UsbSetpoint(69, "l1_curve_minus_10c", "L1 heating curve -10 °C", 0, 1000, 10, 10, "°C"),
    UsbSetpoint(71, "l1_curve_0c", "L1 heating curve 0 °C", 0, 1000, 10, 10, "°C"),
    UsbSetpoint(73, "l1_curve_plus_10c", "L1 heating curve +10 °C", 0, 1000, 10, 10, "°C"),
    UsbSetpoint(75, "l1_curve_plus_20c", "L1 heating curve +20 °C", 0, 1000, 10, 10, "°C"),
    UsbSetpoint(91, "l1_summer_shutoff", "L1 summer shutoff setting", 5, 95, 1, 1),
    UsbSetpoint(126, "l1_max_supply_change_rate", "L1 maximum supply change rate", 1, 50, 1, 1),
    UsbSetpoint(127, "l1_supply_setpoint", "L1 supply setpoint", 0, 950, 10, 10, "°C"),
    UsbSetpoint(134, "l1_fine_adjustment", "L1 fine adjustment", -40, 40, 1, 10, "°C"),
)
USB_BY_KEY = {spec.key: spec for spec in USB_SAFE_SETPOINTS}
USB_BY_ID = {spec.property_id: spec for spec in USB_SAFE_SETPOINTS}
FORBIDDEN_PROPERTY_IDS = frozenset({56, 57, 58, 92})
assert len(USB_SAFE_SETPOINTS) == len(USB_BY_KEY) == len(USB_BY_ID)
assert not (set(USB_BY_ID) & FORBIDDEN_PROPERTY_IDS)

_REPLY = re.compile(r"PROPERTY\(\s*(\d+)\s*\):'([^']+)'\(([^)]*)\)\s*=\s*(-?\d+)", re.I)

def raw_from_value(spec: UsbSetpoint, value: float) -> int:
    """Refuse unknown IDs, values outside range or nonrepresentable steps."""
    if USB_BY_ID.get(spec.property_id) != spec:
        raise ValueError("Not an approved EH-800B property")
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid setpoint") from None
    if not num.is_finite():
        raise ValueError("Non-finite setpoint")
    raw_dec = num * spec.scale
    if raw_dec != raw_dec.to_integral_value():
        raise ValueError("Invalid setpoint precision")
    raw = int(raw_dec)
    if raw < spec.raw_min or raw > spec.raw_max or raw % spec.raw_step:
        raise ValueError("Setpoint outside approved range or step")
    return raw

def confirm_property_reply(property_id: int, raw: int, response: str) -> None:
    """Validate single SET response; never resend to discover whether it worked."""
    match = _REPLY.search(response)
    if not match:
        raise ValueError("EH-800B confirmation missing; physical state unknown")
    if property_id not in USB_BY_ID or int(match.group(1)) != property_id:
        raise ValueError("Wrong property returned")
    if (int(match.group(4)) & 65535) != (raw & 65535):
        raise ValueError("EH-800B returned a different value")
