"""Bounded, read-only Modbus TCP diagnostics independent of register profiles."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import struct
import time

EXCEPTIONS = {
    1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value",
    4: "Server Device Failure", 5: "Acknowledge", 6: "Server Device Busy",
    8: "Memory Parity Error", 10: "Gateway Path Unavailable",
    11: "Gateway Target Device Failed to Respond",
}


def unit_ids(raw):
    """Explicit IDs only; no broadcast or automatic address sweep."""
    try:
        units = [int(part.strip()) for part in raw.split(',')]
    except (AttributeError, ValueError) as err:
        raise ValueError("Use comma-separated Unit IDs") from err
    if not 1 <= len(units) <= 8 or len(set(units)) != len(units) or any(
            unit < 1 or unit > 255 for unit in units):
        raise ValueError("Use 1–8 distinct Unit IDs in range 1–255")
    return units


def read_parameters(address, address_base, count, function):
    if any(type(v) is not int for v in (address, address_base, count, function)):
        raise ValueError("Read parameters must be integers")
    if address_base not in (0, 1) or function not in (3, 4) or not 1 <= count <= 32:
        raise ValueError("FC03/04, explicit address base and 1–32 words required")
    offset = address - address_base
    if offset < 0 or offset + count > 65536:
        raise ValueError("Read outside Modbus address space")
    return offset


async def tcp_status(host, port, timeout=2.5):
    """TCP connectivity only; no Modbus request is sent."""
    writer = None
    try:
        async with asyncio.timeout(timeout):
            _, writer = await asyncio.open_connection(host, port)
        return {"tcp_connected": True}
    except (OSError, TimeoutError) as err:
        return {"tcp_connected": False, "error": str(err) or type(err).__name__}
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
            except (OSError, TimeoutError):
                pass


async def probe(host, port, unit, *, function=43, address=None, address_base=0,
                count=1, timeout=2.5):
    """One FC43/14 identification or explicit FC03/04 read; no retries/writes.

    A TCP connection is recorded before sending the Modbus read request. A
    Modbus exception proves a protocol response, not the presence of a point.
    """
    if type(unit) is not int or not 1 <= unit <= 255:
        raise ValueError("Unit must be 1–255")
    if function == 43:
        pdu = b'\x2b\x0e\x01\x00'
    else:
        offset = read_parameters(address, address_base, count, function)
        pdu = struct.pack('>BHH', function, offset, count)
    request = struct.pack('>HHHB', 1, 0, len(pdu) + 1, unit) + pdu
    result = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "unit_id": unit, "function_code": function,
              "tcp_connected": False, "modbus_response": False,
              "success": False, "request_hex": request.hex()}
    if function != 43:
        result.update(address=address, address_base=address_base, count=count,
                      pdu_address=offset)
    writer = None
    started = time.monotonic()
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(host, port)
            result['tcp_connected'] = True
            writer.write(request)
            await writer.drain()
            header = await reader.readexactly(7)
            tid, protocol, length, reply_unit = struct.unpack('>HHHB', header)
            result['response_hex'] = header.hex()
            if tid != 1 or protocol != 0 or reply_unit != unit or not 2 <= length <= 254:
                raise ValueError("Invalid MBAP transaction/protocol/unit/length")
            reply = await reader.readexactly(length - 1)
            result['response_hex'] += reply.hex()
            if reply[0] == (function | 0x80) and len(reply) == 2:
                result.update(modbus_response=True, exception_code=reply[1],
                              exception_name=EXCEPTIONS.get(reply[1], "Unknown exception"))
            elif reply[0] != function:
                raise ValueError("Unexpected function or malformed exception")
            elif function in (3, 4):
                if len(reply) != 2 + 2 * count or reply[1] != 2 * count:
                    raise ValueError("Invalid register byte count")
                result.update(modbus_response=True, success=True,
                              registers=list(struct.unpack('>' + 'H' * count, reply[2:])))
            else:
                if len(reply) < 7 or reply[1:3] != b'\x0e\x01':
                    raise ValueError("Malformed identification response")
                objects, pos = {}, 7
                for _ in range(reply[6]):
                    if pos + 2 > len(reply):
                        raise ValueError("Truncated identification object")
                    oid, size = reply[pos:pos+2]
                    pos += 2
                    if pos + size > len(reply):
                        raise ValueError("Truncated identification value")
                    objects[str(oid)] = reply[pos:pos+size].decode('utf-8', 'replace')
                    pos += size
                if pos != len(reply):
                    raise ValueError("Unexpected identification bytes")
                result.update(modbus_response=True, success=True, objects=objects,
                              more_follows=reply[4], next_object=reply[5])
    except (OSError, TimeoutError, asyncio.IncompleteReadError, ValueError) as err:
        result['error'] = str(err) or type(err).__name__
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=0.5)
            except (OSError, TimeoutError):
                pass
        result['duration_ms'] = round((time.monotonic() - started) * 1000, 1)
    return result


class DiscoveryDriver:
    """Connection diagnostic only. No register entities or implicit polling reads."""

    def __init__(self, data):
        self.data = {**data, 'allow_writes': False}
        self.points = []
        self.discovery = True
        self.io_lock = asyncio.Lock()
        self.last_diagnostics = data.get('discovery_diagnostics', {})
        self.last_research = []

    async def async_connect(self):
        return

    async def async_read(self):
        async with self.io_lock:
            status = await tcp_status(self.data['host'], self.data['port'])
        self.last_diagnostics = {**self.last_diagnostics, **status}
        # False is a meaningful diagnostic value; the entry stays loaded offline.
        return {'discovery_tcp_connected': status['tcp_connected']}

    async def async_close(self):
        return

    async def async_write(self, *args, **kwargs):
        raise ValueError("Discovery Mode never permits writes")


async def research(driver, units, *, function=43, address=None, address_base=0, count=1):
    if driver.data.get('transport') != 'modbus_tcp':
        raise ValueError("Research requires Modbus TCP")
    parsed = unit_ids(units)
    if function != 43:
        read_parameters(address, address_base, count, function)
    async with driver.io_lock:
        results = []
        for unit in parsed:
            results.append(await probe(driver.data['host'], driver.data['port'], unit,
                                       function=function, address=address,
                                       address_base=address_base, count=count))
            if len(parsed) > 1:
                await asyncio.sleep(0.2)
        driver.last_research = results
    return results
