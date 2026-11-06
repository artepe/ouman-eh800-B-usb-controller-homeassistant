# Jäspi Tehowatti Dry Contact

**Open HVAC / OpenLVI Bridge — isolated module download**

Local ESPHome relay example for the traditional Tehowatti electric boiler's NO temperature-setback contact.

**Validation:** manufacturer-documented / hardware-unverified  
**Module:** jaspi-tehowatti-contact  
**Source commit:** e1f3479114544a9dd0b87c9d8da1aa52d98a5719

## Install

Download this branch as a ZIP, extract it, and follow the module's
[full installation guide](https://github.com/artepe/Open-HVACBridge-homeassistant/blob/main/docs/JASPI_TEHOWATTI.md).
This is a source snapshot; do not install unrelated files or assume
that simulation testing proves physical device compatibility.

**Destination:** manual (ESPHome firmware on separate ESP32 and isolated NO relay)

## Safety

Only the existing temperature setback input; electrical wiring requires qualified verification. No internal registers or safety bypass.

Contribute in [main](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/main), not in a
download branch. The download branches are regenerated from main.

Independent MIT-licensed community project, not manufacturer-endorsed.
