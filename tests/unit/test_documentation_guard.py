"""
Documentation & Reality Guard Tests (Static Assertions)
Lisans: UNLICENSED

Bu test paketi, Faz 3 kuralları gereğince depodaki kod ve dokümanların
gerçeklik standartlarına uyumunu doğrular:
1. Desteklenmeyen Togg API/donanım iddialarının (TruCar, CAN-bus, REST telemetry gateway) bulunmadığı.
2. ALO 182'nin kriz bağlamında hiçbir kod veya dokümanda yer almadığı.
3. package.json lisansının UNLICENSED olduğu.
4. Vision modülünde sentetik 52 + (intervalCount % 5) döngüsünün kalmadığı.
"""

import os
import subprocess
from pathlib import Path
import json

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

def test_no_unsupported_togg_terms_in_repo():
    """TruCar, CAN-bus, REST telemetry gateway gibi doğrulanmamış Togg terimleri depoda bulunmamalıdır."""
    unsupported_patterns = [
        "trucar",
        "can-bus",
        "can bus",
        "rest telemetry gateway",
        "oem android automotive"
    ]
    
    # Taranacak uzantılar
    scan_extensions = [".md", ".ts", ".tsx", ".py", ".json"]

    violations = []

    # Product source includes untracked candidate changes, but ignored datasets,
    # generated audits and isolated third-party installations are not our claims.
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                     '--exclude-standard', '-z'], cwd=ROOT_DIR).decode('utf-8').split('\0')
    for relative in paths:
        if not relative: continue
        p = ROOT_DIR / relative
        if p.resolve() == Path(__file__).resolve() or p.suffix.lower() not in scan_extensions:
            continue
        content = p.read_text(encoding='utf-8', errors='ignore').lower()
        for pattern in unsupported_patterns:
            if pattern in content: violations.append(f"{relative}: '{pattern}' bulundu")

    assert len(violations) == 0, f"Desteklenmeyen terim ihlalleri tespit edildi:\n" + "\n".join(violations)

def test_package_json_license_is_unlicensed():
    """Kendi kodumuzun lisansı package.json içinde UNLICENSED olmalıdır."""
    pkg_path = ROOT_DIR / "package.json"
    assert pkg_path.exists(), "package.json bulunamadı"
    
    with open(pkg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("license") == "UNLICENSED", f"Beklenen UNLICENSED, ancak {data.get('license')} bulundu."

def test_no_182_in_crisis_contexts():
    """Kriz tespit ve müdahale dosyalarında 182 numarası kesinlikle yer alamaz."""
    crisis_files = [
        ROOT_DIR / "services" / "core-api" / "mental_provider.py",
        ROOT_DIR / "packages" / "safety" / "crisisDetector.ts",
        ROOT_DIR / "SAFETY.md",
        ROOT_DIR / "docs" / "clinical-safety" / "clinical_evaluation_protocol.md"
    ]

    for cf in crisis_files:
        if cf.exists():
            content = cf.read_text(encoding="utf-8")
            assert "182" not in content, f"{cf.name} içinde 182 bulundu! Krizde yalnızca 112 kullanılmalıdır."

def test_no_synthetic_distance_generator_in_vision():
    """Vision modülünde 'intervalCount % 5' benzeri sahte mesafe döngüsü bulunmamalıdır."""
    vision_page = ROOT_DIR / "apps" / "vehicle-app" / "src" / "app" / "vision" / "ContinuousPage.tsx"
    assert vision_page.exists()
    content = vision_page.read_text(encoding="utf-8")
    assert "intervalCount % 5" not in content, "Sahte mesafe hesabı 'intervalCount % 5' tespit edildi!"
    assert "verifiedDistanceCm" not in content
    assert "relativeScaleChange" in content and "Mutlak mesafe ölçülmüyor" in content
