"""Explicit macOS netcat transport for hosts with per-executable LAN permissions.

No shell, telnet escaping, retries or protocol changes. Used only when selected.
"""
import math
import select
import socket
import subprocess


class NetcatSocket:
    def __init__(self, host, port, timeout):
        if host.startswith('-') or any(c in host for c in '\r\n\x00'):
            raise ValueError('Invalid netcat host')
        self.timeout = timeout
        self.process = subprocess.Popen(
            ['/usr/bin/nc', '-n', '-w', str(math.ceil(timeout)), host, str(port)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, data):
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def recv(self, size):
        if not select.select([self.process.stdout], [], [], self.timeout)[0]:
            raise socket.timeout('Netcat response deadline exceeded')
        return self.process.stdout.read(size)
