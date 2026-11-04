# Open-HVACBridge: Finnish building automation device and protocol catalog
**Research snapshot 2026-11-04 · English-first · experimental hardware coverage**

This is a researched selection, **not an exhaustive list** of all
controllers installed in Finland. Device names alone never imply
plug-and-play support or approved remote writes. Check exact model,
firmware, physical communications module, application keys, point
definitions and on-site commissioning records.

## Tosibox (Tosi): read-only Modbus TCP monitoring

Official register specification:
https://helpdesk.tosibox.com/serviceportal?id=kb_article_view&sysparm_article=KB0010272

Tosibox Lock 150/210/250/500 and TOSIBOX 175/350/375/610/650/670/675/695
can provide local Modbus TCP status starting at firmware 5.5.0 when explicitly
enabled. Port 502 is for the trusted local management network only. Do not
expose it publicly or treat Tosibox secure VPN access as an open interface.

Vendor numbers are **offsets from holding 40001**. Open-HVACBridge uses
one-based PDU addresses, so offset 14 becomes address 15.

| Manufacturer offset | Internal address | Reading |
|---|---|---|
| 14 / 15 | 15 / 16 | Cellular RSRP/RSSI raw, validate dBm encoding |
| 16 | 17 | Internet connection interface enum |
| 17 | 18 | Tosibox cloud connected 0/1 |
| 18 | 19 | VPN tunnel count (may include establishing tunnels) |
| 19 / 20 | 20 / 21 | Internet/VPN enabled flags, **read only** |
| 21-23 | 22-24 | Firmware version, only >=5.6.0 |

A 0xFFFF value means unavailable, not 65535.
Vendor offsets 19/20 are writable in the original device: writing could
sever network/VPN access, so Open-HVACBridge **never writes them**.
SMS sending registers 47-138 are excluded.

## Finnish underfloor heating and cooling

| Brand/model | Verified bus / system | Open-HVACBridge |
|---|---|---|
| Uponor Smatrix Base PRO X-148 | Modbus RTU RS485; FC04 input 30001 outside, 30002–30013 rooms, 30014–30025 RH; 0x7FFF missing; temperatures in 0.1 °F by default, RH in the low byte | 25-point new read-only profile |
| Uponor Smatrix Base PRO X-147 | KNX converter R-147 + I-147 controller; ETS map required | Research only |
| Uponor Smatrix Pulse R-208 | Ethernet R-208 module, unofficial community HA integration | Existing third-party, no official generic Modbus |
| Roth Touchline SL | New-generation RS485 Modbus RTU; register 23 room, 74 floor, 122 RH, 170 actuator %, 221 target, 270 battery | First-zone read-only profile |
| Roth Touchline SL WiFi | Vendor API requires approved access to its documents | Research |
| Wavin Sentio | Modbus RTU slave; TCP with CCU+panel firmware TM60014+, same register map | Research until verified register export |
| Danfoss Icon2 | Zigbee 3.0 wireless thermostats and Ally Gateway | Device-dependent ZHA/Z2M/Ally support |
| Resideo HCC100 | 868.3 MHz, OpenTherm, BLE setup, Evohome-compatible | Not LoRaWAN / not general Modbus |
| Honeywell Evohome HCC80/HCE80 | TCC cloud or model-specific RAMSES-II radio | Third-party / research; RAMSES-III differs |
| LK Systems ICS.2, OJ WLM2/WLM3, Salus, Watts | Model- and option-specific gateways | No verified common register map |

Sources:
- Uponor X-148:
  https://www.uponor.com/getmedia/bb95eecf-5c04-4114-a46b-210ac9f76309/Uponor-IM-Smatrix-Base-PRO-Modbus-RTU-X-148-EN-1090255.pdf?sitename=UponorInternational
- Uponor Smatrix engineering:
  https://www.uponor.com/fi-fi/tuotejarjestelmat/lattialammitys-viilennys/saatojarjestelma/uponor-smatrix-base-pro/uponor-smatrix-base-pro-tekniset-tiedot
- Community Pulse R-208:
  https://github.com/asev/homeassistant-uponor
- Roth official Modbus and API:
  https://www.roth-finland.fi/tekninen-tuki/modbus-ja-api-roth-touchliner-sl
- Wavin Sentio handbook:
  https://mediahub.wavin.com/m/143765f439b8a4dd/original/Sentio-Technical-Handbook-ENG.pdf
- Danfoss Icon2:
  https://www.danfoss.com/fi-fi/products/dhs/hydronic-underfloor-heating/products/danfoss-icon2-hydronic-floor-heating/danfoss-icon2-support/
- Resideo:
  https://www.resideo.com/emea/en/products/comfort/zoning-underfloor-heating/underfloor-heating/hcc100m2022-underfloor-multi-zone-controller-hcc100m2022/

**Addressing warning:** Uponor's documented register 30001 means first
FC04 input at PDU address 0; Open-HVACBridge represents it as input
address 1, not 30001. Roth's manual uses direct one-based holding
register numbers (e.g. 23 -> PDU 22). Never enable a write just
because the vendor labels a point R/W.

**Uponor temperature unit:** the X-148 sends temperatures as tenths of a
degree **Fahrenheit** by default (manual: 21.0 °C is sent as 698). The
built-in profile therefore declares °F and Home Assistant converts to
°C. If the site's U_BMS file was switched to Celsius, use a custom
read-only profile with `"unit": "°C"` instead. Relative humidity is
in the low byte; the profile masks the high byte (`"mask": 255`).

## Siemens and Honeywell building controllers

- Siemens Desigo PXC4/PXC5/PXC7: BACnet/IP, BACnet/SC, model-dependent
  MS/TP and Modbus plus KNX PL-Link. Site-configured BACnet objects.
  https://sid.siemens.com/r/A6V12027144/13182215947_25410647179__en-US_13182050571
- Siemens DXR2/PXC3, Climatix POL6xx, Synco/OZW672: require
  actual OEM application, communication hardware and export.
- Honeywell/CentraLine EAGLEHAWK NX: Niagara NX/BACnet; site-assigned
  object IDs, no universal numeric register list.
  https://buildings.honeywell.com/gb/en/brands/our-brands/centraline/products/eaglehawk
- Honeywell Optimizer VAV: BACnet IP/MS/TP/T1L variants, Modbus RTU;
  flow, damper and pressure points depend on the commissioned system.
  https://buildings.honeywell.com/dk/en/products/by-category/building-management/controllers/zone-and-unitary-controllers/honeywell-optimizer-vav-controller

BACnet/SC is certificate/hub based; it cannot be polled with a
plain BACnet/IP adapter. Existing Open-HVACBridge BACnet support
reads only configured/private-network objects.

## Ouman devices and related gateways

Official downloads:
https://ouman.fi/downloads/
Official Modbus topology/port manual:
https://ouman.fi/wp-content/uploads/2025/09/YM0105_Modbus-guide_FIN.pdf
WL-BASE:
https://kauppa.ouman.fi/tuote/wl-base-2-1-fin/

- Existing narrow profiles: EH-800/EH-800B, A203, S203, C203, H23.
- Research: H21, S105, EC-104 (including fan CO2/VOC input),
  EH-203/EH-105/EH-686 and RU23.
- Ouflex / Ouflex A, A XL, AX, M, M BA and C: freely programmable,
  site-specific application/export required, NOT one fixed map.
- WL-BASE 2.1 and WL-TEMP-RH-CO2/VOC: wireless sensor base station
  with Modbus RTU/TCP; it is **not automatically a LoRaWAN gateway**.
- Oulink ETH, M-LINK, ADF Web, ACCESS, MODBUS-100/200/600 adapters,
  FLEX UI8/AO8/DO4: each has own interface and sometimes master-only
  Modbus ports; verify the exact documented connection role.

No dangerous PID, manual valve, frost, pump, ventilation stop or
alarm override outputs are added.

## Further Finnish-market integration targets (not yet verified)

Ventilation: Swegon, Vallox, Enervent, Koja, FläktGroup, Systemair,
Halton, Lindab, Climecon, Blauberg.
Heat sources: Oilon, Gebwell, Jäspi, NIBE, Thermia, Bosch, Panasonic,
Mitsubishi Electric, Daikin, CTC, Viessmann, Danfoss.
Automation: Fidelix, Schneider Electric, Regin, Produal, Belimo,
ABB, WAGO, Beckhoff, Siemens, Honeywell, Ouman.
Meters: Kamstrup, Elvaco, Landis+Gyr, Aidon, Diehl, Sensus, Shelly,
Carlo Gavazzi, Janitza.
Networks: Modbus, BACnet, KNX, wired/wireless M-Bus, Zigbee,
Z-Wave, BLE, LoRaWAN, EnOcean, DALI, eBUS, EMS, LON, 0-10 V,
4-20 mA, IEC 62056 optical.

## Useful BMS software features

Point freshness and calibration status; alarm logs and 24/7 escalation;
valve and pump response observation; water/district heat measurements;
CO2 ventilation and humidity trends; COP and refrigerant cycle estimates;
device runtime and firmware audit; leak/flood alarms; manual approval
and change history; local-first SCADA dashboards.

Refer to THERMAL_AND_REFRIGERANT_COP.md for calculators and the
CO2 supplemental fan automation blueprint. Hardware verification is
still required before production operation.
