"""In-process real handler + finite QA origin boundary; never contacts port8311."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services/core-api"))
import main
from qa_vehicle_read import MAX_LEASE_SECONDS, QA_VEHICLE_ORIGIN, QAVehicleReadPolicy

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
NORMAL = "http://127.0.0.1:3000"
EVIDENCE = []


class Clock:
    utc = NOW
    tick = 100.0

    def policy(self, env=None):
        if env is None:
            env = {"ATTUNE_QA_VEHICLE_READ_ORIGIN": QA_VEHICLE_ORIGIN,
                   "ATTUNE_QA_VEHICLE_READ_EXPIRES_UTC": (NOW + timedelta(minutes=45)).isoformat()}
        return QAVehicleReadPolicy.from_environment(
            env, utc_clock=lambda: self.utc, monotonic_clock=lambda: self.tick)


@pytest.fixture(autouse=True)
def isolated_policy(monkeypatch):
    before = dict(main.vehicle_state)
    monkeypatch.setattr(main, "qa_vehicle_read_policy", QAVehicleReadPolicy())
    yield
    main.vehicle_state.clear()
    main.vehicle_state.update(before)


@pytest.fixture(scope="session", autouse=True)
def write_evidence():
    yield
    target = os.getenv("ATTUNE_QA_POLICY_TEST_EVIDENCE")
    if target:
        path = Path(target)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"scope": "in-process policy/real handler; no live API or browser acceptance",
                                    "rows": EVIDENCE}, indent=2), encoding="utf-8")
        temp.replace(path)


def observe(case, response, expected, *, qa=False, note=""):
    row = {"case": case, "status": response.status_code, "expectedStatus": expected,
           "ACAO": response.headers.get("access-control-allow-origin"),
           "credentials": response.headers.get("access-control-allow-credentials"),
           "cacheControl": response.headers.get("cache-control"),
           "vary": response.headers.get("vary"), "note": note}
    headers_ok = (row["credentials"] is None and (
        (row["ACAO"] == QA_VEHICLE_ORIGIN and row["cacheControl"] == "no-store"
         and "origin" in {v.strip().lower() for v in (row["vary"] or "").split(",")})
        if qa else row["ACAO"] != QA_VEHICLE_ORIGIN))
    row["passed"] = response.status_code == expected and headers_ok
    EVIDENCE.append(row)
    assert response.status_code == expected
    assert "access-control-allow-credentials" not in response.headers
    if qa:
        assert row["ACAO"] == QA_VEHICLE_ORIGIN
        assert row["cacheControl"] == "no-store"
        assert "origin" in {v.strip().lower() for v in row["vary"].split(",")}
    else:
        assert row["ACAO"] != QA_VEHICLE_ORIGIN


def test_default_off_does_not_change_normal_origin():
    client = TestClient(main.app)
    observe("default-off-qa", client.get("/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN}), 403)
    normal = client.get("/api/vehicle/state", headers={"Origin": NORMAL})
    observe("default-off-normal-unchanged", normal, 200)
    assert normal.headers["access-control-allow-origin"] == NORMAL
    assert "cache-control" not in normal.headers


def test_exact_read_uses_actual_vehicle_handler_and_truth(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(main, "qa_vehicle_read_policy", clock.policy())
    client = TestClient(main.app)
    # This is the actual in-process speed handler, not a live mutation or PARK stub.
    assert client.post("/api/vehicle/speed", json={"speedKmH": 37}, headers={"Origin": NORMAL}).status_code == 200
    reply = client.get("/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN})
    observe("exact-get-real-moving-handler", reply, 200, qa=True,
            note="Actual speed handler set37 in test process; real read must report moving, never force PARK")
    assert reply.json() == main.get_vehicle_state()
    assert reply.json()["currentSpeed"] == 37 and reply.json()["vehicleParked"] is False
    assert QA_VEHICLE_ORIGIN not in main.trusted_origins


@pytest.mark.parametrize("case,method,path,extra", [
    ("post-speed-denied", "POST", "/api/vehicle/speed", {"json": {"speedKmH": 80}}),
    ("post-toggle-denied", "POST", "/api/vehicle/toggle", {}),
    ("post-health-wipe-denied", "POST", "/api/privacy/wipe", {}),
    ("delete-denied", "DELETE", "/api/vehicle/state", {}),
    ("head-denied", "HEAD", "/api/vehicle/state", {}),
    ("other-health-read-denied", "GET", "/api/mental/sessions", {}),
    ("other-path-denied", "GET", "/api/profile", {}),
    ("trailing-slash-denied", "GET", "/api/vehicle/state/", {}),
    ("encoded-path-denied", "GET", "/api/vehicle/%73tate", {}),
    ("query-denied", "GET", "/api/vehicle/state?x=1", {}),
    ("get-body-denied", "GET", "/api/vehicle/state", {"content": b"x"}),
    ("get-undeclared-body-denied", "GET", "/api/vehicle/state", {"content": b"x", "headers": {"Content-Length": "0"}}),
    ("chunked-denied", "GET", "/api/vehicle/state", {"headers": {"Transfer-Encoding": "chunked"}}),
    ("cookie-denied", "GET", "/api/vehicle/state", {"headers": {"Cookie": "qa=1"}}),
    ("empty-cookie-denied", "GET", "/api/vehicle/state", {"headers": {"Cookie": ""}}),
    ("authorization-denied", "GET", "/api/vehicle/state", {"headers": {"Authorization": "Bearer synthetic-test"}}),
    ("empty-authorization-denied", "GET", "/api/vehicle/state", {"headers": {"Authorization": ""}}),
    ("preflight-denied", "OPTIONS", "/api/vehicle/state", {"headers": {"Access-Control-Request-Method": "GET"}}),
])
def test_qa_denials_never_reach_mutation(monkeypatch, case, method, path, extra):
    monkeypatch.setattr(main, "qa_vehicle_read_policy", Clock().policy())
    before = dict(main.vehicle_state)
    kwargs = dict(extra)
    headers = {"Origin": QA_VEHICLE_ORIGIN, **kwargs.pop("headers", {})}
    reply = TestClient(main.app).request(method, path, headers=headers, follow_redirects=False, **kwargs)
    observe(case, reply, 403)
    assert main.vehicle_state == before


@pytest.mark.parametrize("origin", ["http://localhost:3447", "http://127.0.0.1:3448",
                                  "https://127.0.0.1:3447", "http://127.0.0.1:3447.evil.invalid"])
def test_other_origins_not_granted(monkeypatch, origin):
    monkeypatch.setattr(main, "qa_vehicle_read_policy", Clock().policy())
    observe("wrong-origin-" + origin, TestClient(main.app).get("/api/vehicle/state", headers={"Origin": origin}), 403)


def test_duplicate_security_headers_denied(monkeypatch):
    monkeypatch.setattr(main, "qa_vehicle_read_policy", Clock().policy())
    for label, headers in [
        ("duplicate-origin", [("Origin", QA_VEHICLE_ORIGIN), ("Origin", QA_VEHICLE_ORIGIN)]),
        ("duplicate-length", [("Origin", QA_VEHICLE_ORIGIN), ("Content-Length", "0"), ("Content-Length", "0")]),
    ]:
        observe(label, TestClient(main.app).get("/api/vehicle/state", headers=headers), 403)


@pytest.mark.parametrize("case,origin,expiry", [
    ("missing-both", None, None),
    ("missing-origin", None, (NOW + timedelta(minutes=5)).isoformat()),
    ("missing-expiry", QA_VEHICLE_ORIGIN, None),
    ("wrong-config-origin", "http://127.0.0.1:3448", (NOW + timedelta(minutes=5)).isoformat()),
    ("invalid-expiry", QA_VEHICLE_ORIGIN, "not-a-date"),
    ("naive-expiry", QA_VEHICLE_ORIGIN, "2026-10-18T12:05:00"),
    ("non-utc-expiry", QA_VEHICLE_ORIGIN, "2026-10-18T13:05:00+01:00"),
    ("already-expired", QA_VEHICLE_ORIGIN, (NOW - timedelta(seconds=1)).isoformat()),
    ("expires-now", QA_VEHICLE_ORIGIN, NOW.isoformat()),
    ("over-45-minutes", QA_VEHICLE_ORIGIN, (NOW + timedelta(seconds=MAX_LEASE_SECONDS + 1)).isoformat()),
])
def test_invalid_startup_config_fails_closed(monkeypatch, case, origin, expiry):
    env = {}
    if origin is not None:
        env["ATTUNE_QA_VEHICLE_READ_ORIGIN"] = origin
    if expiry is not None:
        env["ATTUNE_QA_VEHICLE_READ_EXPIRES_UTC"] = expiry
    policy = Clock().policy(env)
    assert not policy.enabled
    monkeypatch.setattr(main, "qa_vehicle_read_policy", policy)
    observe(case, TestClient(main.app).get("/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN}), 403)


@pytest.mark.parametrize("case", ["wall-expiry", "monotonic-expiry-with-wall-rollback"])
def test_each_request_expiry_cannot_be_extended_by_clock_rollback(monkeypatch, case):
    clock = Clock()
    monkeypatch.setattr(main, "qa_vehicle_read_policy", clock.policy())
    client = TestClient(main.app)
    observe(case + "-before", client.get("/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN}), 200, qa=True)
    if case == "wall-expiry":
        clock.utc = NOW + timedelta(seconds=MAX_LEASE_SECONDS)
    else:
        clock.utc = NOW - timedelta(days=1)
        clock.tick += MAX_LEASE_SECONDS
    observe(case + "-after", client.get("/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN}), 403)
    normal = client.get("/api/vehicle/state", headers={"Origin": NORMAL})
    observe(case + "-normal-still-allowed", normal, 200)
    assert normal.headers["access-control-allow-origin"] == NORMAL


def test_startup_snapshot_does_not_follow_environment_mutation():
    env = {}
    policy = Clock().policy(env)
    env.update(ATTUNE_QA_VEHICLE_READ_ORIGIN=QA_VEHICLE_ORIGIN,
               ATTUNE_QA_VEHICLE_READ_EXPIRES_UTC=(NOW + timedelta(minutes=5)).isoformat())
    assert not policy.active()
    EVIDENCE.append({"case": "startup-only-snapshot", "passed": not policy.active()})


def test_absolute_utc_z_config_is_valid(monkeypatch):
    policy = Clock().policy({"ATTUNE_QA_VEHICLE_READ_ORIGIN": QA_VEHICLE_ORIGIN,
                             "ATTUNE_QA_VEHICLE_READ_EXPIRES_UTC": "2026-10-18T12:05:00Z"})
    monkeypatch.setattr(main, "qa_vehicle_read_policy", policy)
    observe("absolute-utc-Z-config", TestClient(main.app).get(
        "/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN}), 200, qa=True)


@pytest.mark.parametrize("fault", ["expiry-during-handler", "handler-503"])
def test_late_response_and_handler_error_not_replaced_with_success(monkeypatch, fault):
    clock = Clock()
    monkeypatch.setattr(main, "qa_vehicle_read_policy", clock.policy())
    route = next(r for r in main.app.routes if getattr(r, "path", None) == "/api/vehicle/state")
    original = route.dependant.call

    def handler():
        if fault == "handler-503":
            raise HTTPException(status_code=503, detail="Synthetic in-process handler failure")
        value = original()
        clock.tick += MAX_LEASE_SECONDS
        return value

    monkeypatch.setattr(route.dependant, "call", handler)
    response = TestClient(main.app).get("/api/vehicle/state", headers={"Origin": QA_VEHICLE_ORIGIN})
    observe(fault, response, 503 if fault == "handler-503" else 403, qa=fault == "handler-503")


def test_normal_preflight_still_uses_existing_policy(monkeypatch):
    monkeypatch.setattr(main, "qa_vehicle_read_policy", Clock().policy())
    reply = TestClient(main.app).options("/api/privacy/wipe", headers={
        "Origin": NORMAL, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    observe("normal-preflight-unchanged", reply, 200)
    assert reply.headers["access-control-allow-origin"] == NORMAL
