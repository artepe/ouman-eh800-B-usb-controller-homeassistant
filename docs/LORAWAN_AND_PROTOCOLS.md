# OpenLVI LoRaWAN, MQTT and additional building-network research

**Status 2026-11-04:** research, a standalone offline JSON inspector and
test fixtures are included. There is **no live LoRaWAN transport inside
the OpenLVI configuration wizard yet**, no automatic discovery of a
gateway, no radio receive hardware and no downlink/control commands.

## Preferred local path: Milesight UG65 -> existing MQTT -> Home Assistant

Manufacturer guide:
https://support.milesight-iot.com/support/solutions/articles/73000514193-how-to-connect-lorawan-gateway-to-mqtt-broker-

With UG65's **embedded LoRaWAN network server**:

1. Leave the gateway's network server and device registrations intact.
2. Under Network Server > Applications, configure a MQTT data-transmission
   integration for the application.
3. Use the Home Assistant Mosquitto broker's *real reachable LAN address*
   and its configured authentication/TLS. Do not use Nabu Casa's remote
   Home Assistant URL as an MQTT endpoint.
4. Configure an uplink topic with the Milesight substitution token:
   /milesight/uplink/$deveui (the path is operator-selected).
5. In Home Assistant MQTT settings, **Listen to a topic**:
   /milesight/uplink/# (use your actual configured topic).
6. Inspect one JSON uplink for devEUI, fPort, fCnt, rxInfo, data.
   The manufacturer's example data field is base64 of **decrypted
   application payload**, not a decoded temperature/leak measurement.
7. Activate the gateway's payload codec for the exact device model if
   supported; use only verified decoded field names for MQTT sensors.
8. Add retained MQTT discovery messages for confirmed sensors and
   availability/birth messages, or rely on Home Assistant's native
   MQTT entities to avoid creating duplicate OpenLVI devices.

The user's existing three leak sensors must keep their current DevEUIs,
device identifiers and associations. Do not reset/replace their
LoRaWAN AppKeys or overwrite join session state as part of integration.

## Network-server alternatives

| Backend | MQTT uplink topic | Common JSON shape |
|---|---|---|
| Milesight UG65 Embedded NS | User-selected /milesight/uplink/$deveui | devEUI, data(base64), fPort, fCnt, rxInfo |
| ChirpStack v4 | application/APPLICATION_ID/device/DEV_EUI/event/up | deviceInfo.devEui, data(base64), fPort, object (if codec) |
| The Things Stack v3 | v3/APP_ID@TENANT/devices/DEVICE_ID/up | end_device_ids, uplink_message.frm_payload, decoded_payload |

Official sources:
- https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html
- https://www.chirpstack.io/docs/chirpstack/integrations/events.html
- https://www.thethingsindustries.com/docs/integrations/other-integrations/mqtt/
- https://www.chirpstack.io/docs/gateway-configuration/milesight.html

ChirpStack MQTT Forwarder for UG65/UG67 requires firmware **60.0.0.43+
when using that configuration mode**. The alternative UDP Semtech
packet forwarder does not provide encrypted transport by itself and
should not be exposed to the internet.

## Already implemented offline inspector

From the repository root:

    python3 tools/lorawan_uplink_inspect.py examples/lorawan/milesight-ug65-uplink.example.json
    python3 tools/lorawan_uplink_inspect.py examples/lorawan/chirpstack-v4-uplink.example.json
    python3 tools/lorawan_uplink_inspect.py examples/lorawan/tts-v3-uplink.example.json

Or pipe a **single JSON payload** to stdin. No third-party Python package,
HA connection or MQTT credentials are required. Results are normalized
to format, DevEUI, FPort, frame counter, RSSI, SNR, raw hex payload and
any already-decoded simple fields.

**The tool deliberately does not decode device-specific binary frames.**
A water-leak bit, temperature or battery value must be validated using
the precise manufacturer's codec and firmware before creating a sensor.
It does not send LoRaWAN downlinks or gateway configuration.

## Further communication transports worth supporting

| Network / bus | Required hardware and integration | Recommended OpenLVI boundary |
|---|---|---|
| LoRaWAN EU868 | Existing UG65 or other gateway + network server + MQTT | Decode app-server uplinks only, no downlinks by default |
| Wired M-Bus EN 13757-2/3 | Powered active M-Bus master (OpenLVI already has an experimental read adapter) | Read metering records with units |
| Wireless M-Bus / OMS | Compatible 868 MHz wM-Bus radio, decoder such as wmbusmeters, licensed keys where needed | Read decoded heat/water meter data via MQTT |
| Z-Wave EU868 | Z-Wave radio controller + Z-Wave JS | Use Home Assistant entities (NorthQ is not LoRaWAN) |
| Zigbee | Compatible coordinator + ZHA or Zigbee2MQTT | Reuse native entities, avoid duplicate radio stacks |
| Matter/Thread | Matter controller + Thread border router when needed | Reuse native HA Matter entities |
| BLE | Bluetooth adapter/proxy compatible with device's GATT protocol | Prefer existing HA integrations |
| KNX/IP | KNX/IP gateway/router and ETS project for group addresses | Reuse native HA KNX integration; separate approval for writes |
| BACnet MS/TP | Actual RS-485 BACnet MS/TP adapter/router | Proposed adapter; existing OpenLVI supports targeted BACnet/IP |
| DALI-2 | DALI controller/gateway, e.g. DALI -> KNX/IP / Modbus | Read gateway mapped endpoints |
| EnOcean | Supported 868 MHz transceiver + telegram decoder | Read existing Home Assistant entities |
| eBUS | Isolated bus interface + ebusd | Use ebusd MQTT Discovery, no blind bus writes |
| EMS/EMS2 | Properly isolated EMS-ESP bridge | Use EMS-ESP MQTT integration |
| RS-485 Modbus RTU | Isolated serial gateway / serial interface | Existing OpenLVI driver; unit ID, parity, register map required |
| Modbus TCP | IP-accessible controller/gateway, private LAN | Existing OpenLVI driver; no public internet exposure |
| 0–10 V / 4–20 mA | Calibrated ADC/DAC via gateway | Analog signal, **not a radio protocol** |
| Pulse / IEC 62056 optical | Suitable optocoupler head or protocol reader | Verify pulse LED vs IEC 62056-21 serial optical port |
| LoRa raw P2P | Explicit raw-LoRa transmitter and matching software | Not interoperable with LoRaWAN network server by default |

Other source references:
- https://www.home-assistant.io/integrations/mqtt
- https://www.home-assistant.io/integrations/knx/
- https://www.home-assistant.io/integrations/zha
- https://www.home-assistant.io/integrations/thread
- https://www.home-assistant.io/integrations/matter/
- https://github.com/wmbusmeters/wmbusmeters
- https://github.com/john30/ebusd
- https://github.com/emsesp/EMS-ESP32

## Architecture recommendation

No universal direct-radio scanner. Prefer dedicated protocol collectors:

    device -> correct radio/bus interface -> verified decoder
           -> MQTT / Home Assistant integration
           -> OpenLVI read-only analytics and SCADA

Attach a hardware- and firmware-qualified point profile with:
- exact source URL and publication/revision date;
- physical port, region/frequency, network server and topic;
- unique source identity (DevEUI or stable bus address);
- signedness, scaling, offset, units and sentinel values;
- explicit read/write/unsafe classification, model/firmware match;
- static tests plus a physical acceptance report before any control.

Safety: keep Modbus, BACnet, unencrypted MQTT and LoRaWAN gateways inside
trusted networks; use authenticated brokers and TLS over untrusted links.
Never store AppKeys or tenant/plant credentials in GitHub.
