import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir / "services" / "core-api"))

from care_provider import (
    CareSearchProvider,
    DemoCareSearchProvider,
    BrowserCareSearchProvider,
    CalendarProvider,
    TravelTimeProvider
)

def test_care_demo_provider_uses_synthetic_names_and_demo_badges():
    """Demo hekim verilerinde gerçek marka/hastane adı (Acıbadem, Dünyagöz vb.) yer almamalıdır."""
    provider = DemoCareSearchProvider()
    result = provider.search_slots(specialty="Göz Hastalıkları", city="İstanbul")
    
    assert result["status"] == "SUCCESS"
    assert result["sourceBadge"] == "Demo Randevu Verisi"
    assert len(result["slots"]) > 0
    
    for slot in result["slots"]:
        assert slot["sourceType"] == "DEMO"
        assert slot["sourceBadge"] == "Demo Randevu Verisi"
        # Gerçek zincir hastane adları kesinlikle bulunmamalı
        clinic_lower = slot["clinicName"].lower()
        provider_lower = slot["providerName"].lower()
        assert "acıbadem" not in clinic_lower
        assert "dünyagöz" not in clinic_lower
        assert "memorial" not in clinic_lower
        assert "demo" in provider_lower or "demo" in clinic_lower

def test_live_provider_only_cannot_contain_invented_datetime():
    """Müsaitlik saati DOM'dan okunamadığında sistem sahte datetime üretmemelidir (LIVE_PROVIDER_ONLY kuralı)."""
    care_provider_file = root_dir / "services" / "core-api" / "care_provider.py"
    content = care_provider_file.read_text(encoding="utf-8")
    
    # LIVE_PROVIDER_ONLY bloğunda sahte dateTime üretimi olmamalı
    assert "LIVE_PROVIDER_ONLY" in content
    assert "Doktor profili canlı kaynaktan bulundu" in content

def test_calendar_provider_interval_conflict_math_and_demo_label():
    """Takvim sağlayıcısı zaman aralığı çakışmalarını doğru hesaplamalı ve Demo etiketi taşımalıdır."""
    cal = CalendarProvider()
    now = datetime.now()
    
    # 1. Çakışan zaman: Yarın 18:20 (Kullanıcının yarın 18:00 - 19:00 arası toplantısı var)
    conflict_time = (now + timedelta(days=1)).replace(hour=18, minute=20, second=0, microsecond=0).isoformat()
    assert cal.has_conflict(conflict_time, duration_min=45) is True

    # 2. Uygun zaman: Yarın 14:00 (Program boş)
    free_time = (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0).isoformat()
    assert cal.has_conflict(free_time, duration_min=45) is False

def test_travel_time_provider_mock_badge():
    """Harita anahtarı olmadığında seyahat süresi açıkça 'Tahmini Süre — Demo Model' olarak işaretlenmelidir."""
    travel = TravelTimeProvider.calculate_travel_time_min("Merkez Şube, İstanbul")
    assert travel["isLiveTraffic"] is False
    assert travel["provider"] == "MockTravelTimeProvider"
    assert "Demo Model" in travel["trafficBadge"]
    assert travel["estimatedMinutes"] > 0

def test_care_browser_search_bot_block_provides_safe_handoff(monkeypatch):
    """Playwright arama bot engeli ile karşılaştığında çökmek yerine güvenli handoff URL'i dönmelidir."""
    # A deterministic blocked transport, not a live provider/browser campaign.
    from contextlib import contextmanager
    from types import SimpleNamespace
    import playwright.sync_api
    calls=[]
    class Page:
        url='https://www.doktortakvimi.com/arama'
        def set_default_timeout(self,value): assert value==7000
        def set_default_navigation_timeout(self,value): assert value==7000
        def goto(self,url,**kwargs): calls.append(url);return SimpleNamespace(status=403)
        def content(self): return '<html>captcha</html>'
        def title(self): return 'Access denied'
    class Browser:
        def new_context(self,**kwargs): return SimpleNamespace(new_page=lambda:Page())
        def close(self): pass
    @contextmanager
    def blocked_browser():
        yield SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs:Browser()))
    monkeypatch.setattr(playwright.sync_api,'sync_playwright',blocked_browser)
    browser_provider = BrowserCareSearchProvider()
    result = browser_provider.search_slots(specialty="Dermatoloji", city="İstanbul")
    
    assert "status" in result
    assert result["status"] == "ACCESS_BLOCKED"
    assert "slots" in result
    assert result['providerType']=='PUBLIC_HANDOFF' and result['slots']
    assert all(row['sourceType']=='PUBLIC_SEARCH_ONLY' and row['dateTime'] is None
               and row['bookingStatus']=='DISCOVERED_ONLY' for row in result['slots'])
    assert len(calls)==1
    assert "liveSearchUrl" in result
    assert "https://www.doktortakvimi.com" in result["liveSearchUrl"]

def test_care_page_consent_gate_enforcement():
    """Randevu sayfasında kullanıcı açık onayı (consent checkbox) zorunlu olmalıdır."""
    care_page_file = root_dir / "apps" / "vehicle-app" / "src" / "app" / "care" / "page.tsx"
    assert care_page_file.exists()
    content = care_page_file.read_text(encoding="utf-8")
    assert "consentApproved" in content
    assert "disabled={!consentApproved}" in content
