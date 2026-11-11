"""Read-only archive boundaries and corruption detection; no hardware required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('archive', Path(__file__).resolve().parents[1]/'tools/ouflex_archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class ArchiveTests(unittest.TestCase):
    def test_reject_write_and_out_of_range_plans(self):
        valid = dict(port=502, unit=1, function=3, address=0, count=1)
        self.assertEqual(archive.validate_plan([valid]), [valid])
        for field, value in [('function', 16), ('unit', 0), ('address', -1),
                             ('count', 65536), ('port', 80), ('count', True)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                archive.validate_plan([{**valid, field: value}])
        with self.assertRaises(ValueError):
            archive.validate_plan([{**valid, 'command': 'erase'}])

    def test_corruption_missing_and_extra_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root/'data'
            data.write_bytes(b'\x00\xfforiginal')
            archive.store(root, 'manifest.json', {'files': {'data': {
                'bytes': data.stat().st_size, 'sha256': archive.digest(data)}}})
            self.assertTrue(archive.verify(root)['integrity_ok'])
            data.write_bytes(b'\x00\xffmodified')
            self.assertFalse(archive.verify(root)['integrity_ok'])
            data.unlink()
            self.assertFalse(archive.verify(root)['integrity_ok'])
            (root/'extra').write_text('extra')
            self.assertIn('extra', archive.verify(root)['errors'])

    def test_ftp_binary_and_traversal(self):
        class FTP:
            name = 'firmware.bin'
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def connect(self, *args, **kwargs): pass
            def login(self, *args): pass
            def mlsd(self, path):
                return iter([(self.name, {'type': 'file', 'size': '3'})])
            def retrbinary(self, command, callback):
                self.command = command
                callback(b'\x00\xff\x80')
        with tempfile.TemporaryDirectory() as d, patch.object(archive.ftplib, 'FTP', FTP):
            root = Path(d)
            result = archive.ftp_archive(root, 'test', 'user', 'password')
            self.assertTrue(result['complete'])
            self.assertEqual((root/'ftp/firmware.bin').read_bytes(), b'\x00\xff\x80')
            FTP.name = '../escape'
            result = archive.ftp_archive(root, 'test', 'user', 'password')
            self.assertFalse(result['complete'])
            self.assertFalse((root/'escape').exists())

    def test_ftp_size_budget(self):
        class FTP:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def connect(self, *args, **kwargs): pass
            def login(self, *args): pass
            def mlsd(self, path): return iter([('huge', {'type': 'file', 'size': '999'})])
            def retrbinary(self, *args): raise AssertionError('Must reject before retrieval')
        with tempfile.TemporaryDirectory() as d, patch.object(archive.ftplib, 'FTP', FTP):
            result = archive.ftp_archive(Path(d), 'test', 'user', 'pass', max_bytes=10)
            self.assertFalse(result['complete'])
            self.assertEqual(result['bytes_received'], 0)

    def test_manifest_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            archive.store(root, 'manifest.json', {'files': {'../outside': {'bytes': 0, 'sha256': ''}}})
            self.assertIn('../outside', archive.verify(root)['errors'])


if __name__ == '__main__':
    unittest.main()
