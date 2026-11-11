# Jäspi Tehowatti AIR – local Modbus monitoring

**Scope:** only the **Tehowatti AIR** heat pump indoor unit with the optional
**MODBUS 40** accessory. Other Tehowatti products have different interfaces.

| Product | Verified interface | Open HVAC implementation | Validation |
|---|---|---|---|
| **Tehowatti AIR** heat pump indoor unit | Optional **MODBUS 40** module (Jäspi item M02924), **Modbus RTU** | OpenLVI Bridge model entry; operator-supplied **read-only** register profile required | Manufacturer-documented interface; **no bundled verified register map / no hardware-tested driver** |
| Conventional **Tehowatti electric boiler** | Only a potential-free temperature setback input; no data interface | **Not supported** | – |
| Other Tehowatti versions and Tehowatti Air Evo | Do not assume the same interface | Not supported without a matching manual and hardware test | Unverified |

## Tehowatti AIR: optional local MODBUS 40

Jäspi's **Tehowatti AIR installer manual**, chapter "Lisätarvikkeet",
specifies **MODBUS 40** (M02924) for monitoring and control over
**Modbus RTU** and menu **5.3.11** for bus address and word swap.

https://jaspi.fi/wp-content/uploads/2017/01/D104224-JASPI_Tehowatti-AIR-asentajan-kasikirja_v2.pdf

1. Confirm that the unit is **Tehowatti AIR** and MODBUS 40 is
   physically installed and enabled. Check exact model, firmware,
   device address, serial settings, physical interface and register list
   against the accessory manual. The module does not imply built-in TCP/Wi-Fi.
2. Install OpenLVI Bridge. In the wizard select **Jäspi →
   Tehowatti AIR (MODBUS 40)**, then **Modbus RTU** (USB/RS-485 bridge)
   or **Modbus TCP** *only if* a suitable serial-to-LAN gateway is installed
   and verified to expose the required mode.
3. Supply a **site- and version-specific Modbus register JSON** from
   documentation or a verified device export. This model has **no guessed
   default register addresses**. Without a valid profile the wizard
   refuses setup. See [OpenLVI's read-only custom profile format](OPENLVI_BRIDGE.md#custom-site-specific-registers-always-read-only).
4. The first connection must be **read-only**. Compare every value and
   scaling to the physical controller before accepting the mapping.
   Generic JSON profiles stay read-only even if a user includes
   `"writable": true`. Tehowatti AIR Modbus setpoint writes are **not
   enabled**.

MODBUS 40 is a NIBE accessory. Home Assistant's built-in
[NIBE Heat Pump integration](https://www.home-assistant.io/integrations/nibe_heatpump/)
also communicates through MODBUS 40 and may be an alternative, but it has not
been tested with Tehowatti AIR.

**Not supported:** assuming that myUpway/myUplink metric IDs are Modbus
register addresses; automatic register discovery, generic changes to
safety/operating mode, or claiming the ordinary Tehowatti electric boiler
has the AIR module interface.

## Community research

- Legacy cloud API research for AIR:
  https://github.com/lemanjo/pyupway
  (the README says the Tehowatti AIR was tested; **cloud-dependent**,
  not an Open HVAC local integration).

**Release status:** manufacturer interface documented and OpenLVI guarded
setup provided; **no physical-device acceptance test**. We welcome device
model/year, a redacted register list, read-only Modbus captures and feedback
from a hardware tester. Do not claim plug-and-play.
