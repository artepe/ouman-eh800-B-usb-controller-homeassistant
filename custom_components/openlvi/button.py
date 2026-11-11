"""Manual, read-only AI analysis request on the device page."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_MODEL, CONF_VENDOR

async def async_setup_entry(hass, entry, async_add_entities):
    if getattr(entry.runtime_data.driver, "discovery", False):
        return
    async_add_entities([OpenLVIReviewButton(entry.runtime_data)])

class OpenLVIReviewButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_key = "review_settings_en"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_ai_review_button"
        self._attr_icon = "mdi:clipboard-text-search-outline"

    async def async_press(self):
        await self.coordinator.guide.review()

    @property
    def device_info(self):
        entry = self.coordinator.config_entry
        return {"identifiers": {(DOMAIN, entry.entry_id)},
                "name": f"{entry.data[CONF_VENDOR]} {entry.data[CONF_MODEL]}",
                "manufacturer": entry.data[CONF_VENDOR],
                "model": entry.data[CONF_MODEL]}

