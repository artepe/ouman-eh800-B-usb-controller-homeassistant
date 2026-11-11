# DEVIreg 330 price setback blueprint

**Open HVAC / OpenLVI Bridge — isolated module download**

Per-circuit Home Assistant spot-price setback automation for independently commissioned DEVIreg 330 (+5 to +45 C) external timer inputs.

**Validation:** manufacturer-documented / hardware-unverified  
**Module:** devireg330-price-setback  
**Source commit:** 71b6ac3d654735f476dbd939f047b03b2d434b98

## Install

Download this branch as a ZIP, extract it, and follow the module's
[full installation guide](https://github.com/artepe/Open-HVACBridge-homeassistant/blob/main/docs/DANFOSS_MCX_DEVIREG330.md).
This is a source snapshot; do not install unrelated files or assume
that simulation testing proves physical device compatibility.

**Destination:** /config/blueprints/automation/openlvi

## Safety

No Modbus on DEVIreg 330. The external timer input is mains-referenced; install a correctly rated and physically fail-safe relay through qualified electrical work. Restores normal mode on stale prices but cannot protect against HA outages.

Contribute in [main](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/main), not in a
download branch. The download branches are regenerated from main.

Independent MIT-licensed community project, not manufacturer-endorsed.
