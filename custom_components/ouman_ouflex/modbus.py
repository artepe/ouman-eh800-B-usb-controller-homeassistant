"""Small dependency-free Modbus TCP transport. Each request owns one socket.

No RTU-over-TCP guessing, retries, discovery writes, or implicit address offsets.
The Ouflex gateways use TCP MBAP framing; unit identifies the RTU destination.
"""
from __future__ import annotations

import socket
import struct
import time
from datetime import datetime, timezone


class ModbusError(Exception):
    def __init__(self, message, exception_code=None):
        super().__init__(message)
        self.exception_code = exception_code


def address_offset(address, base, count=1):
    if type(address) is not int or type(base) is not int or base not in (0, 1):
        raise ValueError("Explicit integer address and base 0 or 1 required")
    offset = address - base
    if type(count) is not int or count < 1 or offset < 0 or offset + count > 65536:
        raise ValueError("Register range outside PDU address space")
    return offset


class Client:
    def __init__(self, host, port=502, unit=1, timeout=2, audit=None):
        if not isinstance(host, str) or not host or not 1 <= int(port) <= 65535:
            raise ValueError("Invalid host/port")
        if not 1 <= int(unit) <= 255 or not 0 < float(timeout) <= 30:
            raise ValueError("Unit must be 1..255; timeout must be 0..30 seconds")
        self.host, self.port, self.unit = host, int(port), int(unit)
        self.timeout, self.audit, self.transaction = float(timeout), audit, 0
        self.events = []

    @staticmethod
    def _exact(sock, size, deadline=None):
        data = b""
        while len(data) < size:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout("Modbus response deadline exceeded")
                sock.settimeout(remaining)
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise ModbusError("Truncated TCP response")
            data += chunk
        return data

    def request(self, function, payload=b"", *, address=None, count=None,
                name=None, datatype=None, value=None, decoder=None):
        self.transaction = (self.transaction + 1) & 65535
        tid = self.transaction
        started = time.monotonic()
        event = dict(timestamp=datetime.now(timezone.utc).isoformat(), ip=self.host,
                     port=self.port, unit_id=self.unit, function_code=function,
                     address=address, address_base=0, count=count, raw=None,
                     interpreted=value, datatype=datatype, point_name=name,
                     tcp_connected=False, modbus_response=False, success=False,
                     exception_code=None)
        pdu = bytes([function]) + payload
        event['request_hex'] = (struct.pack('>HHHB', tid, 0, len(pdu) + 1, self.unit) + pdu).hex()
        try:
            with socket.create_connection((self.host, self.port), self.timeout) as sock:
                event['tcp_connected'] = True
                # A single deadline bounds fragmented responses as well as connect.
                deadline = started + self.timeout
                sock.settimeout(max(0.001, deadline - time.monotonic()))
                sock.sendall(bytes.fromhex(event['request_hex']))
                header = self._exact(sock, 7, deadline)
                rt, protocol, length, unit = struct.unpack('>HHHB', header)
                if rt != tid or protocol != 0 or unit != self.unit or not 2 <= length <= 254:
                    raise ModbusError('Invalid MBAP transaction/protocol/unit/length')
                sock.settimeout(max(0.001, deadline - time.monotonic()))
                reply = self._exact(sock, length - 1, deadline)
                event['response_hex'] = (header + reply).hex()
                if reply[0] == function | 0x80:
                    if len(reply) != 2:
                        raise ModbusError('Malformed exception PDU')
                    event['modbus_response'] = True
                    raise ModbusError('Modbus exception %d' % reply[1], reply[1])
                if reply[0] != function:
                    raise ModbusError('Unexpected response function')
                if function in (3, 4):
                    if len(reply) != 2 + count * 2 or reply[1] != count * 2:
                        raise ModbusError('Invalid register byte count')
                    result = list(struct.unpack('>' + 'H' * count, reply[2:]))
                    event['raw'] = result
                elif function in (6, 16):
                    expected = payload if function == 6 else payload[:4]
                    if reply[1:] != expected:
                        raise ModbusError('Write echo mismatch')
                    result = reply[1:]
                    event['echo_hex'] = expected.hex()
                    data = payload[2:] if function == 6 else payload[5:]
                    event['raw'] = list(struct.unpack('>' + 'H' * (len(data)//2), data))
                elif function == 43:
                    if len(reply) < 7 or reply[1:3] != b'\x0e\x01':
                        raise ModbusError('Malformed device identification')
                    objects, pos = {}, 7
                    for _ in range(reply[6]):
                        if pos + 2 > len(reply):
                            raise ModbusError('Truncated identification object')
                        oid, n = reply[pos:pos+2]
                        pos += 2
                        if pos + n > len(reply):
                            raise ModbusError('Truncated identification text')
                        objects[str(oid)] = reply[pos:pos+n].decode('utf-8', 'replace')
                        pos += n
                    if pos != len(reply):
                        raise ModbusError('Unexpected identification bytes')
                    result = dict(objects=objects, more_follows=reply[4], next_object=reply[5])
                    event['interpreted'] = result
                else:
                    raise ValueError('Unsupported function')
                event['modbus_response'] = True
                if decoder is not None:
                    event['interpreted'] = decoder(result)
                event['success'] = True
                return result
        except Exception as err:
            event['error'] = str(err)
            event['exception_code'] = getattr(err, 'exception_code', None)
            raise
        finally:
            event['duration_ms'] = round((time.monotonic() - started) * 1000, 3)
            self.events.append(event)
            if self.audit:
                self.audit(event)

    def read(self, address, count=1, function=3, **metadata):
        address_offset(address, 0, count)
        if function not in (3, 4) or count > 125:
            raise ValueError('FC03/FC04, 1..125 registers required')
        return self.request(function, struct.pack('>HH', address, count),
                            address=address, count=count, **metadata)

    def identify(self):
        return self.request(43, b'\x0e\x01\x00')

    def write(self, address, words, function=16, **metadata):
        address_offset(address, 0, len(words))
        if any(type(w) is not int or not 0 <= w <= 65535 for w in words):
            raise ValueError('Words must be U16')
        if function == 6 and len(words) == 1:
            payload = struct.pack('>HH', address, words[0])
        elif function == 16 and len(words) <= 123:
            payload = struct.pack('>HHB', address, len(words), len(words)*2)
            payload += struct.pack('>' + 'H'*len(words), *words)
        else:
            raise ValueError('FC06 requires one word; FC16 requires 1..123')
        return self.request(function, payload, address=address, count=len(words), **metadata)
