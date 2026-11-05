"""No credentials, raw private status DPs, or user account identifiers."""

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_DEVICE_ID, CONF_LOCAL_KEY


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(
            entry.as_dict(), {CONF_DEVICE_ID, CONF_LOCAL_KEY, "host", "unique_id"}
        ),
        "parameters_in_profile": len(coordinator.profile.parameters),
        "parameters_read": sum(len(s.fields) for s in coordinator.snapshots.values()),
        "failed_groups": sorted(coordinator.failed_groups),
        "communication_state": coordinator.connection_state,
        "consecutive_status_failures": coordinator.consecutive_status_failures,
        "connection_grace_seconds": coordinator.connection_grace_seconds,
        "last_transport_error": coordinator.client.last_transport_error,
        "status_reconnects": coordinator.client.status_reconnects,
        "last_status_received_at": coordinator.client.last_status_received_at,
        "verified_write_routes_this_connection": sorted(coordinator.client.verified_writes),
        "last_operation": coordinator.client.last_operation,
        "all_parameter_permissions_verified": False,
    }
