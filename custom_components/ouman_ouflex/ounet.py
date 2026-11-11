"""Adapter for observed Ounet controllertemplate XML, not arbitrary vendor XML.

Address indices are documented one-based. Access levels are retained as evidence,
never translated into authorization. Calendar structures remain raw read ranges.
No targetdetails (site/person/address) are exported.
"""
from dataclasses import asdict
import hashlib
import xml.etree.ElementTree as ET

from .pointmap import Point, load_map
import json


def import_ounet(text, *, firmware, source='FTP /files/ounetDescrFile_fi-FI.xml'):
    if len(text) > 10_000_000 or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('Oversized or unsafe XML')
    try:
        root = ET.fromstring(text.lstrip('\ufeff'))
    except ET.ParseError as err:
        raise ValueError('Malformed Ounet XML') from err
    if root.tag != 'controllertemplate' or root.get('type') != 'Modbus':
        raise ValueError('Unsupported Ounet schema')
    rows, rejected, ranges = [], [], []
    for el in root.iter('point'):
        a = el.attrib
        try:
            address = int(a['addressindex'])
            kind = a.get('addressformat', '').lower()
            if a.get('pointtype') in ('15', '16', '17'):
                count = int(a['addressmultiple'])
                if count != 120 or not 1 <= address <= 65537-count:
                    raise ValueError('Unsupported calendar range')
                ranges.append(dict(address=address, address_base=1, count=count,
                                   name=a['name'], pointtype=a['pointtype']))
                continue
            alarm = a.get('pointtype') == '14'
            if alarm:
                # Explicit packed alarm masks establish a 16-bit holding word.
                if a.get('mask') != '1' or a.get('addressackmask') != '2':
                    raise ValueError('Unsupported alarm layout')
                kind = 'u16'
            elif a.get('registertype') != 'Holding':
                raise ValueError('Unsupported register area')
            enums = {}
            for item in a.get('enum', '').split(';'):
                if item:
                    key, label = item.split('=', 1)
                    enums[str(int(key))] = label
            decimals = int(a.get('decimals', '0'))
            scaling = int(a.get('scaling', str(10**decimals)))
            if scaling != 10**decimals and not (decimals == 0 and scaling == 0):
                raise ValueError('Scaling contradicts decimals')
            entity = 'alarm' if alarm else ('binary_sensor' if
                     a.get('pointtype') in ('8', '9', '11') and set(enums) == {'0', '1'}
                     else 'sensor')
            metadata = {'pointtype': a.get('pointtype'),
                        'read_access_level': a.get('readacceslevel'),
                        'write_access_level': a.get('writeacceslevel'),
                        'write_authorized': False}
            if alarm:
                metadata['operation'] = 'alarm_state'
                metadata['alarm_masks'] = {k: int(a[v]) for k, v in {
                    'active': 'mask', 'unacknowledged': 'addressackmask',
                    'priority': 'addressprioritymask', 'group': 'addressgroupmask'}.items()}
                metadata['ack_register'] = int(a['ackindex'])
                metadata['transfer_ack_register'] = int(a['transferackindex'])
                metadata['ack_value'] = int(a['ackvalue'])
            children = [c for c in el if c.tag == 'point' and c.get('pointtype') == '5']
            manual = int(children[0].get('addressindex')) if len(children) == 1 else None
            # Stable hashed vendor identity avoids illegal dotted keys and site IDs.
            key = 'p_' + hashlib.sha256(a['pointid'].encode()).hexdigest()[:20]
            rows.append(asdict(Point(key, a['name'], address, 1, kind,
                decimals=decimals, unit=a.get('unit'),
                minimum=float(a['min']) if 'min' in a else None,
                maximum=float(a['max']) if 'max' in a else None,
                enums=enums, manual_reg=manual, entity=entity,
                source=source, metadata=metadata)))
        except (KeyError, ValueError, TypeError) as err:
            rejected.append({'address': a.get('addressindex'), 'error': str(err)})
    doc = dict(schema_version=1, identity={'model': 'Ouflex', 'firmware': firmware,
               'application': root.get('version', '')}, points=rows,
               source=source, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
               rejected_rows=rejected, structured_read_ranges=ranges,
               imported_permissions_only=True)
    load_map(json.dumps(doc))
    return doc
