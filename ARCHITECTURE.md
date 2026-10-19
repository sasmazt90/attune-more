# Sistem Mimarisi (ARCHITECTURE.md)

Bu belge, **Attune.more**'un modüler yapısını, veri akışını ve otomotiv soyutlama katmanlarının önceki mimari kesitini açıklar. Güncel beş sağlık modülü ve gerçek/simüle/planlanan özellik ayrımı için [README](README.md) esas alınır; aşağıdaki eski şema güncel teslim envanteri değildir.

---

## 1. Genel Sistem Mimarisi

```
+-------------------------------------------------------------------------+
|                         ATTUNE.MORE KOKPİT                              |
|                  (Next.js 14 / TypeScript / Tailwind)                   |
+--------------------+-------------------------------+--------------------+
                     |                               |
        [VehicleContextProvider]            [Unified Health Profile]
        - Sürüş / Park Durumu                - Görme Geçmişi (Gerçek Staircase)
        - Hız & Konum (Simüle Kontrol)       - Cilt Değişim Geçmişi (MediaPipe)
        - Kamera / Mikrofon İzinleri         - Seans Özetleri & Eğilimler
                     |                               |
+--------------------+-------------------------------+--------------------+
|                         FASTAPI CORE API                                |
|                   (Python 3.11 / Asenkron Çekirdek)                     |
+------------+---------------+-------------------+------------------------+
             |               |                   |                        |
             v               v                   v                        v
      [1. GÖRME]        [2. CİLT]          [3. MENTAL]              [4. CARE AGENT]
      - Landolt C       - MediaPipe Mesh   - Web Speech API (TR)    - Playwright Keşif
      - 2-Down/1-Up     - 6 Anatomik ROI   - Sürüş Modu Kısıtları   - Safe Handoff
      - Weber Kontrast  - 2R - G - B       - SessionAnalyzer        - Demo Takvim Çakışma
      - Doğrulanan Mesafe- Parlaklık/Doku  - İki Katmanlı Kriz      - Demo TravelTime
             |               |                   |                        |
             +---------------+-------------------+------------------------+
                                         |
                       [Yerel localStorage & JSON Oturum Belleği]
```

---

## 2. Monorepo Yapısı

```
attune-more/
  apps/
    vehicle-app/                  # Next.js 14 kokpit web uygulaması
  services/
    core-api/                     # FastAPI ana API servisi
  packages/
    vehicle-context/              # IVehicleProvider & MockVehicleProvider
    health-profile/               # Ortak Pydantic ve TypeScript veri tipleri
    session-memory/               # Seans kayıt ve eğilim analiz motoru
    safety/                       # Klinik ve sürüş güvenlik katmanları
    shared/                       # Ortak konfigürasyon ve yardımcılar
  docs/                           # Ürün, mimari ve klinik güvenlik dokümantasyonu
  tests/                          # Birim ve entegrasyon testleri
```

---

## 3. Dört Modülün Gerçek Teknik Mimarisi

### 3.1. Modül 1 — Görme Ön Değerlendirmesi (`services/vision` & `apps/vehicle-app`)
* **Lisans Güvenliği:** GPL lisanslı FrACT kodundan tamamen bağımsız; kamu malı standart formüllerle sıfırdan geliştirilmiş psikofiziksel test motoru.
* **Ekran Kalibrasyonu:** Standart kimlik / kredi kartı referans genişliği (85.6 mm) kullanılarak kullanıcının ekran DPI ve milimetre/piksel oranı kalibre edilir.
* **Test Mesafesi (Kullanıcı Doğrulamalı):** Kamera kadraj kılavuzu ile yüz hizalaması yapılır; test mesafesi kullanıcı tarafından onaylanır (50, 55 veya 60 cm). Sentetik veya simüle mesafe döngüsü kesinlikle kullanılmaz.
* **Optotip ve Test Akışı:** Landolt C halkaları 4 temel yönde (Yukarı, Aşağı, Sol, Sağ) çizilir. 2-down / 1-up adaptif basamak (staircase) algoritması ile kullanıcının gerçek yanıtlarına göre LogMAR ve Snellen eşdeğerleri hesaplanır.
* **Ekran Tabanlı Kontrast Duyarlılığı (Ön Değerlendirme):** Weber kontrast prensibiyle ($C = \frac{L_{\text{target}} - L_{\text{background}}}{L_{\text{background}}}$) ekran üzerinde kademelendirilen 5 basamakta sürücünün kontrast ayırt etme eşiğine dair işlevsel bir ön değerlendirme sunulur. Standart tüketici ekranı fotometrik olarak kalibre edilmiş bir klinik cihaz olmadığından klinik Pelli-Robson tanısı iddiası taşımaz.
* **Sürüş Kısıtı:** Araç hareket halindeyken ($v > 0$) test başlatılamaz; sadece park halinde çalışır.
* **Sonuç Dürüstlüğü:** Test tamamlanmadığında hiçbir sahte klinik sonuç (20/30 vb.) üretilmez.

### 3.2. Modül 2 — Cilt Kontrolü ve Referans Takibi (`apps/vehicle-app` & `services/core-api`)
* **MediaPipe Face Landmarker Entegrasyonu:** Sürümü pinlenmiş (`1.0.1`) Apache-2.0 lisanslı `@mediapipe/tasks-vision` paketi ile canlı video karesinden 468 yüz noktası çıkarılır. Yüz algılanamazsa anında `NO_FACE` uyarısı verilir. MediaPipe kütüphanesi veya model asset'i yüklenemezse gerçek cilt analizi başlatılmaz ve sağlık trend metriği üretilmez. Yalnızca `usedMediaPipe = true` olan sonuçların kalıcı olarak kaydedilmesine izin verilir. İlk çalıştırmada model asset'inin Google CDN üzerinden indirilmesi için internet bağlantısı gereklidir.
* **6 Anatomik ROI Ekstraksiyonu:** Alın, Sağ Yanak, Sol Yanak, Burun, Çene ve Göz Çevresi pikselleri gerçek landmark koordinatlarına göre kırpılır. Göz ve dudak bölgeleri maskelenerek piksel kalitesinin bozulması engellenir.
* **Dürüst Non-Klinik Metrikler:**
  - *Kızarıklık Eğilimi:* $2R - G - B$ piksel renk farkı formülü (0-100 normalize).
  - *Cilt Tonu/Parlaklık Eğilimi:* $0.299R + 0.587G + 0.114B$ CIE parlaklık hesabı.
  - *Doku Değişim Göstergesi:* Bölgesel parlaklık standart sapması.
  - "Melanin", "gözenek" veya "kırışıklık analizi" gibi doğrudan ölçülmeyen klinik iddialar yer almaz.
* **Referans (Baz Çizgi) Karşılaştırması:** İlk tarama referans olarak saklanır. Sonraki taramalarda bölgesel değişim ($\Delta$) hesaplanır. Değişim %20 üzerinde olduğunda kullanıcıya *"Bir dermatologla görüşmek faydalı olabilir"* tavsiye dili kullanılır.
* **Sıfır Ham Görüntü Depolama:** Ham fotoğraf veya video asla kaydedilmez; analiz tarayıcı belleğinde bittiği anda kare temizlenir, yalnızca sayısal telemetri saklanır.

### 3.3. Modül 3 — Ruhsal İyi Oluş Asistanı (`services/core-api` & `apps/vehicle-app`)
* **Ses Altyapısı:** Tarayıcı içi W3C Web Speech API (`SpeechRecognition` + `SpeechSynthesis`) ile Türkçe canlı ses tanıma ve okuma.
* **Sağlayıcı Soyutlaması (`MentalConversationProvider`):** `OPENAI_API_KEY` tanımlıysa canlı LLM devreye girer; anahtar yoksa açıkça `[Demo / Fallback Modu]` rozeti taşıyan yerel kural motoru çalışır.
* **Sürüş Modu Sınırları:** Araç hareket halindeyken yanıtlar en fazla 25 kelimeyle sınırlandırılır, ekrana baktırmaz, sürüşe odaklanmayı teşvik eder.
* **Dinamik Oturum Özeti (`MentalSessionAnalyzer`):** Seans sonunda kullanıcının gerçek ifadelerinden yapılandırılmış özet ve temalar çıkarılır; sabit/ezbere temalar yazılmaz.
* **İki Katmanlı Kriz Güvenliği:**
  - *Katman 1:* Deterministik anahtar kelime filtresi (pre-LLM).
  - *Katman 2:* Yapılandırılmış LLM güvenlik değerlendirmesi.
  - Akut krizde yalnızca **112 Acil Çağrı Merkezi** ve güvenli duruş talimatı verilir. 182 hiçbir kriz mesajında yer almaz.
* **Gizlilik:** Kullanıcı gizlilik ekranında mental özet saklamayı kapattıysa oturum belleğe veya diske kesinlikle yazılmaz.

### 3.4. Modül 4 — Sağlık Asistanı ve Hekim Randevusu (`services/core-api/care_provider.py`)
* **Hekim Arama ve Keşif (Doctor Discovery):** Desteklenen ve erişilebilir kamuya açık kaynaklarda hekim ve görünür randevu müsaitliklerini salt-okunur olarak araştırabilecek şekilde tasarlanmıştır. Bu geliştirme ortamında DoktorTakvimi'nin Cloudflare/bot korumasıyla karşılaşılması durumunda bot bypass yapılmaz; şeffaf `FALLBACK_BLOCKED` durumu ve güvenli web devri (Safe Handoff) sunulur. Canlı DoktorTakvimi müsaitlik slotu bu ortamda doğrulanmış değildir; hekim arama denemesi ve bot koruması algılaması doğrulanmıştır.
* **Müsaitlik Dürüstlüğü:**
  - Gerçek siteden slot saati açıkça okunamadığında uydurma randevu tarihi üretilmez; durum `LIVE_PROVIDER_ONLY` olarak işaretlenir ve kullanıcıya *"Doktor profili canlı kaynaktan bulundu — müsaitlik için siteyi aç"* denir.
  - Yalnızca siteden gerçek zaman okunabilirse `LIVE_AVAILABILITY` kullanılır.
  - Demo slotlar açıkça `[Demo Randevu Verisi]` rozeti taşır ve tamamen sentetik hekim/klinik isimleri kullanılır.
* **Takvim Kesişim Matematiği (`CalendarProvider`):** Mevcut program aralıkları ile talep edilen slot arasında $\max(start_1, start_2) < \min(end_1, end_2)$ formülüyle gerçek çarpışma denetimi yapılır. Durum açıkça "Demo Takvim (Yerel Simülasyon)" olarak etiketlenir; gerçek Google/Apple Calendar OAuth entegrasyonu planlanmıştır.
* **Ulaşım Süresi (`TravelTimeProvider`):** Harita API anahtarı olmadığında açıkça "Tahmini Süre — Demo Model" etiketiyle çalışır.
* **Açık Onay Kapısı:** Kullanıcının açık checkbox onayı olmadan randevu kesinleştirilemez.

---

## 4. Araç Bağlamı Soyutlama Katmanı (Vehicle Context)

Gelecekte entegre edilecek araç üreticisinin API/SDK erişimi için `VehicleDataProvider` / `ToggVehicleProvider` mimari soyutlaması kullanılmıştır. İkinci ad eski bir teknik tanımlayıcıdır; mevcut üretici ortaklığı veya tak-çalıştır donanım entegrasyonu kanıtı değildir:

```typescript
export interface VehicleState {
  vehicleMoving: boolean;
  vehicleParked: boolean;
  currentSpeed: number; // km/h
  currentLocation: { lat: number; lng: number; label: string };
  destination?: { lat: number; lng: number; label: string };
  estimatedTravelTime: number; // dakika
  driverAuthenticated: boolean;
  driverName: string;
  driverFatigueSignal: 'LOW' | 'MEDIUM' | 'HIGH';
  cabinCameraAvailable: boolean;
  microphoneAvailable: boolean;
}
```

MVP ortamında bu arayüz `MockVehicleProvider` tarafından beslenir ve üst bardan araç hız simülasyonu (0 km/s - Park / 50 km/s - Sürüş) yönetilir.

---

## 5. Gizlilik ve Veri Güvenliği (Privacy-by-Design & /privacy Ekranı)

- **Ham Veri Politikası:** Bu eski mimari kesitte ham yüz görüntüleri veya mikrofon ses dalgaları kalıcı saklanmıyordu. Güncel Attune.more sürümünde fotoğraf saklama ilgili hizmetin açık tercihine bağlıdır; güncel izin ve saklama akışı için README ve uygulamanın Gizlilik & İzinler ekranı esas alınır. Web Speech API'nin tarayıcı/cihaz seviyesinde çalışması platforma bağlıdır. Canlı LLM etkinse metin transkripti yanıt üretimi için ilgili sağlayıcıya iletilir.
- **Yerel Depolama (Local-First):** Görme ölçüm sonuçları, cilt baz çizgisi ve mental oturum özetleri yerel tarayıcı depolamasında (`localStorage`) ve yerel backend JSON oturum dosyasında tutulur.
- **Gizlilik Yönetim Ekranı (`/privacy`):** Donanım izinlerinin testi, seans özeti kaydetme tercihi, kayıtlı telemetri sayaçları ve tek tıkla "Tüm Yerel Veriyi Kalıcı Olarak Sil" imkânı sunulur.
- Kod tabanımız UNLICENSED (özel mülkiyet) statüsündedir; üçüncü taraf kütüphaneler (Next.js, FastAPI, MediaPipe, Playwright) izin verici açık kaynak lisanslara sahiptir.
