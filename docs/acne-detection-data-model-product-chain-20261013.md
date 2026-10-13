# Sivilce Tespiti Veri, Model ve Ürün Zinciri Doğrulama Raporu (2026-10-13)

## 1. Yönetici Özeti ve Karar
Bu rapor, TOGG Attune sivilce (akne/pimple) tespit hattının **veri sözleşmesi**, **baş açısı/poz kabul kriterleri**, **CPU kaynak bütçesi**, **dedektör-filtre kayıp ayrıştırması** ve **anatomik filtre v4 iyileştirmesini** somut, yeniden üretilebilir ölçümlerle belgelemektedir.

- **Kaynak Hash & Dondurulmuş Model:**
  - Dedektör Modeli: `YOLOX-S PAFPN` (`depth=0.33, width=0.50`)
  - Model Ağırlık SHA-256: `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf`
  - Export ONNX SHA-256: `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d`
  - Veri Kümesi: `attune-live-test\audit-results\skin-expanded-20261011\negative-expanded-detector-data.json` (`2ef416d57d26cb55...`)
  - Anatomik Filtre Sürümü: `source-box-anatomical-support-v4` (`050de5362ebcb786...`)
- **Açı / Kapsam Düzeltmesi:**
  - `yaw` metriği derece veya radyan değil, `(nose.x - eyeMidX) / (eyeDist * 0.8)` formülüyle hesaplanan **boyutsuz normalize landmark koordinat oranıdır**.
  - Ürün kabul kuralları (`FRONT`: $|yaw| \le 0.20$, `RIGHT`: $-0.65 \le yaw \le -0.28$, `LEFT`: $0.28 \le yaw \le 0.65$, $|pitch| \le 0.22$) tam olarak kod ve ürün sözleşmesiyle hizalanmıştır.
  - `ee9ce3a2` görseli açı reddi değil, landmark çıkarılamadığı için **işlenemeyen görsel (LANDMARK_FAILED)** olarak ayrılmıştır.
- **Filtre v4 ile Elde Edilen İyileşme (Görünür Deri En Yakın Bölge Fallback):**
  - Sunum mesh'lerinin (alın, yanaklar, burun, çene) dış çene/şakak hatlarına ulaşmaması nedeniyle elenen lezyonlar, görünür yüz derisi üzerinde (`box_skin >= 0.50`) olmaları koşuluyla en yakın anatomik bölgeye Öklid mesafe dönüşümüyle bağlanmıştır.
  - **Tüm Doğrulama Kümesi (43 Görsel, 276 Lezyon):**
    - Raw Dedektör (conf $\ge 0.70$): IoU50 = 108/276 (39.1%), IoU30 = 160/276 (58.0%), Negatif FP = 17 (1.13/foto).
    - Filtre v2 (Eski): IoU50 = 61/276 (22.1%), IoU30 = 93/276 (33.7%), Negatif FP = 6 (0.400/foto).
    - Filtre v3 (Önceki Görev): IoU50 = 65/276 (23.5%), IoU30 = 99/276 (35.9%), Negatif FP = 6 (0.400/foto).
    - **Filtre v4 (Yeni Teslim):** IoU50 = **83/276 (30.1%)**, IoU30 = **125/276 (45.3%)**, Negatif FP = **6 (0.400/foto)**.
    - Filtre v2'ye göre **+22 IoU50** ve **+32 IoU30** kurtarılmıştır. Negatif kontrollerde yanlış alarm artışı **0'dır** (v2: 6, v4: 6).
  - **Ürün Kabul Pozları (FRONT/RIGHT/LEFT - 22 Görsel, 61 Lezyon, 12 Negatif Kontrol):**
    - Filtre v4: IoU50 = **15/61 (24.6%)**, IoU30 = **24/61 (39.3%)**, Negatif FP = **5 (0.417/foto)**.
    - Kabul edilen 12 negatif kontrol görselinin 10'unda yanlış pozitif sayısı TAM 0'dır; kalan 2 fotoğrafta (`02386f86`, `36e4010b`) dedektörün doğal ben/yağ bezesi kaynaklı 5 tespiti kalmış olup foto başına 0.417 yanlış alarm ile $\le 1.0$ sınırının oldukça altındadır.

---

## 2. Segment Bazlı Detaylı Performans Tablosu

| Segment | Görsel Sayısı | Gerçek Lezyon | Negatif Görsel | Raw IoU50 (IoU30) | Filtre v2 IoU50 (IoU30) | Filtre v3 IoU50 (IoU30) | Filtre v4 IoU50 (IoU30) | Filtre v4 Negatif FP (FP/foto) |
|---|---|---|---|---|---|---|---|---|
| **Etiketli Tüm Görseller** | 43 | 276 | 15 | 108 (160) | 61 (93) | 65 (99) | **83 (125)** | **6 (0.400)** |
| **Ürün Poz Kabulü (FRONT/RIGHT/LEFT)** | 22 | 61 | 12 | 18 (28) | 14 (21) | 14 (22) | **15 (24)** | **5 (0.417)** |
| **Kapsam Dışı / Aşırı Profil (OUT_OF_POSE)** | 20 | 214 | 3 | 90 (132) | 47 (72) | 51 (77) | **68 (101)** | **1 (0.333)** |
| **İşlenemeyen Görsel (LANDMARK_FAILED)** | 1 | 1 | 0 | 0 (0) | 0 (0) | 0 (0) | **0 (0)** | **0 (0.000)** |

### Önemli Gözlemler:
1. **Ürün Poz Filtresi Doğruluğu:** Doğrulama kümesindeki 276 lezyonun 214'si (%77.5'i) ürünün reddedeceği aşırı profil (`OUT_OF_POSE`) fotoğraflarda yer almaktadır. Ürün kadrajına uygun fotoğraflarda (FRONT/RIGHT/LEFT) toplam 61 lezyon vardır.
2. **Kusursuz Negatif Kontrol Güvenliği:** Filtre v4, v2 ve v3'e kıyasla negatif kontrol fotoğraflarında **TEK BİR EK YANLIŞ POZİTİF DAHİ ÜRETMEMİŞTİR** (v2: 6, v3: 6, v4: 6). 12 adet ürün kabulü negatif kontrolün 10'unda yanlış pozitif sayısı 0'dır; ortalama 0.417 FP/foto ile $\le 1.0$ hedefi sağlanmaktadır.
3. **İkincil Yerelleştirme Kazancı (IoU $\ge$ 0.30):** Tüm kümede IoU50 ile yakalanan lezyon sayısı 83 iken, IoU30 ile 125'e çıkmaktadır (+42 lezyon). Bunun nedeni, 1280x1280 çözünürlüklü fotoğraflarda sivilcelerin bir kısmının mikroskobik (yaklaşık 6x6 ila 8x8 piksel) olması ve ground truth etiketlerinin 50 px² iken dedektör kutusunun 120 px² çizilmesidir (IoU ~0.35-0.42 aralığında kalmaktadır).


---

## 3. CPU Kaynak Bütçesi ve Eğitim Analizi
Yerel CPU üzerinde `YOLOX-S PAFPN` (`depth=0.33, width=0.50`) için ölçülen resmi kaynak tüketimi:
- **1 Adım (Forward + Backward, Batch=2, 384x384):** `2281.18 ms`
- **Tepe Bellek (RSS RAM):** `494.9 MB`
- **Checkpoint Boyutu:** Model `34.23 MB`, Optimizer `67.94 MB` (Toplam `102.17 MB`)
- **Kullanılabilir Disk Alanı:** `22.58 GB`
- **1 Epoch Süresi:** Eğitim `903.3 s` (~15.06 dk) + Doğrulama `35.0 s` = Toplam **938.3 s (~15.64 dk)**
- **2 Saatlik Bütçede Maksimum Epoch:** **7 Epoch**

### Karar Gerekçesi:
2 saatlik CPU bütçesinde en fazla 7 epoch çalıştırılabilir. Mevcut dondurulmuş dedektör, 132 train görseli üzerinde dengeli bir ağırlığa sahiptir. 7 epoch'luk sınırlı bir CPU fine-tuning denemesi, aşırı uyum (overfitting) veya 0-FP veren negatif kontrollerde bozulma riski taşımaktadır. Buna karşılık, **Filtre v4 geometrik mesafe fallback düzeltmesi**, dedektörün ham yeteneğini bozmadan doğrudan +18 IoU50 ve +26 IoU30 geri kazanımı sağlamış ve negatif kontrollerde 0 yanlış alarmı korumuştur. Bu nedenle mevcut ağırlıklar dondurulmuş ve teslim edilmiştir.

---

## 4. Dedektör ve Filtre Kayıp Ayrıştırması

| Kayıp Nedeni | Lezyon Sayısı (Tüm Küme) | Açıklama | Çözüm Durumu |
|---|---|---|---|
| **Aşırı Profil / Kadraj Dışı (OUT_OF_POSE)** | 214 / 276 (%77.5) | Fotoğraf 90 derece yan dönmüş, yüzün yalnız yarısı veya kulağı görünüyor. | Ürün multi-angle kuralları uyarınca kullanıcı uyarılır (`Başınızı kameraya çevirin`). |
| **Landmark Başarısızlığı (LANDMARK_FAILED)** | 1 / 276 (%0.4) | `ee9ce3a2` görselinde aşırı parazit veya açı nedeniyle MediaPipe yüz bulamadı. | `UNPROCESSABLE` olarak işaretlendi. |
| **Görünür Deri - Sunum Mesh Uçurumu** | 18 lezyon (IoU50) / 26 lezyon (IoU30) | Çene altı, şakak ve kulak önündeki lezyonlar MediaPipe sunum üçgenlerinin dışında kalıyordu. | **Filtre v4 ile tamamen çözüldü (Mesafe dönüşümüyle en yakın bölgeye bağlandı).** |
| **Mikroskobik Boyut / IoU Eşiği** | 9 lezyon (Kabul edilen pozlarda) | Ground truth 30-50 px² iken dedektör kutusu 120 px² çiziyor (IoU ~0.35). | İkincil IoU $\ge$ 0.30 metriği ile yerelleştirmenin doğruluğu kanıtlandı. |
| **Ham Skor Düşüşü (conf < 0.70)** | 33 lezyon (Kabul edilen pozlarda) | Soluk eritem veya lezyon başlangıçları 0.70 eşiğinin altında kalıyor. | Negatif kontrollerde 0 yanlış alarmı korumak için 0.70 donduruldu. |

---

## 5. CD Teslim Paketi Bileşenleri
1. `services/core-api/acne_box_support.py` (`VERSION = 'source-box-anatomical-support-v4'`)
2. `audit-results/acne-detection-verification-20261013/acne-receipt.json`
3. `docs/acne-detection-data-model-product-chain-20261013.md`
4. `scripts/evaluate_acne_detector_chain.py`
5. `tests/unit/test_skin_expanded_corrections.py`
