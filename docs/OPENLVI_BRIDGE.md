# OpenLVI Bridge — multi-vendor Home Assistant integration

**Experimental beta 0.4.3-beta.1; NOT hardware validated.** Maintained in the repository
[Open-HVACBridge-homeassistant](https://github.com/artepe/Open-HVACBridge-homeassistant).
The proven Ouman EH-800B USB component (`custom_components/ouman_eh800`
v0.1.2) remains unchanged. Do not replace a live controller's working setup.

## Install (development testers only)

Copy `custom_components/openlvi` to
`/config/custom_components/openlvi`. Restart Home Assistant, then:
**Settings → Devices & services → Add integration → OpenLVI Bridge**.

The interactive wizard asks:
1. **Manufacturer**: Ouman, Danfoss, Regin, Swegon, Kamstrup,
   Enervent, Vallox, Fidelix, Siemens, Schneider Electric, Grundfos,
   Wilo, Belimo, Produal, Koja, NIBE or Jäspi (AIR with MODBUS 40 only).
2. **Model**, installed **firmware**, and for Danfoss the **ECL application key**.
3. **Transport**: HTTP (EH-800), USB (EH-800B), Modbus TCP/RTU,
   read-only BACnet/IP, or wired M-Bus for Kamstrup.
4. IP/USB details, unit ID, serial parity, BACnet device instance
   or an exact site-specific read-only point list.

**English is the default interface language.** Optional Home Assistant
translations (Finnish, Swedish, Estonian, Polish and Russian) are stored
separately and are selected by the user's Home Assistant language preference.
The controller's actual language setting is not changed. See
[Language support](LOCALIZATION.md).

The setup probe is *read-only*. On **EH-800B USB**, 11 guarded L1
Number controls now appear automatically (also on previously configured
OpenLVI entries). **No SET PROPERTY is sent on startup or polling.**
Their actual initial values are unknown until a user manually submits
a new target because a side-effect-free USB GET PROPERTY is not verified.
PID, direct valve position and undocumented properties are not exposed.
Other models retain opt-in writes on only narrowly reviewed registers.
See [EH-800B controls](EH800B_CONTROLS.md).
Other selected manufacturers are **not fully automatic yet**: supply
their exact, site-specific, read-only register map.

## Confirmed document mappings, but NOT proven on live devices

| Vendor/model | Interface | Included points | Writes |
|---|---|---|---|
| Ouman EH-800 | local HTTP | detected active HTTP API endpoints | limited numeric setpoints, optional |
| Ouman EH-800B | local USB Mini-B | up to 28 measurements + 11 L1 setup controls | explicitly entered and bounded setpoints only; PID and direct valve position blocked |
| Ouman A203/S203/C203/H23 | Modbus RTU/TCP | temperature subsets, version-specific room targets | limited room targets, optional |
| Danfoss ECL Comfort 210/296/310/310B | Modbus RTU (210), TCP or RTU (296/310) | sensor S2 PNU 10202; circuit 1 comfort target 11180 only when application A266.1 is entered | read only until model and application tested |
| Regin Corrigo E Ventilation 3.2 | Modbus RTU or gateway | outdoor/supply/extract temperatures, fan flow, run state | read only |
| Jäspi Tehowatti AIR + MODBUS 40 | Modbus RTU or verified RTU-to-LAN gateway | No built-in point map; exact site/firmware register JSON required | custom profile read only |
| Swegon CASA Genius SW4.x with SEM/SEC | Modbus RTU or gateway | fan RPM and %, temperature setpoint, mode, CO2 thresholds, heat recovery | selected operating modes 1/2/3 only, optional |
| BACnet/IP (e.g. Siemens, Schneider, Belimo) | Private local network, UDP 47808 | Explicit read-only object list or bounded discovery on one selected device (up to 32 objects) | read only |
| Kamstrup MULTICAL 403/603/803 | Powered wired M-Bus master with serial interface | Telegram records and transmitted units | read only |
| Regin Corrigo 5, Exigo; Swegon Smart/GOLD; Enervent eAir/eWind; Vallox MyVallox; Fidelix FX-series; Siemens Climatix/Desigo; Produal Proxima; Koja KojaControl; NIBE S-series; Grundfos, Wilo, Belimo and other Ouman models | Hardware/firmware-dependent Modbus or BACnet | **requires exact site-specific point map** | custom profiles always read only |

The model list is not a claim that all these controllers offer Modbus
without accessories. Confirm physical interface availability, interface
options/licensing and wiring against the exact unit.

For the *different* conventional Jäspi Tehowatti electric boiler, see
[documented dry-contact temperature setback example](JASPI_TEHOWATTI.md).
Its heating input is not a Modbus register interface. Tehowatti AIR
requires an installed MODBUS 40 module (not just an Ethernet connection).

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

**New research:** see [manufacturer register source map](REGISTER_AND_CONTROL_SOURCE_MAP.md) and
[LoRaWAN / other network research](LORAWAN_AND_PROTOCOLS.md). These are
not proof of direct interoperability; the researched point maps are not
activated by model name alone.

## New Finnish controller and building automation profiles

- Uponor Smatrix Base PRO X-148: input registers 30001–30025
  (logical one-based PDU addresses 1–25), missing marker 0x7FFF.
- Roth Touchline SL: first-zone Modbus RTU room/floor temperatures,
  humidity, zone output, target and battery, all monitoring-only.
- Tosibox: status register offsets 14–23 from 40001, with disabled
  status writes. Firmware >= 5.5.0 and enabled local Modbus required.
- Siemens Desigo, Honeywell EAGLEHAWK, Wavin Sentio, Ouman WL-BASE,
  Danfoss Icon2 and others are documented research targets, **not**
  plug-and-play without the model-specific interface and point map.

See [Finnish market source catalog](FINLAND_BUILDING_AUTOMATION_CATALOG.md),
[CO2 supplemental fan blueprint](../blueprints/automation/openlvi/co2_supplemental_fan_0_10v.yaml)
and [thermal and refrigerant COP guide](THERMAL_AND_REFRIGERANT_COP.md).

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
JSON-supplied registers can never become writable. For **read-only** engineering
units, an optional finite numeric `offset` is applied after decimal scaling.
For example, a MyVallox 16-bit unsigned centikelvin register may use
`decimals:2` and `offset:-273.15` to display Celsius. This is not used
by writes. See [MyVallox sample](../examples/modbus-myvallox-readonly.json).
The site and vendor address-to-PDU conversion must still be verified.

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
- The experimental BACnet/IP adapter already offers **selected-device** object
  discovery; general network discovery remains unimplemented.
- Follow-up: physically validate device access, then add safe select/switch
  entities, coil/discrete support, more complete point maps and restart tests.
- See the [BACnet/M-Bus/SCADA extension guide](OPENLVI_EXTENSIONS.md)
  for adapter requirements and the 2.5D monitoring dashboard.

## Optional English AI guidance

This beta includes a read-only English setup guide on the device page, a review button, the `openlvi.ask_assistant` Home Assistant action, and optional local Ollama/Qwen2.5 0.5B. It uses named, verified readings. The AI does **not** apply any controller setting. See [OpenLVI AI Guide](OPENLVI_AI_GUIDE.md).
