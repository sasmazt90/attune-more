import pytest
from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir / "services" / "skin"))

from color_metrics import SkinRegionAnalyzer, DEFAULT_DEMO_CHANGE_THRESHOLD

def test_skin_redness_metric_bounds():
    """Kızarıklık indeksi (2R - G - B) 0-100 aralığında normalize olmalıdır."""
    # Tam kırmızı
    val_red = SkinRegionAnalyzer.calculate_redness_index(255.0, 0.0, 0.0)
    assert val_red == 100.0

    # Tam yeşil (kızarıklık yok)
    val_green = SkinRegionAnalyzer.calculate_redness_index(0.0, 255.0, 0.0)
    assert val_green == 0.0

    # Nötr gri
    val_gray = SkinRegionAnalyzer.calculate_redness_index(128.0, 128.0, 128.0)
    assert 0.0 <= val_gray <= 100.0

def test_skin_multiple_skin_tones_pixel_cases():
    """Farklı ten rengi / aydınlatma profillerinde kızarıklık indeksi istikrarlı olmalıdır."""
    # Açık ten tonu (R: 240, G: 200, B: 180) -> 2*240 - 200 - 180 = 100 -> ~39.2%
    val_light = SkinRegionAnalyzer.calculate_redness_index(240.0, 200.0, 180.0)
    assert 20.0 <= val_light <= 60.0

    # Orta/Buğday ten tonu (R: 195, G: 145, B: 110) -> 2*195 - 145 - 110 = 135 -> ~52.9%
    val_medium = SkinRegionAnalyzer.calculate_redness_index(195.0, 145.0, 110.0)
    assert 30.0 <= val_medium <= 70.0

    # Koyu ten tonu (R: 120, G: 85, B: 60) -> 2*120 - 85 - 60 = 95 -> ~37.2%
    val_dark = SkinRegionAnalyzer.calculate_redness_index(120.0, 85.0, 60.0)
    assert 20.0 <= val_dark <= 60.0

def test_skin_baseline_delta_and_configurable_threshold():
    """Baz çizgi karşılaştırması konfigüre edilebilir eşik ile doğru çalışmalıdır."""
    baseline = {
        "Alın": 20.0,
        "Sağ Yanak": 25.0,
        "Sol Yanak": 22.0
    }
    current = {
        "Alın": 21.0,        # +5%
        "Sağ Yanak": 31.25,   # +25%
        "Sol Yanak": 22.5     # +2.2%
    }

    # Varsayılan %20 eşik ile: Sağ Yanak %25 değişim gösterir -> referral önerilmeli
    res_default = SkinRegionAnalyzer.compare_against_baseline(current, baseline, change_threshold=20.0)
    assert res_default["highestChangeRegion"] == "Sağ Yanak"
    assert res_default["highestChangePct"] == 25.0
    assert res_default["referralRecommended"] is True
    assert "belirgin bir görsel değişim gözlendi" in res_default["clinicalNote"]
    assert "dermatologla görüşmek" in res_default["clinicalNote"]

    # Eşik %30'a çekilirse aynı ölçümde referral tetiklenmemeli (configurable threshold testi)
    res_high_thresh = SkinRegionAnalyzer.compare_against_baseline(current, baseline, change_threshold=30.0)
    assert res_high_thresh["referralRecommended"] is False
    assert "referans bandında" in res_high_thresh["clinicalNote"]

def test_skin_non_diagnostic_language_guard():
    """Sonuç metninde hiçbir zaman tıbbi hastalık ismi veya teşhis yer almamalıdır."""
    forbidden_terms = ["akne", "melanom", "kanser", "ekzema", "sedef", "hastalıklısınız", "tedavi", "derhal doktora gidin"]
    
    baseline = {"Sağ Yanak": 20.0}
    current = {"Sağ Yanak": 35.0} # +75% değişim
    res = SkinRegionAnalyzer.compare_against_baseline(current, baseline)
    
    note_lower = res["clinicalNote"].lower()
    for term in forbidden_terms:
        assert term not in note_lower

def test_skin_no_raw_image_persistence_contract():
    """Persist edilen model nesnesinde ham piksel dizisi veya base64 resim bulunmamalıdır."""
    baseline = {"Alın": 18.0, "Çene": 19.0}
    current = {"Alın": 18.5, "Çene": 19.2}
    res = SkinRegionAnalyzer.compare_against_baseline(current, baseline)
    
    assert "rawImage" not in res
    assert "imageData" not in res
    assert "pixels" not in res
    assert isinstance(res["deltas"], dict)

def test_skin_roi_out_of_bounds_clamping():
    """Sınır dışına taşan ROI koordinatları hata fırlatmamalı ve güvenli clamp edilmelidir."""
    skin_analyzer_file = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "skinAnalyzer.ts"
    assert skin_analyzer_file.exists()
    content = skin_analyzer_file.read_text(encoding="utf-8")
    # Kodda sınır aşımı engeli olmalı (Math.max, Math.min clamping)
    assert "Math.max(0, Math.min(width" in content
    assert "Math.max(0, Math.min(height" in content
    assert "NO_FACE" in content

def test_skin_mediapipe_required_for_persistence_contract():
    """MediaPipe FaceLandmarker olmadan sağlık metriği persist edilemez ve ROI üretilemez."""
    skin_analyzer_file = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "skinAnalyzer.ts"
    assert skin_analyzer_file.exists()
    content = skin_analyzer_file.read_text(encoding="utf-8")

    # 1. canPersistResult fonksiyonu ve usedMediaPipe kontrolü var olmalı
    assert "canPersistResult" in content
    assert "result.usedMediaPipe === true" in content

    # 2. analyzeRegions içinde MediaPipe landmark zorunluluğu (MEDIAPIPE_REQUIRED) olmalı
    assert "MEDIAPIPE_REQUIRED" in content
    assert "isMediaPipeActive" in content

    # 3. Byte-identical pinned SDK is now delivered locally; no runtime CDN.
    assert "@mediapipe/tasks-vision@latest" not in content
    assert "'/mediapipe/wasm'" in content
    import json
    manifest=json.loads((root_dir/'apps/vehicle-app/public/mediapipe/manifest.json').read_text())
    assert manifest['sdkVersion']=='1.0.1' and not manifest['modelChange']

    # 4. skin/page.tsx içinde de persist öncesi MediaPipe doğrulaması yapılmalı
    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    page_content = skin_page.read_text(encoding="utf-8")
    assert "canPersistResult" in page_content
    assert "isMediaPipeLoaded" in page_content

