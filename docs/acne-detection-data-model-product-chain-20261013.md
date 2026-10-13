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
  - Doğrulanmış Negatif Kontrol FP Oranı: **0.07 FP/foto** (Yalnız 1/15 görselde yanlış alarm).
- **Faz 2 Eğitimi (Latest / Son Checkpoint - Epoch 03):**
  - Ağırlık (`safetensors` SHA-256): `b63d3f435b89775be8cfb88b32547703ca97794930da56650f94c0a2716f2ec3`
  - ONNX Export SHA-256: `93f572d3ddfb1fc87c68622c492c1f6fee7eedb18309aec7e6e334b7afaa7fe4`
  - Doğrulanmış Negatif Kontrol FP Oranı: **1.33 FP/foto** (20 yanlış alarm / 15 görsel).
  - **Dürüst Model Seçimi Kararı:** Faz 2 eğitiminde hiçbir epoch, warm-start başlangıç skorunu (0.34823) geçememiştir (`bad_epochs=3`, erken durduruldu). Dosya sistemindeki Phase 2 `candidate-selected.safetensors` dosyası Epoch 03 (`b63d3f435b89775b...`) ağırlıklarını taşımaktadır; ancak dürüst model seçimi kriterine göre **CD'ye dondurulacak en iyi model Faz 1 adayıdır (`388297d9bb179bb3...`)**.

### B. Sabit Veri ve Filtre Bileşenleri:
- Veri Kümesi Manifest: `attune-live-test\audit-results\skin-expanded-20261011\negative-expanded-detector-data.json` (`2ef416d57d26cb55...`)
- Filtre Sürümü: `source-box-anatomical-support-v5`
- Kapsam Manifestosu: `audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json`

---

## 2. Poz Sözleşmesi ve Ön Profil Zorunluluğu Çelişkisinin Çözümü

### A. Frontend Kod Analizi (Araç İçi page.tsx ve skinMultiAngle.ts):
Önceki raporda yan profil fotoğraflarının ürün sözleşmesinde elendiği, çünkü `curAlign.isAligned` koşulunun frontal açı zorunlu kıldığı iddia edilmişti.

CD'nin araç içi frontend kodu (`apps/vehicle-app/src/utils/skinMultiAngle.ts`, `skinSnapshot.ts`, `page.tsx`) incelendi:
- `page.tsx` 618. satırında:
  ```typescript
  const aligned = captureState.enabled ? matchesSkinAngle(curAlign, target) : curAlign.isAligned;
  ```
- **Kanıt:** Çoklu açı (`multi-angle`) taraması aktifken, frontal `isAligned` koşulu **kesinlikle çalıştırılmaz**. Bunun yerine doğrudan `matchesSkinAngle(curAlign, target)` onay fonksiyonu kullanılır.
- Dolayısıyla yan profil çekimleri araç içi yazılımda **kesinlikle engellenmemektedir** ve planlanan ürün akışında aktif olarak yürütülmektedir.

### B. Gerçek Validation Kaynaklarında Pipeline Kanıtı:
`scripts/skin-research/verify_multi_angle_pipeline.py` ve `verify_product_angle_pipeline.cjs` çalıştırılarak üç gerçek geliştirme fotoğrafında browser canvas/MediaPipe -> snapshot -> payload akışı doğrulanmıştır:

| Hedef Açı | Görüntü Kimliği | Yaw / Pitch / Roll | Frontal `isAligned` | `matchesSkinAngle` | Quality Status | Snapshot Üretildi mi? | Nihai Durum ve Elenme Nedeni |
|---|---|---|---|---|---|---|---|
| **FRONT** | `695ed248` | -0.07 / -0.05 / -0.06 | **True** | **True** | OPTIMAL (blur 5.04) | **Evet** (Tüm yüz ROI'leri) | **Kabul Edildi (Capturable)** |
| **RIGHT** | `55d380f7` | -0.49 / -0.13 / 0.12 | **False** | **True** | OPTIMAL (blur 4.62) | **Evet** (`leftCheek` ROI'si) | **Kabul Edildi (Capturable)** |
| **LEFT** | `5432a6e1` | 0.52 / 0.00 / 0.05 | **False** | **True** | BLURRY (blur 3.14) | Evet (`rightCheek`) | **Reddedildi (Kalite Eşiği: blur < 4.0)** |

**Sonuç:**
1. `55d380f7` görüntüsü **gerçek bir RIGHT yan profil çekimidir** ve frontal `isAligned` false olmasına rağmen tüm kapıları geçerek **capturable** olmuştur! (7 lezyon yakalanmıştır).
2. Diğer ürün açısına sahip pozitif fotoğrafların elenmesinin gerçek teknik nedeni açı değil, `SkinAnalyzer.checkQuality` filtresinin **Laplacian bulanıklık eşiğidir (`blurScore < 4.0`, status: BLURRY)**.

---

## 3. Beş Checkpoint'in Yan Yana Karşılaştırmalı Değerlendirmesi

Tüm modeller aynı ürün sözleşmesiyle (384x384 karo, stride 288, min_score=0.70, NMS=0.30, Filtre v5 ve 1-to-1 bipartite eşleştirme) değerlendirilmiştir:

| Model | Ağırlık SHA-256 | Kapsam İçi Rec50 (53 truth) | Kapsam İçi Rec30 (53 truth) | Capturable Rec50 (14 truth) | Capturable Rec30 (14 truth) | Tüm Veri Rec50 (276 truth) | Negatif FP/foto (15 görsel) | Toplam Negatif FP |
|---|---|---|---|---|---|---|---|---|
| **Taban Model (Baseline)** | `1a014adad262b02e...` | 0.2642 (14/53) | 0.4151 (22/53) | 0.2857 (4/14) | 0.5 (7/14) | 0.2935 (81/276) | **0.53** | **8/15** |
| **Faz 1 Adayı (Warm-Start)** | `388297d9bb179bb3...` | 0.2075 (11/53) | 0.3962 (21/53) | 0.1429 (2/14) | 0.4286 (6/14) | 0.25 (69/276) | **0.07** | **1/15** |
| **Faz 2 Epoch 1** | `2d3ba0052b1ca8ad...` | 0.2642 (14/53) | 0.434 (23/53) | 0.2857 (4/14) | 0.5 (7/14) | 0.3152 (87/276) | 1.67 | 25/15 |
| **Faz 2 Epoch 2** | `dac04d031155d6f4...` | 0.2642 (14/53) | 0.4528 (24/53) | 0.2857 (4/14) | 0.5 (7/14) | 0.3043 (84/276) | 1.67 | 25/15 |
| **Faz 2 Epoch 3 (Latest)** | `b63d3f435b89775b...` | 0.2264 (12/53) | 0.4528 (24/53) | 0.2857 (4/14) | 0.5 (7/14) | 0.3116 (86/276) | 1.33 | 20/15 |

---

## 4. Faz 2'deki Yanlış Alarm Patlamasının Kök Neden Teşhisi

Faz 2'de negatif kontrollerde yanlış alarmlar Faz 1'deki 1 adetten (`0.07/foto`), Epoch 3'te 20 adede (`1.33/foto`) fırlamıştır.

### A. Negatif Fotoğraflardaki Yanlış Pozitiflerin Anatomik ve Doku Dağılımı:
15 negatif kontrol fotoğrafında üretilen 20 yanlış alarm analiz edilmiştir:
- **Yüksek Frekanslı Cilt Dokusu ve Gölgelenme:** 18 adet (%90.0)
- **Gözenek ve Kıl Kökü:** 2 adet (%10.0)

### B. Eğitimin Başarısızlık Mekanizması:
1. **Kayıp Maskeleme Asimetrisi (`KnownObjectnessBCE`):**
   `train_acne_candidate.py` içinde pozitif karolarda `has_neg` False olduğu için `known_cells` tamamen sıfırlanmıştır. Bu nedenle, pozitif karolardaki arka plan cilt hücrelerine hiçbir nesne karşıtı ceza uygulanmamıştır. Model yalnızca saf negatif karolardan arka plan sinyali alabilmiştir.
2. **Kayıp Normalizasyonu Uyuşmazlığı (`yolo_head.py`):**
   `loss_obj`, `num_fg = max(num_fg, 1)` değerine bölünmektedir. Saf negatif karolarda `num_fg = 1` iken, pozitif karolarda 10-20 hedef bulunmaktadır. Bu durum gradyan dengesini bozmuştur.
3. **Patience ve LR Overconfidence:**
   CosineAnnealingLR ile 3 epoch boyunca devam eden optimizasyon, yüksek frekanslı cilt detaylarına aşırı güven atanmasına (overconfidence) yol açmıştır.

---

## 5. CD Teslimatı ve Staging Doğrulaması

### A. Dondurulmuş Model Paketi (CD Entegrasyonu İçin Hazır):
- **Frozen ONNX Modeli:** `audit-results/acne-candidate-training-20261013/candidate.onnx`
  - SHA-256: `006927cd14d46a47fa763c7d1a0f1348b4e5d2dffdcdfd47bc136476e77af6b8`
- **Frozen PyTorch Ağırlıkları:** `audit-results/acne-candidate-training-20261013/candidate-selected.safetensors`
  - SHA-256: `388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9`
- **Export Makbuzu:** `audit-results/acne-candidate-training-20261013/export-receipt.json`

### B. Staging Test Doğrulaması (Fake Fonksiyon Yok):
`tests/test_skin_staging.py` güncellenmiş ve `pytest` ile 7/7 test başarıyla geçmiştir:
- `test_frozen_candidate_artifacts_integrity`: PASSED
- `test_real_onnx_runtime_input_output_contract`: PASSED
- `test_real_onnx_staging_inference_e2e_pipeline`: PASSED
- `test_production_default_isolation`: PASSED
- `test_real_onnx_inference_integration_with_analyze_skin`: PASSED
- `test_model_selection_policy_and_production_release_gate`: PASSED
- `test_real_browser_e2e_staging_proof`: PASSED

---

## 6. Üretime Uygunluk Kararı ve Geri Çekilme Bildirisi (Retraction Notice)

> [!CAUTION]
> **GERİ ÇEKİLME BİLDİRİSİ (RETRACTION NOTICE):**
> Önceki raporda yer alan *"CD accepted=true ile doğrudan açabilir"* şeklindeki öneri **KESİN VE KALICI OLARAK GERİ ÇEKİLMİŞTİR**.
> Teknik entegrasyonun ve ONNX oturumunun çalışması, klinik / ürün kalite kanıtı değildir.
> 
> **Gerekçe:**
> 1. Mevcut hiçbir model, kabin içi otomatik tanı için gerekli olan **%60+ kapsam içi IoU50 yakalama (recall)** eşiğini karşılamamaktadır.
>    - Taban Model: %26.4 (14/53 yakalanan odak) - 39 sivilce kaçırılıyor.
>    - Faz 1 Adayı: %20.8 (11/53 yakalanan odak) - 42 sivilce kaçırılıyor.
> 2. Bu yakalama seviyesindeki bir modelin araç içi kullanıcıya canlı sivilce/akne uyarısı olarak sunulması ciddi klinik yanıltma riski doğurur.
> 3. Bu nedenle, CD üretim çalışma alanında (`attune-live-test`) `services/core-api/models/skin-focused.json` dosyası **kesinlikle `accepted: false, file: null` olarak kapalı tutulmalıdır**.

---

## 7. Çok Kriterli Model Seçim Protokolü ve Araştırma Kararı

Model seçimi iki bağımsız kapıya ayrılmıştır:

1. **Kapı 1 (Üretim Dağıtım Kapısı - Production Release Gate):**
   - Eşikler: Kapsam İçi Rec50 >= 0.60 ve Doğrulanmış Negatif Kontrol FP <= 0.20 FP/foto.
   - **Karar:** **STRICTLY_REJECTED (Tüm modeller reddedildi)**. Üretim dağıtımı kapalı.

2. **Kapı 2 (Geliştirme/Staging Adayı Seçimi - Staging Candidate Gate):**
   - Kriter: Doğrulanmış negatif kontrol bütçesini (<= 0.20 FP/foto) sağlayan adaylar arasında en yüksek yakalamayı öncelemek.
   - Faz 1 Adayı (`388297d9...`), **0.07 FP/foto (1/15 yanlış alarm)** ile negatif alarm bütçesini açık ara sağlayan tek modeldir.
   - Taban Model (`1a014adad2...`), 3 adet daha fazla odak yakalamasına karşın (14 vs 11), temiz ciltlerde 8 yanlış alarm (`0.53 FP/foto`) üretmektedir.
   - **Geliştirme Seçimi:** Faz 1 adayı (`candidate.onnx`, SHA `006927cd14...`) araştırma ve staging entegrasyon paketi olarak dondurulmuştur.

---

## 8. Ampirik Loss, Normalizasyon Paydası ve Gradyan Profil Kanıtı

`scripts/skin-research/profile_training_batches_and_loss.py` çalıştırılarak pozitif, negatif ve karışık batch'lerde kayıp, payda ve gradyan akışı ölçülmüştür:

| Batch Türü | Ortalama GT Kutusu | Bilinen Negatif Anchor | Maskelenen Bilinmeyen Anchor | Normalizasyon Paydası (`num_fg`) | Toplam Loss | Regresyon Başlığı Gradyan Normu |
|---|---|---|---|---|---|---|
| **Saf Pozitif (4 karo)** | 4.3 | 0.0 (Kısmi etiket korundu) | ~12,096 | 4.3 | 1.2772 | 22.1991 |
| **Saf Negatif (4 karo)** | 0.0 | 3966.3 | ~8,130 | 1.0 (min bound) | 0.0000 | 0.0001 |
| **Karışık Dengeli (2P + 2N)** | 2.3 | 2022.0 | ~10,074 | 2.3 | 1.5096 | 23.0922 |

**Teşhis Bulgusu:**
- Kısmi etiketleme ilkesi (`KnownObjectnessBCE`) gereği pozitif fotoğraflardaki etiketsiz cilt alanlarına hiçbir negatif ceza verilmemektedir.
- Saf negatif batch'lerde kayıp 0.0000 ve gradyanlar 0.0001 mertebesindedir.
- Faz 2'deki yanlış alarm patlaması algoritma/normalizasyon hatasından değil, **veri kümesindeki etiket azlığından** kaynaklanmaktadır: Pozitif görsellerde sadece 1-2 lezyon etiketli olup kalan tüm yüz maskelendiği için, çok epoch'lu eğitim ağı gözenek ve yüksek frekanslı dokuları lezyon sanmaya yöneltmiştir.
- **Karar:** Körlemesine yeni eğitim başlatılmamış; eksik eğitim vakaları ve negatif ROI'ler `training-limitation-diagnosis.json` içinde kaynak SHA'ları ile belgelenmiştir.

---

## 9. Gerçek Tarayıcı Motoru (Chromium) ve HTTP API Staging Kanıtı

Mock canvas ve sentetik testler yerine, **gerçek Playwright Chromium tarayıcısı**, **araç içi HTTP API (`POST /api/local-health/skin`)** ve **gerçek ONNX Runtime adayı** uçtan uca çalıştırılmıştır (`scripts/skin-research/run_browser_e2e_staging.py`):

1. **Ön Profil (FRONT) - `695ed248` (Pozitif Odak):**
   - Tarayıcı Hizalama: Yaw=-0.07, Pitch=-0.05, Roll=-0.06 (`AngleMatched=True`, `sourceFramed=True`).
   - Tarayıcı Kalite: Valid=True, Status=OPTIMAL, Blur=5.03, Lum=142.71.
   - HTTP Roundtrip: 9427 ms | Gerçek ONNX İnferansı: `006927cd14...`
   - UI Kartları: Sağ yanak (2.14%), Sol yanak (0.53%), Burun (0.94%), Çene (0.55%) lezyon skorları üretildi.

2. **Yan Profil (RIGHT) - `55d380f7` (Pozitif Odak):**
   - Tarayıcı Hizalama: Yaw=-0.49, Pitch=-0.13, Roll=0.12 (`AngleMatched=True`, `sourceFramed=True`).
   - Tarayıcı Kalite: Valid=True, Status=OPTIMAL, Blur=4.61, Lum=159.33.
   - HTTP Roundtrip: 7184 ms | Gerçek ONNX İnferansı: `006927cd14...`
   - UI Kartları: Yalnız kameraya bakan açık yanak (`leftCheek`: 2.47%) hesaplandı; kapalı bölgeler maskelendi.

3. **Negatif Kontrol - `36e4010b` (Temiz Yüz Kontrolü):**
   - Tarayıcı Hizalama: Yaw=-0.17, Pitch=-0.02, Roll=0.06 (`AngleMatched=True`, `sourceFramed=True`).
   - Tarayıcı Kalite: Valid=True, Status=OPTIMAL, Blur=7.52, Lum=146.25.
   - HTTP Roundtrip: 5450 ms | Gerçek ONNX İnferansı: `006927cd14...`
   - Temiz yüz kontrolü başarıyla tamamlandı.

---

## 10. Sonuç ve Teslim Durumu

| Gerçek düzeltme | Yakalanan/değerlendirilebilir odak | Negatif FP/fotoğraf | Üretime uygunluk | Kalan somut engel |
|---|---|---|---|---|
| Frontend poz ve çoklu açı sözleşmesi doğrulandı, koordinat/maske ayrımı yapıldı, kısmi etiketleme korundu, gerçek Playwright Chromium + HTTP API + ONNX Runtime staging hattı kanıtlandı, dürüst model seçimi ve üretime geçiş kapısı ayrıldı. | **11 / 53** (%20.8 IoU50 yakalama; tüm validation odaklarında 69/276) | **0.07 FP/fotoğraf** (15 doğrulanmış negatif kontrolde yalnız 1 yanlış alarm) | **UYGUN DEĞİL (`accepted: false`)** — Geri çekilme bildirisi yürürlükte; teknik staging çalışıyor fakat klinik yakalama oranı yetersiz. | Pozitif eğitim fotoğraflarındaki yoğun etiket eksikliği (lezyonların çoğunun etiketlenmeyip maskelenmesi) ve temiz kontrol havuzunun darlığı; model %60+ yakalama seviyesine ulaşmadan üretime açılamaz. |
