# Tosi / Tosibox gateway integration with Open-HVACBridge

**Status: experimental; original integration supports a small read-only
Modbus TCP status map. The OpenLVI Lab branch adds offline snapshot
interpretation, connectivity findings, setup instructions and tests.**

Source: official Tosi / Tosibox documentation (checked 2026-11-04):
- Node Modbus register map (firmware 5.5.0+):
  https://helpdesk.tosibox.com/serviceportal?id=kb_article_view&sysparm_article=KB0010272
- Lock mode versus Client mode:
  https://helpdesk.tosibox.com/serviceportal?id=kb_article_view&sysparm_article=KB0010112
- Full Gateway/Key/Lock manual:
  https://www.tosibox.com/hubfs/Tosibox%20User%20Manual%202025.pdf
- Tosi Hub (VPN concentrator for central SCADA):
  https://tosibox.service-now.com/serviceportal?id=kb_article_view&sysparm_article=KB0010421
- Latest Hub version and connectivity announcements:
  https://tosibox.service-now.com/serviceportal?id=kb_article_view&sysparm_article=KB0010151
- Client software for Windows/macOS:
  https://helpdesk.tosibox.com/serviceportal?id=kb_article_view&sysparm_article=KB0010149

## Tosibox has TWO distinct integration roles

**Role A — monitor the Tosibox itself:**
On an authorized site LAN, OpenLVI polls the Tosibox gateway's own
holding registers (FC03) at TCP/502. This gives connection interface,
cellular raw signal, coordination-service status, VPN tunnel count,
Internet/VPN enabled flags and gateway firmware version.

**Role B — use an authenticated VPN to reach OTHER HVAC devices:**
A Tosibox Key/Client, Gateway–Gateway tunnel or licensed Tosi Hub
provides protected IP routing to equipment on the site LAN. Once
authorized routing exists, OpenLVI uses its **existing native**
Modbus/BACnet/HTTP drivers to query an Ouman, Swegon, Siemens, etc.
Nothing in the Tosibox status register map provides those Ouman
temperatures automatically.

### Preferred small-site architecture

    On-site independent OT LAN
    ┌─────────────────────────────────────────────┐
    │ Ouman, Swegon, PLC, Modbus meters            │
    │       │                                     │
    │       ├── local Modbus/BACnet/HTTP ─┐       │
    │       │                             │       │
    │ Tosibox Gateway  ← status Modbus ───┤       │
    │       │                             │       │
    │       └── encrypted VPN ──────┐     │       │
    │                               │     │       │
    │                    Open-HVACBridge on-site   │
    │                    read-only monitoring     │
    └───────────────────────────────┼─────────────┘
                                    │
                           Authorized Tosi Key
                           or gateway/HUB route
                                    │
                        Remote maintenance operator

When the WAN or VPN fails, Open-HVACBridge's on-site sensor collection
and OEM controllers continue on the local LAN.

### Many buildings

    Property A: BMS + site OpenLVI -> Tosi Gateway A ─┐
    Property B: BMS + site OpenLVI -> Tosi Gateway B ─┼→ Tosi Hub
    Property C: BMS + site OpenLVI -> Tosi Gateway C ─┘      │
                                                          ├→ technician client
                                                          └→ central SCADA

Use Tosi Hub for licensed persistent network-to-network connectivity,
segmentation and audit events. A centrally deployed OpenLVI can only
query site BMS devices if correct Tosi **L3 routing and access policy**
exist. Never assume every Key can reach every subnet. Overlapping
site subnets require an explicitly approved routing/NAT design.

**This does not mean Tosibox can operate its full remote access service
without Tosi infrastructure.** A private/local Tosi Hub may handle data
plane routes and some coordination, but the documented vendor service,
authentication, license, provisioning and remote matching dependencies
must be confirmed with Tosibox before promising 100% vendor-independent
VPN operation. For a strict no-vendor-service requirement, keep the
HVAC side local and independently evaluate self-managed WireGuard.

## Step-by-step: local Tosibox status in Home Assistant

1. Confirm **exact gateway model and firmware**. The official Modbus
   status map requires firmware >=5.5.0 on the supported models.
2. Physically connect Open-HVACBridge and Tosibox to the permitted OT
   / management LAN. Gateway IP is the **local Tosibox LAN address**,
   not its remote internet address and not an app URL.
3. In authorized Tosibox admin UI, go to **Advanced Settings**:
   enable **Modbus server**. Use the documented **Listen IP** restriction
   and additional firewall/VLAN rules to authorize only the collector.
   Avoid the wildcard 0.0.0.0 where unnecessary.
4. Leave **Master for Internet/VPN access states** disabled, and **do
   not** write network access registers under any circumstances.
5. In Home Assistant: Settings > Devices & Services > Add Integration >
   OpenLVI Bridge > manufacturer **Tosibox** > exact model >
   exact firmware > **Modbus TCP**. Host = Tosibox LAN IP,
   port **502**, unit ID = server-supported ID (the OpenLVI form
   suggests 1, but verify it rather than assuming every firmware).
   Leave custom register JSON empty and uncheck **Allow Writes**.
6. The existing OpenLVI profile reads documented holding offsets
   14–20, adding 21–23 for firmware >=5.6.0.
7. Allow a few seconds and read again when initial values are
   **0xFFFF (unavailable)**. Tosibox updates Modbus data roughly
   every 10 seconds. Suggested normal interval: 15–30 seconds.
   Firmware 5.7.0+ permits up to five concurrent TCP clients;
   earlier firmware permitted one. Avoid repeated persistent scanners.
8. Build the monitoring dashboard using status entities. A VPN tunnel
   count >0 does NOT verify that a remote PLC is reachable. Check
   a *separate* authorized heartbeat from the actual target BMS.

### Correct manufacturer offsets

Modbus FC03 PDU zero-based address is the manufacturer's offset.
OpenLVI's one-based logical address is offset + 1.

| Vendor offset | OpenLVI register | Reading | Version |
|---:|---:|---|---|
| 14 | 15 | Cellular RSRP (raw 16-bit, verify signed dBm conversion) | 5.5.0 |
| 15 | 16 | Cellular RSSI (raw 16-bit, verify signed dBm conversion) | 5.5.0 |
| 16 | 17 | Active uplink: 0 none, 1 WAN, 2 internal LTE, 3 external LTE, 4 LAN, 5 Wi-Fi, 10 unknown | 5.5.0 |
| 17 | 18 | Tosi/Tosibox cloud coordination connected: 0/1 | 5.5.0 |
| 18 | 19 | Open VPN tunnel count (may include failed/establishing) | 5.5.0 |
| 19 | 20 | Internet enabled flag 0/1 — **read-only in OpenLVI** | 5.5.0 |
| 20 | 21 | VPN enabled flag 0/1 — **read-only in OpenLVI** | 5.5.0 |
| 21 | 22 | Firmware major | 5.6.0 |
| 22 | 23 | Firmware minor | 5.6.0 |
| 23 | 24 | Firmware patch | 5.6.0 |

The 0xFFFF sentinel is missing/unavailable, not a valid number.
The official manual calls signal values unsigned 16-bit 'dBm':
we keep them RAW until the actual 16-bit signedness/encoding is
confirmed on real devices. No ICCID/SIM identifiers or GNSS tracks
are collected by the default profile.

The manufacturer's holding offsets 19 and 20 are writable, and
changing them can **cut off the gateway's WAN/VPN**. The OpenLVI
profiles force these to **read-only**. Never use FC06/FC16 for
these offsets, remote support, or SMS trigger registers 47–138.

## Existing Tosibox support in Open-HVACBridge

As of main branch 0.4.3-beta.1:
- `custom_components/openlvi/const.py` contains selected Tosibox models.
- `custom_components/openlvi/profiles.py` has `TOSIBOX_STATUS_BASE`
  and `TOSIBOX_FIRMWARE`, enforced as read-only.
- `custom_components/openlvi/transport.py` uses an existing Modbus TCP
  FC03 reader with one-based -> PDU offset translation.
- The HA setup can create a normal device with point sensors.
- It is NOT a Tosibox Key VPN client. It cannot create/match Key
  identities, tunnel endpoints or Hub memberships.
- It does not query the other devices behind Tosibox unless their
  LAN IPs are already routed/reachable.

### New development-branch diagnostic (offline)

`tools/openlvi_lab/tosibox.py` accepts a **captured** register
snapshot and emits quality/freshness, actual interface enum,
VPN tunnel count caveat and useful connection notes. It does
NOT poll the actual gateway.

From the repository root:

    python3 tools/openlvi_lab_cli.py tosibox-status \
      --input examples/openlvi-lab/tosibox-snapshot.json

    python3 tools/openlvi_lab_cli.py tosibox-plan \
      --deployment few_sites --gateway-mode lock \
      --monitoring-location on_site

Output contains no VPN keys, SIM ICCIDs or personal identifiers.

## Security and operational acceptance

- No port forwards from Internet to 502/TCP, 47808/UDP or controllers.
- Use original Tosi authorization, matching, Key/client and approved
  VLAN or access groups. Do not reverse engineer or bypass keys.
- Lock mode provides a protected subnet by default. **Client Mode
  joins an existing LAN and its own firewall does not isolate all
  devices**. Confirm filtering and fallback Internet routes.
- Site identity, physical device IP and tunnel route are different.
  In multi-site installations use non-overlapping subnets or explicit
  carefully reviewed L3 NAT; central reachability is not automatic.
- An unreachable Tosi Cloud service does not necessarily stop local
  automation, but can affect remote coordination.
- For production, add stale-signal alerts and audit/log retention.
  Tosi Hub has official Prometheus and remote-log options, but do
  not guess endpoints, authentication or scrape settings.
- No physical Tosibox or PLC was contacted by this research.
  Real integration requires a site acceptance test.
