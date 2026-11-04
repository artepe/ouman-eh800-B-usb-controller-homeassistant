# OpenHVAC manufacturer register and control research (2026-11-04)

This is a **source-backed engineering backlog**, not a claim of working hardware.
The sources are published manufacturer manuals or upstream protocol docs.
Copying addresses across firmware, applications, protocol media, or Modbus
addressing conventions without verification is unsafe. No new device writes
are implemented by this research.

## Direct manufacturer register findings

### 1. NIBE S1155 / S1255 / S1156 / S1256

Source: NIBE official S-Series Modbus technical information:
https://www.nibe.eu/download/18.42a6470a1963dded290bb1/1746538843623/Technical%20information%20Modbus%20S-Series.pdf

- On compatible systems, enable Modbus TCP in menu 7.5.9; local port 502;
  manufacturer's guide states software 2.2.1 or later, max 100 registers/s
  and 20 registers/request. Restrict allowed client IPs.
- Official FC04 (input) **register IDs**: 1 outdoor BT1, 5 supply BT2,
  7 return BT3, 8 DHW top BT7, 9 DHW charging BT6,
  10/11 brine in/out BT10/BT11, 12 supply line BT12, 13 discharge BT14,
  14 liquid BT15, 16 suction BT17, 26 room BT50, 39 external supply BT25.
  Temperatures: signed 16-bit, divide by 10.
- Additional FC04 IDs: 1046 compressor frequency, unsigned 16-bit
  /10 Hz; 1102 heating circulation pump speed %, 1104 source/brine pump
  speed %; 2196 reversing-valve indication.
- Manufacturer also lists FC03 writable registers. **Do not enable writes
  automatically**: mode and manual pump registers can affect real equipment.
- **Missing:** a dedicated NIBE model/firmware-specific driver and safe
  addressing test. Current OpenHVAC generic driver subtracts one from
  configured 1-based addresses; verify the manufacturer ID-to-PDU offset
  on actual equipment before using this data in a live configuration.
- The S-series can export installed-register CSV from menu 7.5.9; use
  that model-specific export, not a universal guess.

### 2. Vallox MyVallox (MyVallox Control document D5269)

Manufacturer's Modbus RTU register list:
https://res.cloudinary.com/vallox/image/upload/v1683801768/FileStock/AllManuals/Manual_Modbus_ENG_Colour_20150925.pdf
Official FAQ linking it:
https://www.vallox.com/en/support-and-instructions/frequently-asked-questions/

- **Modbus RTU / RS-485**, not native Modbus TCP from the MyVallox
  Control interface. All listed registers are **holding (FC03)**,
  unsigned 16-bit. RTU: selectable 9600–115200, parity and stop bits.
- Read-only examples: 4353 fan %, 4354 extract air temperature,
  4355 exhaust, 4356 outdoor, 4357 post-heat-recovery supply,
  4358 final supply, 4361 extract fan RPM, 4362 supply fan RPM,
  4363 relative humidity %, 4364 CO2 ppm, 4616 heat exchanger state,
  4621 unit fault condition.
- Temperature data is **centikelvin**:
  temperature °C = raw / 100 - 273.15, not raw / 10.
- Documented controls (reference only): 4609 basic Home/Away mode,
  4612 Boost timer, 4613 Fireplace timer, 4614 custom timer,
  4610 operating override/off. These are **NOT enabled** in OpenHVAC;
  a mistaken write can interrupt ventilation.
- **New in this research:** the generic read-only profile accepts a finite
  engineering-unit 'offset' and an experimental example is provided at
  examples/modbus-myvallox-readonly.json. Hardware/offset verification
  required. All imported points remain read-only.

### 3. Swegon CASA Genius, SEM/SEC interface, SW4.0+

Manufacturer SCB4.3 register list, revised 2025-09-10:
https://www.swegon.com/globalassets/digizuite/18172-en-casa_modbusregisters_en.pdf

- Existing OpenHVAC profile: selected 3x6301/6303/6304/6305/6306,
  3x6320, 3x6348, 3x6370, 4x5001, 4x5009 and 4x5114/5115.
- Additional **documented register candidates**:
  - 4x5102 boost timer (0 continuous; 1=30min, 2=60min, etc.).
  - 4x5116 CO2 boost threshold ppm.
  - 4x5010 humidity automation selection.
  - 4x5101 supply-air temperature target (/10 °C).
  - 4x5168 summer temperature target (/10 °C), SW4.0+.
  - 3x6129 service info, 3x6132 active alarms,
    3x6343 hours until next service.
  - 3x6136 active-alarm bitmask (requires documented bit interpretation).
- **Do not expose** 4x5018 emergency stop/overpressure, alarm reset
  4x5401–5408 or commissioning mode 4x5029 as generic writes.
- Operating mode 4x5001 also documents 0 Shutdown, 4 Travelling and
  5 Home+; current OpenHVAC deliberately allows only 1 Away, 2 Home,
  3 Boost as test-bounded writes. Do NOT widen without physical tests.
- Firmware-dependent values and Celsius/Fahrenheit variants need
  exact SW version and SEM/SEC hardware confirmation.

### 4. Danfoss ECL Comfort 210 / 296 / 310

Manufacturer ECL communication description:
https://assets.danfoss.com/documents/198690/AQ074886472234en-010601.pdf
Manufacturer ECL Comfort data sheet:
https://assets.danfoss.com/documents/latest/550090/AI155886469487en-010802.pdf

- ECL Modbus PNU interface can expose S1–S10 temperatures, heating
  curve, room setpoints, schedules, alarms, M-Bus energy meter readings
  and modes. Data may be application-key- and circuit-specific.
- Existing OpenHVAC uses generic sensor S2 PNU 10202 (/100) and
  A266.1 circuit-1 comfort target PNU 11180 (/10).
- More documented candidates (application-specific): 11174 motor
  protection, 11175 heating curve, 11176 shift, 11177 supply min,
  11178 supply max, 11179 summer cutoff, 11181 reduced room target.
- ECL 210 supports serial Modbus and Modbus-over-USB for service;
  296/310 also offer Ethernet Modbus TCP and M-Bus meter support.
- **Do not implement setpoint writes** on general ECL PNU IDs until
  the ECL application key and readback semantics are verified.

### 5. Regin Corrigo E 3.2 vs Corrigo 5.0

Official Corrigo 5 register list:
https://www.regincontrols.com/globalassets/pimmediafiles/documents/corrigo-5_0_vl40006_en.pdf

- Corrigo 5 has its **own** coil/discrete/input/holding Modbus map,
  BACnet and EXOline. Do not reuse the Corrigo E Ventilation 3.2 table.
- Communication constraint: 10 fast requests per 30 seconds;
  approximately 1 second delay beyond that. Max 47 registers per read.
- Typical real signals scale by 10; Corrigo 5 exceptions documented:
  input 321 CO2 concentration and holding 967 CO2 setpoint are /1;
  input 321 and holding 967 refer to Corrigo **5**, not Corrigo E.
- **Missing:** separate firmware-verified Corrigo 5 read-only profile,
  coil/discrete input support, EXOline, object/bitfield enumerations.

### 6. Grundfos MAGNA3 with CIM communications module

Grundfos product literature:
https://api.grundfos.com/literature/Grundfosliterature-6154248.pdf

- Communication depends on **installed CIM option**:
  CIM 200 Modbus RTU, CIM 300 BACnet MS/TP, CIM 500 Ethernet.
- CIM 500 and pump family still require the exact applicable functional
  profile/regmap. Do not invent speed/flow addresses.
- **Missing:** CIM feature/profile selection, proper point map and
  explicit module discovery.

### 7. Wilo Stratos, Stratos MAXO and CIF/IF modules

Official Wilo Modbus/data point index:
https://wilo.com/gb/en/Digital-Energy/Building-automation/Data-points-and-data-point-list/Modbus/

- Stratos MAXO uses its compatible CIF communication module.
  Other Stratos lines use model- and firmware-dependent IF modules.
- Official downloadable datapoint lists exist. Do not assume all models
  expose the same holding/input addresses or control points.
- **Missing:** manufacturer profile importer and module-type validation.

### 8. Bosch/Buderus/Junkers/IVT EMS bus

Maintained external adapter project:
https://github.com/emsesp/EMS-ESP32

- EMS, EMS+, EMS2/Heatronic communicate over a **dedicated electrical
  interface**, not bare ESP32 UART or Modbus RS-485 without hardware.
- Best integration path: a properly interfaced EMS-ESP gateway with
  Home Assistant/MQTT discovery; OpenHVAC can read the resulting sensors.
- Do not duplicate or relicense GPL-3 firmware without reviewing the
  license. Do not auto-transmit undocumented boiler controls.

### 9. Panasonic Aquarea / HeishaMon

Maintained community topic and command documentation:
https://github.com/HeishaMon/HeishaMon/blob/main/MQTT-Topics.md

- MQTT telemetry includes main/Pump_Flow, main/Main_Inlet_Temp,
  main/Main_Outlet_Temp, main/Main_Target_Temp and compressor data.
- Command topics also exist but should not be automatically exposed:
  changing a setpoint/mode is a physical equipment action.
- Connection depends on model, HeishaMon hardware and firmware.

## Existing versus researched (not yet installed)

Already in OpenHVAC: Ouman EH-800 HTTP, EH-800B USB, small
Ouman A203/S203/C203/H23 firmware maps, minimal Danfoss ECL,
Swegon CASA Genius, Corrigo E 3.2, selected-device BACnet/IP and
active-master wired M-Bus.

Research-only: complete NIBE S-series telemetry, MyVallox example,
expanded CASA Genius alarms, complete ECL application maps,
Corrigo 5, Grundfos CIM, Wilo data points, EMS-ESP, HeishaMon.

## Next implementation sequence

1. Bench verify MyVallox 4353/4358 and centikelvin conversion; no writes.
2. Add hardware-confirmed NIBE S-series model subprofiles and CSV export
   support; confirm register base and endianness before a default map.
3. Add Swegon alarm and service measurements with SW4.x and exact SEM/SEC
   decoding/bitfield tests.
4. Parse manufacturer reports (CSV/XML) into read-only profiles with
   verified source/firmware metadata.
5. After physical acceptance tests, consider individually reviewed,
   operator-approved commands; never silently open all RW registers.

The project is **not a certified BMS, safety controller or universal
plug-and-play driver**. All field commands remain subject to original
manufacturer safety functions.
