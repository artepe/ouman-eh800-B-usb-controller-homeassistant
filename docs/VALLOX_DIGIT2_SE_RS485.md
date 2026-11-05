# Vallox Digit2 SE / Digit SE 2 → Home Assistant (local RS485)

**Status (2026-11-05): documented external integration path; not a native OpenLVI driver.**
The original `Vallox Digit2 SE` (also written `Digit SE 2`) uses the
**proprietary Vallox Digit/SE RS485 bus**, **not Modbus RTU**. Never apply
OpenLVI's `MyVallox` Modbus register profile or generic Modbus RTU wizard
to this controller. This guide covers the electric, VKL and MLV variants
subject to hardware/options verification.

## Compatibility evidence — keep these distinctions

| Implementation | Digit2 SE evidence | Connection to Home Assistant | Project status |
|---|---|---|---|
| [kotope/valloxesp](https://github.com/kotope/valloxesp) | **Digit SE 2 explicitly listed as tested** by its maintainer | ESP-01 firmware → MQTT → upstream `vallox2mqtt` custom component | External project; not bundled or retested by OpenLVI |
| [Tom-Bom-badil/home-assistant_helios-vallox](https://github.com/Tom-Bom-badil/home-assistant_helios-vallox) | Digit SE is reported working; **Digit SE2 is listed as expected, not confirmed** | USB-RS485 or local serial-to-TCP / ESPHome RS485 bridge → HACS Helios/Vallox integration | Recommended *evaluation* route for a HA-native setup |
| [skjall/home-assistant-vallox-rs485](https://github.com/skjall/home-assistant-vallox-rs485) | Compatible Digit-family protocol, but no specific Digit2 SE field confirmation found | USB-RS485 → standalone HA integration | Beta alternative; check upstream issues |

A device that is supported by an upstream project is **not automatically
supported inside `custom_components/openlvi`**. OpenLVI does not yet
implement Digit/SE telegram handling or expose its controls.

## Architecture (offline/local)

```text
Vallox Digit2 SE ── proprietary RS485 bus (A/B) ──┬── isolated USB/RS485 ── HA OS host
                                                   ├── RS485/Ethernet bridge ── local LAN ── HA
                                                   └── compatible ESP32/RS485 bridge ── local Wi-Fi ── HA
                                                              |
                   Third-party Helios/Vallox HA integration or other tested Digit driver
                                                              |
                   Home Assistant entities → dashboards/automations/OpenLVI SCADA by entity ID
```

No Internet, cloud login, inbound port-forward or Tailscale client on the
ventilation unit is needed. A separate USB adapter on a remote Mac is **not**
an HA serial port: connect it to the HA host or expose it through a
supported, secured local serial bridge.

## Vallox factory bus wiring

The *Vallox Digit2 SE technical wiring diagram*, external connections
(page **8**), labels the terminal block **`A B - + M`** under
`RS-485 BUS` (verify marking on *your* machine before any work).
The wall control panel's own diagram lists:

| Digit2 SE terminal | Role | Factory diagram example (NOMAK) |
|---|---|---|
| `A` | RS485 A signal | Orange 2 |
| `B` | RS485 B signal | White 2 |
| `M` | Signal ground / shield | Black / metal |
| `-` | Control-panel supply negative | White 1 |
| `+` | Control-panel positive supply, approximately **21 VDC** in the manual | Orange 1 |

- Connect adapter **A ↔ A** and **B ↔ B** following its own polarity
  definitions. Manufacturer A/B naming is not consistent across all adapters;
  if there is no traffic, first verify polarity and baud/parity.
- `M` is **not** automatically interchangeable with the DC supply `-`.
  Follow the adapter's isolation/grounding instructions; do not bridge
  them arbitrarily.
- **Do not connect `+` or `-` to an ESP32 GPIO, UART pin or 3.3/5 V rail.**
  An RS485 transceiver is required, not a bare TTL UART. If powering a
  bridge from the Vallox panel supply, first verify its *actual measured
  voltage*, acceptable input voltage range, polarity, current budget and
  isolation. A bus-powered adapter verified on another Helios/Vallox
  model is not automatic approval for Digit2 SE.
- Power **off and unplug the unit** before opening the connection box.
  It also contains **230 V wiring**. The manual warns that an incorrect
  connection of the `+` conductor can destroy control electronics.
  Electrical work belongs to a qualified installer.
- Do not install a new **120 Ω termination resistor** by default: inspect
  existing bus end termination, cable topology and adapter jumper first.
  A second termination or concurrent talkers can disrupt the wall panel.
- Preserve the original wall controller and all native freeze protection,
  heater limits and fan safety functions. Do not make remote 'OFF'
  automatic or override frost/overheat protections.

**Official product:** https://www.vallox.com/en/product/vallox-digit2-se/

**Digit2 SE technical manual, especially pages 5 and 8:**
https://www.hts.com.pl/wp-content/uploads/2014/12/VALLOX_DIGIT2_SE.pdf

## Path A: HACS Helios/Vallox + local RS485 bridge (recommended evaluation)

1. Identify the exact Digit2 SE model and panel wiring. Choose an
   **isolated RS485-to-USB adapter** on the HA machine (stable wired choice),
   or a compatible RS485-to-LAN / ESPHome serial bridge.
2. Configure the serial link to the upstream integration's **9600 baud,
   8 data bits, no parity, 1 stop bit** baseline. This is the **Vallox
   proprietary protocol**, not Modbus; do not set a Modbus unit ID.
   The adapter must support **bidirectional transparent byte transport**,
   not Modbus register polling.
3. Follow the upstream [wiring guide](https://github.com/Tom-Bom-badil/home-assistant_helios-vallox/wiki/Wiring-how%E2%80%90to).
   When using an ESP32 bridge, follow the upstream
   [ESP plug-and-play guide](https://github.com/Tom-Bom-badil/home-assistant_helios-vallox/wiki/esp-plug-and-play-solution).
   ESPHome adoption alone only creates the bridge: it **does not**
   install a Vallox decoder.
4. Install **Helios/Vallox** from HACS (search `helios`) and add it from
   **Settings → Devices & services → Add integration → Helios/Vallox**.
   Select the actual USB serial port or LAN/ESPHome transport exposed by
   the adapter; complete its guided device setup.
   [Official upstream installation instructions](https://github.com/Tom-Bom-badil/home-assistant_helios-vallox/wiki/Installation-and-setup).
5. **Read/verify first:** compare outside/extract/supply/exhaust readings
   and fan level to the physical wall panel. Observe at least one complete
   update cycle and a Home Assistant restart before considering control.
6. Only after physically verifying the model and avoiding other bus writers,
   test **one user-initiated** fan-speed adjustment within the original
   commissioned limits. Check that wall panel and Home Assistant agree,
   and that manual local operation still works.

A USB-RS485 adapter needs actual USB access from the HA OS host. A Wi-Fi
ESP bridge needs sufficient local Wi-Fi coverage; avoid exposing serial
ports or ESPHome API to public Internet.

## Path B: specifically Digit SE 2 tested upstream — ESP-01 + MQTT

If you prefer an implementation whose upstream README **explicitly
reports testing with Digit SE 2**, use
[kotope/valloxesp](https://github.com/kotope/valloxesp).
Follow the project's **separate ESP-01 hardware, firmware and MQTT
configuration guides**, then install its `vallox2mqtt` Home Assistant
custom component and configure it via the HA integrations UI.

This is **not the same thing** as connecting the Helios/Vallox integration
to an ESPHome serial bridge. Do **not** flash both firmware families onto
one ESP. MQTT should stay on your local trusted Mosquitto broker with
authentication; never expose broker port 1883 to the Internet.

Upstream's custom component reports fan level **1–8**, four temperature
sensors, status, summer mode, filter-service counter, optional RH/CO2,
and some heater / boost / fireplace functions. **Availability depends
on hardware, firmware and installed sensors.** Confirm actual entities
on your machine.

## Troubleshooting / acceptance checklist

- **No entities or connection failure:** confirm that the adapter is
  connected to **A/B**, not to `0–10 V` analogue fan control;
  verify power, physical wires, 9600 8N1, and transparent data forwarding.
- **Wall panel glitches / failed reads:** stop the integration; inspect
  termination, duplicate RS485 connections, address/collision issues and
  supply wiring. Do not blindly keep retrying commands.
- **Temperatures missing:** confirm controller version and installed
  sensors; optional CO2/RH cannot be assumed.
- **Fan does not change:** first verify readings and the upstream
  protocol/firmware mapping; no speculative raw register writes.
- **HA shows 'unavailable':** investigate adapter Wi-Fi/USB, local IP,
  integration logs and read freshness; never display stale data as live.
- **Acceptance:** stable 15–60 minute reads, plausible temperatures,
  fan-level match, original panel still usable, no unintended modes after
  reboot, and a written rollback: disable integration/unplug adapter.

## Native OpenLVI implementation backlog (not shipped)

To add this family *inside* OpenLVI in the future, implement a
**separate `vallox_digit_rs485` transport**:
transparent serial/serial-over-TCP; proprietary packet parser with
checksum, address/filter, collision-safe rate limiting; read-only sensor
mapper; per-variant compatibility profile; freshness and reconnect;
mock packet tests; physical acceptance and documented write gates.
Do **not** route it through the generic Modbus RTU transport or publish
a non-working selection in the OpenLVI wizard.

A future driver must retain **read-only default**, require explicit
opt-in for commands, confirm bus state after commands, and leave
critical protective functions outside its write allowlist.
Before copying third-party source code, inspect each upstream license;
this guide only **links** to upstream components and contains no
third-party firmware or integration code.

### Primary references

- Vallox Digit2 SE factory wiring/manual: https://www.hts.com.pl/wp-content/uploads/2014/12/VALLOX_DIGIT2_SE.pdf
- Vallox discontinued product page: https://www.vallox.com/en/product/vallox-digit2-se/
- Digit SE 2 tested upstream: https://github.com/kotope/valloxesp
- Helios/Vallox HACS support and model caveat: https://github.com/Tom-Bom-badil/home-assistant_helios-vallox
- Helios/Vallox wiring: https://github.com/Tom-Bom-badil/home-assistant_helios-vallox/wiki/Wiring-how%E2%80%90to
- Helios/Vallox ESP bridge: https://github.com/Tom-Bom-badil/home-assistant_helios-vallox/wiki/esp-plug-and-play-solution
- Alternative beta integration: https://github.com/skjall/home-assistant-vallox-rs485
