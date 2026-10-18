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
import os
import unicodedata

def verified_source_slot_time(node, source_timezone="Europe/Istanbul"):
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
            return _aware_timestamp(raw, source_timezone).isoformat()
        except (ValueError, TypeError):continue
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
        query_encoded = urllib.parse.quote(specialty, safe="")
        city_encoded = urllib.parse.quote(city, safe="")
        target_url = f"https://www.doktortakvimi.com/arama?q={query_encoded}&loc={city_encoded}"

        extracted_providers: List[Dict[str, Any]] = []
        is_blocked = False
        failure_status = "EMPTY_RESULT"
        error_message = None

        browser = None
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.set_default_timeout(7000)
                page.set_default_navigation_timeout(7000)

                response = page.goto(target_url, wait_until="domcontentloaded")
                content = page.content().lower()
                title = page.title().lower()
                if not safe_care_url(page.url, "doktortakvimi"):
                    browser.close()
                    return public_handoff_result(specialty, city, status="ACCESS_BLOCKED")
                if response and response.status == 404:
                    return public_handoff_result(specialty, city, status="EMPTY_RESULT")
                if response and response.status >= 500:
                    return public_handoff_result(specialty, city, status="NETWORK_ERROR")

                # Bot koruması veya doğrulama denetimi
                if (
                    "captcha" in content
                    or "access denied" in content
                    or "just a moment" in title
                    or "cloudflare" in content
                    or (response and response.status in [401, 403, 429])
                ):
                    is_blocked = True
                    failure_status = "ACCESS_BLOCKED"
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
                        if not safe_care_url(profile_url, "doktortakvimi"): continue

                        # DOM'da açıkça okunabilen takvim slotu var mı denetle
                        slot_btn = card.query_selector(".calendar-slot, [data-qa-id='slot-button'], .btn-time")
                        if slot_btn and slot_btn.inner_text().strip():
                            # Gerçek DOM slot zamanı bulundu
                            raw_slot_text = slot_btn.inner_text().strip()
                            source_time=verified_source_slot_time(slot_btn)
                            extracted_providers.append({
                                "sourceId": "doktortakvimi",
                                "sourceTimeZone": "Europe/Istanbul",
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
                                "sourceId": "doktortakvimi",
                                "sourceTimeZone": "Europe/Istanbul",
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
            failure_status = "TIMEOUT" if isinstance(e, TimeoutError) or type(e).__name__ == "TimeoutError" else "NETWORK_ERROR"
            error_message = "Kaynak bağlantısı doğrulanamadı."
        finally:
            if browser:
                try: browser.close()
                except Exception: pass  # Driver context may already have closed it.

        if is_blocked or not extracted_providers:
            # Şeffaf Fallback
            return public_handoff_result(specialty, city, status=failure_status)

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


# Official public directory templates; no request or availability claim is made here.
# Doctolib.de is deliberately limited to configured German cities, not an Istanbul substitute.
CARE_SOURCES = {
    "doktortakvimi": {"host": "www.doktortakvimi.com", "name": "DoktorTakvimi", "zone": "Europe/Istanbul", "prefix": ""},
    "doktorsitesi": {"host": "www.doktorsitesi.com", "name": "Doktorsitesi", "zone": "Europe/Istanbul", "prefix": "/uzmanlik-alanlari"},
    "doctolib": {"host": "www.doctolib.de", "name": "Doctolib", "zone": "Europe/Berlin", "prefix": ""},
}
SPECIALTY_PATHS = {
    "Dermatoloji": ("dermatoloji", "dermatoloji", "hautarzt"),
    "Diş Hekimliği": ("dis-hekimi", "dis-hekimi", "zahnarzt"),
    "Göz Hastalıkları": ("goz-hastaliklari", "goz-hastaliklari", "augenarzt"),
    "Kulak Burun Boğaz": ("kulak-burun-bogaz", "kulak-burun-bogaz-hastaliklari", "facharzt-fur-hno"),
    "Odyoloji": ("odyoloji-dil-konusma-ve-ses-bozukluklari", "odyoloji", None),
    "Klinik Psikoloji": ("psikoloji", "klinik-psikolog", "psychologischer-psychotherapeut-psychotherapeutin"),
    "Psikiyatri": ("psikiyatri", "psikiyatri", "psychiatrie-und-psychotherapie"),
}
TR_CITIES = {"istanbul", "ankara", "izmir"}
DE_CITIES = {"berlin", "hamburg", "muenchen", "koeln", "frankfurt"}

def _slug(value):
    value = value.translate(str.maketrans({"ı":"i", "İ":"I", "ş":"s", "Ş":"S", "ğ":"g", "Ğ":"G"}))
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")

def safe_care_url(value, source_id=None):
    """Only HTTPS directory/profile links on the exact official source, no redirects."""
    if not isinstance(value, str) or len(value)>2048 or any(ord(c)<33 for c in value) or "\\" in value: return False
    try:
        u = urllib.parse.urlsplit(value)
        if source_id is not None and not isinstance(source_id,str): return False
        sources = [CARE_SOURCES[source_id]] if source_id in CARE_SOURCES else list(CARE_SOURCES.values()) if source_id is None else []
        if u.scheme != "https" or u.username or u.password or u.port not in (None,443) or u.fragment: return False
        if u.hostname not in {source["host"] for source in sources}: return False
        path = urllib.parse.unquote(u.path)
        if not re.fullmatch(r"/[a-zA-Z0-9_/-]*", path) or "//" in path or ".." in path: return False
        if any(segment.lower() in {"redirect", "redirects", "out", "login", "auth", "logout"} for segment in path.split("/")): return False
        if u.query:
            # Legacy DoktorTakvimi public search only; no next/url/returnTo parameter.
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            if u.hostname != CARE_SOURCES["doktortakvimi"]["host"] or path != "/arama" or set(q)!={"q","loc"}: return False
            if any(len(v)!=1 or not v[0] or "://" in v[0] for v in q.values()): return False
        return True
    except ValueError: return False

def public_handoff_result(specialty, city, status="PUBLIC_HANDOFF"):
    slots = []
    paths = SPECIALTY_PATHS.get(specialty)
    slug = _slug(city)
    slug = {"munchen":"muenchen", "koln":"koeln"}.get(slug,slug)
    if paths:
        for i, (source_id, source) in enumerate(CARE_SOURCES.items()):
            if slug not in (DE_CITIES if source_id=="doctolib" else TR_CITIES) or paths[i] is None: continue
            url = f"https://{source['host']}{source['prefix']}/{paths[i]}/{slug}"
            if source_id=='doktortakvimi' and specialty=='Klinik Psikoloji':
                url = 'https://www.doktortakvimi.com/arama?' + urllib.parse.urlencode({'q':specialty,'loc':city})
            assert safe_care_url(url, source_id)
            slots.append(dict(id=f"public-{source_id}", sourceId=source_id, sourceTimeZone=source['zone'], specialty=specialty,
                providerName=source['name'], title=specialty, clinicName="Branş araması", locationLabel=city,
                isOnline=None, dateTime=None, sourceType="PUBLIC_SEARCH_ONLY", sourceBadge="Sağlayıcı araması • saat doğrulanmadı",
                bookingUrl=url, bookingStatus="DISCOVERED_ONLY"))
    return dict(status=status if slots else "EMPTY_RESULT", providerType="PUBLIC_HANDOFF", sourceBadge="Saat doğrulanmadı",
        specialty=specialty, city=city, liveSearchUrl=slots[0]['bookingUrl'] if slots else None, slots=slots)

class PublicCareSearchProvider(CareSearchProvider):
    def __init__(self, status="PUBLIC_HANDOFF"): self.status=status
    def search_slots(self, specialty, city="İstanbul"):
        return public_handoff_result(specialty, city, self.status)

# Code-owned registry: future partnership adapters must enforce their real transport
# timeout (<=8 seconds), without retries/fallback endpoints or reservation side effects.
# No endpoint, key, dynamic import, account connection or partner API exists today.
PARTNER_CARE_ADAPTERS = {}

class PartnerCareSearchProvider(CareSearchProvider):
    def __init__(self, client): self.client=client
    def search_slots(self, specialty, city="İstanbul"):
        try:
            result = self.client.search_slots(specialty=specialty, city=city, timeout_seconds=8)
            if not isinstance(result,dict) or not isinstance(result.get('slots'),list):
                return public_handoff_result(specialty,city,"SOURCE_ERROR")
            if result.get('status') not in ('SUCCESS','EMPTY_RESULT'):
                status = result.get('status') if result.get('status') in ('ACCESS_BLOCKED','TIMEOUT','NETWORK_ERROR') else 'SOURCE_ERROR'
                return public_handoff_result(specialty,city,status)
            # A successful but empty partner response remains empty, never a demo.
            return {**result, 'status':'SUCCESS' if result['slots'] else 'EMPTY_RESULT', 'providerType':'PARTNER_API'}
        except TimeoutError: return public_handoff_result(specialty,city,"TIMEOUT")
        except PermissionError: return public_handoff_result(specialty,city,"ACCESS_BLOCKED")
        except (ConnectionError,OSError): return public_handoff_result(specialty,city,"NETWORK_ERROR")
        except Exception: return public_handoff_result(specialty,city,"SOURCE_ERROR")

def get_care_provider(use_browser=True, config=None):
    config = os.environ if config is None else config
    mode = config.get('ATTUNE_CARE_PROVIDER','public')
    if mode=='demo' and config.get('ATTUNE_CARE_ALLOW_DEMO')=='1' and use_browser is False: return DemoCareSearchProvider()
    if mode=='browser': return BrowserCareSearchProvider()
    if mode=='partner':
        factory = PARTNER_CARE_ADAPTERS.get(config.get('ATTUNE_CARE_PARTNER',''))
        return PartnerCareSearchProvider(factory()) if factory else PublicCareSearchProvider('CONFIGURATION_REQUIRED')
    return PublicCareSearchProvider('PUBLIC_HANDOFF' if mode=='public' else 'CONFIGURATION_REQUIRED')

_TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?')
def _aware_timestamp(value, zone_name):
    if not isinstance(value,str) or not _TIMESTAMP.fullmatch(value): raise ValueError('INVALID_TIMESTAMP')
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is not None: return parsed
    try: zone=ZoneInfo(zone_name)
    except (KeyError,ValueError,TypeError): raise ValueError('INVALID_TIME_ZONE') from None
    first, second = parsed.replace(tzinfo=zone,fold=0), parsed.replace(tzinfo=zone,fold=1)
    # Missing spring time or ambiguous autumn time needs an explicit offset.
    if first.utcoffset()!=second.utcoffset() or first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)!=parsed:
        raise ValueError('AMBIGUOUS_OR_MISSING_LOCAL_TIME')
    return first

def available_window_match(slot_iso,windows,duration_min=45,time_zone='Europe/Istanbul',slot_timezone='Europe/Istanbul'):
    """User windows use user zone; naive source timestamps use source zone, never user zone."""
    try:
        ZoneInfo(time_zone)
        if type(duration_min) is not int or not 15<=duration_min<=120 or not isinstance(windows,list) or len(windows)>30: raise ValueError()
        intervals=[(_aware_timestamp(v['start'],time_zone).astimezone(timezone.utc),_aware_timestamp(v['end'],time_zone).astimezone(timezone.utc)) for v in windows]
        if any(b<=a for a,b in intervals): raise ValueError()
    except (KeyError,TypeError,ValueError): raise ValueError('INVALID_AVAILABLE_WINDOW') from None
    if not slot_iso or not windows: return None
    try: start=_aware_timestamp(slot_iso,slot_timezone).astimezone(timezone.utc)
    except (KeyError,TypeError,ValueError): return None
    end=start+timedelta(minutes=duration_min)
    return any(a<=start and end<=b for a,b in intervals)

def normalize_care_slots(search_result, windows, duration, user_zone):
    """A source row is not a verified time, calendar event or measured travel route."""
    available_window_match(None,windows,duration,user_zone)
    rows=[]
    for raw in search_result.get('slots',[]):
        if not isinstance(raw,dict) or not safe_care_url(raw.get('bookingUrl'),raw.get('sourceId')): continue
        row=dict(raw)
        row.setdefault('isOnline',None)
        if row.get('sourceType') not in ('LIVE_AVAILABILITY','LIVE_PROVIDER_ONLY','PUBLIC_SEARCH_ONLY','DEMO'): continue
        if row.get('sourceType')=='DEMO' and search_result.get('providerType')!='DEMO': continue
        source=CARE_SOURCES.get(row.get('sourceId'))
        demo=row.get('sourceType')=='DEMO' and search_result.get('providerType')=='DEMO'
        source_zone=source['zone'] if source else None
        try: date=_aware_timestamp(row.get('dateTime'),source_zone).isoformat() if row.get('sourceType')=='LIVE_AVAILABILITY' and source else None
        except (KeyError,TypeError,ValueError): date=None
        if demo: date=row.get('dateTime')
        if not date and row.get('sourceType')=='LIVE_AVAILABILITY':
            row['sourceType']='LIVE_PROVIDER_ONLY'
            row['sourceBadge']='Hekim profili (tam tarih ve saat doğrulanmadı)'
        row['dateTime']=date
        if not date: row['rawExtractedTime']=None
        fits=available_window_match(date,windows,duration,user_zone,source_zone or 'Europe/Istanbul')
        if fits is False: continue
        row.update(calendarConflict=None,calendarFits=fits,calendarBadge='Kullanıcının uygun zaman aralığı' if fits is not None else 'Saat doğrulanmadı',
            travelTimeMin=None,trafficBadge=None,matchScore=None,durationMin=duration,timeZone=user_zone)
        rows.append(row)
    return rows
