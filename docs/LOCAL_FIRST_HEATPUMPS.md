# OpenLVI Local-First HVAC and Chinese Heat Pump Research

**Experimental branch. English is the default documentation language.**
This guide describes local data paths and the separate read-only
`tools/openlvi_lab/local_hvac.py` adapter. It is NOT a finished direct
replacement for manufacturer cloud apps or a new heat-pump control driver.

## Mandatory design principle

Device -> verified local serial/Modbus/Tuya/MQTT/ESPHome/native Home
Assistant integration -> read-only OpenLVI normalization, diagnostics,
COP calculations and the digital twin.

There is no vendor-cloud call in the new Lab code. **A Home Assistant
integration can still depend on a manufacturer cloud**; using its HA
entities does not turn it into local control. A strict local profile
refuses such paths. Hardware must be tested with WAN disconnected.

Three different requirements must be assessed independently:
1. **Offline runtime:** commands and readings work without an Internet link.
2. **Offline commissioning:** onboarding, Wi-Fi provisioning and obtaining
   necessary legal tokens/keys work without a manufacturer account.
3. **Offline radio/firmware:** the device firmware itself does not depend
   on periodically reaching the manufacturer service to remain stable.

Never promise all three merely because LAN packets can be read.

## Panasonic: Comfort Cloud vs local alternatives

| Device/service | Access | Honest cloud-free assessment |
|---|---|---|
| Panasonic Comfort Cloud (`panasonic_cc`) | Vendor cloud, account and 2FA | **Cloud-dependent, explicitly blocked** in strict mode |
| Aquarea Smart Cloud | Vendor cloud | **Cloud-dependent, blocked** |
| Compatible Panasonic split heat pump | ESPHome UART via CN-CNT/CN-WLAN | Local through ESP32 on *verified* indoor unit; replaces/augments Wi-Fi module per model |
| Aquarea H/J/K/L and some supported later units | HeishaMon via CN-CNT/CN-NMODE -> local MQTT/JSON | Local; generation, board compatibility and bus-master arbitration must be checked |
| Panasonic Aquarea M series with option PCB | CZ-NSMB -> RS485 Modbus RTU | Local; requires documented M-specific PCB and point table |

Authoritative/maintained upstream:
- https://github.com/DomiStyle/esphome-panasonic-ac
- https://github.com/heishamon/HeishaMon
- https://community.home-assistant.io/t/panasonic-aquarera-m-series-local-integration/973612
- https://github.com/sockless-coding/panasonic_cc
- https://web.media.panasonic.eu/public/nordic/finland/NE-FI-AQUAREA.pdf

**Physical hazard:** CN-CNT may provide 5 V logic while ESP32 GPIOs are
3.3 V. Use the right verified isolated/level-shifted interface and
disconnect mains safely. Panasonic Comfort Cloud and Aquarea Smart Cloud
are not synonymous. The `panasonic_cc` API is a cloud **fallback**,
not the implementation of the local branch.

For your Panasonic split heat pumps, check exact indoor model/connector
before replacing Comfort Cloud. Preserving the original remote and
physical frost/defrost protection is essential.

## Chinese monobloc VILP, Mango and OEM heat pumps

OpenLVI should select a protocol by controller hardware/firmware, NOT
by generic manufacturer country or visible app branding.

| Platform | Hardware-specific path | Remaining requirements |
|---|---|---|
| Mango R290 and compatible Chinese Tuya Wi-Fi controllers | Device-local Tuya LAN protocol (existing HA Tuya Heat Pump / tuya-local) | Original legitimate local key, device IP/ID, firmware/version, model-specific datapoint table |
| OEM heat pump with open Modbus port | Isolated RS485 Modbus RTU or authenticated Modbus TCP on LAN | Exact vendor register map, 0/1-based address, scaling, signedness and safe polling |
| Tuya cloud-only product / wireless gateway that hides datapoints | No guaranteed local runtime | Obtain compatible official local interface/bridge; do not call it local |
| Midea / M-Smart compatible AC | Home Assistant Core Midea local LAN after commissioning | V3 may require a *one-time* cloud token/key. Some modules repeatedly contact the cloud even when HA uses local LAN |
| Gree-compatible split AC | Home Assistant Gree local UDP/LAN | Initial Gree+ Wi-Fi binding may need the vendor app |
| Mitsubishi Ecodan FTC | Tested local ESPHome CN105 interface | Exact indoor FTC model and bus electrical compatibility |
| Supported Daikin local BRP | Home Assistant Daikin local network | Some ONECTA models have no usable LAN API |

Sources:
- https://github.com/Korkuttum/tuya_heat_pump
- https://github.com/make-all/tuya-local
- https://www.home-assistant.io/integrations/midea
- https://www.home-assistant.io/integrations/gree
- https://github.com/gekkekoe/esphome-ecodan-hp
- https://www.home-assistant.io/integrations/daikin

Korkuttum's Tuya Heat Pump project explicitly lists **Mango** and has a
LAN mode. It also documents cloud API registration for obtaining setup
information: **local operation is not proof of cloud-free commissioning**.
Other device-local Tuya projects may have one local connection limit.
Do not compete for a device's only local connection with two integrations.

### The missing Mango register/DPS table

**This branch does not pretend to know the ~770 OEM controller
parameters.** Tuya datapoint IDs, USB/RS485 register addresses, write
limits, EVI/EEV/defrost parameters and compressor performance are
device- and firmware-specific. No automatic writes are allowed.

A proper model profile requires:
- Exact manufacturer OEM board, firmware, protocol version and local
  identity; saved legitimate keys must NOT be committed to GitHub.
- Verified read-only datapoint observations (raw ID, type, unit, scale,
  read timestamp) compared with the original controller.
- Native hardware safety boundaries: antifreeze, high pressure,
  compressor short cycling, defrost, EEV, EVI, circulation, DHW.
- Bench tests confirming every actuator write individually before
  proposing any operator-controlled command layer.

## Existing Home Assistant entities, not duplicate drivers

The read-only adapter can normalize real HA entities for outdoor,
supply/return, DHW, measured flow, electric/thermal power, compressor
frequency, refrigerant temperatures and an observed defrost state.
Unknown or unsupported units are rejected. Missing states never become
invented measurements; stale readings remain marked as stale.

It cannot assert that a sample HA sensor is local purely from its
entity_id. Check the underlying HA integration, WAN-blocked operation,
device firmware/network traffic and whether commissioning required cloud.

Run from repository root with Python 3.11+:

    python3 tools/openlvi_lab_cli.py local-hvac-path --path mango_r290_tuya_local
    python3 tools/openlvi_lab_cli.py local-heatpump-readings --input examples/openlvi-lab/local-heatpump.json

These commands **do not communicate with any hardware**.

## Zigbee: extend, do NOT duplicate the Zigbee stack

Use **one** local coordinator per Zigbee PAN, connected to ZHA **or**
Zigbee2MQTT, not both claiming the same radio. Then create manufacturer
support in ZHA quirks or Zigbee2MQTT external converters.

- ZHA: https://www.home-assistant.io/integrations/zha/
- Zigbee2MQTT: https://www.zigbee2mqtt.io/guide/usage/integrations/home_assistant.html
- Custom Zigbee2MQTT converters:
  https://www.zigbee2mqtt.io/advanced/more/external_converters.html
- ZHA manufacturer quirks:
  https://github.com/zigpy/zha-device-handlers

A Zigbee coordinator, already-paired device and unique network keys are
required; OpenLVI has **no radio stack or cloud-based pairing bypass**.
Custom converters must use exact fingerprints/firmware and validated
reporting. The OpenLVI Zigbee mesh auditor reads a manually supplied,
non-secret inventory. It does **not** clone Zigbee keys or pair devices.

For a Finnish multi-site BMS, prefer separate local collectors:
- Zigbee2MQTT / ZHA for room thermostats and indoor sensors;
- LoRaWAN UG65 + local MQTT for extended-range leak and climate sensors;
- Wireless M-Bus for compatible heat/water meters;
- Modbus/BACnet/M-Bus for plant equipment and energy meters;
- ESPHome for selected 0-10 V, pulse counters and isolated serial links.

Do not broadcast unencrypted control across public networks. TLS/auth
for cross-site MQTT; no internet-facing Modbus or BACnet.

## Proposed acceptance checklist

1. Device model and firmware recorded.
2. Real local hardware interface verified (voltage, connector, isolation).
3. Saved legitimate credentials locally, no plaintext secrets in reports.
4. WAN connection physically blocked for an extended real-device test.
5. Sensor values and units compared to equipment display.
6. Any firmware update must not silently remove LAN functionality.
7. HA remains reliable after reboots, DHCP changes and gateway outage.
8. Compressor/EEV/pump/frost and original OEM safety remain independent.
9. No automatic write action without separate manual approval.
10. Device support marked bench/site verified only after signed evidence.

This is **local-first architecture and read-only adapter code**, not
the complete hardware-tested integration for each named product.
