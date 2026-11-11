# Ouman EH-800B Legacy

**Open HVAC / OpenLVI Bridge — isolated module download**

Separate EH-800B USB implementation v0.1.2 verified on one controller.

**Validation:** hardware-tested  
**Module:** ouman-eh800b-legacy  
**Source commit:** 71b6ac3d654735f476dbd939f047b03b2d434b98

## Install

Download this branch as a ZIP, extract it, and follow the module's
[full installation guide](https://github.com/artepe/Open-HVACBridge-homeassistant/blob/main/docs/STABLE_RELEASE_v0.1.2.md).
This is a source snapshot; do not install unrelated files or assume
that simulation testing proves physical device compatibility.

**Destination:** /config

## Safety

YAML setup required; PID and manual valve writes can be hazardous. Do not poll the same USB port using multiple integrations.

Contribute in [main](https://github.com/artepe/Open-HVACBridge-homeassistant/tree/main), not in a
download branch. The download branches are regenerated from main.

Independent MIT-licensed community project, not manufacturer-endorsed.
