"""Redacted diagnostics; raw site maps and network addresses stay local."""
async def async_get_config_entry_diagnostics(hass, entry):
    c = entry.runtime_data
    return dict(identity=c.doc['identity'], points=len(c.points),
                write_enabled=c.write_enabled, last_update_success=c.last_update_success,
                failed_points=list(c.point_errors),
                last_write_confirmed=bool(c.last_write and c.last_write.get('success')),
                responses=[{k: e.get(k) for k in ('function_code', 'address', 'count', 'success',
                                                 'modbus_response', 'exception_code', 'duration_ms')}
                           for e in c.last_events])
