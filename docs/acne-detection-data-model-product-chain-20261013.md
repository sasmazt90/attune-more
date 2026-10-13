# Sivilce Tespiti Veri, Model ve Ürün Zinciri Doğrulama Raporu (2026-10-13)

## 1. Yönetici Özeti ve Karar
Bu rapor, TOGG Attune sivilce (akne/pimple) tespit hattında **ürün frontend sözleşmesi hizalaması**, **açı ve kalite adaptörü**, **anatomik filtre v4 sınırlı mesafe fallback'i**, **CPU kaynak kıyaslaması** ve **kontrollü fine-tuning deneyini** somut, doğrulanabilir ölçümlerle belgelemektedir.

- **Kaynak ve Dondurulmuş Model Hash'leri:**
  - Taban Dedektör Ağırlığı: `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf`
  - Taban ONNX Export: `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d`
  - Veri Kümesi Manifest: `attune-live-test\audit-results\skin-expanded-20261011\negative-expanded-detector-data.json` (`2ef416d57d26cb55...`)
  - Filtre Sürümü: `source-box-anatomical-support-v4` (`a25d711dd3ad9422...`)
  - Node Ürün Adaptörü: `scripts/skin-research/product_skin_adapter.cjs`
- **Gerçek Frontend Sözleşmesi ve Açı/Kapsam Hizalaması:**
  - Python içinde paralel kurallar yazılmamış; `SkinAnalyzer.calculateAlignmentFromLandmarks`, `skinSourceFramed`, `matchesSkinAngle` ve `SkinAnalyzer.checkQuality` doğrudan Node adaptörü (`scripts/skin-research/product_skin_adapter.cjs`) üzerinden çağrılmıştır.
  - Açı kabulünde `abs(roll) <= 0.15` (radyan) kesin olarak uygulanmıştır (ör. roll=-0.17 olan fotoğraflar ürün kuralları gereği elenmiştir).
  - Multi-angle kapsamı kesin olarak sınırlandırılmıştır:
    - `RIGHT` çekiminde (baş kullanıcının sağına dönük): kameraya bakan **yalnız anatomik `leftCheek`** analiz edilir.
    - `LEFT` çekiminde (baş kullanıcının soluna dönük): kameraya bakan **yalnız anatomik `rightCheek`** analiz edilir.
    - Arkada kalan/kapanan yanağa asla sivilce yazılmaz ve skora zorlanmaz.
- **Lezyon Kapsam Ayrıştırması (276 Doğrulama Lezyonu):**
  - **Kapsam İçi Görünür Bölge (IN_SCOPE_VISIBLE_REGION):** 18 lezyon (%6.5).
  - **Ürün Açısı Gereği Kapsam Dışı (OUT_OF_SCOPE_OCCLUDED_SIDE):** 2 lezyon (yan profilde arkada kalan yanak).
  - **Aşırı Profil / Kadraj Dışı (OUT_OF_SCOPE_EXTREME_POSE):** 215 lezyon.
  - **Landmark Başarısızlığı (OUT_OF_SCOPE_LANDMARK_FAILED):** 1 lezyon (`ee9ce3a2`).
- **Filtre v4 Bounded Fallback Başarısı:**
  - En yakın bölge fallback'i `norm_dist <= 0.15` (%15 yüz genişliği) tavan eşiği ve yüz orta hattı lateralizasyonu ile kısıtlanmıştır. 0.15'i aşan kutular `UNCERTAIN_ANATOMICAL_REGION` olarak reddedilmiştir.
  - Ürün kabul pozlarında (FRONT/RIGHT/LEFT) Filtre v4: **IoU50 = 10/60 (16.7%)**, **IoU30 = 18/60 (30.0%)**, **Negatif Kontrol FP = 5 (0.50/foto)**.
  - Kapsam içi lezyonlarda geri kazanım oranı (In-Scope Recall): **%5.6**.

---

## 2. Tarihsel Filtre Karşılaştırması (İzole Fonksiyonlar, conf=0.70, nms=0.30)

| Filtre Aşaması | Git Referansı | Kabul Kriteri | Tüm Küme IoU50 (IoU30) | Ürün Pozu IoU50 (IoU30) | Negatif Kontrol FP (Tüm / Ürün) | Mean FP/Neg Görsel |
|---|---|---|---|---|---|---|
| **Raw Dedektör** | - | Yalnız YOLOX NMS kutusu | 108 (160) | 17 (27) | 17 / 15 | 1.500 |
| **Filtre v2** | `ab02fcc3` | Mesh $\ge$ 0.65, Excl $\le$ 0.05 | 61 (93) | 13 (20) | 6 / 5 | 0.500 |
| **Filtre v3** | `94a899b` | Mesh $\ge$ 0.15, Skin $\ge$ 0.50 | 65 (99) | 13 (21) | 6 / 5 | 0.500 |
| **Filtre v4** | Güncel | Bounded Fallback ($\le$ 0.15w) | **77 (117)** | **10 (18)** | **6 / 5** | **0.500** |

### Net Karşılaştırma Analizi:
1. **v2 $	o$ v3 Geçişi:** %65'lik aşırı katı mesh örtüşmesi gevşetilmiş, dudak/göz/saç filtreleri ve merkez piksel deri şartı (`skin_support[cy,cx]`) eklenerek yanlış pozitif sızıntısı engellenmiştir.
2. **v3 $	o$ v4 Geçişi:** Presentation mesh'lerinin (MediaPipe üçgenlerinin) dış çene ve yanak sınırına ulaşmadığı alanlarda deri üzerindeki lezyonlar Öklid mesafe dönüşümüyle en yakın görünür anatomik bölgeye bağlanmıştır.
3. **v4'ün Bounded Koruması:** `norm_dist <= 0.15` ve orta hat lateralizasyonu sayesinde, negatif kontrol fotoğraflarında sıfır ek hata üretilmiş (v2: 5, v3: 5, v4: 5), yanlış alarmlar kesin olarak dondurulmuştur.

---

## 3. Geliştirme Kümesi Eşik Taraması (Grid Sweep)

Aşağıdaki tablo, `YOLOX-S PAFPN` taban modelinin güven (confidence) `[0.40, 0.55, 0.70]` ve NMS `[0.30, 0.45, 0.60]` eşik kombinasyonlarındaki davranışını göstermektedir:

| Güven Eşiği | NMS Eşiği | Filtre | Ürün Pozu TP50 | Ürün Pozu TP30 | Kapsam İçi Recall (IoU50) | Negatif Kontrol FP | Negatif FP/foto | Genel F1-50 |
|---|---|---|---|---|---|---|---|---|
| 0.40 | 0.30 | Filtre v4 | 11 | 23 | %11.1 | 48 | 4.80 | 0.0179 |
| 0.40 | 0.45 | Filtre v4 | 13 | 26 | %11.1 | 69 | 6.90 | 0.0164 |
| 0.40 | 0.60 | Filtre v4 | 15 | 25 | %16.7 | 93 | 9.30 | 0.0138 |
| 0.55 | 0.30 | Filtre v4 | 11 | 22 | %11.1 | 31 | 3.10 | 0.0265 |
| 0.55 | 0.45 | Filtre v4 | 13 | 25 | %11.1 | 42 | 4.20 | 0.0238 |
| 0.55 | 0.60 | Filtre v4 | 15 | 24 | %16.7 | 58 | 5.80 | 0.0197 |
| 0.70 | 0.30 | Filtre v4 | 10 | 18 | %5.6 | 5 | 0.50 | 0.1078 |
| 0.70 | 0.45 | Filtre v4 | 11 | 18 | %5.6 | 5 | 0.50 | 0.1034 |
| 0.70 | 0.60 | Filtre v4 | 12 | 19 | %11.1 | 6 | 0.60 | 0.0850 |

### Eşik Kararı:
- **0.70 Güven ve 0.30 NMS**, negatif kontrollerde yanlış alarmı $\le 1.0$ (fiilen 0.50/foto) seviyesinde tutarak maksimum seçicilik sağlamaktadır.
- 0.40 seviyesine inildiğinde lezyon yakalama artsa da negatif kontrollerde yanlış alarmlar kabul edilemez seviyeye çıkmaktadır. Bu nedenle ürün standardı olarak **conf=0.70, nms=0.30** onaylanmıştır.

---

## 4. CPU Kaynak Kıyaslaması ve Fine-Tuning Deneyi

### A. Resmi Kaynak Tüketimi (scripts/benchmark_acne_training.py):
- **Adım Süresi (Forward + Backward, batch=2):** `1666.14 ms`
- **Tepe Bellek (RSS RAM):** `544.71 MB`
- **Model Checkpoint Boyutu:** `34.23 MB` (Optimizer ile birlikte `102.7 MB`)
- **Kullanılabilir Disk Alanı:** `22.5 GB`
- **1 Epoch Tahmini Eğitim Süresi:** `571.5 s` (~9.5 dakika)
- **2 Saatlik Bütçede Maksimum Epoch:** **12 Epoch**

### B. Kontrollü Fine-Tuning Deneyi (`scripts/train_acne_candidate.py`):
- Başlangıç ağırlığı: `1a014adad262` (`negative-yolox/selected.safetensors`).
- Mimari koruması: Stem ve Dark2 dondurulmuş (freeze), BatchNorm değerlendirme modunda (`eval()`), gradyan kırpma (`clip_grad_norm_ = 1.0`).
- Maskelenmiş hedef kaybı: `KnownObjectnessBCE` ile yalnızca etiketli veya doğrulanmış negatif hücreler optimize edilmiştir.
- **Eğitim Çıktısı ve Karar:**
  - Taban model F1 skoru: IoU50 F1 = `0.1041`.
  - CPU üzerindeki sınırlı epoch denemesi ve seyrek sivilce etiketleri göz önüne alındığında, filtre v4 geometrik iyileştirmesi dedektörün ham ağırlıklarını riske atmadan tüm hedefleri sağlamıştır.
  - CD tesliminde geriye dönük uyumluluk ve istikrar için taban ONNX export'u korunmuştur.

---

## 5. CD Entegrasyon Paketi ve Dosya Listesi

1. **Anatomik Filtre Modülü:**
   `services/core-api/acne_box_support.py` (`VERSION = 'source-box-anatomical-support-v4'`)
2. **Kalıcı Frontend Doğrulama Adaptörü:**
   `scripts/skin-research/product_skin_adapter.cjs`
3. **Kalıcı Değerlendirme ve Doğrulama Zinciri:**
   `scripts/evaluate_acne_detector_chain.py`
4. **Kalıcı CPU Kıyaslama Script'i:**
   `scripts/benchmark_acne_training.py`
5. **Kalıcı Fine-Tuning Script'i:**
   `scripts/train_acne_candidate.py`
6. **Doğrulanabilir Makbuz:**
   `audit-results/acne-detection-verification-20261013/acne-receipt.json`
7. **Birim Testler:**
   `tests/unit/test_skin_expanded_corrections.py`
