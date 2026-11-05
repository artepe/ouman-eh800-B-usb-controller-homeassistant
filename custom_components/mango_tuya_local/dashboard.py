"""Local dashboard, English help, and registry-resolved entity identities."""

import json
from pathlib import Path

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, VERSION

CARD_URL = f"/{DOMAIN}/frontend/mango-parameter-card.js?v={VERSION}"
PANEL_PATH = "mango-control"


def load_catalog():
    data = json.loads(Path(__file__).with_name("descriptions.json").read_text())
    if data["format"] != "mango_dashboard_catalog_v1" or len(data["parameters"]) != 770:
        raise ValueError("invalid_dashboard_catalog")
    if {g["group"] for g in data["groups"]} != set(range(17)):
        raise ValueError("invalid_dashboard_categories")
    return data


async def async_setup_dashboard(hass):
    catalog = await hass.async_add_executor_job(load_catalog)
    hass.data[DOMAIN] = {"catalog": catalog}
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/{DOMAIN}/frontend", str(Path(__file__).with_name("frontend")), False)]
    )
    frontend.add_extra_js_url(hass, CARD_URL)
    websocket_api.async_register_command(hass, websocket_dashboard)
    if not frontend.async_panel_exists(hass, PANEL_PATH):
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="mango-control-panel",
            sidebar_title="Mango Control",
            sidebar_icon="mdi:heat-pump-outline",
            module_url=CARD_URL,
            embed_iframe=False,
            trust_external=False,
            config_panel_domain=DOMAIN,
        )


@callback
def dashboard_data(hass, permissions):
    registry = er.async_get(hass)
    catalog = hass.data[DOMAIN]["catalog"]
    devices = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        coordinator = entry.runtime_data

        def resolve(platform, suffix, unique_id=entry.unique_id):
            entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{unique_id}_{suffix}")
            return entity_id if entity_id and permissions.check_entity(entity_id, POLICY_READ) else None

        groups = []
        for category in catalog["groups"]:
            parameters = []
            for parameter in coordinator.profile.parameters.values():
                if parameter.group != category["group"]:
                    continue
                platform = "select" if parameter.key in coordinator.profile.known_select_options else "number"
                entity_id = resolve(platform, parameter.id_hex)
                if entity_id is None:
                    continue
                parameters.append(
                    {
                        "key": parameter.key,
                        "name": parameter.name,
                        "entity_id": entity_id,
                        "domain": platform,
                        "can_control": permissions.check_entity(entity_id, POLICY_CONTROL),
                        "scale_verified": parameter.scale_verified,
                        **catalog["parameters"][parameter.key],
                    }
                )
            groups.append({**category, "parameters": parameters})
        if not any(g["parameters"] for g in groups):
            continue
        devices.append(
            {
                "entry_id": entry.entry_id,
                "name": entry.title,
                "groups": groups,
                "sensors": {
                    "current_temperature": resolve("sensor", "current_temperature"),
                    "target_temperature": resolve("sensor", "target_temperature"),
                    "parameters_read": resolve("sensor", "parameters_read"),
                },
                "refresh_entity": resolve("button", "refresh_parameters"),
            }
        )
    return {"version": VERSION, "devices": devices}


@websocket_api.websocket_command({"type": f"{DOMAIN}/dashboard"})
@callback
def websocket_dashboard(hass, connection, msg):
    connection.send_result(msg["id"], dashboard_data(hass, connection.user.permissions))
