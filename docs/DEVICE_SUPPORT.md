# OpenLVI Bridge device support

**Status 2026-11-11.** The setup wizard lists only devices that OpenLVI can
reach locally through its transports: Modbus TCP/RTU, BACnet/IP, wired M-Bus
and the Ouman EH-800 HTTP / EH-800B USB drivers. Devices without such a
route were removed from the wizard; [section 3](#3-removed-from-the-setup-wizard)
lists them with the integration to use instead.

All OpenLVI drivers are experimental. Unless stated otherwise, support is
checked against manufacturer documentation and automated tests only, not on
physical hardware. Exact model, firmware, communication module and
commissioning records always decide what is actually available.

## 1. Built-in support (✓ in the setup wizard)

A built-in driver or read-only point map exists for the documented firmware.
Most maps are small, conservative subsets of the manufacturer documentation.

| Device | Interface | Requirement / scope |
|---|---|---|
| Ouman EH-800 | Local HTTP (`ouman-eh-800-api` 2.0.0) | Home Assistant's official [Ouman EH-800 integration](https://www.home-assistant.io/integrations/ouman_eh_800/) is the recommended route |
| Ouman EH-800B | USB | 28 measurements and 11 guarded L1 setpoints; legacy v0.1.2 tested on one unit |
| Ouman A203, S203, C203, H23 | Modbus RTU/TCP | Exact firmware 2.0.2 (A203), 3.0.10 (S203, C203) or 4.0.5 (H23) |
| Danfoss ECL Comfort 210/296/310/310B | Modbus | Sensor S2; circuit 1 comfort target only with application A266.1 |
| Swegon CASA Genius | Modbus (SEM/SEC) | Firmware 4.x |
| Regin Corrigo E Ventilation | Modbus | Firmware 3.2 |
| Uponor Smatrix Base PRO X-148 | Modbus RTU | 25 input registers |
| Roth Touchline SL | Modbus RTU | First zone only |
| Tosibox 175, 350, 375, Lock 500, 610, 650, 670, 675, 695 | Modbus TCP | Firmware 5.5.0 or later with local Modbus enabled |
| Kamstrup MULTICAL 403/603/803 | Wired M-Bus | Powered M-Bus master with a serial interface |

## 2. Possible with your own register map or BACnet/IP discovery

These devices have a documented local Modbus or BACnet/IP interface, but
OpenLVI has no built-in map for them. Supply a verified read-only register
map (Modbus) or use read-only object discovery on one BACnet/IP device (up to
32 objects). Many need an optional communication module, licence or gateway.

| Device | Local route | Register / object list |
|---|---|---|
| Ouman Ouflex, Ouflex A / A XL / AX, M / M BA, C | Modbus RTU/TCP | Freely programmable; site map from OuflexTool or the integrator |
| Ouman H21 | Modbus via M-LINK | [H21 data sheet][ouman-h21], [M-LINK manual][ouman-mlink] |
| Ouman S105 | Modbus RTU | [Ouman documentation][ouman-pricelist] |
| Ouman EH-203, EH-105 | Modbus RTU via MODBUS-100/200 adapter (card or DIN) or M-LINK | [EH-203 manual][ouman-eh203], [EH-net instructions][ouman-ehnet] |
| Ouman EH-686 | Modbus RTU via MODBUS-600 DIN adapter | [EH-net instructions][ouman-ehnet] |
| Ouman EC-104 | Modbus | [EC-104 documentation][ouman-ec104] |
| Ouman WL-BASE 2.1 | Modbus RTU/TCP | Register list exported from the base station ([manual][ouman-wlbase]) |
| Danfoss ECL 120/220 | Modbus | Danfoss ECL 120/220 Modbus description; [community integration][ecl-120] |
| Danfoss MCX | Modbus RTU on RS485 variants | Application-specific MCXShape export; see [Danfoss MCX](DANFOSS_MCX.md) |
| Regin Corrigo 5 | Modbus | [Corrigo 5.0 variable list][regin-corrigo5] |
| Regin Exigo | Modbus | [Exigo 4.3 variable list][regin-exigo] |
| Swegon CASA Smart | Modbus | [CASA Smart register list][swegon-smart] |
| Swegon GOLD | Modbus | [GOLD Modbus document][swegon-gold] |
| Enervent eAir, eWind | Modbus RTU/TCP | Enervent register list; [community Modbus bridge][enervent-eda] |
| Vallox MyVallox | Modbus RTU | [Vallox Modbus manual][vallox-modbus], [example map](../examples/modbus-myvallox-readonly.json). Home Assistant's [Vallox integration](https://www.home-assistant.io/integrations/vallox/) is a local alternative |
| Fidelix FX2030, FX3000 | BACnet/IP; Modbus TCP server after activation | Site-specific ([Fidelix FX3000][fidelix]) |
| Siemens Climatix POL6xx | Modbus or BACnet with a POL908/909 module | OEM application export |
| Siemens Desigo PXC4 / PXC5 / PXC7 (incl. E16, E24, E400) | BACnet/IP | Site-configured objects ([Desigo PXC][siemens-pxc]) |
| Siemens Desigo DXR2 | BACnet/IP (.E models) | Site-configured objects |
| Honeywell / CentraLine EAGLEHAWK NX, EAGLEHAWK, EAGLE Controller | BACnet/IP | Site-assigned objects ([EAGLEHAWK][honeywell-eaglehawk]) |
| Honeywell Optimizer VAV | BACnet/IP or Modbus RTU variant | Commissioned system ([Optimizer VAV][honeywell-vav]) |
| Schneider Electric SpaceLogic MP-C | BACnet/IP | Programmable; site objects |
| Produal Proxima | Modbus | Register lists in Produal data sheets |
| Jäspi Tehowatti AIR | Modbus RTU via MODBUS 40 | See [Jäspi Tehowatti AIR](JASPI_TEHOWATTI.md) |
| Wavin Sentio | Modbus RTU; Modbus TCP with CCU firmware TM60014+ | [Sentio Modbus manual][wavin-sentio] |
| LK Systems ICS.2 | Modbus RTU | Protocol from LK Systems on request; [community setup notes][lk-ics2] |
| Grundfos MAGNA3 with CIM 500, CIM 500 / CIU 500 | Modbus TCP or BACnet/IP | [Grundfos CIM literature][grundfos-cim] |
| Wilo Stratos MAXO, Stratos GIGA | Modbus RTU/TCP via CIF module (older Stratos GIGA: IF module) | [Wilo data point lists][wilo-modbus] |
| Belimo Modbus actuators and VAV controllers | Modbus RTU | [Belimo Modbus register list][belimo-modbus] |

## 3. Removed from the setup wizard

These devices have no Modbus TCP/RTU, BACnet/IP or M-Bus route that OpenLVI
can use, have no public interface documentation, or are accessories rather
than controllers. Existing configuration entries are not changed.

| Device | Why not OpenLVI | Alternative |
|---|---|---|
| Danfoss Icon2 | Zigbee | [ZHA or Zigbee2MQTT][danfoss-icon2] |
| Danfoss Ally Gateway | Zigbee gateway with a cloud API | [Community Danfoss Ally integration][danfoss-ally] (cloud) |
| Resideo / Honeywell Evohome, HCC100, HCC80, HCE80 | RAMSES-II radio | [ramses_cc][ramses-cc] with an RF dongle (local), or Home Assistant's [Evohome integration](https://www.home-assistant.io/integrations/evohome/) (cloud) |
| SALUS Smart Home UG600 | Own encrypted local gateway API | [Salus iT600 client and community integration][salus] |
| Roth Touchline SL WiFi | Cloud API | Home Assistant's [Roth Touchline SL integration](https://www.home-assistant.io/integrations/touchline_sl/) (cloud) |
| Uponor Smatrix Base PRO X-147 KNX | KNX through the R-147 converter | Home Assistant's [KNX integration](https://www.home-assistant.io/integrations/knx/) |
| Uponor Smatrix Pulse R-208 | Own local HTTP API | [Community Uponor integration][uponor-pulse] |
| Siemens Synco RMU7xx | KNX | Home Assistant's [KNX integration](https://www.home-assistant.io/integrations/knx/) |
| Siemens Synco OZW672 | HTTP web API; would need its own driver | None verified |
| NIBE S-series | Already supported locally elsewhere | Home Assistant's [NIBE Heat Pump integration](https://www.home-assistant.io/integrations/nibe_heatpump/) (Modbus TCP) |
| Belimo BACnet actuators | BACnet MS/TP; OpenLVI reads BACnet/IP devices only | Belimo Modbus variant |
| Koja KojaControl | No public interface documentation found | None verified |
| OJ Electronics WLM2, WLM3 | No public register list found | None verified |
| Ouman Oulink ETH, M-LINK | Adapters, not controllers | Select the controller behind the adapter |
| Ouman RU23, FLEX I/O | Display unit and I/O module of an Ouflex system | Select the Ouflex controller |
| Jäspi Tehowatti electric boiler | Only a potential-free setback input; no data interface ([manual][jaspi-boiler]) | The ESPHome relay example was removed |
| Roth Touchline PL | Only a heat-source relay output; no data interface ([product page][roth-pl]) | The ESPHome monitor example was removed |
| DEVIreg 330 | Thermostat with an external setback input only ([product page][devireg-330]) | The price setback blueprint was removed |

## Notes on built-in maps

### Tosibox: read-only Modbus TCP status

[Official register specification][tosibox].
Tosibox devices with firmware 5.5.0 or later can provide local Modbus TCP
status when explicitly enabled. Port 502 is for the trusted local management
network only. Do not expose it publicly or treat Tosibox secure VPN access as
an open interface.

Vendor numbers are **offsets from holding 40001**. OpenLVI uses one-based PDU
addresses, so offset 14 becomes address 15.

| Manufacturer offset | Internal address | Reading |
|---|---|---|
| 14 / 15 | 15 / 16 | Cellular RSRP/RSSI raw, validate dBm encoding |
| 16 | 17 | Internet connection interface enum |
| 17 | 18 | Tosibox cloud connected 0/1 |
| 18 | 19 | VPN tunnel count (may include establishing tunnels) |
| 19 / 20 | 20 / 21 | Internet/VPN enabled flags, **read only** |
| 21-23 | 22-24 | Firmware version, only >=5.6.0 |

A 0xFFFF value means unavailable, not 65535. Vendor offsets 19/20 are
writable in the original device: writing could sever network/VPN access, so
OpenLVI **never writes them**. SMS sending registers 47-138 are excluded.

### Address conventions

Uponor's documented register 30001 ([X-148 manual][uponor-x148]) means the
first FC04 input at PDU address 0; OpenLVI represents it as input address 1,
not 30001. Roth's [Touchline SL Modbus documentation][roth-sl] uses direct
one-based holding register numbers (e.g. 23 -> PDU 22). Never enable a write
just because the vendor labels a point R/W.

### Ouman adapters and BACnet limits

- MODBUS-100/200/600 adapters and M-LINK connect older Ouman controllers to
  Modbus. Some adapter ports are master-only: verify the documented
  connection role ([Ouman Modbus guide][ouman-modbus]).
- WL-BASE 2.1 is a wireless sensor base station with Modbus RTU/TCP; it is
  **not** a LoRaWAN gateway.
- BACnet/SC is certificate/hub based and cannot be polled with a plain
  BACnet/IP client. OpenLVI addresses one BACnet/IP device directly, so
  devices behind a BACnet MS/TP router are not reachable.

[ouman-h21]: https://kauppa.ouman.fi/wp-content/uploads/2024/05/H21_DATA_SHEET_FI_H21_HEATING_CONTROLLER.pdf
[ouman-mlink]: https://ouman.fi/wp-content/uploads/2019/01/YM0010.01_M-Link_User-manual_ENG_v.2.6.pdf
[ouman-pricelist]: https://ouman.fi/wp-content/uploads/Price-list_2026_v5_LQ.pdf
[ouman-eh203]: https://ouman.fi/documentbank/EH-203__manual__fi.pdf
[ouman-ehnet]: https://ouman.fi/documentbank/EH-net__deployment_instructions__en.pdf
[ouman-ec104]: https://kauppa.ouman.fi/wp-content/uploads/2026/04/Ouman-EC-104-puhallinohjauskeskus.pdf
[ouman-wlbase]: https://kauppa.ouman.fi/wp-content/uploads/2022/06/YM0022B-N-00.pdf
[ouman-modbus]: https://ouman.fi/wp-content/uploads/2025/09/YM0105_Modbus-guide_FIN.pdf
[ecl-120]: https://github.com/nichlasrohde/ha-ecl-modbus
[regin-corrigo5]: https://www.regincontrols.com/globalassets/pimmediafiles/documents/corrigo-5_0_vl40006_en.pdf
[regin-exigo]: https://www.regincontrols.com/globalassets/pimmediafiles/documents/exigo_4.3_vl40001_en.pdf
[swegon-smart]: https://serviceportal.swegon.com/fi//docs/smartmodbusregisterfull
[swegon-gold]: https://www.swegon.com/globalassets/digizuite/9313-en-gold_e_modbus_other_en.pdf
[enervent-eda]: https://github.com/Jalle19/eda-modbus-bridge
[vallox-modbus]: https://res.cloudinary.com/vallox/image/upload/v1683801768/FileStock/AllManuals/Manual_Modbus_ENG_Colour_20150925.pdf
[fidelix]: https://support.fidelix.com/en/knowledge/fx3000c
[siemens-pxc]: https://sid.siemens.com/r/A6V12027144/13182215947_25410647179__en-US_13182050571
[honeywell-eaglehawk]: https://buildings.honeywell.com/gb/en/brands/our-brands/centraline/products/eaglehawk
[honeywell-vav]: https://buildings.honeywell.com/dk/en/products/by-category/building-management/controllers/zone-and-unitary-controllers/honeywell-optimizer-vav-controller
[wavin-sentio]: https://mediahub.wavin.com/asset/efc42c92-8116-425c-a4ba-d9d27c0b6c38/Sentio-Modbus-Manual-EN.pdf
[lk-ics2]: https://github.com/astrandb/lk-systems-floor
[grundfos-cim]: https://api.grundfos.com/literature/Grundfosliterature-6154248.pdf
[wilo-modbus]: https://wilo.com/gb/en/Digital-Energy/Building-automation/Data-points-and-data-point-list/Modbus/
[belimo-modbus]: https://www.belimo.com/mam/general-documents/system_integration/Modbus/belimo_Modbus-Register_AirWater_V3_8_en-gb.pdf
[danfoss-icon2]: https://community.home-assistant.io/t/zigbee-integration-of-danfoss-icon2-main-controller/675000
[danfoss-ally]: https://github.com/MTrab/danfoss_ally
[ramses-cc]: https://github.com/ramses-rf/ramses_cc
[salus]: https://pypi.org/project/salus-it600-client/
[uponor-pulse]: https://github.com/asev/homeassistant-uponor
[jaspi-boiler]: https://jaspi.fi/wp-content/uploads/2016/05/Tehowatti_manual_r3_1114.pdf
[roth-pl]: https://www.roth-finland.fi/tuotteet/lattialammon-ohjausjarjestelmat/roth-touchline-pl
[devireg-330]: https://devi.com/en/products/thermostats/outdoor-applications/devireg-330
[tosibox]: https://helpdesk.tosibox.com/serviceportal?id=kb_article_view&sysparm_article=KB0010272
[uponor-x148]: https://www.uponor.com/getmedia/bb95eecf-5c04-4114-a46b-210ac9f76309/Uponor-IM-Smatrix-Base-PRO-Modbus-RTU-X-148-EN-1090255.pdf?sitename=UponorInternational
[roth-sl]: https://www.roth-finland.fi/tekninen-tuki/modbus-ja-api-roth-touchliner-sl
