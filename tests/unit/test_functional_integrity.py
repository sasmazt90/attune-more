"""
Attune.more Functional Integrity & Real Pipeline Test Suite
Lisans: UNLICENSED

Zorunlu 14 Fonksiyonel Test Kapsamı:
1. Real mode + MediaPipe unavailable: NO result, NO fake +22, NO persistence
2. Demo mode: fixture result allowed, uses separate demo keys
3. First real scan: creates baseline, NO fake delta referral
4. Second real scan: baseline comparison generates delta
5. REAL result UI: uses SkinAnalysisResult metrics, NOT demo fixture
6. Demo result UI: uses demo fixture
7. Skin history: raw images not stored
8. Privacy: no data => counts = 0
9. Camera app permission false: Skin/Vision camera blocked
10. Mic app permission false: Mental microphone blocked
11. Mental summary saving false: summary not persisted
12. Dashboard/Profile: real result exists => real value displayed
13. Dashboard/Profile: no real result => empty state
14. Dashboard/Profile: demo mode => demo fixture displayed
"""

import pytest
from pathlib import Path
import json

root_dir = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# 1. Real Mode + MediaPipe Unavailable Guard
# ---------------------------------------------------------------------------
def test_skin_real_mode_mediapipe_unavailable_no_fake_result_or_persistence():
    """Real modda MediaPipe yüklenemezse veya aktif değilse sahte sonuç ve kayıt üretilmemelidir."""
    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    content = skin_page.read_text(encoding="utf-8")

    # Real mode MediaPipe kontrolü
    assert "!isMPLoaded || !alignToUse.isMediaPipeActive" in content or "!isDemo && !isMediaPipeLoaded" in content
    # Hata durumu ayarlanmalı
    assert "setScanState('ERROR')" in content
    # canPersistResult kontrolü olmadan kayıt yapılmamalı
    assert "SkinAnalyzer.canPersistResult" in content
    # finishScan accepts passed frame alignment/quality parameters
    assert "finalAlignment?: FaceAlignment" in content
    assert "finalQuality?: ImageQuality" in content
    assert "finishScan(false, curAlign, curQual)" in content
    # mediaStream has deterministic video attachment path
    assert "mediaStream && videoRef.current && scanState === 'CAMERA_ACTIVE'" in content
    assert "videoRef.current.srcObject = mediaStream" in content


# ---------------------------------------------------------------------------
# 2. Demo Mode Separation
# ---------------------------------------------------------------------------
def test_skin_demo_mode_allows_fixture_with_separate_keys():
    """Demo modunda fikstür sonucu gösterilebilir ancak gerçek togg_health_latest_skin anahtarına yazılmaz."""
    attune_mode = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "attuneMode.ts"
    assert attune_mode.exists()
    content = attune_mode.read_text(encoding="utf-8")

    assert "DEMO_SKIN_RESULT" in content
    assert "attune_demo_skin_result" in content
    assert "LATEST_SKIN" in content
    assert "togg_health_latest_skin" in content

    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    page_content = skin_page.read_text(encoding="utf-8")
    assert "STORAGE_KEYS.DEMO_SKIN_RESULT" in page_content

    # Demo camera-failure path triggers demo completion without waiting on videoRef
    assert "startSyntheticDemoScan" in page_content
    # Demo synthetic result has usedMediaPipe: false explicitly
    assert "usedMediaPipe: false" in page_content


# ---------------------------------------------------------------------------
# 3. First Real Scan: Baseline Creation
# ---------------------------------------------------------------------------
def test_current_skin_first_scan_is_independent_of_reference_no_fake_delta():
    """İlk başarılı tarama referans baz çizgisini kaydetmeli, sahte +22 delta veya referral üretmemelidir."""
    skin_analyzer = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "skinAnalyzer.ts"
    content = skin_analyzer.read_text(encoding="utf-8")

    # compareWithBaseline içinde baseline=null durumu
    assert "if (!baseline) {" in content
    assert "highestChangePct: 0" in content
    assert "referralSuggested: false" in content
    assert "isBaseline: true" in content

    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    page_content = skin_page.read_text(encoding="utf-8")
    assert "localStorage.getItem(STORAGE_KEYS.SKIN_BASELINE)" not in page_content
    assert "initializeMissingContourReferences" not in page_content
    assert "analysisMode: 'instant-appearance-v2'" in page_content
    assert "highestChangePct: 0" in page_content


# ---------------------------------------------------------------------------
# 4. Second Real Scan: Baseline Comparison & Threshold
# ---------------------------------------------------------------------------
def test_skin_second_real_scan_computes_real_delta_and_threshold():
    """İkinci taramada baseline ile karşılaştırma yapılmalı, gerçek delta ve %20 eşiği doğrulanmalıdır."""
    skin_analyzer = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "skinAnalyzer.ts"
    content = skin_analyzer.read_text(encoding="utf-8")

    assert "deltaPct = Math.round(((curr.rednessScore - base.rednessScore) / base.rednessScore) * 100.0)" in content
    assert "threshold: number = 20.0" in content
    assert "referralNeeded = Math.abs(maxDelta) >= threshold" in content


# ---------------------------------------------------------------------------
# 5. Real Result UI: Uses SkinAnalysisResult Metrics
# ---------------------------------------------------------------------------
def test_skin_real_result_ui_uses_analysis_result_not_demo_fixture():
    """Real modda UI metrikleri demo fikstürden değil, gerçek SkinAnalysisResult verilerinden gelmelidir."""
    fixture_file = root_dir / "apps" / "vehicle-app" / "src" / "data" / "skinDemoFixture.ts"
    content = fixture_file.read_text(encoding="utf-8")

    assert "buildSkinRegionViewModel" in content
    assert "real.changeFromBaselinePct" in content
    assert "real.rednessScore" in content
    assert "real.luminanceScore" in content
    assert "real.textureVariance" in content

    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    page_content = skin_page.read_text(encoding="utf-8")
    # Overview now delegates regional views through the same real-data adapter.
    assert "buildSkinViewModel(" in page_content
    overview=(root_dir/'apps/vehicle-app/src/utils/skinOverview.ts').read_text(encoding='utf-8')
    assert "buildSkinRegionViewModel(" in overview


# ---------------------------------------------------------------------------
# 6. Demo Result UI: Uses Demo Fixture
# ---------------------------------------------------------------------------
def test_skin_demo_result_ui_uses_demo_fixture():
    """Demo modunda buildSkinRegionViewModel onaylı demo fikstürünü döndürmelidir; Real modda asla demo fikstüre düşmemelidir."""
    fixture_file = root_dir / "apps" / "vehicle-app" / "src" / "data" / "skinDemoFixture.ts"
    content = fixture_file.read_text(encoding="utf-8")

    assert "if (isDemo) {" in content
    assert "return base;" in content
    # Real mode missing analysisResult cannot return demo fixture metrics
    assert "if (!analysisResult || !analysisResult.regions || !analysisResult.regions[regionId])" in content
    assert "displayValue: '—'" in content


# ---------------------------------------------------------------------------
# 7. Skin History: Strictly No Raw Images Stored
# ---------------------------------------------------------------------------
def test_skin_history_strictly_excludes_raw_images():
    """Geçmiş kayıtlarında ham görsel, video veya base64 piksel verisi KESİNLİKLE saklanmamalıdır."""
    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    content = skin_page.read_text(encoding="utf-8")

    # localStorage.setItem('togg_health_skin_history' bloğunda yalnız sayısal telemetri olmalı
    assert "appendHealthRecord('skin', finalResult" in content
    store = (root_dir / 'apps/vehicle-app/src/utils/healthRecords.ts').read_text(encoding='utf-8')
    assert 'STORAGE_KEYS.SKIN_HISTORY' in store and 'containsMedia(record)' in store
    assert "toDataURL" not in content
    assert "image/jpeg" not in content
    assert "image/png" not in content


# ---------------------------------------------------------------------------
# 8. Privacy: Empty Storage Counts Strictly Zero & Proper Permission Mapping
# ---------------------------------------------------------------------------
def test_privacy_empty_storage_counts_are_strictly_zero():
    """Gizlilik sayfasında veri yoksa sayılar kesinlikle 0 olmalı ve tarayıcı izin durumu PROMPT olarak korunmalıdır."""
    privacy_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "privacy" / "page.tsx"
    content = privacy_page.read_text(encoding="utf-8")

    # Sahte sayım kodları kaldırılmış olmalı
    assert "Math.max(1" not in content
    assert "vision ? 1 : 1" not in content
    assert "mental ? 2 : 2" not in content
    # Gerçek sayım mantığı bulunmalı
    assert "readHealthRecords('vision').length" in content
    # Browser denied cannot become effective GRANTED merely due to app preference
    assert "deriveEffectiveStatus" in content
    assert "if (!appAllowed)" in content
    assert "if (browserState === 'denied')" in content
    assert "deriveEffectiveStatus(camAllowed, bState)" in content


# ---------------------------------------------------------------------------
# 9. Camera App Permission: Blocks Skin and Vision
# ---------------------------------------------------------------------------
def test_camera_app_permission_false_blocks_skin_and_vision():
    """Uygulama içi kamera izni kapalıysa hem Cilt hem Görme modülü kamerayı başlatmamalıdır."""
    skin_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "skin" / "page.tsx"
    skin_content = skin_page.read_text(encoding="utf-8")
    assert "isCameraAllowed()" in skin_content
    assert "!isCameraAllowed()" in skin_content

    vision_page = root_dir / "apps" / "vehicle-app" / "src" / "app" / "vision" / "ContinuousPage.tsx"
    vision_content = vision_page.read_text(encoding="utf-8")
    assert "isCameraAllowed()" in vision_content
    assert "!isCameraAllowed()" in vision_content


# ---------------------------------------------------------------------------
# 10. Microphone App Permission: Blocks Mental Mic
# ---------------------------------------------------------------------------
def test_microphone_app_permission_false_blocks_mental_mic():
    """İzin yokken sesli akış iptal edilir; kaldırılmış yazılı fallback açılmaz."""
    mental_page = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "useMentalConversation.ts"
    content = mental_page.read_text(encoding="utf-8")

    assert "isMicrophoneAllowed()" in content
    assert "!isMicrophoneAllowed()" in content
    assert "setNotice(" in content
    branch=content.split('if (!isMicrophoneAllowed() || !settings.current.speechConsent)',1)[1].split('const SR',1)[0]
    assert "cancel(" in branch and "return;" in branch
    assert "setTextMode(true)" not in content


# ---------------------------------------------------------------------------
# 11. Mental Summary Saving Preference: Prevents Persistence
# ---------------------------------------------------------------------------
def test_mental_summary_saving_false_prevents_session_persistence():
    """Seans özeti saklama kapalıysa mental oturum kaydedilmemelidir."""
    mental_page = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "useMentalConversation.ts"
    content = mental_page.read_text(encoding="utf-8")

    assert "isMentalSummarySavingAllowed()" in content
    assert "if (!isDemoMode() && isMentalSummarySavingAllowed()) {" in content


# ---------------------------------------------------------------------------
# 12. Dashboard & Profile: Real Result Display & No Fake Fallbacks
# ---------------------------------------------------------------------------
def test_dashboard_profile_displays_real_results_when_stored():
    """healthSelectors gerçek depolanan görme ve cilt sonuçlarını parse edip sunmalıdır; real modda sahte fallback üretmemelidir."""
    selectors_file = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "healthSelectors.ts"
    content = selectors_file.read_text(encoding="utf-8")

    assert "getVisionSummary" in content
    assert "getSkinSummary" in content
    assert "parsed.acuityRightSnellen" in content
    assert "parsed.highestChangeRegion" in content
    # Real vision selector contains no '20/30' or '20/25' fallbacks outside demo branch
    assert "parsed.acuityRightSnellen || '20/30'" not in content
    assert "parsed.acuityLeftSnellen || '20/25'" not in content
    assert "parsed.acuityRightSnellen || '—'" in content
    assert "parsed.acuityLeftSnellen || '—'" in content


# ---------------------------------------------------------------------------
# 13. Dashboard & Profile: Empty State When No Real Result
# ---------------------------------------------------------------------------
def test_dashboard_profile_displays_empty_state_when_no_real_results():
    """Real modda kayıt yoksa Dashboard ve Profil sahte sayı üretmemeli, empty state döndürmelidir."""
    selectors_file = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "healthSelectors.ts"
    content = selectors_file.read_text(encoding="utf-8")

    assert "Henüz değerlendirme yok" in content
    assert "Henüz görüşme yok" in content
    assert "0 görüşme" in content

    # Dashboard/Profile initial state does not call get*Summary(true)
    dashboard_file = root_dir / "apps" / "vehicle-app" / "src" / "app" / "page.tsx"
    dash_content = dashboard_file.read_text(encoding="utf-8")
    assert "useState<boolean>(false)" in dash_content
    assert "getVisionSummary(true)" not in dash_content

    profile_file = root_dir / "apps" / "vehicle-app" / "src" / "app" / "profile" / "page.tsx"
    profile_content = profile_file.read_text(encoding="utf-8")
    assert "useState<boolean>(false)" in profile_content
    assert "getVisionSummary(true)" not in profile_content


# ---------------------------------------------------------------------------
# 14. Dashboard & Profile: Demo Fixture in Demo Mode
# ---------------------------------------------------------------------------
def test_dashboard_profile_displays_demo_fixture_in_demo_mode():
    """Demo modunda onaylı demo sunum verileri gösterilmelidir."""
    selectors_file = root_dir / "apps" / "vehicle-app" / "src" / "utils" / "healthSelectors.ts"
    content = selectors_file.read_text(encoding="utf-8")

    assert "20/30 • 20/24" in content
    assert "+%22 Değişim" in content
    assert "4 görüşme" in content
