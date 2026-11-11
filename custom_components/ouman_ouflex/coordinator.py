"""Executor-based Ouflex coordinator with one lock for polling and writes."""
from __future__ import annotations
import asyncio
from datetime import timedelta
import json
import logging
import os
from pathlib import Path

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .modbus import Client
from .pointmap import load_map, decode, map_digest
from .session import Session

_LOGGER = logging.getLogger(__name__)


def entity_platform(point, allowed):
    if point.entity in ('number', 'select', 'switch') and not allowed:
        return 'sensor'
    return 'binary_sensor' if point.entity == 'alarm' else point.entity


class OuflexCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name='Ouman Ouflex',
                         update_interval=timedelta(seconds=30))
        self.config_entry = entry
        self.doc, self.points = load_map(entry.data['map_json'])
        self.lock = asyncio.Lock()
        self.point_errors = {}
        self.last_write = None
        self.last_events = []
        policy = json.loads(entry.options.get('write_policy', '{}'))
        self.write_enabled = entry.options.get('allow_writes', False) is True
        self.client = Client(entry.data['host'], entry.data.get('port', 502),
                             entry.data.get('unit_id', 1), 3, self._audit)
        self.session = Session(self.client, self.doc, self.points, policy,
                               self.write_enabled, physical=True)

    def _audit(self, event):
        # Audit failures propagate and prevent write attempts at intent phase.
        path = Path(self.hass.config.path('.storage', 'ouflex_' + self.config_entry.entry_id + '.jsonl'))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def can_write(self, point):
        try:
            self.session.permitted(point.key, require_physical=True)
            return point.manual_reg is None
        except ValueError:
            return False

    def _poll(self):
        values, errors = {}, {}
        self.client.events.clear()
        for point in self.points:
            try:
                raw = self.client.read(point.offset, point.count, point.function,
                                       name=point.name, datatype=point.kind, decoder=lambda raw: decode(raw, point))
                values[point.key] = decode(raw, point)
            except Exception as err:
                errors[point.key] = str(err)
        self.point_errors = errors
        self.last_events = self.client.events[-256:]
        return values

    async def _async_update_data(self):
        async with self.lock:
            values = await self.hass.async_add_executor_job(self._poll)
        if not values:
            raise UpdateFailed('No Ouflex Modbus points responded; inspect diagnostics')
        return values

    async def async_write(self, point, value):
        if not self.can_write(point):
            raise ValueError('Point is not physically verified and enabled for writing')
        async with self.lock:
            self.last_write = await self.hass.async_add_executor_job(self.session.write, point.key, value, 16)
        # Publish the confirmed device read-back immediately; HA may debounce
        # a full refresh when several controls are used in quick succession.
        self.async_set_updated_data({**(self.data or {}), point.key: self.last_write["interpreted"]})
        await self.async_request_refresh()
