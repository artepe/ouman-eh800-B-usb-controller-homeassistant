"""Read-only automatic FTP onboarding tests using synthetic device files."""
import unittest
from unittest.mock import patch

from custom_components.ouman_ouflex.ftp_map import fetch_application_map

_XML = b'''<controllertemplate version="1.0" type="Modbus">
<point pointid="synthetic.point" name="Test temperature" pointtype="6"
registertype="Holding" addressformat="S32" addressindex="201" decimals="1" scaling="10"/>
</controllertemplate>'''


class FakeFTP:
    calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def connect(self, host, port, timeout):
        self.calls.append(("connect", host, port, timeout))

    def login(self, user, passwd):
        self.calls.append(("login", user, passwd))

    def cwd(self, directory):
        self.calls.append(("cwd", directory))

    def retrbinary(self, cmd, callback, blocksize=8192):
        self.calls.append(("retrbinary", cmd))
        if cmd == "RETR deviceversion.txt":
            callback(b"2.3.3\n")
        elif cmd == "RETR ounetDescrFile_fi-FI.xml":
            callback(_XML)
        else:
            raise AssertionError(cmd)


class FtpAutoloadTests(unittest.TestCase):
    def setUp(self):
        FakeFTP.calls = []

    def test_import_reads_only_two_documented_files(self):
        with patch("custom_components.ouman_ouflex.ftp_map.ftplib.FTP", FakeFTP):
            doc = fetch_application_map("192.168.10.105")
        self.assertEqual(doc["identity"]["firmware"], "2.3.3")
        self.assertEqual(len(doc["points"]), 1)
        self.assertEqual(doc["points"][0]["access"], "R")
        self.assertEqual([x[1] for x in FakeFTP.calls if x[0] == "retrbinary"],
                         ["RETR deviceversion.txt", "RETR ounetDescrFile_fi-FI.xml"])
        self.assertIn(("cwd", "/files"), FakeFTP.calls)

    def test_non_lan_address_refused_before_ftp(self):
        with patch("custom_components.ouman_ouflex.ftp_map.ftplib.FTP") as client:
            for host in ("127.0.0.1", "8.8.8.8", "example.com"):
                with self.assertRaises(ValueError):
                    fetch_application_map(host)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
