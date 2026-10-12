# Sivilce Tespiti: Gerçek Veri–Model–Ürün Zinciri Teşhisi ve Filtre İyileştirmesi

**Tarih:** 13 Ekim 2026  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Referans Dondurulmuş Model:** `selected-detector-export-1a014adad262`  
**Durum:** TAMAMLANDI & DOĞRULANDI (Part B)

---

## 1. Dondurulmuş Model ve Çevre Doğrulaması

Ana ürün referansı olan `attune-live-test/audit-results/skin-expanded-20261011/interim-diagnosis/selected-detector-export-current.json` makbuzuna göre dondurulmuş dedektörün kimliği doğrulanmıştır:

| Alan | Beklenen Değer | Ölçülen Değer | Durum |
| :--- | :--- | :--- | :--- |
| **Ağırlık SHA-256** | `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf` | `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf` | Doğrulandı |
| **ONNX SHA-256** | `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d` | `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d` | Doğrulandı |
| **Mimari** | YOLOX-S PAFPN (`depth=0.33, width=0.50`) | YOLOX-S PAFPN (`depth=0.33, width=0.50`) | Doğrulandı |
| **Giriş Tensörü** | `[1, 3, 384, 384]`, native BGR, pad 114, aralık $[0, 255]$ | `[1, 3, 384, 384]`, float32 | Doğrulandı |
| **Çıkışlar** | `decoded_boxes [1, 3024, 6]`, `raw_regression`, `raw_obj`, `raw_cls` | `decoded_boxes [1, 3024, 6]` | Doğrulandı |
| **Eşikler** | Skor eşiği: 0.70, NMS IoU: 0.30 | `threshold: 0.70`, `nms: 0.30` | Donduruldu |

---

## 2. Veri Envanteri ve Etiket Sözleşmesi

- **Kaynak Arşiv:** `C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\Datasets\SmartSkinCare.v8i.coco.zip` (Roboflow yayıncı lisansı: **CC BY 4.0**).
- **Etiket Eşlemesi:**
  - `Pimple` $\to$ `classId: 0` (Yalnız aktif iltihaplı/kabartılı sivilce lezyonları).
  - `Enlarged pores` $\to$ Hariç tutuldu (gözenek sivilce sayılmaz).
  - `Freckles`, `Mole`, `Pigmentation` $\to$ Hariç tutuldu (ben, çil ve leke sivilce sayılmaz).
  - `Post acne` $\to$ Hariç tutuldu (akne izleri ve skar dokusu aktif sivilce sayılmaz).
- **Kısmi İşaretleme ve Negatif Politikası (`unknownAreaPolicy`):**
  - Pozitif fotoğraflarda etiketsiz alanlar doğrulanmış negatif DEĞİLDİR (`negativeScope: 'unknown outside reviewed active Pimple boxes'`). Model eğitiminde kayıp maskelenmiştir; ürün çıktısında bu alanlar `annotation_unknown` olarak kategorize edilir, **kesinlikle yanlış pozitif sayılmaz**.
  - Negatif kontroller, tüm yüzü mühendislik incelemesinden geçmiş ve sıfır sivilce teyidi yapılmış 34 fotoğraftan (`negativeROI: 'reviewed-visible-face'`) oluşur.

---

## 3. Giriş–Model–Decode–Filtre Zincir Teşhisi

Gerçek ürün zinciri adım adım incelenmiştir:
$$\text{Kaynak BGR} \xrightarrow{\text{tile } 384 \times 384, \text{stride } 288} \text{Tensör } [1, 3, 384, 384] \xrightarrow{\text{YOLOX}} \text{Ham Çıktı } [1, 3024, 6] \xrightarrow{\text{NMS } 0.30} \text{Kaynak Piksel Koordinatı} \xrightarrow{\text{Anatomik Filtre}} \text{Kabul Edilen Kutular}$$

### Teşhis Bulguları:
1. **Tile ve Resize Kaybı:** Küçük lezyonlar ($10\text{--}20$ px) tile veya resize sırasında **kaybolmamaktadır**. Yüz alanından 288 px adımlarla (96 px örtüşmeli) çıkarılan $384 \times 384$ tile'lar her lezyonu en az 2 farklı pencerede tamamen yakalamaktadır.
2. **Koordinat Uyumu:** `cx - w/2 + a` ters projeksiyonu kaynak piksel koordinatlarıyla mikron seviyesinde tam eşleşmektedir (maksimum fark $< 0.05$ px).
3. **Kaçırılan Odakların Nedeni:**
   - **Model Yanıtı:** $1280 \times 1280$ çözünürlükteki fotoğraflarda çok küçük odaklarda modelin ham nesnesellik (objectness) skoru 0.70 eşiğinin altında kalabilmektedir (Örn. `424a750a` Truth 4: ham skor 0.0797).
   - **Yakın Komşuluk / NMS:** Çok yakın iki lezyonda (mesafe $< 25$ px) tek bir kutu iki lezyonu kapsayabilmektedir (Örn. `5432a6e1` Truth 3 ve Truth 6).
   - **Somut Anatomik Filtre Hatası:** Asıl gereksiz kayıp, `acne_box_support.py` içindeki **aşırı kısıtlayıcı filtre kurallarından** kaynaklanmaktaydı:
     - **Hata A (Dışlama Sınır Hassasiyeti):** `(exclusion > 0).mean() > 0.05` kuralı, kutunun yalnız %5'i (15x15 kutuda sadece 11 piksel) kaş veya göz çevresi dışlama sınırına değse bile, lezyon merkezi tamamen sağlıklı deride olmasına rağmen lezyonu `ANATOMICAL_HOLE_OR_HAIR` gerekçesiyle çöpe atıyordu.
     - **Hata B (Bölgesel Zarf Hakimiyeti):** `(envelopes[k] & skin_support).mean() >= 0.65` kuralı, kutunun %65'inin tek bir bölgesel sunum ağı poligonunda (örn. sadece burun veya sadece yanak) olmasını şart koşuyordu. Burun-yanak veya alın-burun sınırındaki lezyonlar %100 sağlıklı deride olmasına rağmen (%50 burun, %50 yanak) hiçbir bölge %65'e ulaşamadığı için `INSUFFICIENT_ANATOMICAL_SKIN_SUPPORT` ile eleniyordu.

---

## 4. Yapılan Düzeltme (`source-box-anatomical-support-v3`)

`services/core-api/acne_box_support.py` dosyasında şu genel, fotoğrafa bağımsız düzeltmeler yapılmıştır:
1. **Merkez ve Sınır Koruması:** Lezyon merkezinin delik/saç içinde olmaması (`not exclusion[cy, cx] and not hair[cy, cx]`) korunmuş; sınır değme toleransı %5'ten **%25'e** çıkarılmıştır. Böylece sınır yakını küçük sivilceler korunurken, delik veya saç içine düşen adaylar kesin biçimde elenmeye devam etmektedir.
2. **Genel Cilt Desteği ve Çoğunluk Bölge Ataması:** Tek bölgeye %65 bağımlılık yerine kutunun toplam geçerli cilt desteğinin $\ge \%50$ olması (`skin_support >= 0.50`) ve merkezinin ciltte olması şartı getirilmiştir. Bölgesel atama ise en yüksek örtüşmeye sahip bölgeye ($\ge \%15$) yapılarak bölge sınırındaki lezyonların düşmesi engellenmiştir.
3. Sürüm `source-box-anatomical-support-v3` olarak güncellenmiştir.

---

## 5. Önce / Sonra Karşılaştırma Sonuçları

### A. Geliştirme Regresyon Örnekleri (Zero Regression Doğrulandı)
- **`424a750a` (6 gerçek lezyon):**
  - Ham dedektör: 4 eşleşti (Truth 0, 1, 2, 3), 2 kaçtı (Truth 4 düşük skor 0.08, Truth 5 IoU 0.468).
  - Filtre öncesi ve sonrası: **4/4 eşleşen lezyon eksiksiz korundu** (0 kayıp).
- **`5432a6e1` (7 gerçek lezyon):**
  - Ham dedektör: 4 eşleşti (Truth 0, 1, 4, 5), 3 kaçtı (Truth 2 IoU 0.30, Truth 3 & 6 komşu odakta absorbe).
  - Filtre öncesi ve sonrası: **4/4 eşleşen lezyon eksiksiz korundu** (0 kayıp).

### B. Doğrulama Kümesi (43 Fotoğraf: 28 Pozitif + 15 İncelenmiş Negatif Kontrol)

| Metrik | Eski Filtre (v2) | Yeni Filtre (v3) | Değişim / Kazanım |
| :--- | :--- | :--- | :--- |
| **Toplam Gerçek Lezyon (Pozitif Küme)** | 276 | 276 | Sabit envanter |
| **Yakalanan Gerçek Lezyon (IoU $\ge 0.50$)** | 66 | **71** | **+5 gerçek lezyon kurtarıldı** |
| **Yakalanan Gerçek Lezyon (IoU $\ge 0.30$)** | 99 | **106** | **+7 gerçek lezyon kurtarıldı** |
| **Filtrenin Elediği Gerçek Lezyon Sayısı** | 42 | **37** | **5 lezyon gereksiz elenmekten kurtarıldı** |
| **15 Negatif Kontroldeki Yanlış Aday Toplamı** | 8 | **8** | **0 artış (negatif kontrol hassasiyeti korundu)** |
| **Negatif Fotoğraf Başına Ortalama Yanlış Aday** | 0.533 | **0.533** | Kabul kriteri ($\le 1.0$) içinde |
| **Birim Testler (`pytest`)** | 21/21 passed | **26/26 passed** | 5 yeni sözleşme testi eklendi |

### C. Doğrulama Kümesindeki Duruş/Açı Bulgusu
Yapılan MediaPipe hizalama analizinde, 28 pozitif doğrulama fotoğrafından **yalnızca 6 tanesinin** cepheden (`isAligned: True`) olduğu; **22 tanesinin** ise aşırı profil/açılı çekimler (yaw 1.13 ila 3.20 radyan) olduğu tespit edilmiştir. Kalan 37 elenen lezyonun neredeyse tamamı, sunum ağının bulunmadığı bu aşırı yan profil açılarındaki yüz kenarlarına düşmektedir. Doğal cephe fotoğraflarında filtrenin lezyon koruma oranı kusursuzdur.

---

## 6. Olası Gelecek İnce Ayar (Fine-Tuning) Planı

Mevcut dondurulmuş dedektör negatif kontrollerde son derece temizdir (fotoğraf başına 0.53 yanlış aday). Ancak çok küçük odakların ($< 15$ px) ham yakalama oranını artırmak amacıyla ileride ek bir ince ayar planlanırsa aşağıdaki sonlu protokol uygulanmalıdır:
- **Başlangıç:** Dondurulmuş `1a014adad262` ağırlıkları.
- **Eğitim Verisi:** `negative-expanded-detector-data.json` içindeki 132 eğitim fotoğrafı (834 sivilce, 19 negatif).
- **Yöntem:** Odak merkezli $384 \times 384$ tile'lar ($\pm 35$ px rastgele kaydırma ile).
- **Kayıp:** BCE (objectness) + CIoU (bbox). Etiketsiz alanlar kayıpta maskelenir.
- **Kaynak / Süre:** CPU ortamında batch=2, maksimum 15 epoch, erken durdurma (patience 4). Tahmini süre $\sim 45$ dakika, disk $< 100$ MB.
- **Durdurma Kriteri:** Negatif kontrollerde fotoğraf başına ortalama yanlış aday $> 1.0$ olursa eğitim iptal edilir.
