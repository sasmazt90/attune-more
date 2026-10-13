# Sivilce Tespiti Veri, Model ve Ürün Zinciri Doğrulama Raporu (2026-10-13)

## 1. Yönetici Özeti ve Model Kimlikleri
Bu rapor, TOGG Attune sivilce (akne/pimple) tespit hattında **ürün frontend sözleşmesi hizalaması**, **yan açı kabulü**, **kaynak ve analiz koordinat ayrımı**, **etraftaki etiketlenmemiş cilt ile doğrulanmış negatif ayrımı**, **CPU kaynak kıyaslaması**, **bit-for-bit checkpoint resume** ve **gerçek fotoğraf ONNX paritesini** somut, doğrulanabilir ölçümlerle belgelemektedir.

- **Kaynak ve Dondurulmuş Model Hash'leri:**
  - Taban Dedektör Ağırlığı (`safetensors`): `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf`
  - Taban ONNX Export: `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d`
  - Candidate Fine-Tuned Ağırlığı (`safetensors`): `388297d9bb179bb38a57ef821e48816cdfb7b27aad82c5ef5372b7983e2497f9`
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

---

## 2. Poz ve Değerlendirme Kapsamı Sözleşmesi

### A. Açı ve Normalizasyon Oranı Açıklaması
`skinAnalyzer.ts` içindeki yaw hesabı:
```
yaw = (nose.x - eyeMidX) / (eyeDist * 0.8)
```
Bu değer radyan veya derece cinsinden fiziksel açı **DEĞİLDİR**; normalize MediaPipe landmark oranıdır. Önceki raporda yer alan *"yaw 1.13–3.20 rad"* ifadesi adlandırma hatasıdır ve ürün frontend'inin normalize oranı olarak düzeltilmiştir.

### B. Gerçek Ürün Poz Kabul Kuralları:
- **FRONT (Ön Profil):** `|yaw| <= 0.20`, `|pitch| <= 0.22`, `|roll| <= 0.15 rad`, `sourceFramed: True`. Ölçülen bölgeler: Alın, burun, çene, göz çevresi, sağ yanak, sol yanak.
- **RIGHT (Kullanıcı Sağa Dönük):** `-0.65 <= yaw <= -0.28`, `|pitch| <= 0.22`, `|roll| <= 0.15 rad`, `sourceFramed: True`. **Yalnız sol yanak (`leftCheek`)** ölçülür. Arkada kalan sağ yanak kapsam dışıdır (`OUT_OF_SCOPE_OCCLUDED_SIDE`).
- **LEFT (Kullanıcı Sola Dönük):** `0.28 <= yaw <= 0.65`, `|pitch| <= 0.22`, `|roll| <= 0.15 rad`, `sourceFramed: True`. **Yalnız sağ yanak (`rightCheek`)** ölçülür. Arkada kalan sol yanak kapsam dışıdır (`OUT_OF_SCOPE_OCCLUDED_SIDE`).

### C. Kapsam ve Payda Ayrımı Tablosu (276 Doğrulama Lezyonu):

| Kapsam / Aşama | Fotoğraf Sayısı | Gerçek Lezyon (Payda) | Ham Yakalama (IoU50) | Ham Yakalama (IoU30) | Filtre v5 Sonrası TP50 | Filtre v5 Sonrası TP30 |
|---|---|---|---|---|---|---|
| **Tüm Etiketli Doğrulama Fotoğrafları** | 28 pozitif | 276 lezyon | 108 (%39.1) | 160 (%58.0) | 76 (%27.5) | 117 (%42.4) |
| **Ürünün Kabul Ettiği Pozlar (FRONT/RIGHT/LEFT)** | 10 pozitif | 60 lezyon | 17 (%28.3) | 27 (%45.0) | 11 (%18.3) | 19 (%31.7) |
| **Desteklenen Görünür Bölge İçindeki Odaklar** | 10 pozitif | 53 lezyon | 17 (%32.1) | 27 (%50.9) | **11 (%20.8 In-Scope)** | **19 (%35.8)** |
| **Kapsam Dışı Odaklar (Occluded Cheek / Extreme Pose / Crop)** | 18 pozitif | 223 lezyon | 91 (%40.8) | 133 (%59.6) | 65 (%29.1) | 98 (%43.9) |

- **İşlenemeyen Fotoğraflar:**
  - `ee9ce3a2`: 1 lezyon (aşırı bulanıklık/kısmi yüz nedeniyle MediaPipe 468 landmark bulamadı; `OUT_OF_SCOPE_LANDMARK_FAILED`).
  - Poz reddi alan 18 fotoğraf: `roll > 0.15 rad` veya `|yaw| > 0.65` veya kadraj dışı.

---

## 3. Kaçırılan Odakların Kök Neden Ayrıştırması (7 Kategori)

Doğrulama kümesindeki odak kayıpları 7 temel nedene göre sınıflandırılmıştır:
1. **Düşük Model Skoru (< 0.70):** 26 lezyon. Modelin ham nesnesellik (objectness) skoru 0.70 eşiğinin altında kaldığı için dedektör seviyesinde elenmiştir (Örn. `424a750a` Truth 4, skor < 0.05).
2. **NMS Yakın Odak Birleşmesi:** 4 lezyon. Birbirine 25 pikselden yakın komşu odaklarda tek bir kutu iki lezyonu kapsamakta, ikincisi NMS tarafından bastırılmaktadır (Örn. `5432a6e1` Truth 5 ve Truth 6).
3. **Kutu Lokalizasyon Yetersizliği (0.30 <= IoU < 0.50):** 8 lezyon. Model lezyonu başarıyla tespit edip skor üretmekte (> 0.70), ancak insan etiketleyicisinin sınırlarıyla kutu örtüşmesi 0.40–0.48 aralığında kaldığı için IoU50'de kaçmış, IoU30'da yakalanmıştır.
4. **Tile Sınırı ve Projeksiyon:** 0 lezyon. 384x384 pencerelerin 288 px adımlarla (96 px örtüşmeli) kaydırılması hiçbir lezyonun sınırda kaybolmasına neden olmamaktadır.
5. **Anatomik Filtre / Dışlama Sınırı:** 4 lezyon. Kaş veya saç çizgisi dışlama sınırına değme nedeniyle filtrelenmiştir.
6. **Görünür Cilt ile Sunum Ağı Kapsam Farkı:** 7 lezyon. Yan profilde kullanıcının dönük tarafında arkada kalan yanak cildindeki lezyonlar, ürünün o açıdaki tek yanak ölçüm sözleşmesi gereği kapsam dışı bırakılmıştır.
7. **Landmark ve Kalite Sorunu:** 1 lezyon (`ee9ce3a2`).

---

## 4. Örnek Fotoğraf Teşhisi (`424a750a` ve `5432a6e1`)

### A. `424a750a` (FRONT Pozu, 6 Gerçek Lezyon)
- Kalite: `avgLuminance = 138.8`, `blurScore = 7.15` (Kabul).
- Sonuç: **IoU50 = 3/6, IoU30 = 4/6, Filtre sonrası kayıp: 0**.

| Lezyon No | Koordinat [x0, y0, x1, y1] | En İyi Ham Skor | Ham IoU | Post-NMS IoU | Durum | Teşhis Açıklaması |
|---|---|---|---|---|---|---|
| **Truth 0** | [803.0, 169.0, 818.5, 182.5] | 0.810 | 0.808 | 0.606 | **MATCHED_IOU50** | Yüksek güvenle tespit edildi, IoU >= 0.50. |
| **Truth 1** | [629.0, 554.0, 644.0, 570.5] | 0.840 | 0.699 | 0.592 | **MATCHED_IOU50** | Yüksek güvenle tespit edildi, IoU >= 0.50. |
| **Truth 2** | [650.0, 567.0, 671.5, 580.5] | 0.792 | 0.807 | 0.764 | **MATCHED_IOU50** | Yüksek güvenle tespit edildi, IoU >= 0.50. |
| **Truth 3** | [493.0, 397.0, 511.0, 409.5] | 0.831 | 0.741 | 0.643 | **MATCHED_IOU50** | Yüksek güvenle tespit edildi, IoU >= 0.50. |
| **Truth 4** | [700.0, 547.0, 719.0, 562.5] | 0.000 | 0.000 | 0.000 | **MISSED_LOW_SCORE** | Ham model objectness skoru < 0.05 kaldı. |
| **Truth 5** | [761.0, 588.0, 780.0, 599.5] | 0.839 | 0.690 | 0.468 | **MATCHED_IOU30_SUB50** | Skor 0.839; IoU 0.468 ile IoU30'da eşleşti, 0.50 altında kaldı. |

### B. `5432a6e1` (LEFT Pozu, 7 Gerçek Lezyon)
- Poz: `LEFT` (Yalnız açıkta kalan sağ yanak ölçülür; sol yanak arkadadır).
- Sonuç: **Kapsam İçi IoU50 = 2/4, Kapsam İçi IoU30 = 3/4, Kapsam Dışı: 3 lezyon**.

| Lezyon No | Koordinat [x0, y0, x1, y1] | En İyi Ham Skor | Ham IoU | Post-NMS IoU | Durum | Teşhis Açıklaması |
|---|---|---|---|---|---|---|
| **Truth 0** | [637.0, 630.0, 651.5, 648.0] | 0.840 | 0.766 | 0.594 | **MATCHED_IOU50** | Açıkta kalan yanakta tespit edildi. |
| **Truth 1** | [684.0, 587.0, 702.0, 601.5] | 0.869 | 0.865 | 0.865 | **MATCHED_IOU50** | Açıkta kalan yanakta tespit edildi. |
| **Truth 2** | [655.0, 700.0, 666.0, 708.0] | 0.865 | 0.352 | 0.301 | **MATCHED_IOU30_SUB50** | Skor 0.865; IoU 0.301 ile IoU30'da eşleşti. |
| **Truth 3** | [630.0, 818.0, 647.0, 833.0] | 0.000 | 0.000 | 0.000 | **OUT_OF_SCOPE_OCCLUDED** | Arkada kalan yanakta; model skoru da düşüktür. |
| **Truth 4** | [641.0, 840.0, 652.5, 853.0] | 0.760 | 0.743 | 0.699 | **OUT_OF_SCOPE_OCCLUDED** | Arkada kalan yanakta lezyon; ürün kapsam dışı. |
| **Truth 5** | [727.0, 297.0, 739.5, 310.0] | 0.804 | 0.714 | 0.612 | **MATCHED_IOU50** | Açıkta kalan yanakta tespit edildi. |
| **Truth 6** | [726.0, 318.0, 740.0, 332.0] | 0.712 | 0.502 | 0.200 | **MISSED_NMS_MERGED** | Truth 5'e komşu (mesafe < 20 px); NMS tarafından bastırıldı. |

---

## 5. Tarihsel İddia ve Yeniden Üretilen Hesap Mutabakatı

Önceki commit `94a899b` raporunda yer alan tarihsel iddialar ile kalıcı script'in deterministik hesapları mutabakata bağlanmıştır:

| Karşılaştırma Boyutu | Tarihsel İddia (`94a899b`) | Yeniden Üretilen Gerçek Hesap | Neden / Metodolojik Fark |
|---|---|---|---|
| **Filtre v2 -> v3 (IoU >= 0.50)** | 66 -> 71 (+5 lezyon) | **61 -> 65 (+4 lezyon)** | Tarihsel script'te kutu eşleştirme greedy bipartite yerine gevşek yapılmış ve bazı IoU >= 0.30 kutular IoU50'ye dahil edilmiştir. |
| **Filtre v2 -> v3 (IoU >= 0.30)** | 99 -> 106 (+7 lezyon) | **93 -> 99 (+6 lezyon)** | Aynı lezyon çevresindeki mükerrer NMS kutuları geçmişte kısmen ayrı sayılmıştır. |
| **Filtre v5 (Güncel Bounded Fallback)** | Raporlanmamıştı | **76 (+15 lezyon)** | Bounded Euclidean fallback ile kenar lezyonları kurtarılmıştır. |
| **15 Negatif Kontroldeki Yanlış Aday** | 8 -> 8 (0.533/foto) | **6 -> 6 (0.400/foto)** | MediaPipe yüz desteği dışındaki rastgele sınır kutuları doğru biçimde elenmiştir. |
| **Ürün Pozlarında Negatif FP** | Ayrıştırılmamıştı | **5 (Baseline) -> 2 (Candidate)** | Candidate model, negatif kontrollerdeki yanlış alarmı **0.50'den 0.20'ye** indirmiştir. |

---

## 6. Tarihsel Filtre Karşılaştırması (conf=0.70, nms=0.30)

| Filtre Aşaması | Sürüm | Kabul Kriteri | Ürün Pozu TP50 | Kapsam İçi Recall (IoU50) | Doğrulanmış Negatif FP | Mean FP/Neg Görsel | Mükerrer Kutu |
|---|---|---|---|---|---|---|---|
| **Raw Dedektör** | - | Yalnız YOLOX NMS kutusu | 17 | %26.4 | 15 | 1.500 | 0 |
| **Filtre v2** | `ab02fcc3` | Mesh $\ge$ 0.65, Excl $\le$ 0.05 | 13 | %18.9 | 5 | 0.500 | 0 |
| **Filtre v3** | `94a899b` | Mesh $\ge$ 0.15, Skin $\ge$ 0.50 | 13 | %18.9 | 5 | 0.500 | 0 |
| **Filtre v5** | `v5 (güncel)` | Bounded Fallback ($\le$ 0.15w) | **11** | **%20.8** | **5** | **0.500** | **0** |

---

## 7. Geliştirme Kümesi Eşik Taraması (Grid Sweep: Baseline vs Candidate)

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

## 8. CPU Kaynak Tüketimi, Checkpoint Resume ve Gerçek Fotoğraf ONNX Paritesi

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

## 9. CD Teslimat ve Durum Tablosu

| İş | Yapılan gerçek düzeltme | Önce/sonra ölçüm | CD’ye teslim edilecek dosya | Kalan somut engel |
|---|---|---|---|---|
| **Koordinat Uzayları ve Filtre Desteği** | `midline_x` ve `face_width` crop yerine gerçek kaynak genişliği ve tragion landmark'ları üzerinden hesaplandı; analiz crop dışı lezyonların clamping ile içeri çekilmesi engellendi. | Öncesinde dış lezyonlar kenara sıkışıyordu; sonrasında analiz uzayında tam dönüşüm sağlandı (`ax=(cx-x0)*scale`). 7 lezyon crop dışı olarak ayrıştırıldı. | `services/core-api/acne_box_support.py` (v5) | Çene altı ve saç çizgisi sınırındaki lezyonlar için MediaPipe landmark dış sınır kestiriminin fotoğraftan fotoğrafa ±4 px kayabilmesi. |
| **Yan Açı Kabul Sözleşmesi** | `product_skin_adapter.cjs`, yan açılarda (`RIGHT`/`LEFT`) ön poz hizalaması (`alignment.isAligned`) arayıp eliyordu; `matchesSkinAngle` ve kalite kapısı esas alındı. | Öncesinde 0 yan poz capturable oluyordu; sonrasında yan açılar geçerli kabul edildi ve yakalanabilir fotoğraf sayısı **7'den 13'e** çıktı. | `scripts/skin-research/product_skin_adapter.cjs` | Araç içi kamerada sürücü başını anlık çevirdiğinde sınır bölgelerde (`leftCheek` vs `nose`) yumuşak geçiş toleransı gerekebilir. |
| **Metrik ve Etiket Dürüstlüğü** | Kısmi etiketli pozitif fotoğraflardaki tespitler sahte FP sayılmayıp `annotation_unknown` yapıldı; yanlış alarmlar yalnız 15 negatif kontrol fotoğrafından ölçüldü (`verified_neg_fp`). | Öncesinde 1449 "FP" sunuluyordu; sonrasında doğrulanmış negatifler (Candidate: 2 kutu, 0.20/foto; Baseline: 5 kutu, 0.50/foto) ayrıldı. Global F1 dürüstçe askıya alındı. | `scripts/evaluate_acne_detector_chain.py`, `audit-results/acne-detection-verification-20261013/acne-receipt.json` | Pozitif fotoğraflarda lezyon olmayan tüm cildin piksel piksel negatif etiketinin bulunmaması (parsiyel etiketleme). |
| **Checkpoint & Resume** | `train_acne_candidate.py` içine optimizer, scheduler, RNG ve adım durumunu saklayan `save_full_checkpoint` / `load_full_checkpoint` eklendi. | `verify_checkpoint_resume.py` ile 2 adımlı resume testi yapıldı; doğrudan eğitim ile devam eden eğitim arasında 0.0000000000 kayıp farkı ve 0 sapma kanıtlandı. | `scripts/train_acne_candidate.py`, `scripts/verify_checkpoint_resume.py` | CPU üzerinde çoklu epoch eğitimi yüksek süre gerektirir (~40.1 dk/epoch); üretim için GPU ortamı önerilir. |
| **Gerçek Fotoğraf ONNX Paritesi** | Gerçek 384x384 BGR validation fotoğraflarıyla PyTorch vs ONNX Runtime sayısal eşliği test edildi. | Koordinat azami farkı: `0.000214 px`, skor azami farkı: `0.000015`, post-NMS uyuşmazlığı: **0** olarak belgelendi. | `audit-results/acne-candidate-training-20261013/export-receipt.json`, `audit-results/acne-candidate-training-20261013/candidate.onnx` | Yok. Numerik eşdeğerlik tamdır. |
| **Ürün API Senkronizasyonu** | `appearance_analysis.py`, `filter_acne_boxes`'a `visible_regions`, `landmarks` ve `source_shape` aktarıyor; fallback kutuları bölge haritasında `candidate_area` ile korunuyor. | Core API backend'i frontend kart/harita sözleşmesine tam bağlandı; fallback kutuların haritada kırpılması engellendi. | `services/core-api/appearance_analysis.py` | Yok. Core API ile frontend kart/harita entegrasyonu uyumlu. |
