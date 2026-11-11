"""Allowlisted write transactions with durable intent and raw rollback."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from .pointmap import encode, decode, map_digest


class Session:
    def __init__(self, client, doc, points, policy=None, enabled=False, physical=False):
        self.client, self.doc = client, doc
        self.points = {p.key: p for p in points}
        self.policy, self.enabled, self.physical = policy or {}, enabled, physical
        self.audit_errors = []

    def point(self, key):
        if key not in self.points:
            raise ValueError('Point absent from imported map')
        return self.points[key]

    def read(self, key):
        p = self.point(key)
        raw = self.client.read(p.offset, p.count, p.function, name=p.name, datatype=p.kind, decoder=lambda raw: decode(raw, p))
        return raw, decode(raw, p)

    def permitted(self, key, require_physical=False):
        p = self.point(key)
        identity = self.doc['identity']
        if not self.enabled or self.policy.get('map_sha256') != map_digest(self.doc):
            raise ValueError('Writes disabled or policy does not match exact map digest')
        if self.policy.get('identity') != identity:
            raise ValueError('Write policy identity mismatch')
        evidence = self.policy.get('points', {}).get(key, {})
        if not evidence.get('documentation') or not evidence.get('reviewed_by'):
            raise ValueError('Point requires documentation and reviewer in separate policy')
        if (require_physical or self.physical) and evidence.get('physically_verified') is not True:
            raise ValueError('Point has no physical verification in policy')
        if p.access != 'RW' or p.area != 'holding' or not p.source:
            raise ValueError('Point is not documented writable holding data')
        if p.minimum is None or p.maximum is None:
            raise ValueError('Write bounds missing')
        # Ack, calendar, firmware, destructive commands require separate semantics,
        # not value restoration. Never use the generic control transaction for them.
        if p.metadata.get('operation', 'value') != 'value':
            raise ValueError('Command/event register requires a dedicated adapter')
        return p

    def _journal(self, phase, **data):
        if not self.client.audit:
            raise ValueError('Persistent audit callback required for writes')
        self.client.audit(dict(timestamp=datetime.now(timezone.utc).isoformat(),
                               operation='write_transaction', phase=phase,
                               ip=self.client.host, port=self.client.port,
                               unit_id=self.client.unit, **data))

    def _put(self, p, words, function, phase):
        original_audit = self.client.audit
        restoring = phase.startswith('restore_')
        if restoring:
            # The original snapshot was durable before testing. Even if storage
            # fails later, attempt this idempotent raw restoration and read-back.
            def recovery_audit(event):
                try:
                    if original_audit:
                        original_audit(event)
                except Exception as err:
                    self.audit_errors.append(str(err))
            self.client.audit = recovery_audit
        try:
            self._journal(phase, point_name=p.name, address=p.offset, words=words,
                          function_code=function, datatype=p.kind)
            self.client.write(p.offset, words, function, name=p.name, datatype=p.kind, value=decode(words, p))
            actual = self.client.read(p.offset, p.count, p.function, name=p.name, datatype=p.kind, decoder=lambda raw: decode(raw, p))
            if actual != words:
                raise ValueError('Raw read-back mismatch: %r != %r' % (actual, words))
            self._journal(phase + '_confirmed', raw=actual, interpreted=decode(actual, p), point_name=p.name)
        finally:
            self.client.audit = original_audit

    def write(self, key, value, function=16):
        p = self.permitted(key)
        if p.manual_reg is not None:
            raise ValueError('Manual-mode point: use isolated write-test transaction')
        words = encode(value, p)
        if function == 6 and p.count != 1:
            raise ValueError('32-bit values require atomic FC16')
        original, original_value = self.read(key)
        if encode(original_value, p) != original:
            raise ValueError('Original value does not match documented representation')
        self._journal('original', key=key, raw=original)
        self._put(p, words, function, 'write')
        return dict(key=key, success=True, raw=words, interpreted=decode(words, p))

    def write_test(self, key, value, function=16, disconnected=False, display_note=None, observer=None):
        if not disconnected:
            raise ValueError('Physical disconnection confirmation required')
        p = self.permitted(key)
        words = encode(value, p)
        if function == 6 and p.count != 1:
            raise ValueError('32-bit values require atomic FC16')
        original, original_value = self.read(key)
        if encode(original_value, p) != original:
            raise ValueError('Original value does not match documented representation')
        manual_original, manual = None, None
        if p.manual_reg is not None:
            # Separate point, independently documented/reviewed in the policy.
            candidates = [m for m in self.points.values() if m.address == p.manual_reg
                          and m.address_base == p.address_base and m.area == 'holding']
            if len(candidates) != 1:
                raise ValueError('Manual register must be one explicit mapped point')
            manual = self.permitted(candidates[0].key)
            if manual.count != 1 or manual.manual_reg is not None:
                raise ValueError('Unsupported manual register shape')
            encode(1, manual)
            manual_original, manual_value = self.read(manual.key)
            if encode(manual_value, manual) != manual_original:
                raise ValueError('Original manual mode does not match documented representation')
        self.audit_errors.clear()
        result = dict(key=key, original=original, original_value=original_value,
                      requested=value, test_confirmed=False, restored=False,
                      display_comparison=display_note or 'not performed', errors=[])
        self._journal('test_original', **result, manual_original=manual_original)
        # Mark attempts before network send: a timeout may follow a successful write.
        value_attempted = manual_attempted = False
        try:
            if manual:
                manual_attempted = True
                self._put(manual, encode(1, manual), 6, 'manual_enable')
            value_attempted = True
            self._put(p, words, function, 'test_write')
            result['test_confirmed'] = True
            if observer is not None:
                result['display_comparison'] = observer(dict(result)) or 'not performed'
                self._journal('display_observation', observation=result['display_comparison'], key=key)
        except Exception as err:
            result['errors'].append(str(err))
        finally:
            value_restored = not value_attempted
            manual_restored = not manual_attempted
            if value_attempted:
                try:
                    self._put(p, original, function, 'restore_value')
                    value_restored = True
                except Exception as err:
                    result['errors'].append('RESTORE VALUE FAILED: ' + str(err))
            if manual_attempted:
                try:
                    self._put(manual, manual_original, 6, 'restore_manual')
                    manual_restored = True
                except Exception as err:
                    result['errors'].append('RESTORE MANUAL FAILED: ' + str(err))
            result['restored'] = value_restored and manual_restored
            result['success'] = result['test_confirmed'] and result['restored'] and not result['errors']
            result['audit_errors'] = list(self.audit_errors)
            if self.audit_errors:
                result['success'] = False
            try:
                self._journal('test_complete', **result)
            except Exception as err:
                result['errors'].append('Final audit failed: ' + str(err))
                result['success'] = False
        return result
