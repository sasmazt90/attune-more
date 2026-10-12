# TOGG Attune — Hedef D: İnce Kaz Ayakları Yerelleştirme ve Doğrulama Raporu (v4)

**Tarih:** 12 Ekim 2026  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Dondurulmuş Baseline Commit:** `ff0b161bd807fe81d2ba5ee6283d4f5b26f6a102` (`outer-canthus-gabor-radiating-hair-excluded-v3`)  
**Aday Normalizasyon Sürümü:** `outer-canthus-gabor-radiating-hair-excluded-v4`  
**Doğrulama ve Kanıt Klasörü:** `audit-results/crows-feet-v4-verification-20261012/`  
**Resmi Makine Makbuzu:** `audit-results/crows-feet-v4-verification-20261012/crows-feet-receipt.json`  
**Görsel Karşılaştırma Galerisi:** `audit-results/crows-feet-v4-verification-20261012/gallery/index.html`  

---

## 1. Giderilen Hatalar ve Kök Neden Analizi

### A. Harita Koordinat Dönüşüm Hatasının Giderilmesi
- **Eski Durum:** Değerlendirme script'inde `decode_map_overlay`, `localMap` nesnesinin `step` alanını (`step = 1 / scale`) kullanmıyor ve analiz-grid koordinatlarını doğrudan kaynak fotoğraf koordinatı gibi yerleştiriyordu. Bu durum harita örtüşmesinin küçülmesine ve şakak bölgesine doğru kaymasına yol açıyordu.
- **Düzeltme:** Araç içi SVG bileşeninin (`SkinFacePanel.tsx: width={localMap.width*localMap.step}, height={localMap.height*localMap.step}`) gerçek çizim sözleşmesi esas alındı.
  - `rgba` ve `validMask` tensörleri `step` katsayısıyla `INTER_NEAREST` (piksel tabanlı çizim) kullanılarak kaynak boyutuna yeniden örneklendi (`src_w = width * step`, `src_h = height * step`).
  - Koordinat uzayları açıkça ayrıldı: **Analiz-Grid Aktif Pikselleri** (`grid_active_pixels`) ve **Kaynak Eşlenmiş Aktif Pikselleri** (`source_mapped_active_pixels`) ayrı kaydedildi.
  - `dataUrl` alpha kodlaması (0–100 aralığı) doğrulanarak siyan katman kaynak fotoğraftaki gerçek anatomik lateral canthus çizgilerinin üzerine piksel hassasiyetiyle oturtuldu.

### B. Sabit Başarı Değerlerinin Kaldırılması ve Canlı Baseline Yürütümü
- Makbuzdaki `positiveSamplesRescued`, `positiveSamplesPreserved`, `negativeControlsFalsePositiveCount`, `zeroMapCardConsistencyVerified` ve `nonRegressionVerified` alanları sabit değerler yerine dinamik kurallardan hesaplandı.
- Baseline skorları metin içinden değil, dondurulmuş `ff0b161` sürümünün izole modül olarak (`scratch/appearance_analysis_ff0b161.py`) aynı üretim girdileriyle eşzamanlı çalıştırılmasıyla canlı elde edildi.
- Morluk (`dark`), torbalanma (`bags`), kuruluk (`dry`) ve sarkma (`sag`) kriterlerinin önce/sonra değer farkı (\(\Delta < 10^{-4}\)), sınırlama kodu ve kalite durumları 7 örnekte birebir karşılaştırılarak %100 non-regression kanıtlandı.

### C. Yuvarlama ile Yanlış Sinyalin Gizlenmesinin Önlenmesi
- Skorlar yalnızca tam sayı UI (%0 veya %1) üzerinden değil; ham sürekli değer (`raw`), yerel piksel dağılımı ve incelenmiş negatif ROI ilişkisiyle raporlandı.
- Harita alpha kodlamasında (\(\text{alpha} = \text{round}(\text{clip}(v/100, 0, 1) \times 100)\)) ham skorun \(< 0.50\) olduğu zayıf sinyallerin tamsayı alpha'da 0'a yuvarlanması durumu matematiksel bir tutarsızlık olarak değil, PNG yoğunluk nicemlemesinin doğal bir sonucu olarak belgelendi.
- %0 UI gösterimi "ham sinyal tamamen sıfır" iddiasıyla sunulmadı; `4b13b16a` (ham: `0.3322`) ve `5bd42346` (ham: `0.4156`) örneklerindeki mikron katlantı ve köşe gürültüsü kalıntıları açıkça belirtildi.

### D. Makyaj Dışlama Tabanının Bağıl Cilt Parlaklığına Bağlanması
- `appearance_analysis.py` içindeki `(gray > 0.18)` mutlak tabanı kaldırılarak yerine bağıl medyan cilt parlaklığı `gray >= med_l * 0.50` getirildi.
- Bu sayede koyu ciltli veya hafif periorbital gölgede kalan gerçek kırışıklıkların (\(0.12 < gray < 0.18\)) makyaj zannedilerek elenmesi engellendi; mutlak koyu pikselleri tek başına makyaj sayma hatası kapatıldı.

---

## 2. Gerçek Baseline (ff0b161) ve Aday (v4) Karşılaştırma Sonuçları

`scripts/evaluate_crows_feet_v4.py` tarafından canlı yürütülerek `audit-results/crows-feet-v4-verification-20261012/crows-feet-receipt.json` makbuzuna kaydedilen kesin sonuçlar:

| Örnek SHA | Örnek Kategorisi / Rolü | Baseline v3 (raw / UI / grid_px / src_px) | Candidate v4 (raw / UI / grid_px / src_px) | Değerlendirme ve Yerel Doğrulama Durumu |
| :--- | :--- | :--- | :--- | :--- |
| **`a94f1646`** | **Development Kontrolü**<br>(Pozitif İnce Kaz Ayağı) | `0.0000` / %0 / 0 px / 0 px<br>*(False Negative — Başarısız)* | **`0.5838`** / **%1** / **101 px** / **107 px** | **KURTARILDI & DOĞRULANDI**<br>Lateral canthus'tan şakağa radyal uzanan ince çizgiler yakalandı; haritada siyan örtüşme doğrulandı. |
| **`02386f86`** | **Development Kontrolü**<br>(Pozitif Derin Kaz Ayağı) | `1.4335` / %1 / 104 px / 157 px | **`3.3882`** / **%3** / **184 px** / **260 px** | **KORUNDU & GÜÇLENDİRİLDİ**<br>Derin anatomik oluklar çok ölçekli frekans bankasıyla (\(0.13, 0.18, 0.26\)) tam güçte ölçüldü. |
| **`beda0290`** | **Development Kontrolü**<br>(Eyeliner & -24.5° Roll Negatifi) | `0.4012` / %0 / 5 px / 5 px | **`0.0009`** / **%0** / **0 px** / **0 px** | **TEMİZ SIFIR NEGATİF**<br>Siyah eyeliner ucu bağıl parlaklık tabanıyla dışlandı; aşırı açılı sağ göz `INSUFFICIENT_VISIBLE_AREA` ile korundu. |
| **`4b13b16a`** | **Development Kontrolü**<br>(Doğal Dik Negatif Kontrol) | `0.4113` / %0 / 10 px / 10 px | **`0.3322`** / **%0** / **10 px** / **10 px** | **TEMİZ SIFIR UI (Düşük Taban)**<br>Göz yarığı bileşkesindeki 10 piksellik mikro-katlantı taban altında; UI %0, sahte alarm üretmiyor. |
| **`5bd42346`** | **Development Kontrolü**<br>(Dönüştürülmüş Regresyon) | `0.3335` / %0 / 25 px / 25 px | **`0.4156`** / **%0** / **72 px** / **72 px** | **TEMİZ SIFIR UI (Gürültü Kontrolü)**<br>20.5° dönme ve köşe üçgeni yapaylığına rağmen skor taban altında tutuldu. |
| **`01955323`** | **Keşif Amaçlı Doğal Kontrol**<br>(Görsel Negatif İnceleme) | `0.0000` / %0 / 0 px / 0 px | **`0.0000`** / **%0** / **0 px** / **0 px** | **GÖRSEL İNCELEME NEGATİFİ**<br>Dik doğal çekim (yaw: 0.31, roll: 0.08); göz dış köşelerinde sıfır çizgi, sıfır aktif piksel. Görsel olarak pürüzsüz teyit edilmiş olup, bağımsız görülmemiş test kümesi genellemesi iddia edilmez. |
| **`7a8f4488`** | **Kalite Reddi Kontrolü**<br>(Üretim Kapısı Elenmesi) | `None` (`CAPTURE_QUALITY`) | `None` (`CAPTURE_QUALITY`) | **GÜVENLİ KALİTE REDDİ**<br>Etiketli kırışıklık mevcut ancak aşırı baş açısı (`yaw: -1.02 < -0.35`) nedeniyle üretim kalite kapısınca güvenle elendi. |

> [!NOTE]
> **Negatif Seçim ve Genelleme İlkesi:** Etiketsiz alanlar otomatik negatif kanıtı kabul edilmez. Negatif kontroller için yalnız doğrulanmış negatif ROI (`beda0290`, `4b13b16a`), dönüştürülmüş regresyon (`5bd42346`) veya görsel olarak incelenmiş pürüzsüz anatomik alan (`01955323`) dayanak alınmıştır.


---

## 3. Diğer Yöntemlerin Korunması (Non-Regression Kanıtı)

Tüm örneklerde aşağıdaki kriterler eşzamanlı doğrulanmış ve mutlak farkın sıfır olduğu (\(\Delta < 10^{-4}\)) makine makbuzunda kayıt altına alınmıştır:
- **Morluk v4 (`dark`):** `lower-lid-contrast-chroma-local-v4` skorları ve sınırlama kodları birebir korunmuştur.
- **Torbalanma v5 (`bags`):** `contour-fold-local-support-v5` pretarsal marj ofsetleri ve skorları etkilenmemiştir.
- **Kuruluk (`dry`):** `eligible-flake-area-fixed-v2-shared` analizi değişmemiştir.
- **Sarkma (`sag`):** Yanak ve çene süreklilik formülleri korunmuştur.
- **Test Güvencesi:** [`tests/unit/test_skin_expanded_corrections.py`](file:///c:/Users/PC/Desktop/AI%20Workspace/TOGG/attune-antigravity-skin/tests/unit/test_skin_expanded_corrections.py) (10 test), [`tests/unit/test_skin_anatomical_bands.py`](file:///c:/Users/PC/Desktop/AI%20Workspace/TOGG/attune-antigravity-skin/tests/unit/test_skin_anatomical_bands.py) ve [`tests/unit/test_local_appearance_health.py`](file:///c:/Users/PC/Desktop/AI%20Workspace/TOGG/attune-antigravity-skin/tests/unit/test_local_appearance_health.py) (25 test) olmak üzere **35/35 birim test %100 yeşil olarak geçmiştir**.

---

## 4. Kaynak Hash'leri ve Doğrulama Kimliği

- **Makbuz Dosyası:** `audit-results/crows-feet-v4-verification-20261012/crows-feet-receipt.json`
- **Çalışma Başlangıcı:** `2026-10-12T18:46:57Z`
- **Çalışma Bitişi:** `2026-10-12T18:48:01Z` (Süre: 63.86 saniye)
- **Dosya Hash'leri (SHA-256):**
  - `services/core-api/appearance_analysis.py`: `ef693b29b5e5f8c389b882ac17b7033e62c794f1b43b210ab5d55cdf1eb271dd`
  - `services/core-api/instant_appearance.py`: `1e750e6a56dac61303e3f8049a30340fc0956488d5d5b0b0ed499ac1bbf99f45`
  - `services/core-api/skin_models.py`: `9416452913099d709e77313a87a05b84420af03c77466c4cafea1e428a5a8ba4`
  - `face_landmarker.task`: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- **CD İzolasyon Garantisi:** `attune-live-test` çalışma alanı salt okunur kalmış, hiçbir dosyasına yazılmamış ve mevcut çalışma ağacı korunmuştur.
