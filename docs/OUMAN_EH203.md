# Ouman EH-203 — OpenLVI Bridge (experimental, read-only)

## Requirements

- Ouman **EH-203** heating controller with identified 1.22+ or 2.x firmware.
- An installed **MODBUS-200** interface card or **MODBUS-200-DIN** adapter.
- An isolated USB-to-RS485 adapter connected to the Modbus RS-485 pair,
  **or** a locally reachable, correctly configured RTU-to-TCP gateway.
- Home Assistant running the OpenLVI Bridge custom integration.

**The EH-203's built-in EIA-232 / RS-232 connector is not automatically
Modbus.** Do not connect a generic USB-RS232 adapter and expect this
Modbus driver to work. The MODBUS-200-DIN uses the controller's EIA-232
terminals to provide a separate RS-485 Modbus interface. Follow the Ouman
wiring diagram; the controller contains mains voltage.

## Controller and bridge setup

1. Install and configure MODBUS-200/-DIN according to the manufacturer.
   Set the slave ID and baud rate using the adapter DIP switches.
   Supported speeds are **4800, 9600, 19200 and 38400** baud. Check the
   exact parity against the connected adapter/gateway and use the matching
   serial setting. Use a twisted RS-485 bus with 120-ohm termination at
   both **physical** ends, and the documented biasing arrangement.
2. In HA: Settings → Devices & services → Add integration → **OpenLVI
   Bridge** → **Ouman** → **EH-203**. Enter the actual controller firmware,
   for example `2.18c`.
3. Choose **Modbus RTU** for RS-485 USB or **Modbus TCP** only with a
   correctly configured *local* RTU-to-TCP gateway. Enter unit ID, device
   serial path/host, baud rate and parity.
4. Begin with raw read-only values. Compare temperatures and valve
   positions with the local display before relying on any automation.

### Built-in read-only points

The profile covers the official document's zero-based registers:

| Official address (PDU) | Meaning | Decoding |
| --- | --- | --- |
| 231 | Outdoor temperature | signed 16-bit / 100 °C |
| 232, 233, 234 | H1 supply, H1 room and H1 return | signed 16-bit / 100 °C |
| 235, 236 | Domestic hot water and anticipation | signed 16-bit / 100 °C |
| 237 | H2 supply | signed 16-bit / 100 °C |
| 238–241 | Additional measurement channels | signed 16-bit / 100 °C |
| 242–244 | H1, H2 and domestic hot water valve positions | unsigned 16-bit, % |
| 253 | Digital state word | unsigned raw bits |
| 254–255 | Alarm state words | unsigned raw bits |
| 272 | General A/B alarm word | unsigned raw bits |

**Important offset distinction:** The legacy MODBUS-200 vendor
documentation starts its table at **0**, unlike many modern Ouman
device templates. OpenLVI stores internal 1-based addresses and its
transport subtracts one before calling pymodbus, so the profile adds
one to each documented legacy address. E.g. manufacturer's register
231 → internal Register.address 232 → Modbus PDU address 231.

No writable controls are published for EH-203 — even when the operator
selected the generic setup checkbox. No pump override, valve driving,
frost protection changes, alarm acknowledgment, safety overrides or
heating-curve writes are performed. The raw bitmask readings are **not**
alarm acknowledgment operations.

Only manufacturer-documented common measurement points are included.
Additional version-2-specific registers 290–292 and 308–311 are omitted
until scaling and a physical implementation are verified. Some installed
sites do not have every optional sensor: validate each reading against
the controller and disable irrelevant entities. The MODBUS-200 card may
need about 13 seconds to start up, and the slowest manufacturer update
category refreshes around every 60 seconds.

**Important alarm caveat:** Ouman states that when the MODBUS-200
adapter updates registers 254–255, it automatically acknowledges alarms
to the controller; the local alarm may therefore not sound normally.
This behavior belongs to the hardware adapter even if OpenLVI never
writes or acknowledges an alarm. Maintain independent critical alarms.

OpenLVI does not yet have a physically tested EH-203 unit. Firmware
prior to 1.22 or unknown major versions require a confirmed
site-specific read-only JSON register profile.

## Official references

- [Ouman MODBUS-200 / MODBUS-200-DIN manual (English), v2.18](https://ouman.fi/documentbank/MODBUS-200__manual__en.pdf)
- [Ouman EH-203 manual (Finnish)](https://kauppa.ouman.fi/wp-content/uploads/2026/01/EH-203_ver.2.18c-_FIN_press.pdf)
- [OpenLVI Bridge installation](OPENLVI_BRIDGE.md)
