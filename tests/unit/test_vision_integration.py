import pytest
import math
from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir / "services" / "vision"))
sys.path.insert(0, str(root_dir / "services" / "core-api"))

from staircase import AdaptiveVisionStaircase
from main import app, vehicle_state
from fastapi.testclient import TestClient

client = TestClient(app)

def test_vision_staircase_correct_response_shrinks_optotype():
    """Doğru yanıtlar optotipi (LogMAR değerini) küçültmelidir."""
    staircase = AdaptiveVisionStaircase(initial_logmar=0.3, step_size=0.1)
    assert staircase.current_logmar == 0.3
    
    # 2 ardışık doğru -> zorlaşır (LogMAR düşer)
    staircase.register_response(True)
    staircase.register_response(True)
    assert staircase.current_logmar == 0.2
    
    # Boyut mm hesabı küçülmeli
    size_03 = AdaptiveVisionStaircase(0.3).calculate_optotype_size_mm(55.0)
    size_02 = staircase.calculate_optotype_size_mm(55.0)
    assert size_02 < size_03

def test_vision_staircase_incorrect_response_enlarges_optotype():
    """Yanlış yanıt optotipi büyütmelidir."""
    staircase = AdaptiveVisionStaircase(initial_logmar=0.2, step_size=0.1)
    staircase.register_response(False)
    assert staircase.current_logmar == 0.3
    assert staircase.consecutive_correct == 0

def test_vision_staircase_separate_left_right_eyes():
    """Sağ ve sol göz birbirinden bağımsız basamak yürütmeli ve farklı LogMAR üretebilmelidir."""
    right_eye = AdaptiveVisionStaircase(initial_logmar=0.3)
    left_eye = AdaptiveVisionStaircase(initial_logmar=0.3)
    
    # Sağ göz zorlansın (doğrular)
    right_eye.register_response(True)
    right_eye.register_response(True)
    
    # Sol göz yanlış yapsın
    left_eye.register_response(False)
    
    assert right_eye.current_logmar == 0.2
    assert left_eye.current_logmar == 0.4
    assert right_eye.get_snellen_equivalent() != left_eye.get_snellen_equivalent()

def test_vision_distance_optotype_mm_scaling():
    """Mesafe arttıkça aynı LogMAR için fiziksel mm boyutu büyümeli (açısal sabitlik)."""
    staircase = AdaptiveVisionStaircase(0.1)
    size_at_40cm = staircase.calculate_optotype_size_mm(40.0)
    size_at_80cm = staircase.calculate_optotype_size_mm(80.0)
    assert size_at_80cm > size_at_40cm
    assert math.isclose(size_at_80cm, size_at_40cm * 2.0, rel_tol=0.05)

def test_vision_park_lock_enforcement():
    """Araç hareket halindeyken görme testi kilitli olmalı, park halinde izin verilmelidir."""
    # Sürüş moduna al
    client.post("/api/vehicle/speed", json={"speedKmH": 65.0})
    state_resp = client.get("/api/vehicle/state").json()
    assert state_resp["vehicleMoving"] is True
    assert state_resp["vehicleParked"] is False
    
    # Park moduna geri al
    client.post("/api/vehicle/speed", json={"speedKmH": 0.0})
    parked_resp = client.get("/api/vehicle/state").json()
    assert parked_resp["vehicleMoving"] is False
    assert parked_resp["vehicleParked"] is True

def test_vision_no_synthetic_distance_generator():
    """Vision sayfasında intervalCount veya 52+ simülasyon döngüsü kesinlikle yer alamaz."""
    vision_file = root_dir / "apps" / "vehicle-app" / "src" / "app" / "vision" / "ContinuousPage.tsx"
    assert vision_file.exists()
    content = vision_file.read_text(encoding="utf-8")
    assert "52 + (intervalCount % 5)" not in content
    assert "intervalCount % 5" not in content
    assert "verifiedDistanceCm" not in content
    assert "relativeScaleChange" in content and "Mutlak mesafe ölçülmüyor" in content

def test_vision_incomplete_result_has_no_fake_snellen_fallback():
    """Tamamlanmamış test durumunda sahte 20/30 veya 20/24 Snellen fallback'i gösterilmemelidir."""
    vision_file = root_dir / "apps" / "vehicle-app" / "src" / "app" / "vision" / "ContinuousPage.tsx"
    content = vision_file.read_text(encoding="utf-8")
    # testResults.rightEye null olduğunda '20/30' basılmamalı
    assert "testResults.rightEye?.snellen || '20/30'" not in content
    assert "testResults.leftEye?.snellen || '20/24'" not in content
    assert "if(t.completed)" in content
    assert "isVisionSavingAllowed()" in content
    assert "eyeOcclusionVerification:'not-camera-verified-user-instruction'" in content
    assert "conditionFailure" in content
