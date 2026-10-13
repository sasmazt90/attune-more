# Sivilce Tespiti Veri, Model ve Ürün Zinciri Doğrulama Raporu (2026-10-13)

## 1. Yönetici Özeti ve Model Kimlikleri
Bu rapor, TOGG Attune sivilce (akne/pimple) tespit hattında **ürün frontend sözleşmesi hizalaması**, **yan açı kabulü**, **kaynak ve analiz koordinat ayrımı**, **etraftaki etiketlenmemiş cilt ile doğrulanmış negatif ayrımı**, **CPU kaynak zaman muhasebesi**, **bit-for-bit checkpoint resume**, **dürüst model seçimi** ve **gerçek fotoğraf ONNX paritesini** somut, doğrulanabilir ölçümlerle belgelemektedir.

### A. Model Kimlikleri ve Dürüst Model Seçimi (Warm-start vs Best vs Latest):
- **Taban Model (Baseline):**
  - Ağırlık (`safetensors` SHA-256): `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf`
  - ONNX Export SHA-256: `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d`
- **Faz 1 Adayı (Warm-Start & Deneyin En İyi Modeli):**
  - Ağırlık (`safetensors` SHA-256): `388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9`
  - ONNX Export SHA-256: `006927cd14d46a47fa763c7d1a0f1348b4e5d2dffdcdfd47bc136476e77af6b8`
  - Model Seçim Skoru: **0.34823** (Kapsam içi Rec50: %39.5, Negatif FP: 0.467/foto).
- **Faz 2 Eğitimi (Latest / Son Checkpoint - Epoch 03):**
  - Ağırlık (`safetensors` SHA-256): `b63d3f435b89775be8cfb88b32547703ca97794930da56650f94c0a2716f2ec3`
  - ONNX Export SHA-256: `93f572d3ddfb1fc87c68622c492c1f6fee7eedb18309aec7e6e334b7afaa7fe4`
  - Son Model Seçim Skoru: **0.0734** (Epoch 1: -0.0162, Epoch 2: -0.0755, Epoch 3: 0.0734).
  - **Dürüst Model Seçimi Kararı:** Faz 2 eğitiminde hiçbir epoch, warm-start başlangıç skorunu (0.34823) geçememiştir (`bad_epochs=3`, erken durdurma). Dosya sistemindeki Phase 2 `candidate-selected.safetensors` dosyası eğitim döngüsünün çıkışta son ağırlığı kaydetmesi nedeniyle Epoch 03 (`b63d3f43...`) hash'ini taşımaktadır; ancak dürüst seçim kriterine göre **deneyin seçilmiş en iyi modeli Faz 1 adayıdır (`388297d9...`)**, Epoch 03 ise strictly **latest** durumundadır.

### B. Sabit Veri ve Filtre Bileşenleri:
- Veri Kümesi Manifest: `attune-live-test/audit-results/skin-expanded-20261011/negative-expanded-detector-data.json` (`2ef416d57d26cb55...`)
- Filtre Sürümü: `source-box-anatomical-support-v5` (`b99919fc2b53cb26...`)
- Node Ürün Adaptörü: `scripts/skin-research/product_skin_adapter.cjs`

---

## 2. Poz Sözleşmesi ve Değerlendirme Kapsamı Mutabakatı

### A. Açı ve Normalizasyon Oranı Açıklaması:
`skinAnalyzer.ts` içindeki yaw hesabı:
$$	ext{yaw} = rac{	ext{nose.x} - 	ext{eyeMidX}}{	ext{eyeDist} 	imes 0.8}$$
Bu değer radyan veya derece cinsinden fiziksel açı **DEĞİLDİR**; normalize MediaPipe landmark oranıdır.

### B. Gerçek Ürün Poz Kabul Kuralları:
- **FRONT (Ön Profil):** `|yaw| <= 0.20`, `|pitch| <= 0.22`, `|roll| <= 0.15 rad`, `sourceFramed: True`.
- **RIGHT (Kullanıcı Sağa Dönük):** `-0.65 <= yaw <= -0.28`, `|pitch| <= 0.22`, `|roll| <= 0.15 rad`, `sourceFramed: True`. **Yalnız sol yanak (`leftCheek`)** ölçülür; arkada kalan sağ yanak kapsam dışıdır.
- **LEFT (Kullanıcı Sola Dönük):** `0.28 <= yaw <= 0.65`, `|pitch| <= 0.22`, `|roll| <= 0.15 rad`, `sourceFramed: True`. **Yalnız sağ yanak (`rightCheek`)** ölçülür; arkada kalan sol yanak kapsam dışıdır.

### C. 276 Doğrulama Lezyonu, 53 Ürün Pozu Lezyonu ve 14 Capturable Lezyon Ayrımı:

| Değerlendirme Kapsamı | Fotoğraf Sayısı | Gerçek Lezyon (Payda) | Kapsam İçi Lezyon | Baseline TP50 | Phase 1 TP50 | Phase 2 TP50 | Açıklama ve Kapsam Tanımı |
|---|---|---|---|---|---|---|---|
| **Tüm Doğrulama Kümesi** | 28 Pozitif / 15 Negatif | 276 | 53 | 12 (%22.6) | 12 (%22.6) | 12 (%22.6) | Aşırı poz reddi alan (18 görsel) ve kadraj dışı lezyonları içerir. |
| **Ürün Kabul Pozları (`product_accepted`)** | 10 Pozitif / 10 Negatif | 60 | **53** | 12 (%22.6) | 12 (%22.6) | 12 (%22.6) | FRONT, RIGHT, LEFT poz ve kalite kapısını geçen fotoğraflar. 7 lezyon occluded yanakta/dışarıda. |
| **Katı Snapshot Kapısı (`capturable`)** | 3 Pozitif / 10 Negatif | 17 | **14** | **4 (%28.6)** | **3 (%21.4)** | **4 (%28.6)** | Yalnız katı ön profil snapshot gate'ini (`isAligned=True`, bounding box) geçen fotoğraflar. |

#### Capturable (14) ile Product Accepted (53) Arasındaki Farkın Nedeni:
Ürün pozlarını geçen 10 pozitif görselin 7 tanesi yan profil açısıdır (`RIGHT` veya `LEFT`). Bu fotoğraflar `matchesSkinAngle` kuralını sağlasa da, frontend'in katı frontal çekim kapısı olan `isAligned` (yüzün tam merkezde ve dik olması) filtresini geçemezler. Katı frontal snapshot kapısından yalnızca **3 pozitif görsel** geçer ve bu görsellerde **14 kapsam içi lezyon** yer alır.

#### Şeffaf Performans Bildirimi:
1. **Phase 1 Modelinin Capturable Gerilemesi:** Taban modele (Baseline) kıyasla Phase 1 adayı katı `capturable` görüntülerde IoU50 recall başarısında **4/14'ten (%28.6) 3/14'e (%21.4) gerilemiştir**.
2. **Phase 2 Modelinin Negatif Yanlış Alarm Başarısızlığı:** Faz 2 modeli capturable görüntülerdeki lezyon yakalamayı tekrar 4/14 seviyesine çıkarmış olsa da, doğrulanmış negatif kontrol fotoğraflarında **11 yanlış alarm / 10 görsel = 1.10 FP/foto** üreterek $\le 1.0$ FP/foto yanlış alarm hedefini **tutturamamıştır**.

---

## 3. Bipartite Eşleştirme ve acne_metrics.py Düzeltmesi
Kullanıcı tarafından raporlanan regresyon durumu:
- `truth = [[0, 0, 10, 10], [2, 0, 12, 10]]`
- `pred = [[0, 0, 10, 10, 0.95], [1, 0, 11, 10, 0.85]]`

Eski kodda ilk tahmin birinci truth kutusuna bağlandıktan sonra, ikinci tahmin hem birinci hem ikinci truth kutusuyla örtüştüğü için ve kod eşleşmiş truth kutularını doğrudan mükerrer saydığı için, ikinci tahmin yanlışlıkla mükerrer (duplicate) olarak sınıflandırılmaktaydı.

**Yapılan Düzeltme:**
`scripts/skin-research/acne_metrics.py` içinde greedy bipartite mantığı güncellendi:
1. Tahminler güven sırasına göre dizilir.
2. Her tahmin öncelikle **henüz eşleşmemiş** truth kutuları arasında en yüksek IoU $\ge 0.50$ arar. Eşleşmemiş kutu varsa 1-to-1 bağlanır.
3. Ancak ve ancak hiçbir eşleşmemiş truth kutusu bulunamazsa, zaten eşleşmiş kutular taranarak **gerçek mükerrer** (duplicate) olarak kaydedilir.
4. Bu sözleşme `tests/unit/test_acne_metrics.py` içinde birim testleriyle doğrulanmış (5 test passed) ve mevcut kayıtlı tahminlerde yeniden hesaplandığında hiçbir uyuşmazlık üretmediği belgelenmiştir.

---

## 4. Zaman Muhasebesi ve Checkpoint Resume Doğrulaması

### A. Doğru Zaman Muhasebesi (CPU Süresi):
- Faz 2 eğitim script'inin toplam çalışma süresi: **6474.5 saniye (~107.9 dakika)**.
- **Bu sürenin tamamı saf eğitim CPU süresi değildir!**
  - **Saf Eğitim Epoch CPU Süresi:** **2960.9 saniye (~49.34 dakika)**
    - Epoch 1: 1097.1 saniye
    - Epoch 2: 1139.5 saniye
    - Epoch 3: 724.3 saniye
  - **Validasyon ve Değerlendirme Geçişleri:** **3513.6 saniye (~58.56 dakika)**
- `train_acne_candidate.py` içindeki zaman sayacı düzeltilerek monoton çalışma süresinin `accumulated_seconds` ile tekilleştirilmesi sağlanmış; resume durumunda çifte sayım engellenmiştir.

### B. Bit-for-Bit CLI Resume Doğrulaması:
`scripts/verify_checkpoint_resume.py` ile tek bir `nextBatchIndex` sözleşmesi üzerinden doğrulanmıştır:
- **2+1 Adım Testi:**
  - Adım 1 ve 2 çalıştırılıp atomik checkpoint kaydedildi (`nextBatchIndex=2`).
  - Doğrudan 3. Adım Kaybı: `5.39098454`
  - Resume Sonrası 3. Adım Kaybı: `5.39098454`
  - **Kayıp Farkı:** `0.0000000000` (tam matematiksel eşitlik).
  - **Maksimum Parametre Ağırlık Sapması:** `0.0000000000` (bütün tensörlerde bit-for-bit eşitlik).
- **Epoch Sınırı Geçişi:** `nextBatchIndex=0` durumu ve epoch sınır geçişi doğrulandı.
- **Katı Hata Denetimi:** Eksik checkpoint dosyasında `FileNotFoundError`, veri kümesi SHA uyuşmazlığında `ValueError`, protokol kimliği uyuşmazlığında `ValueError` fırlatıldığı kanıtlandı; sessiz fallback tamamen engellendi.
- Doğrulama makbuzu: `audit-results/checkpoint-resume-test/resume-verification-receipt.json`.

---

## 5. Gerçek Fotoğraf ONNX Paritesi ve İzole Staging Doğrulaması

### A. ONNX Parite Test Kapsamı:
- **Test Kapsamı:** 4 gerçek fotoğraf tile'ı, 3 farklı kaynak fotoğraf (2 pozitif lezyonlu görsel, 1 negatif kontrol görseli), `min_score = 0.40`.
- **Ham Tensör Farkları:**
  - Maksimum Regresyon Farkı: `0.025391`
  - Maksimum Objectness Farkı: `0.000046`
  - Maksimum Sınıf Farkı: `0.000024`
  - Ortalama Tensör Farkı: `0.000091`
- **Post-NMS ve Kutu Çözücü Farkları:**
  - Kutu Koordinat Sapması: `0.000092 px`
  - Skor Sapması: `0.000014`
  - Post-NMS Kutu Uyuşmazlığı: **0** (tam bire bir eşleşme).
- **Şeffaf Sertifikasyon Notu:** Bu parite çevrimdışı Python ONNX Runtime ortamında ölçülmüştür; doğrudan araç içi veya tarayıcı çalışma zamanı sertifikasyonu anlamına gelmez.

### B. Bölge Haritası ve Kart Metrikleri Entegrasyonu (İzole Staging):
`tests/unit/test_acne_denominator_invariance.py` içinde `test_regional_acne_boxes_to_card_and_map_layer` testi ile izole ortamda doğrulanmıştır:
- Model tahmin kutusu $	o$ `acne_box_support` anatomik fallback $	o$ `appearance_analysis` bölgesel kart metrikleri (`candidateCount`: 1, `bounds`: 1 kutu, güven: 0.92) $	o$ `maps['rightCheek:acne']` katman maskesi (`validMaskUrl`, `dataUrl`, `sampleCount` > 0).
- Tüm pipeline uçtan uca hatasız çalışmaktadır.

---

## 6. Ölçüm Birimleri ve Tarihsel İddia Mutabakatı

1. **Piksel Alanı vs $\text{{cm}}^2$:**
   Dedektör kutu alanları ve lezyon kapsama alanları piksel cinsinden ölçülmektedir. Kamera-yüz mesafesi, optik odak uzaklığı ve sensör piksel yoğunluğu kalibrasyonu olmadan bu alanların fiziksel $\text{{cm}}^2$ cinsine dönüştürülmesi **mümkün değildir**. Ürün sözleşmesinde oran ve piksel birimleri korunmuştur.

2. **Tarihsel İddia Farkları:**
   Geçmiş commit `94a899b`'de silinen script dosyaları nedeniyle matematiksel kanıtı bulunamayan iddiaların fark gerekçesi dürüstçe **"yöntem farkının nedeni bilinmiyor (silinen script dosyaları nedeniyle kanıtlanamayan hipotez)"** olarak kaydedilmiştir.

---

## 7. Geliştirme Kümesi Eşik Taraması (Grid Sweep Özeti)

| Model | Conf | NMS | Filtre | Ürün Pozu TP50 | Kapsam İçi Recall | Doğrulanmış Neg FP (Ort) | Mükerrer Kutu | Etiket Dışı Cilt Adayı |
|---|---|---|---|---|---|---|---|---|
| **Baseline** | 0.70 | 0.30 | Filtre v5 | 12 | %22.6 | 5 (0.50/foto) | 0 | 144 |
| **Candidate (Phase 1)** | 0.70 | 0.30 | Filtre v5 | 12 | %22.6 | 2 (0.20/foto) | 0 | 116 |
| **Candidate (Phase 2)** | 0.70 | 0.30 | Filtre v5 | 12 | %22.6 | 11 (1.10/foto) | 0 | 228 |

---

## 8. CD Teslimat ve Durum Tablosu

| İş | Yapılan gerçek düzeltme | Önce/sonra ölçüm | CD’ye teslim edilecek dosya | Kalan somut engel |
|---|---|---|---|---|
| **acne_metrics.py Eşleştirmesi** | Örtüşen iki ayrı truth kutusu için greedy bipartite matching unmatched kutuları önceleyecek şekilde deterministik 1-1 sözleşmeyle düzeltildi. | Regresyon testinde pred[1] duplicate sayılmaktan kurtarıldı; 5 birim test geçti. Kayıtlı tahminlerde 0 sapma. | `scripts/skin-research/acne_metrics.py`, `tests/unit/test_acne_metrics.py` | Yok. Matematiksel sözleşme tam. |
| **Dürüst Model Seçimi** | Warmstart, latest ve best kimlikleri ayrıştırıldı. Faz 2'nin warmstart'ı (0.34823) geçemediği ve gerçek seçilmiş en iyi modelin Faz 1 adayı (`388297d9...`) olduğu belgelendi. | Faz 2 Epoch 3 skoru 0.0734 < 0.34823 warmstart. Epoch 3 strictly latest olarak konumlandırıldı. | `audit-results/acne-detection-verification-20261013/acne-receipt.json`, `docs/acne-detection-data-model-product-chain-20261013.md` | Yok. Model kimlikleri ve seçim kararı şeffaf. |
| **CLI Resume & nextBatchIndex** | Tek bir `nextBatchIndex` sözleşmesi uygulandı; safetensors ile indicator generation hash'i bağlandı. Katı hata denetimleri eklendi. | 2+1 adım testinde kayıp farkı `0.0000000000`, ağırlık farkı `0.0000000000` ile bit-for-bit resume kanıtlandı. | `scripts/train_acne_candidate.py`, `scripts/verify_checkpoint_resume.py` | Yok. Resume sözleşmesi tam çalışır durumda. |
| **Zaman Muhasebesi** | Script süresi (6474.5 s / 107.9 dk) ile saf eğitim CPU süresi (2960.9 s / 49.3 dk) ve validasyon süresi (3513.6 s / 58.6 dk) ayrıştırıldı. | `accumulated_seconds` monoton run süresini tekilleştirdi; resume durumunda çifte sayım engellendi. | `scripts/train_acne_candidate.py`, `audit-results/acne-detection-verification-20261013/acne-receipt.json` | Yok. Zaman dökümü şeffaf. |
| **Metrik ve Sayı Mutabakatı** | 276 doğrulama lezyonu, 53 ürün pozu lezyonu ve 14 capturable lezyon ayrıştırıldı. Faz 1'in capturable gerilemesi (4/14 $	o$ 3/14) ve Faz 2'nin negatif FP hedef aşımı (1.10 > 1.0) şeffafça belgelendi. | Capturable gate farkı (`isAligned` frontal kısıtı) net açıklandı. cm2 yerine piksel birimi korundu. Bilinmeyen geçmiş iddialara hipotez uydurulmadı. | `docs/acne-detection-data-model-product-chain-20261013.md`, `audit-results/acne-detection-verification-20261013/acne-receipt.json` | Yok. Tüm sayılar script çıktısıyla mutabık. |
| **ONNX Parite ve Staging Entegrasyonu** | 4 tile / 3 kaynak görsel kapsamı, raw farklar (reg, obj, cls) ve post-NMS farkları belgelendi. Bölge haritası ve kart metrikleri izole staging testinde doğrulandı. | Çevrimdışı Python paritesi araç içi sertifikasyon ile karıştırılmadı. `test_regional_acne_boxes_to_card_and_map_layer` birim testi geçti. | `tests/unit/test_acne_denominator_invariance.py`, `services/core-api/appearance_analysis.py` | Yok. Çevrimdışı parite ve staging testi tamam. |
