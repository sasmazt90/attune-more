"""Finite, credential-free QA access to one real vehicle read; disabled by default."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import isfinite
from time import monotonic
from typing import Callable, Mapping

from starlette.requests import Request

QA_VEHICLE_ORIGIN = "http://127.0.0.1:3447"
QA_VEHICLE_PATH = "/api/vehicle/state"
MAX_LEASE_SECONDS = 45 * 60


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QAVehicleReadPolicy:
    enabled: bool = False
    expires_at: datetime | None = None
    monotonic_deadline: float = 0.0
    utc_clock: Callable[[], datetime] = field(default=_utc_now, repr=False)
    monotonic_clock: Callable[[], float] = field(default=monotonic, repr=False)

    @classmethod
    def from_environment(cls, env: Mapping[str, str], *, utc_clock=_utc_now,
                         monotonic_clock=monotonic):
        """Snapshot startup configuration; invalid or partial opt-in stays off."""
        disabled = cls(utc_clock=utc_clock, monotonic_clock=monotonic_clock)
        if env.get("ATTUNE_QA_VEHICLE_READ_ORIGIN") != QA_VEHICLE_ORIGIN:
            return disabled
        try:
            raw = env["ATTUNE_QA_VEHICLE_READ_EXPIRES_UTC"]
            expiry = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
            if expiry.tzinfo is None or expiry.utcoffset() != timedelta(0):
                return disabled
            remaining = (expiry - utc_clock()).total_seconds()
            tick = monotonic_clock()
            if not 0 < remaining <= MAX_LEASE_SECONDS or not isfinite(tick):
                return disabled
        except (KeyError, TypeError, ValueError, OverflowError):
            return disabled
        return cls(True, expiry, tick + remaining, utc_clock, monotonic_clock)

    def active(self):
        # A wall-clock rollback cannot extend the startup monotonic deadline.
        try:
            return bool(self.enabled and self.expires_at is not None
                        and self.utc_clock() < self.expires_at
                        and self.monotonic_clock() < self.monotonic_deadline)
        except (TypeError, ValueError, OverflowError):
            return False

    async def authorizes(self, request: Request):
        if not self.active() or request.method != "GET":
            return False
        if (request.url.path != QA_VEHICLE_PATH
                or request.scope.get("raw_path") != QA_VEHICLE_PATH.encode("ascii")
                or request.scope.get("query_string")):
            return False
        headers = [(name.lower(), value) for name, value in request.scope["headers"]]
        origins = [value for name, value in headers if name == b"origin"]
        if origins != [QA_VEHICLE_ORIGIN.encode("ascii")]:
            return False
        if any(name in (b"cookie", b"authorization", b"proxy-authorization",
                        b"transfer-encoding") for name, _ in headers):
            return False
        lengths = [value for name, value in headers if name == b"content-length"]
        if lengths not in ([], [b"0"]):
            return False
        # Do not accumulate an untrusted body or accept an undeclared/chunked one.
        try:
            async for chunk in request.stream():
                if chunk:
                    return False
        except Exception:
            return False
        return self.active()
