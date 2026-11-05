"""Serial local transport and read-confirmed single-parameter transactions."""

from __future__ import annotations

import base64
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .protocol import (
    COMMAND_DP,
    Collector,
    Field,
    Headers,
    MangoCancelled,
    MangoError,
    MangoProfileError,
    MangoReadError,
    Parameter,
    Profile,
    Snapshot,
    common_temperatures,
    read_frame,
    write_frame,
)


@dataclass(frozen=True)
class ChangeResult:
    parameter_key: str
    original: int
    requested: int
    snapshot: Snapshot
    changed: bool


class MangoWriteError(MangoError):
    def __init__(
        self,
        reason: str,
        parameter: Parameter,
        original: int,
        requested: int,
        restored: bool,
        snapshot: Snapshot | None,
    ):
        super().__init__(reason)
        self.parameter_key, self.original, self.requested = parameter.key, original, requested
        self.restored, self.snapshot = restored, snapshot


class MangoClient:
    def __init__(
        self,
        host: str,
        device_id: str,
        local_key: str,
        profile: Profile,
        *,
        device_factory: Callable[..., Any] | None = None,
        clock=time.monotonic,
        wall_clock=time.time,
        pause=time.sleep,
        header_factory=None,
    ):
        self.host, self.device_id, self._local_key, self.profile = host, device_id, local_key, profile
        self.device_factory = device_factory
        self.clock, self.wall_clock, self.pause = clock, wall_clock, pause
        self.headers = Headers() if header_factory is None else Headers(header_factory)
        self._device = None
        self._lock = threading.RLock()
        self._closed = False
        self.temperatures: dict[str, float] = {}
        self.temperature_received_at = 0.0
        self.verified_writes: set[str] = set()
        self.last_operation: dict[str, Any] | None = None
        self.last_status_received_at = 0.0
        self.last_transport_error: str | None = None
        self.status_reconnects = 0

    def _status_response(self) -> None:
        """Wait for data after an ACK; never treat an ACK as fresh telemetry."""
        self._device.set_socketTimeout(3)
        deadline = self.clock() + 8
        try:
            response = self._device.status()
            for _ in range(8):
                if isinstance(response, dict):
                    if "Error" in response or "Err" in response:
                        code = str(response.get("Err", ""))
                        safe_code = (
                            code if len(code) == 3 and code.isascii() and code.isdigit() else "unknown"
                        )
                        raise MangoReadError(f"status_error_{safe_code}")
                    if isinstance(response.get("dps"), dict):
                        self._record_telemetry(response)
                        self.last_status_received_at = self.wall_clock()
                        self.last_transport_error = None
                        return
                if self.clock() >= deadline:
                    break
                response = self._device.receive()
            raise MangoReadError("status_data_timeout")
        finally:
            self._device.set_socketTimeout(1)

    def _record_telemetry(self, message: Any) -> None:
        if isinstance(message, dict) and isinstance(message.get("dps"), dict):
            decoded = common_temperatures({str(k): v for k, v in message["dps"].items() if str(k) == "105"})
            if decoded:
                self.temperatures = decoded
                self.temperature_received_at = self.wall_clock()

    def _connect(self) -> None:
        if self._closed:
            raise MangoReadError("client_closed")
        if self._device is not None:
            return
        factory = self.device_factory
        if factory is None:
            import tinytuya

            factory = tinytuya.Device
        try:
            self._device = factory(
                self.device_id,
                self.host,
                self._local_key,
                version=3.5,
                persist=True,
                connection_timeout=3,
                connection_retry_limit=1,
            )
            self._status_response()
        except Exception as error:
            self.last_transport_error = (
                str(error) if isinstance(error, MangoReadError) else "status_transport_exception"
            )
            self._disconnect()
            raise MangoReadError(self.last_transport_error) from None

    def _disconnect(self) -> None:
        if self._device is not None:
            try:
                self._device.close()
            except Exception:
                pass
        self._device = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._disconnect()

    def status(self) -> None:
        with self._lock:
            for attempt in range(2):
                try:
                    if self._device is None:
                        self._connect()
                    else:
                        self._status_response()
                    return
                except Exception as error:
                    self.last_transport_error = (
                        str(error) if isinstance(error, MangoReadError) else "status_transport_exception"
                    )
                    self._disconnect()
                    if self._closed or attempt == 1:
                        raise MangoReadError(self.last_transport_error) from None
                    self.status_reconnects += 1
                    self.pause(0.2)

    def _read_once(self, group: int) -> Snapshot:
        self._connect()
        raw = read_frame(self.headers.new(), group)
        collector = Collector(raw[1:4], self.profile.sections[group])
        deadline = self.clock() + 8
        try:
            response = self._device.set_value(COMMAND_DP, base64.b64encode(raw).decode("ascii"), nowait=True)
            for _ in range(1024):
                if isinstance(response, dict) and "Error" in response:
                    raise MangoReadError("local_receive_failed")
                self._record_telemetry(response)
                collector.record(response, self.wall_clock())
                if collector.complete or self.clock() >= deadline:
                    break
                response = self._device.receive()
                if response is None:
                    self.pause(0.05)
        except Exception:
            self._disconnect()
            raise MangoReadError("matching_read_failed") from None
        return collector.result()

    def _read(
        self,
        group: int,
        *,
        parameter: Parameter | None = None,
        value: int | None = None,
        metadata: Field | None = None,
        attempts: int = 2,
        abort: threading.Event | None = None,
    ) -> Snapshot:
        for attempt in range(attempts):
            if abort is not None and abort.is_set():
                raise MangoCancelled("transaction_cancelled")
            try:
                snapshot = self._read_once(group)
            except MangoReadError:
                if attempt + 1 == attempts:
                    raise
            else:
                if parameter is None:
                    return snapshot
                field = snapshot.field(parameter)
                if metadata is not None and not field.same_metadata(metadata):
                    raise MangoProfileError("fresh_parameter_metadata_changed")
                if value is None or field.value == value:
                    return snapshot
                if attempt + 1 == attempts:
                    raise MangoReadError("target_not_in_fresh_readback")
            self.pause(0.2)
        raise MangoReadError("matching_read_unavailable")

    def read_group(self, group: int) -> Snapshot:
        with self._lock:
            if type(group) is not int or group not in self.profile.sections:
                raise MangoProfileError("unknown_parameter_group")
            return self._read(group)

    def validate_profile(self) -> None:
        """Only read anchor groups; never send an OP4 validation write."""
        with self._lock:
            self._read(14)
            self._read(0)

    def _send_write(self, parameter: Parameter, field: Field, value: int) -> None:
        raw = write_frame(self.headers.new(), parameter, field, value)
        self._connect()
        try:
            response = self._device.set_value(COMMAND_DP, base64.b64encode(raw).decode("ascii"), nowait=True)
            if isinstance(response, dict) and "Error" in response:
                raise MangoError("parameter_send_failed")
        except Exception:
            self._disconnect()
            raise MangoError("parameter_send_failed") from None

    def set_raw(
        self, parameter: Parameter, requested: int, abort: threading.Event | None = None
    ) -> ChangeResult:
        with self._lock:
            if self.profile.parameter(parameter.group, parameter.slot) != parameter:
                raise MangoProfileError("parameter_route_mismatch")
            before = self._read(parameter.group, parameter=parameter, attempts=3, abort=abort)
            field = before.field(parameter)
            if (parameter.scale_verified or parameter.key in self.profile.known_select_options) and (
                field.flags != parameter.flags or field.tag != parameter.tag
            ):
                raise MangoProfileError("known_scale_or_option_metadata_changed")
            field.validate(field.value)
            field.validate(requested)
            operation = {
                "parameter": parameter.key,
                "original_raw": field.value,
                "requested_raw": requested,
                "write_attempted": False,
                "write_verified": False,
                "restore_verified": False,
            }
            self.last_operation = operation
            if requested == field.value:
                operation["already_at_target"] = True
                return ChangeResult(parameter.key, field.value, requested, before, False)
            if abort is not None and abort.is_set():
                raise MangoCancelled("transaction_cancelled")
            attempted = False
            try:
                # Set this before sending: an exception may occur after delivery.
                attempted = True
                operation["write_attempted"] = True
                self._send_write(parameter, field, requested)
                after = self._read(
                    parameter.group, parameter=parameter, value=requested, metadata=field, abort=abort
                )
                if abort is not None and abort.is_set():
                    raise MangoCancelled("transaction_cancelled")
            except (Exception, KeyboardInterrupt) as error:
                restored, recovery = False, None
                if attempted:
                    for _ in range(2):
                        try:
                            self._send_write(parameter, field, field.value)
                            recovery = self._read(
                                parameter.group, parameter=parameter, value=field.value, metadata=field
                            )
                            restored = True
                            break
                        except Exception, KeyboardInterrupt:
                            pass
                operation["restore_verified"] = restored
                operation["failure_code"] = (
                    str(error) if isinstance(error, MangoError) else type(error).__name__
                )
                raise MangoWriteError(
                    "write_failed_original_restored" if restored else "write_failed_restore_unconfirmed",
                    parameter,
                    field.value,
                    requested,
                    restored,
                    recovery,
                ) from None
            operation["write_verified"] = True
            self.verified_writes.add(parameter.key)
            return ChangeResult(parameter.key, field.value, requested, after, True)
