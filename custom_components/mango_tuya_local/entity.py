"""Shared parameter identity and device association."""

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MangoCoordinator
from .protocol import Parameter


class MangoParameterEntity(CoordinatorEntity[MangoCoordinator]):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: MangoCoordinator, parameter: Parameter):
        super().__init__(coordinator, context=parameter.group)
        self.parameter = parameter
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{parameter.id_hex}"
        raw_label = (
            ""
            if parameter.scale_verified or parameter.key in coordinator.profile.known_select_options
            else " (raw)"
        )
        self._attr_name = f"{parameter.section} {parameter.name}{raw_label}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.unique_id)},
            name=coordinator.entry.title,
            manufacturer="Mango Energy",
            model="Tuya heat pump - captured 770-parameter profile",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.parameter_available(self.parameter)

    @property
    def extra_state_attributes(self):
        field = self.coordinator.field(self.parameter)
        return {
            "parameter_group": self.parameter.group,
            "parameter_slot": self.parameter.slot,
            "parameter_id": self.parameter.id_hex,
            "communication_state": self.coordinator.connection_state,
            "data_received_at": None
            if field is None
            else self.coordinator.snapshots[self.parameter.group].received_at,
            "description": self.coordinator.descriptions.get(self.parameter.key, {}).get("description"),
            "description_confidence": self.coordinator.descriptions.get(self.parameter.key, {}).get(
                "confidence"
            ),
            "raw_value": None if field is None else field.value,
            "flags_raw": None if field is None else field.flags,
            "tag_raw": None if field is None else field.tag,
            "scale_verified": self.parameter.scale_verified,
            "local_write_evidence": "verified_this_connection"
            if self.parameter.key in self.coordinator.client.verified_writes
            else self.parameter.local_write_evidence,
        }
