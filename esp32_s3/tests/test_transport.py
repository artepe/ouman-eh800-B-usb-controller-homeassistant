"""Offline regression tests for the experimental USB -> socket:// transport.

No Home Assistant installation, USB device, or pyserial package is needed.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "custom_components" / "ouman_eh800" / "ouman.py"
DIAGNOSTIC = ROOT / "esp32_s3" / "test_ouman_tcp.py"


def import_python(path, name, serial_module=None):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if serial_module is None:
        spec.loader.exec_module(module)
    else:
        with patch.dict(sys.modules, {"serial": serial_module}):
            spec.loader.exec_module(module)
    return module


class PortSelectionTests(unittest.TestCase):
    def setUp(self):
        self.fake_serial = types.ModuleType("serial")
        self.fake_serial.Serial = Mock(return_value="USB")
        self.fake_serial.serial_for_url = Mock(return_value="TCP")
        self.driver = import_python(DRIVER, "ouman_transport_under_test", self.fake_serial)

    def test_socket_uses_serial_for_url(self):
        result = self.driver.OumanUSB("socket://192.168.10.50:8880")._open_port()
        self.assertEqual(result, "TCP")
        self.fake_serial.serial_for_url.assert_called_once_with(
            "socket://192.168.10.50:8880", timeout=0.22, write_timeout=1.0)
        self.fake_serial.Serial.assert_not_called()

    def test_local_usb_keeps_original_exclusive_open(self):
        result = self.driver.OumanUSB("/dev/ttyACM0")._open_port()
        self.assertEqual(result, "USB")
        self.fake_serial.Serial.assert_called_once_with(
            "/dev/ttyACM0", timeout=0.22, write_timeout=1.0, exclusive=True)
        self.fake_serial.serial_for_url.assert_not_called()

    def test_lock_is_shared_for_same_tcp_port(self):
        a = self.driver.OumanUSB("socket://192.168.10.50:8880")
        b = self.driver.OumanUSB("socket://192.168.10.50:8880")
        self.assertIs(a.lock, b.lock)

    def test_measurements_still_sends_original_read_command(self):
        lines = "".join(f"{i}: {i}.0 C\n" for i in range(1, 29)).encode("ascii")
        class FakePort:
            def __init__(self):
                self.commands = []
                self.rx = [lines, b"", b""]
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def reset_input_buffer(self): pass
            def write(self, command): self.commands.append(command)
            def flush(self): pass
            def read(self, size): return self.rx.pop(0) if self.rx else b""
        port = FakePort()
        hub = self.driver.OumanUSB("socket://192.168.10.50:8880")
        with patch.object(hub, "_open_port", return_value=port), patch.object(self.driver.time, "sleep"):
            measurements = hub.measurements()
        self.assertEqual(port.commands, [b"MEASUREMENTS\n"])
        self.assertEqual(len(measurements), 28)
        self.assertEqual(measurements[8], (9.0, "C"))


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diag = import_python(DIAGNOSTIC, "ouman_diagnostic_under_test")

    def test_parse_28_measurements(self):
        payload = b"".join(f"{i}: {i}.0 C\n".encode() for i in range(1, 29))
        self.assertEqual(len(self.diag.parse_measurements(payload)), 28)

    def test_reject_invalid_lines(self):
        self.assertEqual(self.diag.parse_measurements(b"ERROR\nUNKNOWN\n"), [])

    def test_only_read_command_is_sent(self):
        class FakeConnection:
            def __init__(self):
                self.sent = []
                self.results = [b"1: 20 C\n", b""]
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def settimeout(self, timeout): pass
            def sendall(self, data): self.sent.append(data)
            def recv(self, n): return self.results.pop(0)
        fake = FakeConnection()
        with patch.object(self.diag.socket, "create_connection", return_value=fake):
            result = self.diag.read_measurements("192.168.10.50", 8880)
        self.assertEqual(fake.sent, [b"MEASUREMENTS\n"])
        self.assertEqual(result, b"1: 20 C\n")


if __name__ == "__main__":
    unittest.main()
