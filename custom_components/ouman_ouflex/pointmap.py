"""Strict normalized map plus explicit-field CSV/XML adapters.

Vendor schemas vary. Unknown fields are retained, never interpreted as addresses.
Imported permissions describe documentation, not a verified write authorization.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from decimal import Decimal

from .modbus import address_offset


@dataclass(frozen=True)
class Point:
    key: str
    name: str
    address: int
    address_base: int
    kind: str
    area: str = 'holding'
    decimals: int = 0
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    access: str = 'R'
    entity: str = 'sensor'
    enums: dict = field(default_factory=dict)
    manual_reg: int | None = None
    source: str = ''
    byte_order: str = 'big'
    word_order: str = 'big'
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}', self.key):
            raise ValueError('Invalid point key')
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 200:
            raise ValueError('Invalid name')
        if self.kind not in ('u16', 's16', 'u32', 's32'):
            raise ValueError('Explicit U16/S16/U32/S32 type required')
        address_offset(self.address, self.address_base, self.count)
        if self.area not in ('holding', 'input') or self.access not in ('R', 'RW'):
            raise ValueError('Invalid register area/access')
        if self.area == 'input' and self.access != 'R':
            raise ValueError('Input registers are read-only')
        if type(self.decimals) is not int or not 0 <= self.decimals <= 6:
            raise ValueError('Decimals outside 0..6')
        if self.byte_order not in ('big', 'little') or self.word_order not in ('big', 'little'):
            raise ValueError('Invalid byte/word order')
        if self.entity not in ('sensor', 'binary_sensor', 'alarm', 'number', 'select', 'switch'):
            raise ValueError('Unknown entity type')
        for v in (self.minimum, self.maximum):
            if v is not None and (type(v) not in (int, float) or not math.isfinite(v)):
                raise ValueError('Bounds must be finite')
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Reversed bounds')
        if self.manual_reg is not None:
            address_offset(self.manual_reg, self.address_base)
        if not isinstance(self.enums, dict) or any(not isinstance(v, str) for v in self.enums.values()):
            raise ValueError('Enums must map integer strings to labels')
        for k in self.enums:
            if str(int(k)) != k:
                raise ValueError('Enum keys must be canonical integer strings')
        if len(set(self.enums.values())) != len(self.enums):
            raise ValueError('Enum labels must be unique')
        if self.entity == 'select' and not self.enums:
            raise ValueError('Select requires explicit enum values')
        if ((self.entity == 'alarm' and self.count != 1) or
            (self.entity in ('alarm', 'binary_sensor', 'switch') and self.decimals)):
            raise ValueError('Binary/alarm entities require unscaled 16-bit data')

    @property
    def count(self):
        return 2 if self.kind.endswith('32') else 1

    @property
    def offset(self):
        return address_offset(self.address, self.address_base, self.count)

    @property
    def function(self):
        return 3 if self.area == 'holding' else 4


def decode(words, point):
    if len(words) != point.count or any(type(w) is not int or not 0 <= w <= 65535 for w in words):
        raise ValueError('Incorrect register words')
    data = [w.to_bytes(2, point.byte_order) for w in words]
    if point.word_order == 'little':
        data.reverse()
    raw = int.from_bytes(b''.join(data), 'big', signed=point.kind.startswith('s'))
    return raw / (10 ** point.decimals)


def encode(value, point):
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError('Nonfinite value')
    if point.minimum is None or point.maximum is None:
        raise ValueError('Documented bounds required')
    if not Decimal(str(point.minimum)) <= value <= Decimal(str(point.maximum)):
        raise ValueError('Value outside documented bounds')
    scaled = value * 10**point.decimals
    if scaled != scaled.to_integral_value():
        raise ValueError('Unsupported precision')
    if point.enums and str(int(value)) not in point.enums:
        raise ValueError('Value absent from enum')
    if point.entity in ('switch', 'binary_sensor') and value not in (0, 1):
        raise ValueError('Binary value must be 0 or 1')
    try:
        raw = int(scaled).to_bytes(point.count*2, 'big', signed=point.kind.startswith('s'))
    except OverflowError as err:
        raise ValueError('Register overflow') from err
    words = [int.from_bytes(raw[i:i+2], point.byte_order) for i in range(0, len(raw), 2)]
    return words[::-1] if point.word_order == 'little' else words


def alarm_state(value, masks=None):
    value = int(value)
    if masks is not None:
        if set(masks) != {'active', 'unacknowledged', 'priority', 'group'} or any(
                type(m) is not int or not 0 < m <= 65535 for m in masks.values()):
            raise ValueError('Invalid documented alarm masks')
        def field(mask):
            return (value & mask) >> ((mask & -mask).bit_length()-1)
        return dict(raw=value, active=bool(value & masks['active']),
                    unacknowledged=bool(value & masks['unacknowledged']),
                    priority=field(masks['priority']), group=field(masks['group']))
    return dict(active=bool(value & 1), unacknowledged=bool(value & 2),
                priority=(value >> 2) & 7, group=(value >> 5) & 7,
                raw=value, note='Group field is only three bits in YM0105; groups 8..10 need confirmation')


def load_map(text):
    doc = json.loads(text)
    if doc.get('schema_version') != 1 or not isinstance(doc.get('identity'), dict):
        raise ValueError('Map schema_version=1 and identity object required')
    if not all(isinstance(doc['identity'].get(k), str) and doc['identity'][k].strip()
               for k in ('model', 'firmware', 'application')):
        raise ValueError('Explicit model, firmware and application identity required')
    rows = doc.get('points')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise ValueError('Map must contain 1..4096 points')
    points = [Point(**p) for p in rows]
    if len({p.key for p in points}) != len(points):
        raise ValueError('Duplicate point key')
    doc['points'] = [asdict(p) for p in points]
    return doc, points


def map_digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


# Only explicit columns; never infer a register from an unrelated ID.
ALIASES = {
    'technicalname': 'key', 'description': 'name', 'modbusreg': 'address',
    'registertype': 'area', 'addressformat': 'kind', 'desimals': 'decimals',
    'min': 'minimum', 'max': 'maximum', 'rw': 'access', 'manualreg': 'manual_reg',
}


def import_rows(text, format, *, identity, address_base, source):
    if format == 'json':
        return load_map(text)[0]
    if len(text) > 10_000_000:
        raise ValueError('Description file too large')
    rows = []
    if format == 'csv':
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=',;\t')
        rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    elif format == 'xml':
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError('XML DTD/entities forbidden')
        root = ET.fromstring(text)
        # Supported flat Point/Register rows, attributes or direct scalar children.
        for el in root.iter():
            tag = el.tag.rsplit('}', 1)[-1].lower()
            if tag not in ('point', 'register'):
                continue
            row = dict(el.attrib)
            row.update({c.tag.rsplit('}', 1)[-1]: c.text or '' for c in el if not list(c)})
            rows.append(row)
    else:
        raise ValueError('Expected json, csv or xml')
    if not rows:
        raise ValueError('No supported rows: vendor XML schema requires an explicit adapter')
    points, rejected = [], []
    fields = set(Point.__dataclass_fields__)
    for index, row in enumerate(rows):
        try:
            normalized, extras = {}, {}
            for k, v in row.items():
                key = re.sub('[^a-z0-9_]', '', str(k).lower())
                key = ALIASES.get(key, key)
                if key in fields:
                    normalized[key] = v
                else:
                    extras[str(k)] = v
            # Address base is an operator decision, never imported silently.
            normalized.update(address_base=address_base, source=source, metadata={'source_row': row, 'extra': extras})
            for k in ('address', 'decimals', 'manual_reg'):
                if k in normalized:
                    if str(normalized[k]).strip():
                        normalized[k] = int(normalized[k])
                    else:
                        normalized.pop(k)
            for k in ('minimum', 'maximum'):
                if k in normalized:
                    normalized[k] = float(str(normalized[k]).replace(',', '.')) if str(normalized[k]).strip() else None
            if 'kind' in normalized:
                normalized['kind'] = normalized['kind'].lower()
            if 'area' in normalized:
                normalized['area'] = {'holding register': 'holding', 'input register': 'input'}.get(normalized['area'].lower(), normalized['area'].lower())
            if 'access' in normalized:
                normalized['access'] = normalized['access'].upper().replace('/', '').replace(' ', '')
            if 'enums' in normalized and isinstance(normalized['enums'], str):
                normalized['enums'] = json.loads(normalized['enums']) if normalized['enums'].strip() else {}
            points.append(asdict(Point(**normalized)))
        except (TypeError, ValueError) as err:
            rejected.append(dict(row=index+1, error=str(err), original=row))
    doc = dict(schema_version=1, identity=identity, points=points,
               source=source, rejected_rows=rejected, imported_permissions_only=True)
    if not points:
        raise ValueError('No valid explicitly addressed points: ' + json.dumps(rejected, ensure_ascii=False))
    load_map(json.dumps(doc))
    return doc
