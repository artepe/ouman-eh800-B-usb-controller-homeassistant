#!/usr/bin/env python3
"""Synthetic Modbus TCP fixture. Addresses here are NOT Ouflex addresses.

Run: python3 tools/ouflex_simulator.py --port 1502
"""
from __future__ import annotations
import argparse
from pathlib import Path
import socketserver
import struct
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.ouman_ouflex.modbus import Client


class Model:
    def __init__(self):
        self.holding = {0: 7, 1: 0xffff, 2: 0xff85, 3: 0, 4: 39}
        self.inputs = {0: 23}
        self.lock = threading.Lock()
        self.requests = []
        self.delay = 0
        self.bad_transaction = False
        self.drop_after_write = False
        self.dropped = False
        self.reject_reads = False

    def reply(self, pdu):
        with self.lock:
            self.requests.append(pdu)
            fc = pdu[0]
            if fc in (3, 4) and len(pdu) == 5:
                start, count = struct.unpack('>HH', pdu[1:])
                data = self.holding if fc == 3 else self.inputs
                if self.reject_reads or not 1 <= count <= 125 or any(i not in data for i in range(start, start+count)):
                    return bytes([fc | 128, 2])
                return bytes([fc, count*2]) + struct.pack('>' + 'H'*count, *(data[i] for i in range(start, start+count)))
            if fc == 6 and len(pdu) == 5:
                start, value = struct.unpack('>HH', pdu[1:])
                if start not in self.holding:
                    return bytes([134, 2])
                self.holding[start] = value
                return pdu
            if fc == 16 and len(pdu) >= 6:
                start, count, n = struct.unpack('>HHB', pdu[1:6])
                if not 1 <= count <= 123 or n != 2*count or len(pdu) != 6+n:
                    return bytes([144, 3])
                if any(i not in self.holding for i in range(start, start+count)):
                    return bytes([144, 2])
                self.holding.update({start+i: v for i, v in enumerate(struct.unpack('>'+'H'*count, pdu[6:]))})
                return pdu[:5]
            if pdu == b'\x2b\x0e\x01\x00':
                obj = b'Ouflex SIMULATOR (synthetic)'
                return b'\x2b\x0e\x01\x01\x00\x00\x01\x00' + bytes([len(obj)]) + obj
            return bytes([fc | 128, 1])


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.settimeout(3)
            header = Client._exact(self.request, 7)
            tid, proto, length, unit = struct.unpack('>HHHB', header)
            if proto or not 2 <= length <= 254:
                return
            pdu = Client._exact(self.request, length-1)
            model = self.server.model
            reply = model.reply(pdu)
            if model.delay:
                time.sleep(model.delay)
            if pdu[0] in (6, 16) and model.drop_after_write and not model.dropped:
                model.dropped = True
                return
            tid = tid + 1 if model.bad_transaction else tid
            packet = struct.pack('>HHHB', tid, 0, len(reply)+1, unit) + reply
            # Deliberate fragmentation exercises exact-read implementation.
            self.request.sendall(packet[:4])
            self.request.sendall(packet[4:])
        except Exception:
            return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, model=None):
        self.model = model or Model()
        super().__init__(address, Handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=1502)
    args = p.parse_args()
    with Server((args.host, args.port)) as server:
        print('SYNTHETIC Modbus TCP server at %s:%s' % server.server_address, flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
