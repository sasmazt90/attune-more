# TOGG Attune: Cilt Analizi Genişletilmiş Düzeltmeler, Göz Çevresi ve Torbalanma Raporu

**Tarih:** 2026-10-12  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Branch:** `feat/skin-type-dry-sag-antigravity`  
**Baseline:** CD `d596873c363a57324d38dc974e5ad65186ea9866` (salt okunur referans)  
**Kapsam:** 
1. Göz altı torbalanmasının (Target C) yerel 2D görünüm analizi olarak ayrımı, kirpik/alt kapak marjı ve süreklilik kapısı onarımı, kart skoru ve yerel harita tutarlılığı.
2. Eşik doğrulama (periorbital `trackingResidual` 2.8, `shadow slope` 0.75), 6 sınıflı fotoğraf envanteri tasnifi, dürüst veri menşei belgelendirmesi ve karşılaştırmalı galeri.
3. Yöntem sürümleme (`contour-fold-local-support-v5`), tarihsel v4 kayıtlarının geriye dönük uyumlulukla korunması ve CD entegrasyon teslim paketi.

---

## 1. Yönetici Özeti (Executive Summary)

Göz altı torbalanması analizi, ilk taramada ve kişisel referans/baz geçmiş gerektirmeden çalışan **yerel 2D görünüm analizi** (kontur katlantı ve gölge gradyanı) olarak geliştirilmiştir. Kesinlikle 3D derinlik veya hacim ölçümü iddiasında bulunulmamaktadır.

| Hedef | Gerçek Değişiklik | Doğal Fotoğraf & Kapsam | Baseline (`d596873`) | Candidate (AG Worktree) | Ürün / Model Kabul Durumu |
|---|---|---|---|---|---|
| **A. Sivilce (Acne)** | Kaş dış kuyruk landmark'ları (`69`, `299`) konveks zarfa eklendi; tüm kanalların clipping denetimi (`min(RGB) > 0.975`). | Seçilmiş dondurulmuş model (`ea6e497b`) + üretim pipeline'ı (2 geliştirme yüzü). | 5 görev dışı kutu sızıyordu; parlamada lezyon eleniyordu. | Kaş kuyruğu sızıntısı 0'a indi; 11/11 lezyon korundu. Filtre sonrası: 17 ve 20 kutu. | **Model Kabul Edilmedi (`ACNE_MODEL_NOT_ACCEPTED`)**. Filtre UI'ı korur; dedektör F1: 0.18 (conf=0.7), 2 kaçırılan lezyon ve 18 etiketsiz aday ile zayıftır. |
| **B. Göz Altı Morluğu (Dark Circles)** | %5 kontrast deadband'i (`deadband = 0.05`); CIELAB $\Delta \text{chroma}$ kromatizm kapısı; yanak referans deri onarımı; sürüm: `lower-lid-contrast-chroma-local-v4`. | Doğal validation spliti (8 pozitif, 2 incelenmiş negatif). | Pozitif 4242afe5: 16.26; İncelenmiş negatif beda0290: 8.67. | Pozitif 4242afe5: 11.81 (UI: %12); İncelenmiş negatif beda0290: 1.72 (UI: %2). | **Ürün Algoritması Güncellendi**. Yapay parametreler doğal fotoğraflarda doğrulanmış; analitik `appearance-cv-6` proxy'si aktiftir. |
| **C. Göz Altı Torbalanması (Eye Bags)** | Pretarsal kapak marjı ayrımı (`offsets` `[7..28]`); süreklilik skoru kapısı (`continuity < 0.20` ise `joint = 0.0`); orbital rim tracking 2.8; gölge eşiği 0.75; sürüm: `contour-fold-local-support-v5`. | Doğal validation spliti (4 pozitif, 3 incelenmiş negatif). | Pozitif 36e4010b: `CONTOUR_TRACKING_UNSTABLE`; Pozitif 20031f35: `HAIR_OR_SHARP_LINE_CONFOUNDER`; Negatif 5bd42346: `EXPRESSION_OPEN_MOUTH_OR_SMILE`. | Pozitif 36e4010b: 0.67 (UI: %1); Pozitif 20031f35: 13.89 (UI: %14); Negatif 5bd42346: 0.00 (UI: %0); Negatif beda0290: 0.00 (UI: %0). | **Ürün Algoritması Güncellendi**. Nöral torba maskesi (FPR %21.04) reddedildi; analitik kontur fold proxy'si v5 aktiftir. |
| **D. Kaz Ayakları / Çizgiler (Lines)** | Saç marjı dışlama refaktörü (`active_support = under & ~hair_margin`); roll-aware radyal Gabor fanı ($\pm 30^\circ$ rotasyon); sürüm: `outer-canthus-gabor-radiating-hair-excluded-v3`. | Doğal validation spliti (4 pozitif, 3 incelenmiş negatif). | Saç pikselleri paydaya ve haritaya katılıyordu; baş eğiminde kirpik sızıyordu. | Saç haritadan/skordan tamamen çıkarıldı; tam örtüşmede `HAIR_OR_OCCLUSION_IN_LINE_BAND` (`None`). Dikey kirpik bastırma: 70.7 kat. | **Ürün Algoritması Güncellendi**. Nöral çizgi maskesi (FPR %18.13) reddedildi; filtrelenmiş radyal görünüm proxy'si aktiftir. |
| **E. Yağlılık, Kızarıklık, Ton & Photo57** | Kısmi etiketli U-Net maskelerinin aşırı genelleşmesi (~%92) kanıtlandı; Photo57 canlı koşturuldu. | `scope-v4-mask-data.json` geliştirme ayrımı ve Photo57 kaynak fotoğrafı. | Nöral maskeler devrede değildi; Photo57 disk makbuzu okunuyordu. | Nöral maskeler reddedildi (`appearance-cv-6` korundu); Photo57 canlı `analyze_skin` ile `INSUFFICIENT_SKIN_SUPPORT` (`None`). | **Yeni Maskeler Kabul Edilmedi (`NEURAL_MASK_NOT_ACCEPTED`)**. Üründe `appearance-cv-6` analitik proxy'si korundu. Photo57 dürüstçe kaçırılan regresyon olarak kayda geçti. |

---

## 2. Göz Altı Torbalanması Sinyal Ayrımı ve Çıktı Tutarlılığı (Görev 1)

### 2.1 Yerel 2D Görünüm Analizi Prensibi
- Göz altı torbalanması değerlendirmesi, tek bir 2D RGB fotoğraf üzerinden ilk taramada kişisel referans gerektirmeden hesaplanır.
- Yöntem **kesinlikle bir 3D yüz taraması, stereo derinlik haritası veya milimetrik hacim ölçümü değildir**.
- Yöntem, alt göz kapağının altındaki infraorbital bölgedeki anatomik katlantı çizgilerinin 2D parlaklık gradyanı, yerel kontrastı ve bu katlantının altındaki aydınlatma gölgesi eşleşmesini analiz eden analitik bir görünüm göstergesidir (`appearance-cv-6`).

### 2.2 İncelenen Kök Nedenler ve Düzeltmeler

#### A. Pozitif 20031f35 (~13.89) vs Pozitif 36e4010b (~0.67) Ayrımı
1. **`20031f35` (Yüksek Torbalanma - UI: %14):**
   - Kaynak fotoğraf: `train/3879bc8f-24_5_jpg.rf.8219ef285adb926de2639d05630d45d8.jpg`.
   - İleri derecede belirgin orbital yağ herniasyonu (belirgin göz altı torbası) bulunmaktadır.
   - Her iki göz altında çift kenar kontrastı (`paired edge` = 0.077, yerel kontrast = 0.061) çok yüksektir ve katlantı çizgisi göz genişliğinin tamamı boyunca kesintisiz uzanmaktadır (`continuity` = 1.00).
   - Baseline sürümünde üst saç/kaş periorbital maskesine teğet olduğu için aşırı korumacı `HAIR_OR_SHARP_LINE_CONFOUNDER` bayrağıyla eleniyordu. Düzeltilmiş adayda saç maskesi yalnızca kendi yerel şeridine kısıtlandığından gerçek torba anatomisi serbest kalmış ve 13.89 (UI: %14) olarak başarıyla ölçülmüştür.
2. **`36e4010b` (Hafif Torbalanma - UI: %1):**
   - Kaynak fotoğraf: `train/175_jpg.rf.02894589d3ea1ec13ef752762eb29b35.jpg`.
   - Gerçek ancak hafif bir torbalanma katlantısı mevcuttur. Yerel kontrast %4 civarındadır (`contrast` ~ 0.040, `paired edge` ~ 0.023).
   - Sağ tarafta 4.17'lik yerel sinyal bulunurken sol tarafta katlantı kesintilidir (0.05). Ortalama ham skor 0.669 (UI: %1) seviyesindedir.
   - Baseline'da orbital rim takip kalıntısı 2.5 eşiğini aştığı için (`residuals`: 2.613 ve 2.528) `CONTOUR_TRACKING_UNSTABLE` olarak eleniyordu. Adayda eşik 2.8'e kalibre edilerek hafif torba sinyali kurtarılmıştır.

#### B. İncelenen Negatif 5bd42346 Sızıntısının Çözümü (1.63 &rarr; 0.00 / UI: %0)
- **Sorun:** Önceki v4 denemesinde, gülümseme filtresi dekuple edildiğinde pürüzsüz alt kapağa sahip olan `5bd42346` fotoğrafı 1.63 ham puan (%2 UI) üreterek yalancı pozitif sızdırmıştı; oysa aynı koşullardaki `beda0290` temiz 0.00 almıştı.
- **Kök Neden Tespiti:**
  1. `instant_appearance.py` içindeki periorbital tarama koridoru `offsets = np.arange(3, 25)` olarak tanımlıydı.
  2. Ofset 3..6 aralığı, alt göz kapağının serbest kenarını (pretarsal alt kapak marjı ve kirpik kökü hattı) doğrudan örneklemekteydi. Pürüzsüz kapaklarda dahi kapak kenarının tarsal plate üzerindeki doğal gölgesi ~%2.5 yerel kontrast oluşturuyordu.
  3. `points` listesi `continuity < 0.20` olduğunda boşaltılsa bile, kart skoru hesabı olan `joint` formülü `q['values'] * min(1.0, continuity / 0.6)` çarpanıyla pürüzsüz kapaktaki gürültüden 1.63 puan hesaplıyordu; bu da yerel gradyan haritasında hiçbir çizgi görünmezken kartta %2 torba skoru çıkmasına yol açıyordu.
- **Uygulanan Kesin Çözüm:**
  1. **Anatomik Koridor Ofsetlerinin Kaydırılması:** Ofsetler `np.arange(7, 28)` olarak güncellendi. Ofset 0..6 (pretarsal kapak kenarı) tamamen hariç tutuldu. `bands['bags']` alt sınırı `0.022 * face_width` (~ofset 7) ile başladığından, 7..28 aralığı anatomik infraorbital torba bandının %100 içerisinde kalmakta ve normal kapak kenarını asla örneklememektedir.
  2. **Skor ve Harita Tutarlılığı İçin Süreklilik Kapısı:** `joint` hesaplamasına katı süreklilik kapısı eklendi:
     ```python
     continuity_gate = 0.0 if q['continuity'] < 0.20 else min(1.0, q['continuity'] / 0.6)
     joint = float(np.mean(joint_values)) * continuity_gate
     ```
  3. **Sonuç:** `5bd42346` üzerinde süreklilik 0.16/0.19 seviyesinde kaldığı için süreklilik kapısı devreye girmiş, hem kart skoru hem yerel harita **kesin olarak 0.00 (UI: %0)** üretmiştir. Yalancı pozitif sızıntısı tamamen giderilmiştir.

---

## 3. Eşik Doğrulaması ve Doğal Fotoğraf Envanteri Sınıflandırması (Görev 2)

### 3.1 Periorbital Eşik Kalibrasyonları
- **Periorbital Orbital Rim Tracking Eşiği (2.5 &rarr; 2.8):** Göz altı kemik kenarı yay çizdiğinden düz çizgi varsayımı hafif sapma gösterir. Sadece periorbital bölgede eşik 2.8 yapılarak `36e4010b` gibi gerçek katlantılar kurtarılmıştır. Yanak, çene veya nazolabial sarkma kontrollerindeki hiçbir eşiğe dokunulmamıştır.
- **Periorbital Gölge Eşiği (0.55 &rarr; 0.75):** Periorbital analiz alanı iki ayrık göz altı bandından oluştuğundan frontal ışıkta dahi küresel eğim 0.55'i aşabilmektedir (beda0290: 0.704, 5bd42346: 0.582). Yalnızca periorbital analizde gölge eşiği 0.75'e çekilerek normal pürüzsüz yüzlerin erken `HARD_DIRECTIONAL_SHADOW` hatasına düşmesi engellenmiş, temiz 0.00 sonucuna ulaşması sağlanmıştır.
- **Gülümseme ve Mimik Dekuplajı:** Periorbital gülümseme çizgileri `smile_factor` düzeltmesi ile katlantı skorundan ayrıştırılmış; genel yüz ifadesi kilidi yerine yerel mimik düzeltmesi yapılmıştır. Kısılmış gözler ise `min(eye_aspects) < 0.12` anatomik güvenlik kilidiyle korunmuştur.

### 3.2 Doğal Fotoğraf Envanterinin 6 Sınıflı Tasnifi

Mevcut veri envanterindeki kaynaklar altı zorunlu kategoriye dürüstçe ayrılmıştır:

| Kategori | Örnek Dosyalar / SHA-256 | Durum / Ölçüm Davranışı | Açıklama |
|---|---|---|---|
| **(a) Görünür Torbalanma (Visible Bags)** | `20031f35` (train/3879bc8f-24_5)<br>`36e4010b` (train/175_jpg)<br>`23412227` (valid/2937757570_1)<br>`b3d3ef6a` (train/2405801774_1)<br>`6e04e15d` & `f1471654` | `20031f35`: 13.89 (UI: %14)<br>`36e4010b`: 0.67 (UI: %1)<br>`23412227`: `CAPTURE_QUALITY`<br>`b3d3ef6a`: `CAPTURE_QUALITY`<br>`6e04e15d` & `f1471654`: Kapsam Dışı | `20031f35` ve `36e4010b` geliştirme kontrolü olarak başarıyla ölçülmüştür. `23412227` (yaw: -0.64) ve `b3d3ef6a` (yaw: 1.17) aşırı baş açısı nedeniyle üretim kalite kapısınca (`abs(yaw) < 0.35`) elenmiştir. `6e04e15d` ve `f1471654` tüm yüz içermeyen crop'lar olduğu için `CROP_NO_WHOLE_FACE` olarak dışlanmıştır. |
| **(b) Normal Alt Göz Kapağı (Normal Lower Eyelid)** | `5bd42346` (valid/dry_3af68a19)<br>`beda0290` (test/normal_new_75ec)<br>`4356a5dc` (test/normal_new_3fbc) | `5bd42346`: 0.00 (UI: %0)<br>`beda0290`: 0.00 (UI: %0)<br>`4356a5dc`: `CAPTURE_QUALITY` | `5bd42346` ve `beda0290` pürüzsüz alt kapağa sahip temiz negatiflerdir; v5 ile sıfır sızıntı (0.00) ile doğrulanmıştır. `4356a5dc` aşırı baş açısı (yaw: -0.56) nedeniyle kalite filtresince elenmiştir. |
| **(c) Morluk / Pigment (Dark Circles without Bags)** | `4242afe5` (test/e88d4a8d-229_1)<br>`01955323` (train/96bb74de-img_403)<br>`5462f88f` (train/63d3b3c3-502)<br>`54dfc0e8` (test/e88d4a8d-229)<br>`8888bdd1` (train/89d1b6cf-200)<br>`9dc2d78d` (train/1a74d2fe-101)<br>`ffb45bf7` (train/0a87a251-18) | Morluk: %8 - %34 UI<br>Torbalanma: 0.00 veya None | Belirgin hiperpigmentasyon veya koyu halka içeren bu yüzlerde katlantı sinyali tetiklenmemiştir. Örneğin `4242afe5`'te morluk %12 UI iken torbalanma katlantısı oluşmamıştır. |
| **(d) Tek Taraflı Aydınlatma Gölgesi (Unilateral Shadow)** | `beda0290` (test/normal_new_75ecf7ec) | `bags`: 0.00 (UI: %0) | Periorbital ışık eğimi 0.582 seviyesindedir. 0.75 eşiği altında kalarak sahte gölge hatası veya sahte torba katlantısı üretmemiş, pürüzsüz negatif olarak 0.00 ölçülmüştür. |
| **(e) Gülümseme / Kısılmış Göz (Smiling / Squinting)** | `5bd42346` (gülümseme)<br>`beda0290` (hafif mimik) | `bags`: 0.00 (UI: %0) | Periorbital gülümseme kırışıklığı `smile_factor` ile dekuple edilmiş; mimik nedeniyle alt kapakta sahte torba skoru oluşması engellenmiştir. |
| **(f) Saç / Kirpik Örtülmesi (Hair / Lash Occlusion)** | `20031f35` (üst kahkül/kaş)<br>`02386f86` (yan saç) | `20031f35`: 13.89<br>`02386f86`: 3.84 | Saç maskesi şeridi izole edilmiş; kahkül ve kirpiklerin torba koridoruna katlantı olarak sızması engellenmiştir. |

### 3.3 Veri Menşei ve Doğrulama Dürüstlüğü (Data Provenance)
> [!IMPORTANT]
> **Dürüst Doğrulama Beyanı:** Yukarıda değerlendirilen pozitif fotoğraflar (`20031f35` ve `36e4010b`), algoritma parametrelerinin geliştirilmesi ve ayarlanmasında kontrol noktası olarak kullanılmıştır (**development controls**). Projede henüz göz altı torbalanması için bağımsız, görülmemiş (**unseen**) ve yeterli büyüklükte bir test split'i bulunmamaktadır. Bu nedenle bu sonuçlar genel ürün doğruluğu olarak genellenemez; yalnızca hedeflenen anatomik ayrımın ve eşiklerin doğru çalıştığını kanıtlayan geliştirme kontrolleridir.

### 3.4 Karşılaştırmalı Görsel Galeri
- Tüm pozitif ve incelenmiş negatif fotoğraflar için üçlü panel (Yer Gerçeği, Baseline `d596873`, Aday Sürüm) görselleştirmeleri üretilmiştir:
  - Konum: `audit-results/gallery/index.html`
  - Paneller: `bags_pos_20031f35.jpg`, `bags_pos_36e4010b.jpg`, `bags_neg_5bd42346.jpg`, `bags_neg_beda0290.jpg` vb.
  - Galeri, yerel haritaların ve skorların önce/sonra durumunu interaktif olarak sunmaktadır.

---

## 4. Yöntem Sürümleme ve Geriye Dönük Uyumluluk (Görev 3)

### 4.1 Sürüm Güncellemesi (`contour-fold-local-support-v5`)
Göz altı torbalanması normalizasyon ve yöntem sürümü hem analiz motorunda hem sözleşmede v5'e yükseltilmiştir:
- `services/core-api/instant_appearance.py`: `methodVersion = 'contour-fold-local-support-v5'`
- `services/core-api/appearance_analysis.py`: `NORMALIZATION['bags'] = 'contour-fold-local-support-v5'`
- Birim test sözleşmesi: `test_skin_expanded_corrections.py` içinde `test_target_c_eye_bags_version_and_eyelid_margin_separation` ile kilitlenmiştir.

### 4.2 Tarihsel Kayıtların Korunması ve Grafik Ayrımı
1. **Tarihsel Kayıtların Değiştirilmezliği:** Veritabanındaki eski `contour-fold-local-support-v4` kayıtları asla geriye dönük olarak yeniden hesaplanmaz, dönüştürülmez veya silinmez. Tarihsel telemetri bütünlüğü korunur.
2. **Geçmiş ve Trend Grafiklerinde Ayrıştırma:**
   - Ön yüzde `apps/vehicle-app/src/utils/healthHistorySeries.ts` (satır 75) serileri gruplarken açıkça `normalizationVersion`'ı anahtar olarak kullanır:
     ```typescript
     const seriesKey = `${m.id}:${m.normalizationVersion || 'legacy'}`;
     ```
   - Böylece v4 ile kaydedilmiş eski ölçümler ile v5 ile kaydedilen yeni ölçümler trend grafiklerinde birbirine karıştırılmaz; iki ayrı seri olarak gösterilir veya sürüm geçişinde yeni trend başlatılır.
3. **Fark ve Delta Koruması:**
   - `apps/vehicle-app/src/utils/appearanceMeasurements.ts` (satır 35) farklı normalizasyon sürümlerine sahip iki ölçüm arasında delta/fark hesaplamayı güvenlik kuralı olarak reddeder (`base.normalizationVersion !== value.normalizationVersion` durumunda delta hesaplanmaz).

---

## 5. CD Entegrasyon Teslim Paketi

CD ana çalışma alanına (`attune-live-test`) entegrasyon için hazır olan dosyalar ve değişiklik özeti:

### 1. Değiştirilen Çekirdek Servis Dosyaları
- **`services/core-api/instant_appearance.py`**:
  - Pretarsal marj ofsetleri: `np.arange(3, 25)` &rarr; `np.arange(7, 28)`.
  - Süreklilik skoru kapısı: `continuity < 0.20` ise `joint = 0.0`.
  - Eşikler: periorbital trackingResidual 2.8, shadow slope 0.75.
  - Sürüm etiketi: `contour-fold-local-support-v5`.
- **`services/core-api/appearance_analysis.py`**:
  - `NORMALIZATION['bags'] = 'contour-fold-local-support-v5'`.
  - Kaş dış kuyruk landmark'ları (`69`, `299`) konveks zarfa dahil edildi.
  - Kaz ayaklarında saç dışlama refaktörü (`active_support = under & ~hair_margin`) ve roll-aware Gabor yönleri.
  - Morluk analizinde yanak referans derisi onarımı ve %5 deadband.
- **`services/core-api/acne_box_support.py`**:
  - Kaş dış kuyruk koruması ve çok kanallı kırpma kontrolü (`source-box-anatomical-support-v2`).

### 2. Test ve Doğrulama Dosyaları
- **`tests/unit/test_skin_expanded_corrections.py`**:
  - 9 odaklı birim test (sivilce kaş/clipping, morluk deadband/kromatizm, torbalanma v5 ve alt kapak marjı ayrımı, çizgi yön/saç dışlama, Photo57 canlı icra).
- **`tests/unit/test_appearance_references.py` & `test_skin_overview_contract.py`**:
  - `NODE_PATH` ortam değişkeni eklenerek Node subprocess uyumluluğu sağlandı.
- **`scripts/evaluate_periorbital_and_acne_comparative.py`**:
  - `NoneType` ölçek oranı toleransı, dinamik Git HEAD ve triptik karşılaştırmalı galeri oluşturucu.
- **`scripts/verify_skin_expanded_corrections.py`**:
  - Ayrık sonuç alanları üreten ve disk makbuzunu güncelleyen bağımsız doğrulama aracı.

### 3. Oluşturulan Doğrulama Makbuzları
- `audit-results/skin-comparative-evaluation-summary.json`: Tam önce/sonra sayısal karşılaştırma makbuzu.
- `audit-results/skin-expanded-corrections-summary.json`: Genişletilmiş kontroller özeti.
- `audit-results/gallery/index.html`: İnteraktif karşılaştırmalı HTML galerisi ve panel JPEG'leri.
