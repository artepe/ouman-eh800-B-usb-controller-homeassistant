"""Consume worker outcomes even when their asyncio caller is cancelled."""

import asyncio


def run_sync(method, *args):
    try:
        return True, method(*args)
    except Exception as error:
        # Expected transport/recovery errors must not become abandoned Future
        # exceptions when the caller has already been cancelled.
        return False, error


async def async_call(hass, method, *args, abort=None):
    future = hass.async_add_executor_job(run_sync, method, *args)
    try:
        success, result = await asyncio.shield(future)
    except asyncio.CancelledError:
        if abort is not None:
            abort.set()
        # The worker includes any required rollback. Keep its owner lock until
        # that work ends, and consume the boxed result before propagating cancel.
        await asyncio.shield(future)
        raise
    if not success:
        raise result
    return result
