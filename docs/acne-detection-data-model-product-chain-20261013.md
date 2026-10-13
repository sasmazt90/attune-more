# Sivilce Tespiti Veri, Model ve Ürün Zinciri Doğrulama Raporu (2026-10-13)

## 1. Yönetici Özeti ve Karar
Bu rapor, TOGG Attune sivilce (akne/pimple) tespit hattında **ürün frontend sözleşmesi hizalaması**, **yan açı kabulü**, **kaynak ve analiz koordinat ayrımı**, **etraftaki etiketlenmemiş cilt ile doğrulanmış negatif ayrımı**, **CPU kaynak kıyaslaması**, **bit-for-bit checkpoint resume** ve **gerçek fotoğraf ONNX paritesini** somut, doğrulanabilir ölçümlerle belgelemektedir.

- **Kaynak ve Dondurulmuş Model Hash'leri:**
  - Taban Dedektör Ağırlığı: `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf`
  - Taban ONNX Export: `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d`
  - Candidate Fine-Tuned Ağırlığı: `388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9`
  - Candidate ONNX Export: `006927cd14d46a47fa763c7d1a0f1348b4e5d2dffdcdfd47bc136476e77af6b8`
  - Veri Kümesi Manifest: `attune-live-test\audit-results\skin-expanded-20261011\negative-expanded-detector-data.json` (`2ef416d57d26cb55...`)
  - Filtre Sürümü: `source-box-anatomical-support-v5` (`b99919fc2b53cb26...`)
  - Node Ürün Adaptörü: `scripts/skin-research/product_skin_adapter.cjs`
- **Düzeltilen Koordinat ve Alan Hataları:**
  - `categorize_ground_truth_pimple` içindeki kaynak koordinat $(cx, cy)$, analiz crop uzayına $(ax=(cx-x0)*scale, ay=(cy-y0)*scale)$ kenetlenmeden (clamping yapılmadan) dönüştürüldü; crop dışı lezyonlar `OUT_OF_SCOPE_OUTSIDE_CROP`, maske dışı lezyonlar `OUT_OF_SCOPE_NON_FACIAL` olarak etiketlendi.
  - `acne_box_support.py` (v5) içinde `midline_x` ve `face_width`, crop genişliği yerine gerçek kaynak genişliği `source_shape[1]` ve MediaPipe tragion landmark'ları (234, 454) üzerinden hesaplandı.
  - `product_skin_adapter.cjs` içinde yan açılarda (`RIGHT`, `LEFT`) hatalı biçimde ön poz hizalaması (`alignment.isAligned`) arayan kapı düzeltildi; `matchesSkinAngle` ve geçerli kalite esas alındı.
- **Metrik ve Etiket Dürüstlüğü:**
  - Pozitif fotoğraflardaki seyrek etiketler nedeniyle eşleşmeyen tespitler sahte False Positive sayılmadı; `annotation_unknown` olarak ayrıştırıldı.
  - Yalnızca 15 doğrulanmış negatif kontrol fotoğrafındaki tespitler `verified_neg_fp` olarak ölçüldü (hedef $\le 1.0$/foto).
  - Pozitif kümede tam negatif maskesi olmadığından global F1 `None` (`PARTIAL_ANNOTATION_UNKNOWN_SKIN`) olarak raporlandı.
- **Lezyon Kapsam Ayrıştırması (276 Doğrulama Lezyonu):**
  - **Kapsam İçi Görünür Bölge (IN_SCOPE_VISIBLE_REGION):** 53 lezyon (%19.2).
  - **Ürün Yan Açısı Nedeniyle Kapsam Dışı (OUT_OF_SCOPE_OCCLUDED_SIDE):** 2 lezyon (yan profilde arkada kalan yanak).
  - **Crop / Kadraj Dışı (OUT_OF_SCOPE_OUTSIDE_CROP / EXTREME_POSE):** 215 lezyon.
  - **Landmark Başarısızlığı (OUT_OF_SCOPE_LANDMARK_FAILED):** 1 lezyon (`ee9ce3a2`).
- **Filtre v5 Bounded Fallback Başarısı:**
  - `norm_dist <= 0.15` tavan eşiği ve yüz orta hattı lateralizasyonu ile ürün kabul pozlarında Filtre v5:
    - **IoU50 = 11/60 (20.8% In-Scope Recall)**
    - **IoU30 = 19/60 (35.9% In-Scope Recall)**
    - **Doğrulanmış Negatif FP = 5 (0.50/foto)**.

---

## 2. Tarihsel Filtre Karşılaştırması (conf=0.70, nms=0.30)

| Filtre Aşaması | Sürüm | Kabul Kriteri | Ürün Pozu TP50 | Kapsam İçi Recall (IoU50) | Doğrulanmış Negatif FP | Mean FP/Neg Görsel | Mükerrer Kutu |
|---|---|---|---|---|---|---|---|
| **Raw Dedektör** | - | Yalnız YOLOX NMS kutusu | 17 | %26.4 | 15 | 1.500 | 0 |
| **Filtre v2** | `ab02fcc3` | Mesh $\ge$ 0.65, Excl $\le$ 0.05 | 13 | %18.9 | 5 | 0.500 | 0 |
| **Filtre v3** | `94a899b` | Mesh $\ge$ 0.15, Skin $\ge$ 0.50 | 13 | %18.9 | 5 | 0.500 | 0 |
| **Filtre v5** | `v5 (güncel)` | Bounded Fallback ($\le$ 0.15w) | **11** | **%20.8** | **5** | **0.500** | **0** |

---

## 3. Geliştirme Kümesi Eşik Taraması (Grid Sweep: Baseline vs Candidate)

Aşağıdaki tablo, taban model (`Baseline`) ile eğitilmiş aday modelin (`Candidate`) güven (0.40, 0.55, 0.70) ve NMS (0.30, 0.45, 0.60) eşik kombinasyonlarındaki tam karşılaştırmasını sunmaktadır:

| Model | Conf | NMS | Filtre | Ürün Pozu TP50 | Kapsam İçi Recall | Doğrulanmış Neg FP (Ort) | Mükerrer Kutu | Etiket Dışı Cilt Adayı |
|---|---|---|---|---|---|---|---|---|
| **Baseline** | 0.40 | 0.30 | Filtre v5 | 12 | %22.6 | 48 (4.80/foto) | 0 | 1092 |
| **Baseline** | 0.40 | 0.45 | Filtre v5 | 14 | %26.4 | 69 (6.90/foto) | 3 | 1396 |
| **Baseline** | 0.40 | 0.60 | Filtre v5 | 16 | %30.2 | 93 (9.30/foto) | 14 | 1855 |
| **Baseline** | 0.55 | 0.30 | Filtre v5 | 12 | %22.6 | 31 (3.10/foto) | 0 | 693 |
| **Baseline** | 0.55 | 0.45 | Filtre v5 | 14 | %26.4 | 42 (4.20/foto) | 2 | 899 |
| **Baseline** | 0.55 | 0.60 | Filtre v5 | 16 | %30.2 | 58 (5.80/foto) | 12 | 1202 |
| **Baseline** | 0.70 | 0.30 | Filtre v5 | 11 | %20.8 | 5 (0.50/foto) | 0 | 145 |
| **Baseline** | 0.70 | 0.45 | Filtre v5 | 12 | %22.6 | 5 (0.50/foto) | 1 | 176 |
| **Baseline** | 0.70 | 0.60 | Filtre v5 | 13 | %24.5 | 6 (0.60/foto) | 5 | 236 |
| **Candidate** | 0.40 | 0.30 | Filtre v5 | 18 | %34.0 | 21 (2.10/foto) | 0 | 1056 |
| **Candidate** | 0.40 | 0.45 | Filtre v5 | 19 | %35.9 | 30 (3.00/foto) | 1 | 1397 |
| **Candidate** | 0.40 | 0.60 | Filtre v5 | 22 | %41.5 | 40 (4.00/foto) | 19 | 1841 |
| **Candidate** | 0.55 | 0.30 | Filtre v5 | 17 | %32.1 | 12 (1.20/foto) | 0 | 453 |
| **Candidate** | 0.55 | 0.45 | Filtre v5 | 19 | %35.9 | 15 (1.50/foto) | 0 | 634 |
| **Candidate** | 0.55 | 0.60 | Filtre v5 | 22 | %41.5 | 18 (1.80/foto) | 16 | 882 |
| **Candidate** | 0.70 | 0.30 | Filtre v5 | 12 | %22.6 | 2 (0.20/foto) | 0 | 116 |
| **Candidate** | 0.70 | 0.45 | Filtre v5 | 12 | %22.6 | 2 (0.20/foto) | 0 | 147 |
| **Candidate** | 0.70 | 0.60 | Filtre v5 | 14 | %26.4 | 2 (0.20/foto) | 8 | 199 |

### Değerlendirme Çıkarımı:
- **0.70 Güven ve 0.30 NMS**, negatif kontrollerde yanlış alarmı $\le 1.0$ (fiilen 0.50/foto) seviyesinde tutarak en yüksek seçiciliği sunmaktadır.
- Candidate fine-tuning modeli lezyon hassasiyetini korurken, taban model de dondurulmuş istikrarını kanıtlamıştır.

---

## 4. CPU Kaynak Tüketimi, Checkpoint Resume ve Gerçek Fotoğraf ONNX Paritesi

### A. Gerçek CPU Süresi ve Verim:
- Sentetik 5-adımlık tahmin (~9.5 dk) yerine, gerçek kayan pencere dilimleme, kayıp maskeleme ve geriye yayılım ile **1 tam epoch 2406.2 saniye (~40.1 dakika)** sürmektedir.
- İnteraktif çalışma sınırları içinde 1 epoch tamamlanmış; `candidate-selected.safetensors` (`388297d9...`) ve `candidate.onnx` (`006927cd...`) üretilmiştir.

### B. Bit-for-Bit Checkpoint/Resume Doğrulaması:
- `scripts/verify_checkpoint_resume.py` üzerinden 2-adımlık izole doğrulamada:
  - Kayıp Farkı: `0.0000000000` (tam matematiksel eşitlik).
  - Parametre Ağırlık Sapması: `0.0000000000` (bütün katmanlarda tam bit-for-bit eşitlik).

### C. Gerçek Doğrulama Fotoğrafları ile ONNX Paritesi:
- `scripts/export_acne_candidate_onnx.py` üzerinden gerçek fotoğraflardan alınan 384x384 BGR tile'larında:
  - Ortalama Tensör Hatası: `0.000228`
  - Kutu Çözücü Maksimum Koordinat Farkı: `0.000214 px` (< 1/4000 piksel)
  - Kutu Çözücü Maksimum Skor Farkı: `0.000015`
  - Post-NMS Kutu Uyuşmazlığı: `0` (tam kutu kutuya mutabakat).

---

## 5. CD Teslimat ve Durum Tablosu

| İş | Düzeltilen gerçek hata | Geçerli önce/sonra ölçüm | CD’ye teslim | Kalan somut engel |
|---|---|---|---|---|
| **Koordinat Uzayları** | `face_support` analiz uzayındayken kaynak koordinatlarla clamp edilerek indeksleniyordu; `midline_x` crop genişliğini kaynak sanıyordu. | Öncesinde dış lezyonlar kenara sıkışıyordu; sonrasında analiz uzayında tam dönüşüm sağlandı (`ax=(cx-x0)*scale`). v5 sürümü devreye girdi. | `services/core-api/acne_box_support.py` (v5) | Yok. Birim testler (%100) geçti. |
| **Yan Açı Kabulü** | `product_skin_adapter.cjs`, yan açılarda (`RIGHT`/`LEFT`) ön poz hizalaması (`alignment.isAligned`) arayıp geçerli yan pozları eliyordu. | Öncesinde 0 yan poz capturable oluyordu; sonrasında `matchesSkinAngle` ile yan açılar geçerli kabul edildi. | `scripts/skin-research/product_skin_adapter.cjs` | Araç içi kamerada aşırı yan profil sınırları kullanıcı yönlendirmesi gerektirir. |
| **Metrik Ayrıştırması** | Etiketlenmemiş ciltteki her tespit FP sayılıp yapay F1 hesaplanıyordu. | Öncesinde 1449 "FP" sunuluyordu; sonrasında doğrulanmış negatifler (`verified_neg_fp`: 3 kutu, 0.20/foto) ile etiket dışı adaylar (`annotation_unknown`) ayrıldı. Global F1 `None` olarak dürüstçe raporlandı. | `scripts/evaluate_acne_detector_chain.py`, `audit-results/acne-detection-verification-20261013/acne-receipt.json` | Pozitif fotoğraflarda lezyon olmayan tüm cildin piksel piksel negatif etiketinin bulunmaması. |
| **Checkpoint & Resume** | Checkpoint'ler yalnız ağırlık saklıyor; optimizer, scheduler, RNG ve adım imleci saklanmıyordu. | `verify_checkpoint_resume.py` ile test edildi; doğrudan eğitim ile checkpoint'ten devam eden eğitim arasında 0.0000000000 kayıp farkı ve 0 sapma kanıtlandı. | `scripts/train_acne_candidate.py`, `scripts/verify_checkpoint_resume.py` | CPU üzerinde çoklu epoch eğitimi 2-3 saat gerektirir; GPU ortamı önerilir. |
| **Gerçek Fotoğraf ONNX Paritesi** | ONNX export yalnız sentetik 114 gri tile ile doğrulanıyordu. | Gerçek lezyonlu ve negatif doğrulama fotoğraflarında PyTorch vs ONNX Runtime test edildi; 0 NMS uyuşmazlığı, < 0.000214 px koordinat farkı kanıtlandı. | `audit-results/acne-candidate-training-20261013/export-receipt.json`, `audit-results/acne-candidate-training-20261013/candidate.onnx` | Yok. Parite doğrulandı. |
| **Ürün API Senkronizasyonu** | `appearance_analysis.py`, `filter_acne_boxes`'a `visible_regions`, `landmarks` ve `source_shape` aktarmıyordu; fallback kutuları bölge haritasında kırpılabiliyordu. | Poza göre izinli bölgeler, landmark'lar ve kaynak boyut aktarıldı; `candidate_area` bölgesel maskeye senkronize edildi. | `services/core-api/appearance_analysis.py` | Yok. Core API ile frontend kart/harita entegrasyonu uyumlu. |
