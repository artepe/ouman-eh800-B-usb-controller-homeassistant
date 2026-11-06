# Jäspi Tehowatti – local Home Assistant support

**Scope:** Two different product families. Do not mix up their interfaces.

| Product | Verified interface | Open HVAC implementation | Validation |
|---|---|---|---|
| **Tehowatti electric boiler**, traditional 13/21 kW and older variants | Normally-open, potential-free external temperature setback input | Optional ESPHome relay example; also works with a local Shelly dry-contact relay | Manufacturer-documented input; **example not hardware-tested** |
| **Tehowatti AIR** heat pump indoor unit | Optional **MODBUS 40** module (Jäspi item M02924), **Modbus RTU** | OpenLVI Bridge model entry; operator-supplied **read-only** register profile required | Manufacturer-documented interface; **no bundled verified register map / no hardware-tested driver** |
| Other Tehowatti versions and Tehowatti Air Evo | Do not assume the same interface | Not advertised as working without matching manual and hardware test | Unverified |

## 1. Conventional Tehowatti: temperature setback through a dry contact

The Jäspi Tehowatti installation manual describes an **externally controlled,
normally-open, potential-free contact** for temperature setback (for example
a "Kotoa pois" / away switch). It is **not** Modbus, an internal serial
interface, or a general setpoint API. Contact closed requests the
boiler's configured lower temperature; contact open returns the input
to normal operation. The exact reduction setting remains on the boiler.

Manufacturer manual:
https://jaspi.fi/wp-content/uploads/2016/05/Tehowatti_manual_r3_1114.pdf
(see printed page 8, "Liittimet piirikortilla lisävarusteille").

A third-party field guide identifies **relay board terminals 5 and 6**
for a conventional Tehowatti; **do not treat these numbers as universal**:
verify against the installation manual and wiring diagram for the
installed production year before connecting anything:
https://verkkokauppa.nurkantakaa.fi/jaspi-tehowatti-ecowatti/

### Installation paths

- **Shelly:** choose a locally controllable Shelly with a **genuinely
  potential-free NO relay output** (such as a model from the Shelly 1 family).
  Integrate it locally into Home Assistant. Set its power-on default to
  **off/open**. The HA switch ON means *setback*, not heating ON. A
  light-only / mains-switched Shelly output is not suitable.
- **ESPHome:** flash
  [`examples/esphome/jaspi-tehowatti-contact.yaml`](../examples/esphome/jaspi-tehowatti-contact.yaml)
  to a standard ESP32. Use a separate correctly powered, **isolated,
  active-HIGH NO dry-contact relay module** and verify its boot behavior.
  The sample uses GPIO23 and `restore_mode: ALWAYS_OFF`. Replace the GPIO
  and polarity only after verifying the exact relay board. Supply the
  Wi-Fi credentials, a generated 32-byte base64 ESPHome API encryption
  key and a strong OTA password in `secrets.yaml`. For example:

  ```yaml
  wifi_ssid: "local-network-name"
  wifi_password: "replace-with-wifi-password"
  tehowatti_api_key: "replace-with-generated-32-byte-base64-key"
  tehowatti_ota_password: "replace-with-strong-unique-password"
  ```

  Generate the API key with `openssl rand -base64 32`. Keep the actual
  secrets outside Git. This exposes a "Temperature setback" switch to
  Home Assistant over the **local, encrypted** ESPHome API.

**Commissioning:** with the external relay disconnected, verify the
normal boiler operation. Then have a qualified installer connect the
dry contact, test OPEN = normal and CLOSED = setback on the physical
boiler display, and verify that device restart/power loss leaves the
contact open. Monitor supply temperature and restore normal mode.
The relay is only a request for the existing boiler function.

**Important safety:** the boiler is 400 V equipment. Do not connect
GPIO, 3.3 V, 5 V, 230 V, any relay-coil power, or any external voltage
to the potential-free input. Never bypass the boiler's thermostat,
over-temperature cutout, thermal protection, safety logic or contactors.
Electrical wiring/validation must be performed by a qualified person.
Do not use cloud-dependent commands as the sole frost-protection measure.

For extra temperature telemetry, use **independent external sensors**.
The dry-contact interface does *not* expose boiler temperature, current,
faults or heater stages.

## 2. Tehowatti AIR: optional local MODBUS 40

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

**Not supported:** assuming that myUpway/myUplink metric IDs are Modbus
register addresses; automatic register discovery, generic changes to
safety/operating mode, or claiming the ordinary Tehowatti electric boiler
has the AIR module interface.

## Community research

- Local ESP8266 + MQTT + relay + temperature-sensor prototype:
  https://github.com/otoivanen/esp8266-tehowatti
  (the upstream README still lists relay control functions as TODO,
  so it is reference material, **not** an upstream finished driver).
- Legacy cloud API research for AIR:
  https://github.com/lemanjo/pyupway
  (the README says the Tehowatti AIR was tested; **cloud-dependent**,
  not an Open HVAC local integration).

**Release status:** manufacturer interfaces documented, ESPHome example
and OpenLVI guarded setup provided; **no physical-device acceptance test**.
We welcome device model/year, a redacted register list, read-only Modbus
captures and feedback from a hardware tester. Do not claim plug-and-play.
