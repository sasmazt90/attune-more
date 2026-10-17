"""
Care Search & Browser Automation Provider
Lisans: UNLICENSED

İLKELER & GERÇEKLİK KURALI:
1. Anti-bot, CAPTCHA veya Cloudflare engellerini asla aşmaya çalışma (BYPASS YAPMA).
2. Gerçek DOM'dan zamanı okunmamış hiçbir veriyi 'Canlı Kaynak' veya 'LIVE_AVAILABILITY' olarak işaretleme.
3. Doktor profili canlı kaynaktan bulunup müsaitlik saatleri DOM'dan okunamıyorsa:
   sourceType = 'LIVE_PROVIDER_ONLY'
   ve kullanıcıya 'Doktor profili canlı kaynaktan bulundu — müsaitlik için siteyi aç' güvenli el sıkışma (safe handoff) bağlantısı ver.
4. Yalnızca DOM'dan gerçek zaman okunabilirse: sourceType = 'LIVE_AVAILABILITY'.
5. Demo randevu slotları açıkça:
   sourceType = 'DEMO', sourceBadge = 'Demo Randevu Verisi'.
6. Demo verilerde gerçek kurum (Acıbadem, Dünyagöz vb.) veya gerçek hekim isimleri kullanılmaz;
   tamamen jenerik sentetik isimler kullanılır ('Demo Göz Merkezi', 'Demo Dermatoloji Kliniği').
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import urllib.parse
import re

def verified_source_slot_time(node):
    """Only a complete source timestamp can establish provider availability.
    A clock label alone has no date. This Turkish provider's naive timestamps
    use Europe/Istanbul; the user's timezone is never substituted for it.
    """
    candidates=[node.get_attribute(k) for k in ('datetime','data-start','data-datetime')]
    child=node.query_selector('time[datetime]')
    if child:candidates.append(child.get_attribute('datetime'))
    for raw in candidates:
        if not isinstance(raw,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?',raw):continue
        try:
            value=datetime.fromisoformat(raw.replace('Z','+00:00'))
            return (value.replace(tzinfo=ZoneInfo('Europe/Istanbul')) if value.tzinfo is None else value).isoformat()
        except ValueError:continue
    return None

class CareSearchProvider(ABC):
    @abstractmethod
    def search_slots(self, specialty: str, city: str = "İstanbul") -> Dict[str, Any]:
        pass


class DemoCareSearchProvider(CareSearchProvider):
    """
    Çevrimdışı ve test ortamları için jenerik sentetik demo randevu sağlayıcısı.
    Asla gerçek hekim veya hastane adı kullanmaz.
    Açıkça 'DEMO' veri rozeti taşır.
    """
    def search_slots(self, specialty: str, city: str = "İstanbul") -> Dict[str, Any]:
        spec_slug = specialty.lower().replace(" ", "-")
        now = datetime.now()

        if "göz" in spec_slug:
            center_name = "Demo Göz Sağlığı Merkezi"
            doctor_name = "Uzm. Dr. A. Yılmaz (Demo Hekim)"
        elif "derm" in spec_slug or "cilt" in spec_slug:
            center_name = "Demo Dermatoloji Kliniği"
            doctor_name = "Uzm. Dr. B. Kaya (Demo Hekim)"
        else:
            center_name = "Demo Danışmanlık ve Terapi Merkezi"
            doctor_name = "Uzm. Psk. C. Demir (Demo Danışman)"

        slots = [
            {
                "id": f"demo-slot-{specialty[:3].lower()}-01",
                "specialty": specialty,
                "providerName": doctor_name,
                "title": f"{specialty} Uzmanı",
                "clinicName": center_name,
                "locationLabel": f"Merkez Şube, {city}",
                "isOnline": False,
                "dateTime": (now + timedelta(days=1)).replace(hour=14, minute=20, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:00"),
                "displayTime": "Yarın 14:20",
                "travelTimeMin": 14,
                "sourceType": "DEMO",
                "sourceBadge": "Demo Randevu Verisi",
                "bookingUrl": "https://www.doktortakvimi.com",
                "bookingStatus": "DISCOVERED_ONLY"
            },
            {
                "id": f"demo-slot-{specialty[:3].lower()}-02",
                "specialty": specialty,
                "providerName": f"Doç. Dr. D. Öztürk (Demo Hekim)",
                "title": f"{specialty} ve Danışman",
                "clinicName": f"{center_name} - Şube 2",
                "locationLabel": f"Batı Yakası, {city}",
                "isOnline": False,
                "dateTime": (now + timedelta(days=2, hours=3)).replace(minute=45).strftime("%Y-%m-%dT%H:%M:00"),
                "displayTime": "Çarşamba 17:45",
                "travelTimeMin": 22,
                "sourceType": "DEMO",
                "sourceBadge": "Demo Randevu Verisi",
                "bookingUrl": "https://www.doktortakvimi.com",
                "bookingStatus": "DISCOVERED_ONLY"
            },
            {
                "id": f"demo-slot-{specialty[:3].lower()}-03",
                "specialty": specialty,
                "providerName": f"Uzm. E. Şahin (Demo Çevrimiçi)",
                "title": f"Çevrimiçi {specialty} Danışmanı",
                "clinicName": "Togg Araç İçi Tele-Sağlık Odası",
                "locationLabel": "Online / Araç Ekranı",
                "isOnline": True,
                "dateTime": (now + timedelta(days=2, hours=5)).replace(minute=0).strftime("%Y-%m-%dT%H:%M:00"),
                "displayTime": "Çarşamba 20:00",
                "travelTimeMin": 0,
                "sourceType": "DEMO",
                "sourceBadge": "Demo Randevu Verisi",
                "bookingUrl": "https://www.doktortakvimi.com",
                "bookingStatus": "DISCOVERED_ONLY"
            }
        ]
        return {
            "status": "SUCCESS",
            "providerType": "DEMO",
            "sourceBadge": "Demo Randevu Verisi",
            "specialty": specialty,
            "city": city,
            "slots": slots
        }


class BrowserCareSearchProvider(CareSearchProvider):
    """
    Playwright tabanlı otonom hekim bulma motoru.
    Salt-okunur (read-only) arama yapar.
    
    GERÇEKLİK KURALI:
    - Sayfa Cloudflare/CAPTCHA veya bot koruması altındaysa bypass YAPILMAZ.
      Şeffaf biçimde 'FALLBACK_BLOCKED' ve güvenli handoff linki sunulur.
    - Gerçek DOM'dan hekim kartı bulunsa bile, slot tarihi DOM'dan açıkça okunmadıkça
      ASLA uydurma datetime üretilmez; 'LIVE_PROVIDER_ONLY' statüsü verilir.
    - Sadece DOM'dan gerçek müsaitlik zamanı okunabildiğinde 'LIVE_AVAILABILITY' verilir.
    """
    def search_slots(self, specialty: str, city: str = "İstanbul") -> Dict[str, Any]:
        query_encoded = urllib.parse.quote(specialty)
        city_encoded = urllib.parse.quote(city)
        target_url = f"https://www.doktortakvimi.com/arama?q={query_encoded}&loc={city_encoded}"

        extracted_providers: List[Dict[str, Any]] = []
        is_blocked = False
        error_message = None

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.set_default_timeout(7000)

                response = page.goto(target_url, wait_until="domcontentloaded")
                content = page.content().lower()
                title = page.title().lower()

                # Bot koruması veya doğrulama denetimi
                if (
                    "captcha" in content
                    or "access denied" in content
                    or "just a moment" in title
                    or "cloudflare" in content
                    or (response and response.status in [403, 404, 429, 503])
                ):
                    is_blocked = True
                    error_message = (
                        "Web sitesi bot/erişim koruması (Cloudflare/CAPTCHA) tespit edildi. "
                        "Etik otomasyon gereği bypass yapılmadı; güvenli web yönlendirmesi hazırlandı."
                    )
                else:
                    # DOM üzerinden doktor kartlarını ara
                    cards = page.query_selector_all(".search-item, [data-doctor-id], .card, [data-qa-id='doctor-card']")
                    for idx, card in enumerate(cards[:3]):
                        name_elem = card.query_selector("h3, .doctor-name, a.text-body, [data-qa-id='doctor-name']")
                        name = name_elem.inner_text().strip() if name_elem else ""
                        if not name:continue

                        clinic_elem = card.query_selector(".address, .clinic-name, .text-muted, [data-qa-id='doctor-address']")
                        clinic = clinic_elem.inner_text().strip() if clinic_elem else "Klinik bilgisi kaynakta bulunamadı"

                        profile_elem = card.query_selector("a[href*='/doktor/'], a.doctor-link, a")
                        profile_href = profile_elem.get_attribute("href") if profile_elem else ""
                        profile_url = urllib.parse.urljoin("https://www.doktortakvimi.com", profile_href) if profile_href else target_url

                        # DOM'da açıkça okunabilen takvim slotu var mı denetle
                        slot_btn = card.query_selector(".calendar-slot, [data-qa-id='slot-button'], .btn-time")
                        if slot_btn and slot_btn.inner_text().strip():
                            # Gerçek DOM slot zamanı bulundu
                            raw_slot_text = slot_btn.inner_text().strip()
                            source_time=verified_source_slot_time(slot_btn)
                            extracted_providers.append({
                                "id": f"live-slot-{idx+1}",
                                "specialty": specialty,
                                "providerName": name,
                                "title": f"{specialty} Uzmanı",
                                "clinicName": clinic,
                                "locationLabel": f"{city} (Doğrulanan Web Kaynağı)",
                                "isOnline": False,
                                "rawExtractedTime": raw_slot_text,
                                "dateTime":source_time,
                                "sourceType": "LIVE_AVAILABILITY" if source_time else "LIVE_PROVIDER_ONLY",
                                "sourceBadge": "Kaynakta doğrulanan tarih ve saat" if source_time else "Hekim profili (tam tarih ve saat doğrulanmadı)",
                                "bookingUrl": profile_url,
                                "bookingStatus": "DISCOVERED_ONLY"
                            })
                        else:
                            # Hekim profili bulundu ama müsaitlik saatleri DOM'da açık değil
                            # KESİNLİKLE SAHTE DATETIME ÜRETİLMEZ!
                            extracted_providers.append({
                                "id": f"live-provider-{idx+1}",
                                "specialty": specialty,
                                "providerName": name,
                                "title": f"{specialty} Uzmanı",
                                "clinicName": clinic,
                                "locationLabel": f"{city} (Canlı Keşif)",
                                "isOnline": False,
                                "sourceType": "LIVE_PROVIDER_ONLY",
                                "sourceBadge": "Canlı Hekim Profili (Müsaitlik İçin Siteyi Aç)",
                                "bookingUrl": profile_url,
                                "bookingStatus": "DISCOVERED_ONLY",
                                "instructions": "Doktor profili canlı kaynaktan bulundu — müsaitlik için siteyi aç"
                            })

                browser.close()

        except Exception as e:
            is_blocked = True
            error_message = f"Web otomasyon bağlantı durumu: {str(e)[:120]}"

        if is_blocked or not extracted_providers:
            # Şeffaf Fallback
            return dict(status='FALLBACK_BLOCKED',providerType='BROWSER_NO_AVAILABILITY',sourceBadge='Canlı uygunluk doğrulanamadı',liveSearchUrl=target_url,handoffNote=error_message or 'Canlı uzman uygunluğu doğrulanamadı.',specialty=specialty,city=city,slots=[])

        return {
            "status": "SUCCESS",
            "providerType": "BROWSER_LIVE",
            "sourceBadge": "Canlı Kaynak (Browser Agent)",
            "liveSearchUrl": target_url,
            "specialty": specialty,
            "city": city,
            "slots": extracted_providers
        }


class CalendarProvider:
    """
    Kullanıcının yerel simüle takvimini tutar ve randevu saatleri için
    gerçek zaman aralığı kesişim matematiği (interval collision) uygular:
    max(start1, start2) < min(end1, end2)
    
    NOT: Bu bir 'Demo Takvim / Yerel Takvim Simülasyonu'dur.
    Google/Apple Calendar için sağlayıcı arayüzü hazırdır; OAuth2 canlı entegrasyonu planlanmıştır.
    """
    def __init__(self):
        now = datetime.now()
        self.busy_intervals = [
            {
                "title": "Şirket Değerlendirme Toplantısı",
                "start": (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0),
                "end": (now + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
            },
            {
                "title": "Araç Servis Randevusu",
                "start": (now + timedelta(days=2)).replace(hour=17, minute=0, second=0, microsecond=0),
                "end": (now + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
            }
        ]

    def has_conflict(self, slot_iso_time: str, duration_min: int = 45) -> bool:
        try:
            slot_start = datetime.fromisoformat(slot_iso_time)
            slot_end = slot_start + timedelta(minutes=duration_min)

            for event in self.busy_intervals:
                if slot_start < event["end"] and slot_end > event["start"]:
                    return True
            return False
        except Exception:
            return False


class TravelTimeProvider:
    """
    Araç konumu ile randevu konumu arasındaki tahmini sürüş süresi.
    Canlı trafik harita API anahtarı olmadığında açıkça 'MockTravelTimeProvider'
    ve 'Tahmini Süre — Demo Model' etiketiyle çalışır.
    """
    @staticmethod
    def calculate_travel_time_min(dest_location_label: str) -> Dict[str, Any]:
        minutes = 14
        dest_lower = dest_location_label.lower()
        if "batı" in dest_lower or "etiler" in dest_lower:
            minutes = 22
        elif "online" in dest_lower:
            minutes = 0

        return {
            "estimatedMinutes": minutes,
            "isLiveTraffic": False,
            "provider": "MockTravelTimeProvider",
            "trafficBadge": "Tahmini Süre — Demo Model"
        }


def available_window_match(slot_iso,windows,duration_min=45,time_zone='Europe/Istanbul'):
    """Aware UTC interval containment; missing/unparseable real slot time stays unknown."""
    zone=ZoneInfo(time_zone)
    def aware(value):
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return (parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed).astimezone(timezone.utc)
    try:
        intervals=[(aware(v['start']),aware(v['end'])) for v in windows]
        if any(b<=a for a,b in intervals):raise ValueError('INVALID_AVAILABLE_WINDOW')
    except (KeyError,TypeError,ValueError):raise ValueError('INVALID_AVAILABLE_WINDOW') from None
    if not slot_iso or not windows:return None
    try:start=aware(slot_iso)
    except (TypeError,ValueError):return None
    end=start+timedelta(minutes=duration_min)
    return any(a<=start and end<=b for a,b in intervals)
