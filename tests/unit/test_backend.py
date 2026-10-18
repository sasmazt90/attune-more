import sys
import os
from pathlib import Path

# Add core-api to sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent / "services" / "core-api"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["language"] == "tr-TR"

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_vehicle_state_and_toggle():
    # Initial state should be parked
    response = client.get("/api/vehicle/state")
    assert response.status_code == 200
    initial_state = response.json()
    
    # Toggle to driving
    toggle_resp = client.post("/api/vehicle/toggle")
    assert toggle_resp.status_code == 200
    toggled_state = toggle_resp.json()
    assert toggled_state["vehicleMoving"] != initial_state["vehicleMoving"]
    
    # Toggle back to parked
    back_resp = client.post("/api/vehicle/toggle")
    assert back_resp.json()["vehicleParked"] is True

def test_mental_assistant_crisis_guard():
    response = client.post("/api/mental/converse", json={"userMessage": "kendime zarar vermek istiyorum"})
    assert response.status_code == 200
    data = response.json()
    assert data["isCrisis"] is True
    assert "112" in data["reply"]
    assert "182" not in data["reply"]

def test_care_appointment_matching():
    response = client.post("/api/care/match", json={"specialty": "Dermatoloji", "useBrowserAgent": False})
    assert response.status_code == 200
    data = response.json()
    assert len(data["matchedSlots"]) > 0
    assert data["matchedSlots"][0]["calendarFits"] is None
