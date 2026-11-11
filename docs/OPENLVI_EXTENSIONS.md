# OpenLVI Bridge: BACnet/IP, Kamstrup M-Bus, SCADA and diagnostics (beta)

This is an **experimental, read-only-first** multi-vendor extension. No device
was physically connected during authoring. The existing
`custom_components/ouman_eh800` stable EH-800B USB driver is not modified.

## What is implemented

| Feature | State |
|---|---|
| BACnet/IP | Read-only driver via BACpypes3 0.0.110; binds on user-supplied local IPv4/CIDR; reads explicit profile or discovers up to 32 **objects on one selected device** via its object-list |
| Kamstrup MULTICAL 403/603/803 | Wired M-Bus primary-address polling via pyMeterBus 0.8.5 and an **active** M-Bus master / USB interface; creates dynamic read-only records with the meter's actual units |
| Additional brands | Manufacturer/model options for Grundfos, Wilo, Belimo, Schneider and Siemens; **not plug-and-play** until the exact installed firmware/physical interface and site point map are verified |
| Site-specific register import | `tools/openlvi_pointmap_import.py` converts reviewed CSV/XML into **read-only** JSON maps with strict key/address/type validation |
| BACnet object discovery | Targeted one-device object-list read (max 32 objects), no network-wide broadcast scan, no writes |
| Diagnostics | Temperature differences, optional water-only thermal power, rules to flag suspicious measurement values; advisory, not autonomous control |
| SCADA | Separate **isometric 2.5D** Lovelace custom card that follows entity states without write controls; not a full 3D digital twin |
| Energy analytics | Instantaneous water-side kW when `l1_supply`, `l1_return`, and separately decoded `flow_m3h` exist. Historical consumption needs HA recorder/energy meter; never manufacture totals |

## Installation for evaluation

From the repository's `main` branch, copy `custom_components/openlvi` into
`/config/custom_components/openlvi`; restart HA. In
**Settings → Devices & Services → Add Integration → OpenLVI Bridge**,
select the manufacturer and model. In the next step, choose the actual
transport. **Do not enable remote writes** during testing.

### BACnet/IP

Needs a BACnet/IP controller on an *isolated private* network (UDP 47808),
known remote device instance, and a local HA host network interface address.
Home Assistant container's bind address is required to be reachable.

Example settings:
- Vendor: Siemens, model: Desigo PXC4
- Transport: BACnet/IP
- Remote IP: `192.168.20.51`
- Remote BACnet device instance: `12010` (must match real device)
- Local BACnet bind: `192.168.20.10/24` (must be an actual HA host interface)
- Local BACnet client instance: `400000` (must be unique in the network)

With a known object map, prefer specifying it:

```json
{
  "objects": [
    {"key":"supply_temp","type":"analog-input","instance":7,
     "name":"Supply air temperature","unit":"°C"},
    {"key":"fan_run","type":"binary-input","instance":2,
     "name":"Fan running"}
  ]
}
```

**These object instance numbers are examples only.** Use the controller's
actual BACnet object export. If JSON is blank, OpenLVI tries the first
32 entries in the selected BACnet device's object-list (not a general network
discovery sweep). Shared BACnet UDP port ownership is not supported:
another local BACnet service using the same bind port may conflict.

Read-only. No BACnet WriteProperty is exposed.

### Kamstrup wired M-Bus

Kamstrup MULTICAL needs a physical wired M-Bus communications module and a
**powered active M-Bus master** connected over USB/serial. Do not connect
M-Bus directly to RS-485/TTL dongles or Pi GPIO. Use the meter's *primary
M-Bus address* (1..250) and serial baud rate (default 2400, 8E1). The
module may be configured to transmit different record profiles; raw units
are taken from the telegram and record indexes are not guessed.

**Not** wireless M-Bus (wM-Bus): it requires a separate radio receiver and
decoder. Avoid duplicate pollers on one serial bus.

When installed, choose Kamstrup -> MULTICAL 403/603/803 -> physical
M-Bus serial port and primary address. Sensors are created after the
first valid telegram. No meter configuration commands are issued.

### Device-specific Modbus template importer

For a reviewed *CSV* with headings
`key,name,address,kind,decimals,unit,area`:

```bash
python3 tools/openlvi_pointmap_import.py my_device.csv -o my_device.json
```

For XML use `<points><point key="..." name="..." address="305"
kind="s16" decimals="1" area="input" unit="°C"/></points>`.

The address is always the **one-based register number** in the exact
vendor/firmware register table. Use `input` for function 04,
`holding` for function 03. All imported registers remain read-only,
even if the CSV contains a `writable` column.
PDF register tables must be verified and converted by an operator; an
unreviewed PDF is never taken as a trustworthy write map.

### SCADA card

Copy `www/openlvi-scada-card.js` to
`/config/www/openlvi-scada-card.js`.
In **Settings → Dashboards → Resources**, register
`/local/openlvi-scada-card.js` as JavaScript module.
Then paste `examples/lovelace-openlvi-scada.yaml` as a manual card and
**replace the example entity IDs** with the actual OpenLVI IDs.

The isometric scene is a lightweight CSS/HTML schematic with live labels,
**not** a real 3D mesh render. It does not affect any HVAC outputs.

### Diagnostics and energy

A derived `L1 temperature difference` sensor appears when both `l1_supply`
and `l1_return` exist. A `L1 estimated thermal power` sensor is added
if `flow_m3h` is also present and is in 0..100 m³/h.
Formula: P[kW] = 1.163 * flow[m³/h] * (supply°C − return°C),
**for water only**; glycol and different fluid properties change the
factor. Historical kWh requires a meter or integration over time.

The `OpenLVI diagnostics` sensor reports deterministic suspicious
temperature and supply-setpoint deviations. It is *advisory*, not a
guaranteed fault detector, and it never commands a controller.

## Required hardware and sources

- BACnet/IP client: BACpypes3 documentation: https://bacpypes3.readthedocs.io/
- M-Bus protocol: pyMeterBus: https://github.com/ganehag/pyMeterBus
- Kamstrup M-Bus MULTICAL 403 modules:
  https://www.kamstrup.com/fi-fi/product-centre/multical-403
- Grundfos CIM 500 Modbus/BACnet interfaces:
  https://www.grundfos-eica.com/magna3/bacnet-ip.html

**Before production:** validate the HA config flow and third-party libraries,
verify BACnet local bind and responses on a separate test network, verify
M-Bus frame parsing and physical polarity/termination with an active master,
compare readings against a real controller, then test HA restarts and recovery.
No automatic control changes are made by this extension.
