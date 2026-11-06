# Siemens RVD120 / RVD140 — OpenLVI Bridge (read-only)

**Experimental, no physical-controller validation yet.** This profile uses
Siemens *Basic Documentation P2510*, edition 2.0, controller series A/C,
CE1P2510en (2018-04-30), chapter 20.5.6 (Modbus data point table).

Manufacturer document:
https://sid.siemens.com/api/khub/documents/K2sQQXzf6QS87HzaOTu9xQ/content

## Connection

- RS-485 **Modbus RTU** slave, not built-in Ethernet. Use an isolated
  RS-485-to-USB interface in Home Assistant, or a private-network RTU-to-TCP
  gateway (do not expose it to the public Internet).
- Configure controller operating line **171**: unit number 1–247,
  **172**: parity (0 even, 1 odd, 2 none), **173**: baud
  (0 1200, 1 2400, 2 4800, 3 9600, 4 19200).
- Siemens specifies 8 data bits, 1 stop bit. Typical initial setup is
  **9600 baud, even parity**, but match the real panel configuration.
- Siemens specifies **150 ohm, 0.5 W** termination at the first and last
  device on the physical bus. Check proper RS-485 wiring/isolation.

In Home Assistant: install OpenLVI Bridge, choose **Siemens** and
**RVD120** or **RVD140**, Modbus RTU, the serial device, matching baud,
parity and slave address. The interface may also connect through an
RTU-to-TCP gateway selected as Modbus TCP.

**No settings are written**, even when a user previously enabled
OpenLVI's general write option. This device profile does not create
editable Number controls.

## Registers and scaling

Siemens P2510 calls each address a **Modbus address**, not a 4xxxx
reference. Its decimal 1044 is hex 0x0414, the zero-based **wire offset**
to supply in a Modbus FC03 request. OpenLVI's existing driver sends
point.address - 1, so the stored profile address is **1045**.

| P2510 wire address | Meaning | Scaling |
|---|---|---|
| 1019 | Modbus object version | signed raw / 10 |
| 1020 | Controller software version | signed raw / 10 |
| 1021 | Controller model identity | 140=RVD120, 142=RVD140 |
| 1022 | Plant type | integer |
| 1031 | Current fault code | integer |
| 1032 | Active limitation code | integer |
| 1036 | Heating-circuit pump Q1 energised | 0/1 |
| 1044 | Outdoor temperature B9 | signed raw / 64 °C |
| 1045 | Flow temperature B1 | signed raw / 64 °C |
| 1046 | DHW / tank temperature B3 | signed raw / 64 °C |
| 1047 | Room temperature A6 | signed raw / 64 °C |
| 1048 | Primary return temperature B7 | signed raw / 64 °C |
| 1052 | Secondary pressure U1 (RVD140 profile) | signed raw / 50 bar |
| 1053 | Primary pressure U2 (RVD140 profile) | signed raw / 50 bar |
| 1057 | Room setpoint | signed raw / 64 °C |
| 1058 | DHW setpoint | signed raw / 64 °C |
| 1064 | Resulting flow temperature target | signed raw / 64 °C |
| 1066 | Heating-circuit temperature target | signed raw / 64 °C |
| 1068 | Resulting DHW temperature target | signed raw / 64 °C |

The included profile also reads a documented subset of other relay,
outside-temperature and RVD140 sensor registers. Hardware configuration
and selected plant type determine which points respond. Failure of an
optional point does not invalidate all other measurements.

All reads use **FC03 holding registers**, **signed 16-bit**.
On connection, the driver checks document register **1021** and rejects
unknown/mismatched model identities. This guards against accidentally
polling the wrong device or applying an incorrect address base.

## Verification before use

1. Verify the 1021 model code and correct Modbus slave address.
2. Compare outdoor temperature, flow and return against the controller LCD.
3. Confirm pump contact and fault code against the physical equipment.
4. Leave the physical RVD controller in charge of all frost, pressure,
   overheat, heating and DHW protection.
5. Report model, series, firmware, plant type, gateway/adapter and
   redacted Modbus logs when contributing a hardware test.

**Limitations:** no hardware tests in this change; RVD120 supports fewer
plant types than RVD140. Do not assume every sensor exists. No
write/setpoint controls are implemented although Siemens documents
certain FC06/FC16 operations. Modbus requests remain local and should
never be directly Internet-facing.
