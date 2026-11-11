# Roth Touchline PL Relay Monitor

**Open HVAC / OpenLVI Bridge — isolated module download**

ESPHome read-only monitoring of the unused, isolated Roth Touchline PL heat-source relay output (NO/COM); not a zone control driver.

**Validation:** manufacturer-documented / hardware-unverified  
**Module:** roth-touchline-pl-contact-monitor  
**Source commit:** 71b6ac3d654735f476dbd939f047b03b2d434b98

## Install

Download this branch as a ZIP, extract it, and follow the module's
[full installation guide](https://github.com/artepe/Open-HVACBridge-homeassistant/blob/main/docs/ROTH_TOUCHLINE_PL.md).
This is a source snapshot; do not install unrelated files or assume
that simulation testing proves physical device compatibility.

**Destination:** manual (separate ESP32, qualified and electrically isolated dry-contact wiring)

## Safety

Strictly passive and read-only. DO NOT connect ESP32 to 230 V zone outputs, pump supply or existing energized boiler circuits. No Modbus/API support is claimed.

Contribute in [main](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/main), not in a
download branch. The download branches are regenerated from main.

Independent MIT-licensed community project, not manufacturer-endorsed.
