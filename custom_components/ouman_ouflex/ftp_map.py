"""Read-only, size-bounded local Ouflex Ounet map acquisition.

FTP is used only for anonymous RETR of two documented device files.
No site-specific raw XML or credentials are stored in the repository.
"""
from __future__ import annotations

import ftplib
import ipaddress

from .ounet import import_ounet

_MAX_XML = 2_000_000
_MAX_VERSION = 128


def _get_file(ftp: ftplib.FTP, name: str, limit: int) -> bytes:
    result = bytearray()

    def add(chunk: bytes) -> None:
        if len(result) + len(chunk) > limit:
            raise ValueError("Ouflex FTP file exceeds allowed size")
        result.extend(chunk)

    ftp.retrbinary("RETR " + name, add, blocksize=8192)
    return bytes(result)


def fetch_application_map(host: str) -> dict:
    """Retrieve /deviceversion.txt and /files/ounetDescrFile_fi-FI.xml.

    Only private, non-loopback IPv4 hosts are accepted. The caller must run
    this in an executor; Home Assistant's event loop must not be blocked.
    """
    try:
        ip = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError as err:
        raise ValueError("Ouflex automatic FTP import requires a LAN IPv4 address") from err
    if not ip.is_private or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        raise ValueError("Automatic Ouflex FTP import is restricted to private LAN IPv4")

    with ftplib.FTP() as ftp:
        ftp.connect(str(ip), 21, timeout=5)
        ftp.login(user="anonymous", passwd="")
        firmware = _get_file(ftp, "deviceversion.txt", _MAX_VERSION).decode("ascii").strip()
        if not firmware or any(ord(c) < 32 for c in firmware):
            raise ValueError("Invalid firmware version from deviceversion.txt")
        ftp.cwd("/files")
        xml = _get_file(ftp, "ounetDescrFile_fi-FI.xml", _MAX_XML)

    doc = import_ounet(xml.decode("utf-8-sig"), firmware=firmware)
    count = len(doc["points"])
    if not 1 <= count <= 256:
        raise ValueError("Home Assistant supports 1..256 Ouflex points per entry")
    return doc
