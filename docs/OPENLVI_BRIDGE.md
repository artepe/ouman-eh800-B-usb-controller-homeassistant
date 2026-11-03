# OpenLVI Bridge — multi-vendor Home Assistant integration

**Experimental beta; NOT hardware validated.** Maintained in the repository
[OpenLVIBridge-homeassistant](https://github.com/artepe/OpenLVIBridge-homeassistant).
The proven Ouman EH-800B USB component (`custom_components/ouman_eh800`
v0.1.2) remains unchanged. Do not replace a live controller's working setup.

## Install (development testers only)

Copy `custom_components/openlvi` to
`/config/custom_components/openlvi`. Restart Home Assistant, then:
**Settings → Devices & services → Add integration → OpenLVI Bridge**.

The interactive wizard asks:
1. **Manufacturer**: Ouman, Danfoss, Regin, Swegon, Enervent, Vallox,
   Fidelix, Siemens, Produal, Koja or NIBE.
2. **Model**, installed **firmware**, and for Danfoss the **ECL application key**.
3. **Transport**: HTTP (EH-800), USB (EH-800B), Modbus TCP or RS-485 RTU.
4. IP/USB details, unit ID, parity or a site-specific JSON register map.

The setup probe is *read-only*. Automatic writable entity creation is
disabled by default and exposed only for narrowly allowlisted registers.
Other selected manufacturers are **not fully automatic yet**: supply
their exact, site-specific, read-only register map.

## Confirmed document mappings, but NOT proven on live devices

| Vendor/model | Interface | Included points | Writes |
|---|---|---|---|
| Ouman EH-800 | local HTTP | detected active HTTP API endpoints | limited numeric setpoints, optional |
| Ouman EH-800B | local USB Mini-B | up to 28 read-only measurement values | none in this new integration |
| Ouman A203/S203/C203/H23 | Modbus RTU/TCP | temperature subsets, version-specific room targets | limited room targets, optional |
| Danfoss ECL Comfort 210/296/310/310B | Modbus RTU (210), TCP or RTU (296/310) | sensor S2 PNU 10202; circuit 1 comfort target 11180 only when application A266.1 is entered | read only until model and application tested |
| Regin Corrigo E Ventilation 3.2 | Modbus RTU or gateway | outdoor/supply/extract temperatures, fan flow, run state | read only |
| Swegon CASA Genius SW4.x with SEM/SEC | Modbus RTU or gateway | fan RPM and %, temperature setpoint, mode, CO2 thresholds, heat recovery | selected operating modes 1/2/3 only, optional |
| Regin Corrigo 5, Exigo; Swegon Smart/GOLD; Enervent eAir/eWind; Vallox MyVallox; Fidelix FX-series; Siemens Climatix; Produal Proxima; Koja KojaControl; NIBE S-series; other Ouman models | model-dependent Modbus TCP/RTU | **requires exported point map** | custom profiles always read only |

The model list is not a claim that all these controllers offer Modbus
without accessories. Confirm physical interface availability, interface
options/licensing and wiring against the exact unit.

### Vendor documentation

- [Danfoss ECL 210/296/310 communication description](https://assets.danfoss.com/documents/198690/AQ074886472234en-010601.pdf):
  PNU registers are **1-based**, S2 is **10202 / 100**, comfort setpoint
  **11180 / 10**; 296/310 TCP uses port 502. The application key controls
  which PNU values exist.
- [Swegon CASA Genius register table](https://www.swegon.com/globalassets/digizuite/18172-en-casa_modbusregisters_en.pdf):
  SEM/SEC, SW4.0+, 3x=input and 4x=holding. 6305/6306 are RPM, 6303/6304
  control %, 5001 operating mode. All alarm/safety stop overrides excluded.
- [Regin Corrigo E Ventilation 3.2 register list](https://www.regincontrols.com/globalassets/pimmediafiles/documents/corrigo_e_ventilation_variables_for_exoline_and_modbus_3.2_manu_en.pdf):
  input registers 1/3/7/8/9/15/16. Real values generally divide by 10,
  airflow by 1. Avoid aggressive RTU polling (max 10 fast requests/30 s).
- [Regin Corrigo 5 variable list](https://www.regincontrols.com/globalassets/pimmediafiles/documents/corrigo-5_0_vl40006_en.pdf):
  different map, **never reuse** Corrigo E profile.
- [Ouman documents](https://ouman.fi/downloads/), including firmware
  specific register PDFs.
- [Official HA EH-800 integration](https://www.home-assistant.io/integrations/ouman_eh_800/):
  production EH-800 Ethernet users should prefer the official integration.
- [Vallox direct Modbus FAQ](https://www.vallox.com/en/support-and-instructions/frequently-asked-questions/):
  obtain software-version-specific MyVallox map before use.

## Custom site-specific registers (always read-only)

```json
{
  "registers": [
    {"key": "room_temp", "name": "Room temperature", "address": 305,
     "area": "input", "kind": "s16", "decimals": 1, "unit": "°C"}
  ]
}
```

**Address 305 is only an illustration, not a real verified device address.**
Replace it with your controller's actual point table. Valid areas:
`holding` (Modbus function 03) and `input` (function 04). Supported
types: signed/unsigned 16-bit or 32-bit. Vendor 1-based address
is converted internally to the 0-based Modbus protocol address.
JSON-supplied registers can never become writable.

## Safety, constraints, and planned work

- Writes require explicit opt-in and a hardcoded per-model allowlist,
  values are bounded and (for Modbus) verified by reading back.
  *No manual fan safety bypass, freezing override, PID tuning, pump manual
  override, or unknown register writes.*
- Do not connect the controller's Modbus TCP/unencrypted HTTP port directly
  to the internet. Use local VLAN/firewall, and retain local physical fallback.
- Serial settings, firmware and application key must exactly match the device.
  No blind Modbus scanning. Unit probing may take time and register support is
  application-specific.
- For real installations: test with read-only access first, verify sensor
  scaling against the controller's own display, then validate any permitted
  setpoint on an isolated bench.
- Follow-up: add dedicated select/switch for safe modes, robust coil/discrete
  handling, full vendor profiles, device discovery and physical test fixtures.
