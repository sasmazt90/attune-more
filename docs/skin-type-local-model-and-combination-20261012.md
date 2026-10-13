# TOGG Attune - Yerel Cilt Tipi Modeli, Bölgesel Karma v2 ve 4 Sınıflı Başlık Deneyi Raporu

**Tarih:** 12 Ekim 2026  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Baseline / Referans:** `de82971` (Kaz Ayakları v4 dondurulmuş paketi korunmuştur)  
**Hedef Bileşenler:** 
- `services/core-api/skin_models.py`
- `services/core-api/appearance_analysis.py`
- `services/core-api/models/skin-focused.json`
- `services/core-api/models/skin-type-glamour-vit.onnx`
- `scripts/run_skin_type_4class_head_experiment.py`
- `tests/unit/test_skin_type_local.py`  
**Bağımsız Denetim Makbuzları:** 
- `audit-results/skin-type-local-evaluation-20261012.json` (İlk ViT ve Karma v2 çalışma makbuzu)
- `audit-results/skin-type-head-experiment-20261012/receipt.json` (Sonlu 4 sınıflı başlık deneyi ve 3 yönlü karşılaştırma makbuzu)

---

## 1. Yönetici Özeti ve Karar Raporu

TOGG Attune araç içi sağlık ve cilt analizi sisteminde, harici bulut bağımlılıklarını ortadan kaldıran 100% yerel (on-device) Cilt Tipi (Skin Type) analizinde aday/ürün yolları kesin sınırlarla ayrılmış, Karma güven metriği düzeltilmiş, dürüst metrik açıklamaları yapılmış ve dondurulmuş Vision Transformer (ViT) özellikleri üzerinde sonlu bir 4 sınıflı başlık deneyi gerçekleştirilmiştir.

### Temel Kararlar ve Bulgular:

1. **Aday ve Ürün Yolunun Kesin Ayrımı:**
   - `skin_models.load(allow_candidates=False)` ve `skin_models.infer(..., allow_candidates=False)` varsayılan olarak **aday kapalı (product mode)** çalışır.
   - Normal ürün oturumunda yalnızca `accepted: true` olan modeller (ör. bütünsel kızarıklık `degrees`) yüklenir. Manifestte `accepted: false` olan aday ViT modeli ürün oturumuna alınmaz.
   - `allow_candidates=True` açıkça verildiğinde yalnızca `candidateAccepted: true` olan cilt tipi modeli yüklenir; reddedilmiş sivilce (`acne`) veya torbalanma (`bags`) görevleri **asla yeniden açılmaz**.
   - Aday ONNX dosyası (`skin-type-glamour-vit.onnx`) korunmuş, silinmemiştir.
   - Kabul/ret kararları klinik/laboratuvar etiket zorunluluğuna değil, **kozmetik görünüm sınıflandırması**, veri uygunluğu, sınıf ayrımı ve ürün güvenilirliği kriterlerine dayandırılmıştır.

2. **Dürüst Metrik Beyanı ve Veri Sınırları:**
   - Önceki 100 örnekli holdout değerlendirmesinde bildirilen **%30.30** doğruluğun yalnızca geçerli yanıt üreten 66 örnek üzerinden hesaplandığı (66 örnekte 20 doğru), 100 örneğin tümü dikkate alındığında toplam doğruluğun (yakalama oranının) **20/100 (%20.00)** olduğu ve 34 örneğin elendiği (25 parlama/pozlama, 7 landmark, 2 düşük destek) açıkça beyan edilmiştir.
   - Görüntü öneklerine (`.rf.`, `-Copy`) göre ayırmanın aynı fotoğrafın artırılmış kopyalarını temizlediği, ancak Kaggle veri setinde kişi kimliklerinin bağımsızlığını kanıtlamadığı; önceki 200 örneğin artık bağımsız test verisi değil, **geliştirme/kalibrasyon kanıtı** olduğu kaydedilmiştir.

3. **Bölgesel Karma Güven Puanının Düzeltilmesi:**
   - Karma kuralının ürettiği elle ağırlıklandırılmış destek endeksi ($[0.40, 0.88]$), kalibre edilmiş bir olasılık değeri değildir.
   - Bu nedenle `regional_combination_rule` ve `infer`, Karma kararlarında `confidence = None` döndürmektedir.
   - İlgili destek puanı `regionalDivergence` altında `heuristicSupport` ve `ruleSupport` olarak şeffafça sunulmaktadır.
   - 4 sınıflı başlık çıktısı için de ham softmax skorları kalibre edilmemiş skor olarak ele alınmıştır.

4. **Dondurulmuş ViT Üzerinde 4 Sınıflı Başlık Deneyi:**
   - `AishaBaliyan/glamour-ai-skin-model` omurgası `eval` modunda dondurulmuş (sıfır geriye yayılım).
   - Veri setindeki tüm uygun kaynak grupları (yüz algılanan, yüz pikselleri $\ge 180$, anatomik cilt maskeleri geçerli, cilt parlaması $\le 0.15$) taranarak 600 tekil önek seçilmiştir.
   - Bölünme (önek örtüşmesi %0): **Train (402)**, **Validation (99)**, **Held-out Final Test (99)**.
   - 768 boyutlu CLS öznitelikleri önbelleğe alınmış ve 3 düzenlileştirme ayarı ($C \in \{0.01, 0.1, 1.0\}$) taranmıştır.
   - Validasyon kümesinde en iyi ayar olarak **$C = 0.10$** (Val Macro-F1 = 0.2781) seçilmiştir ($C=1.00$ eğitim kümesinde 0.9728 F1 verirken validasyonda aşırı uyuma düşmüştür).

5. **99 Bağımsız Test Örneğinde 3 Yönlü Karşılaştırma ve Görev Durumu:**
   - **(A) Temel 3 Sınıflı ViT:** Macro-F1 = 0.2962 | Yanıtlanan Doğruluk = %38.38 | Tüm Örnekler Doğruluğu = %38.38 | Karma F1 = 0.000
   - **(B) Bölgesel Karma v2:** Macro-F1 = **0.3723** | Yanıtlanan Doğruluk = **%41.24** | Tüm Örnekler Doğruluğu = **%40.40** | Karma F1 = 0.1905
   - **(C) Öğrenilmiş 4 Sınıflı Başlık:** Macro-F1 = 0.2459 | Yanıtlanan Doğruluk = %24.24 | Tüm Örnekler Doğruluğu = %24.24 | Karma F1 = 0.2857
   - **Karar ve Durum:** Yeni 4 sınıflı başlık 24/99 doğru ile rastgele seviyede (%24.24) kaldığı için **ürüne alınmamıştır (`accepted: false`)**. Mevcut ViT/Karma kuralı adayı da nihai başarılı çözüm olarak ilan edilmemiştir; **Cilt tipi görevi açık (unresolved araştırma konusu) olarak kalmaya devam etmektedir**.
   - **Kanıtlanmış Bulgular vs. Olası Nedenler (Hipotezler):**
     - *Kanıtlanmış Bulgu:* 3 sınıflı dondurulmuş ViT omurgası üzerine oturtulan doğrusal 4 sınıflı başlık, 99 bağımsız test örneğinde 4 sınıflı rastgele tahmin (%25) seviyesini aşamamıştır.
     - *Olası Nedenler (Hipotezler):* Bu başarısızlıktan tekil olarak "etiketler kesinlikle aşırı gürültülü" sonucu çıkarılamaz; (1) 3 sınıfa göre önceden eğitilmiş omurganın 768-boyutlu CLS temsilinin Karma (Combination) için ayrım gücünün sınırlı olması, (2) Web/Kaggle kaynaklı veri/etiket tutarlılığı, (3) Train/Val/Test bölümleri arasındaki dağılım kayması, (4) Tek katmanlı doğrusal sınıflandırıcının karmaşık çok modlu yüz özelliklerini çözmedeki kapasite/optimizasyon kısıtları olası faktörlerdir.
   - **Öznitelik Önbelleği ve Doğrulama Kapsamı Makbuzu:** `features_cache.npz` içindeki tüm 600 satır (402 train, 99 val, 99 test), kaynak dosya SHA-256'sı, önek, etiket sırası ve kırpma geometrisi açısından yapısal olarak %100 doğrulanmıştır. Sayısal öznitelik denkliği ise tüm split'ler (train, val, test) ve tüm 4 sınıftan deterministik olarak seçilen 24 temsilci satırda dondurulmuş ViT omurga ileri geçişiyle tam sayısal doğrulukla teyit edilmiş (maksimum fark $0.000000e+00 < 1e-4$), kalan 576 satır hesap bütçesini korumak amacıyla yapısal doğrulamada tutulmuştur. Doğrulanan ve doğrulanmayan kapsamlar ile örnek kimlikleri [`features_manifest.json`](file:///c:/Users/PC/Desktop/AI%20Workspace/TOGG/attune-antigravity-skin/audit-results/skin-type-head-experiment-20261012/features_manifest.json) içinde açıkça ayrıştırılarak mühürlenmiştir. Yerel 4 sınıflı cilt tipi görevi AÇIK (unresolved) kalmaktadır.

---

## 2. Aday ve Ürün Yolu İzolasyonu Mimarisi

```
[ İstek / Analiz Çağrısı ]
           │
           ▼
┌──────────────────────────────────────────────┐
│ skin_models.load(allow_candidates)           │
│                                              │
│ allow_candidates=False (Ürün Varsayılanı):  │
│ ├─ accepted == True -> Yükle (degrees)       │
│ ├─ accepted == False -> ATLANIYOR (type ViT) │
│ └─ acne / bags -> ASLA YÜKLENMEZ             │
│                                              │
│ allow_candidates=True (Aday / Test Modu):    │
│ ├─ accepted == True -> Yükle (degrees)       │
│ ├─ task == 'type' and candidateAccepted      │
│ │   -> Yükle (skin-type-glamour-vit.onnx)   │
│ └─ acne / bags -> ASLA YÜKLENMEZ             │
└──────────────────────────────────────────────┘
```

### Güvenlik ve Bütünlük Kuralları:
1. `skin_models.load` fonksiyonu `@lru_cache(maxsize=2)` ile hem ürün (`False`) hem aday (`True`) oturumlarını ayrı önbelleğe alır.
2. `infer()` varsayılan olarak `allow_candidates=False` parametresiyle çağrılır; ürün analizi sırasında aday ViT oturumu çağrılmaz, `skinType` `None` kalır (veya yetkili hosted adapter varsa çalışır).
3. Aday oturumunda yalnızca `type` adayına izin verilir; geçmişte reddedilen `acne` ve `bags` görevleri hiçbir bayrakla açılmaz.
4. Ağ soketi bloklama testinde (`test_offline_infer_with_blocked_sockets`) ürün ve aday yolları %100 çevrimdışı doğrulanmıştır.

---

## 3. Dürüst Metrik Tablosu: Responded vs All-Samples

| Değerlendirme Kümesi | Yöntem | Yanıtlanan (Responded) Doğruluk | Tüm Örnekler (All-Samples) Doğruluğu | Kapsam (Coverage) | Ret Sayısı ve Nedenleri |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Önceki Validasyon (100 Örnek)** | ViT + Karma v2 | **%30.30** (20 / 66) | **%20.00** (20 / 100) | %66.0 | 34 Ret (25 Glare, 7 Landmarks, 2 Low Model Support) |
| **Held-out Test (99 Örnek)** | (A) 3 Sınıflı ViT | **%38.38** (38 / 99) | **%38.38** (38 / 99) | %100.0* | 0 Ret (Saf model argmax) |
| **Held-out Test (99 Örnek)** | (B) Karma v2 | **%41.24** (40 / 97) | **%40.40** (40 / 99) | %98.0 | 2 Ret (Deadband / Glare sınır kontrolleri) |
| **Held-out Test (99 Örnek)** | (C) 4 Sınıflı Başlık | **%24.24** (24 / 99) | **%24.24** (24 / 99) | %100.0 | 0 Ret (Saf model argmax) |

*\*Not: 99 test örneği ön filtreleme kurallarını (yüz algılama, parıltı $\le 0.15$, maske geçerliliği) zaten başarıyla geçen gruplardan seçilmiştir.*

---

## 4. 4 Sınıflı Başlık Deneyi Detayları ve 3 Yönlü Karşılaştırma

### A. Düzenlileştirme Taraması (Validation Seti - 99 Örnek)

| Düzenlileştirme ($C$) | Ağırlık Cezası | Train Macro-F1 | Train Doğruluk | Val Macro-F1 | Val Dengeli Doğruluk | Val Doğruluk |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| $C = 0.01$ | Güçlü (L2) | 0.5287 | %52.99 | 0.2495 | 0.2546 | %25.25 |
| **$C = 0.10$** *(Seçilen)* | **Dengeli (L2)** | **0.7447** | **%74.38** | **0.2781** | **0.2854** | **%28.28** |
| $C = 1.00$ | Hafif (L2) | 0.9728 | %97.26 | 0.2548 | 0.2542 | %25.25 |

*$C = 1.00$ durumunda model eğitim verisine aşırı uyum sağlayarak (%97.26) genelleme yeteneğini kaybetmiştir. En yüksek doğrulama başarımını $C = 0.10$ vermiştir.*

### B. 99 Held-Out Test Örneğinde 3 Yönlü Karşılaştırma

| Metrik | (A) Temel 3 Sınıflı ViT | (B) Baseline Regional Karma v2 | (C) Öğrenilmiş 4 Sınıflı Başlık ($C=0.10$) |
| :--- | :---: | :---: | :---: |
| **Macro-F1** | 0.2962 | **0.3723** | 0.2459 |
| **Dengeli Doğruluk** | 0.3800 | **0.4055** | 0.2425 |
| **Yanıtlanan Doğruluk** | 0.3838 | **0.4124** | 0.2424 |
| **Tüm Örnekler Doğruluğu** | 0.3838 | **0.4040** | 0.2424 |
| **Kuru (Dry) F1** | 0.2564 | **0.2857** | 0.2667 |
| **Normal F1** | 0.3830 | **0.4186** | 0.2857 |
| **Yağlı (Oily) F1** | 0.5455 | **0.5946** | 0.1455 |
| **Karma (Combination) F1** | 0.0000 (tahmin yok) | 0.1905 | **0.2857** |

### C. 4x4 Karmaşıklık Matrisleri (Held-out Test - 99 Örnek)

#### (A) Temel 3 Sınıflı ViT:
```
              Pred Dry   Pred Normal   Pred Oily   Pred Karma
True Dry          5           5           15            0
True Normal       2           9           14            0
True Oily         1           0           24            0
True Karma        6           8           10            0
```
*Gözlem: 3 sınıflı model aşırı derecede yağlı (oily) sınıfına kaymaktadır (99 örnekten 63'üne yağlı demiştir).*

#### (B) Baseline Regional Karma v2:
```
              Pred Dry   Pred Normal   Pred Oily   Pred Karma
True Dry          5           4            9            7
True Normal       1           9            8            7
True Oily         1           0           22            2
True Karma        3           5           10            4
```
*Gözlem: Fotometrik ölü bölge kuralı, T-bölgesi ve yanak parıltı farkını kullanarak aşırı yağlı tahminini 63'ten 49'a düşürmüş; Kuru kesinliğini %35.7'den %50.0'a, Normal kesinliğini %40.9'dan %50.0'a yükseltmiştir.*

#### (C) Öğrenilmiş 4 Sınıflı Başlık:
```
              Pred Dry   Pred Normal   Pred Oily   Pred Karma
True Dry          6          10            6            3
True Normal       5           8            9            3
True Oily         4          11            4            6
True Karma        5           2           11            6
```
*Gözlem: 4 sınıflı doğrusal başlık sınıfları ayıramamış; gerçek yağlı örneklerin sadece 4'ünü bulup 11'ine normal demiştir. Toplam doğruluk %24.24 ile 4 sınıflı rastgele tahmin (%25) seviyesindedir.*

---

## 5. Karma Güven Skoru ve Belirsizlik Analizi

1. **Karma v2 Destek Endeksi:**
   - Karma kuralında hesaplanan formül:
     $$\text{Support} = \text{clip}(p_{\text{oil}} \times 0.40 + \text{contrast} \times 0.35 + \text{matte} \times 0.25, 0.40, 0.88)$$
   - Bu formül bir sınıf olasılığı değil, el ile tasarlanmış bir **mekânsal destek göstergesidir**.
   - Ürün sözleşmesinde artık `confidence: None` dönülmekte; destek değeri `regionalDivergence.heuristicSupport` olarak raporlanmaktadır.
2. **4 Sınıflı Başlık Softmax Çıktısı:**
   - Doğrusal başlığın ürettiği $\text{softmax}(\mathbf{W}\mathbf{z} + \mathbf{b})$ değerleri kalibre edilmemiştir ve etiket gürültüsünden ötürü yüksek belirsizlik içermektedir.

---

## 6. Doğrulama ve Birim Testleri

Aşağıdaki birim testleri `pytest tests/unit/test_skin_type_local.py -v` ile %100 başarılı şekilde geçmiştir:
- `test_manifest_pins_glamour_vit`: Aday dürüstlük alanları (`accepted: false`, `candidateAccepted: true`).
- `test_onnx_file_integrity`: Dosya boyutu ve SHA-256 bütünlüğü.
- `test_local_sessions_load_offline`: Ürün modunda (`allow_candidates=False`) aday modelin yüklenmediği; aday modunda (`allow_candidates=True`) adayın yüklendiği ve `acne`/`bags` görevlerinin asla açılmadığı.
- `test_numerical_parity_onnx_vs_pytorch`: Gerçek yüz kırpmasında logit farkı $< 10^{-4}$ ($7.15 \times 10^{-7}$).
- `test_separate_anatomical_cheek_masks_and_hole_exclusions`: Yanakların anatomik ayrımı ve deliklerin çıkarılması.
- `test_insufficient_visible_area_rejection`: Yetersiz yüz alanında güvenli ret.
- `test_skin_only_highlight_clipping_gate`: Cilt üstü parlamanın tespiti ve arka planın dışlanması.
- `test_regional_combination_deadband_and_decisions`: $\ge 0.40$ ölü bölge kuralı ve uncalibrated güven (`confidence is None`, `heuristicSupport` mevcut).
- `test_offline_infer_with_blocked_sockets`: Soket engelli ortamda ürün ve aday yollarının tam çevrimdışı doğrulanması.
- `test_end_to_end_receipt_contract`: Makbuz sözleşmesi uyumu.

---

## 7. Teslim Edilen Dosyalar ve Taahhütler

1. `services/core-api/skin_models.py`:
   - `load(allow_candidates=False)` ve `infer(..., allow_candidates=False)` ürün/aday ayrımı.
   - Karma için `final_conf = None` ve `heuristicSupport` / `ruleSupport` aktarımı.
2. `services/core-api/appearance_analysis.py`:
   - `allowCandidates` parametresinin güvenli iletimi.
3. `scripts/run_skin_type_4class_head_experiment.py`:
   - 4 sınıflı başlık deneyi, öznitelik önbellekleme ve 3 yönlü değerlendirme scripti.
4. `tests/unit/test_skin_type_local.py`:
   - Ürün yolu izolasyonu ve uncalibrated Karma güven testleri.
5. `audit-results/skin-type-head-experiment-20261012/receipt.json`:
   - 99 örnekli test, karmaşıklık matrisleri, metrikler, başlık katsayıları ve hata galerisi içeren denetim makbuzu.
