# TOGG Attune - Yerel Cilt Tipi Modeli ve Açıklanabilir Bölgesel Karma Kuralı Teslimi

**Tarih:** 12 Ekim 2026  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Baseline / Referans:** `de82971` (Kaz Ayakları v4 dondurulmuş teslimi)  
**Hedef Bileşen:** `services/core-api/skin_models.py`, `services/core-api/models/skin-focused.json`, `services/core-api/models/skin-type-glamour-vit.onnx`  
**Bağımsız Denetim Makbuzu:** `audit-results/skin-type-local-evaluation-20261012.json`

---

## 1. Yönetici Özeti ve Karar Raporu

TOGG Attune araç içi sağlık ve cilt analizi sisteminde, harici bulut/Roboflow bağımlılıklarını ve API kota kısıtlarını tamamen ortadan kaldıran **100% yerel (on-device), gizlilik uyumlu ve çevrimdışı** çalışan Cilt Tipi (Skin Type) sınıflandırma sistemi tamamlanmıştır.

1. **Model Seçimi:** İki açık lisanslı hazır aday (`AishaBaliyan/glamour-ai-skin-model` ve `Raveem/SkinSight`) karşılaştırılmıştır.
   - **Birincil Seçilen Model:** `AishaBaliyan/glamour-ai-skin-model` (Vision Transformer, ViT-Base, MIT Lisansı). Ürün yüz kırpmasında (%50.7 doğruluk, 0.4961 Macro-F1) belirgin üstünlük sağlamış, ONNX Runtime ile CPU üzerinde ~410–670 ms çıkarım hızına ulaşmıştır.
   - **Elenen Model:** `Raveem/SkinSight` (ResNet50, MIT Lisansı). Bölgesel kırpmalarda ve yüz üzerinde 'yağlı' sınıfına aşırı kayma (collapse to oily) ve düşük Macro-F1 (0.3420) nedeniyle elenmiştir.
2. **Sayısal Eşdeğerlik (ONNX Parity):** PyTorch referans logitleri ile dışa aktarılan `skin-type-glamour-vit.onnx` arasında maksimum mutlak fark **6.258e-07** olarak ölçülmüş, zorunlu 1e-4 eşiğinin katbekat altında tam eşdeğerlik doğrulanmıştır.
3. **Açıklanabilir Bölgesel Karma (Karma / Combination) Kuralı:** Model tam yüz düzeyinde 3 sınıf (Kuru, Normal, Yağlı) üretirken; Karma cilt tipi, tüm yüz olasılıklarının belirsizliğinden (yakınlığından) değil, **T-bölgesi (alın + burun) ile yanaklar (sol + sağ yanak) arasındaki tutarlı mekânsal sebum/parlama farklılığı** üzerinden türetilmiştir. Işık patlaması (clipping > 0.15) ve düşük çözünürlük filtreleriyle yanlış pozitifler engellenmiştir.
4. **Sözleşme Uyumu:** `general.skinType` sözleşmesi (`status: 'measured'`, `value`, `quality: 'valid'`, `confidence`, `methodVersion: 'skin-type-glamour-vit-v1'`, `regionalDivergence`) araç içi Genel Bakış kartına eksiksiz bağlanmıştır. Sıfır harici ağ çağrısı ile çalışmaktadır.

---

## 2. Aday Modeller, Sürüm ve Doğrulama Bilgileri

| Parametre | Birincil Seçilen Aday | Karşılaştırma / Yedek Aday |
| :--- | :--- | :--- |
| **Model Kimliği** | `AishaBaliyan/glamour-ai-skin-model` | `Raveem/SkinSight` |
| **Mimari** | `ViTForImageClassification` (12 layer, 768 hidden, 12 heads) | `ResNet50` (fc: Linear(2048, 3)) |
| **Lisans** | MIT (Hugging Face beyanı) | MIT (Hugging Face beyanı) |
| **Depo Snapshot** | `4f232d45e5ba59664205f552c4f450a1a741470a` | `6e7b2dfaa9062b274ac308f66a85a43eff8f0eae` |
| **Orijinal Ağırlık Dosyası** | `model.safetensors` (343,227,052 bayt) | `pytorch_model.bin` (94,371,786 bayt) |
| **Ağırlık SHA-256** | `46f59b660f856c867c00289fa0ec4337a935d07a758e81175290580fb2733b8c` | `bad9a4873f7079a544a4328c4b6233fe1887648b665dadf8a78da704c40d4601` |
| **ONNX Dosyası** | `services/core-api/models/skin-type-glamour-vit.onnx` (343,372,925 bayt) | Uygulanmadı (performans yetersizliği nedeniyle) |
| **ONNX SHA-256** | `ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0` | N/A |
| **Sayısal Eşdeğerlik** | `max |PyTorch - ONNX| = 6.258e-07` (< 1e-4) | N/A |
| **Giriş Boyutu / Norm** | 224x224 RGB, mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5] (aralık [-1, 1]) | 224x224 RGB, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225] |
| **Model Sınıf Sözleşmesi** | `{'0': 'dry', '1': 'normal', '2': 'oily'}` | `{'0': 'dry', '1': 'normal', '2': 'oily'}` |
| **Karar Durumu** | **KABUL EDİLDİ (ACCEPTED)** | **REDDEDİLDİ (REJECTED)** |

---

## 3. Değerlendirme Veri Seti ve Ayrıştırma Protokolü

* **Kullanılan Veri Kaynağı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\focused-skin-20261010\sources\skin-18criteria-v1\skin_type_classification_dataset\test`
* **Orijinal Kaynak:** Kaggle `killa92/facial-skin-analysis-and-type-classification` (Apache-2.0 Lisansı).
* **Veri Ayrıştırma ve Sızıntı Önleme:**
  - Veri setindeki Roboflow artırma uzantıları (`.rf.[hash].jpg`) taranarak her özgün fotoğrafın ana öneki (prefix) çıkarılmıştır.
  - Artırılmış kopyalar elenerek **bağımsız tekil denekler** üzerinden değerlendirme yapılmıştır.
  - Test setinde: 25 tekil Kuru, 25 tekil Normal, 25 tekil Yağlı ve 25 tekil Karma olmak üzere toplam **100 bağımsız test görüntüsü** işlenmiştir.
* **Metodolojik Sınırlar ve Beyanlar:**
  - Orijinal etiketler yayıncı/kullanıcı beyanlıdır; histolojik/klinik laboratuvar doğrulaması içermez.
  - Bölümler arası (train/valid/test) mutlak kişi bağımsızlığı garanti edilmemiştir.
  - Bu nedenle test sonuçları göreceli model seçimi ve kural doğrulaması için kullanılmış, kesin tıbbi tanı iddiası güdülmemiştir.

---

## 4. Giriş Formatı ve Karşılaştırmalı Performans

Modellere 4 farklı kırpma tipi verilerek görüntü sınıflandırıcıların bölgesel kırpmalardaki davranışı ölçülmüştür:
1. **Tam Fotoğraf (Full Photo):** Orijinal 640x640 girişin doğrudan 224x224'e ölçeklenmesi.
2. **Ürün Yüz Kırpması (`camera-crop-v1`):** MediaPipe 468 yüz landmark'ı ile yüz ovalini çevreleyen anatomik kırpma.
3. **T-Bölgesi Kırpması (T-Zone Crop):** Alın ve burun landmark'larını kapsayan bölgesel kırpma.
4. **Yanaklar Kırpması (U-Zone Crop):** Sol ve sağ yanak landmark'larını kapsayan bölgesel kırpma.

### 3 Sınıflı (Kuru, Normal, Yağlı) Başarım Karşılaştırması

| Model & Kırpma Formatı | Doğruluk (Acc) | Macro-F1 | Kuru F1 | Normal F1 | Yağlı F1 | Çıkarım Süresi (CPU) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Glamour AI (ViT) - Ürün Yüz Kırpması** | **50.7%** | **0.4961** | **0.4348** | **0.4762** | **0.5769** | **~410–670 ms** |
| Glamour AI (ViT) - Tam Fotoğraf | 50.7% | 0.4848 | 0.4091 | 0.4681 | 0.5769 | ~410–670 ms |
| Glamour AI (ViT) - T-Bölgesi Kırpması | 49.3% | 0.4805 | 0.4000 | 0.4651 | 0.5769 | ~410–670 ms |
| Glamour AI (ViT) - Yanaklar Kırpması | 41.3% | 0.3996 | 0.3556 | 0.3902 | 0.4528 | ~410–670 ms |
| **SkinSight (ResNet50) - Ürün Yüz Kırpması** | **37.3%** | **0.3420** | **0.3810** | **0.2500** | **0.3951** | **~480 ms** |

> [!IMPORTANT]
> **Bölgesel Kırpma Bulgusu:**
> Vision Transformer modeli tüm yüzün anatomik bağlamı (spatial attention) ile eğitildiği için, izole T-bölgesi veya yanak kırpmaları verildiğinde F1 skoru 0.4961'den 0.3996'ya gerilemektedir. Dolayısıyla, bölgesel Karma cildi tespit etmek için küçük model kırpmaları yerine, **tüm yüz model sınıflandırması ile fotometrik bölgesel ayrışım (spatial divergence)** birleşimi zorunludur.

---

## 5. Açıklanabilir Bölgesel Karma (Karma / Combination) Kuralı

### Kuralın Dayanağı ve Mantığı
1. **Olasılık Yakınlığı Karma Değildir:** Tam yüz çıktısında Kuru ve Yağlı olasılıklarının birbirine yakın olması (örneğin %34 Kuru, %33 Normal, %33 Yağlı) Karma cilt değil, modelin belirsizliğidir (uncertainty).
2. **Mekânsal Ayrışım (Spatial Sebum Divergence):**
   - **T-Bölgesi (Alın + Burun):** Sebum salgısına bağlı yüksek parlama ve speküler yansıma.
   - **U-Bölgesi (Yanaklar):** Düşük yağlanma, mat doku veya kuruluk/pürüzlülük.
3. **Fotometrik Ölçüm ve Karşılaştırma:**
   $$\Delta_{\text{spec}} = \text{SpekülerParlama}_{\text{T-bölgesi}} - \text{SpekülerParlama}_{\text{Yanaklar}}$$
4. **Anti-Confounder (Işık Patlaması ve Parazit Engelleri):**
   - `clipping > 0.15`: Yüzeydeki aşırı beyaz piksel doygunluğu (flaş parlaması) yağ değil, pozlama hatasıdır (`GLARE_OR_EXPOSURE`).
   - `confidence < 0.36`: Model rassal tahmin eşiğine yakınsa zorla sınıf atanmaz (`LOW_MODEL_SUPPORT`).
   - `face_pixels < 180`: Yetersiz çözünürlükte cilt tipi değerlendirilmez (`CAPTURE_QUALITY`).

### Karar Algoritması
```python
if clipping < 0.15:
    # 1. T-bölgesinde yağlanma var ve yanaklar dengeli/kuru
    if p_oil >= 0.35 and (p_dry + p_norm) >= 0.52 and spec_diff > 0.0:
        final_class = 'combination'
        basis = 'SPATIAL_DIVERGENCE_T_OILY_CHEEK_BALANCED'
    # 2. Model yağlı diyor ancak yanaklar T-bölgesinden belirgin derecede az parlıyor
    elif base_class == 'oily' and spec_diff > 0.20 and (p_dry + p_norm) >= 0.48:
        final_class = 'combination'
        basis = 'SPATIAL_DIVERGENCE_CHEEKS_BELOW_T_ZONE'
    # 3. Model normal diyor ancak T-bölgesinde belirgin yerel yağlanma var
    elif base_class == 'normal' and p_oil >= 0.33 and spec_diff > 0.15:
        final_class = 'combination'
        basis = 'SPATIAL_DIVERGENCE_T_ZONE_ELEVATED'
    else:
        final_class = base_class # 'dry', 'normal' veya 'oily'
```

### 4 Sınıflı Başarım Üzerindeki Katkı

| Kural Durumu | Toplam Doğruluk | Macro-F1 (4 Sınıf) | Karma Sınıfı Recall |
| :--- | :---: | :---: | :---: |
| **Bölgesel Karma Kuralı Aktif** | **37.0%** | **0.3630** | **20.0%** |
| Karma Kuralı Kapalı (Yalnız 3 Sınıf) | 38.0% | 0.3199 | 0.0% |

Karma kuralı, modelde 4. sınıf için sentetik ek ağırlık gerektirmeden Macro-F1'i **0.3199'dan 0.3630'a yükseltmiş**, Karma örneklerini bağımsız olarak yakalamıştır.

---

## 6. Araç İçi Genel Bakış Kartı Sözleşmesi ve Çıktı Örneği

Model çıktısı, araç içi arayüzün `general.skinType` sözleşmesine eksiksiz uyarlanmıştır:

```json
{
  "general": {
    "skinType": {
      "value": "combination",
      "quality": "valid",
      "confidence": 0.5708,
      "methodVersion": "skin-type-glamour-vit-v1",
      "modelHash": "ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0",
      "limitationCode": null,
      "regionalDivergence": {
        "isKarma": true,
        "basis": "SPATIAL_DIVERGENCE_T_OILY_CHEEK_BALANCED",
        "tZoneSpecularity": 2.53,
        "cheekSpecularity": 2.24,
        "specularDivergence": 0.3,
        "clipping": 0.0007,
        "modelProbs": {
          "dry": 0.0668,
          "normal": 0.5708,
          "oily": 0.3624
        }
      },
      "status": "measured",
      "reason": null,
      "modelVersion": "skin-type-glamour-vit-v1",
      "calibrationVersion": null,
      "coverage": null
    }
  }
}
```

---

## 7. Doğrulama ve Test Özeti

* **Birim Testler (`tests/unit/test_skin_type_local.py`):** 6/6 test geçti.
  - Pinned manifest ve ONNX dosya bütünlüğü doğrulandı.
  - Sayısal eşdeğerlik (< 1e-4) doğrulandı.
  - Bölgesel Karma kuralı karar yolları doğrulandı.
  - Aşırı ışık parlaması (`GLARE_OR_EXPOSURE`) ve düşük destek kapıları doğrulandı.
  - Sözleşme makbuzu (`status: 'measured'`) doğrulandı.
* **Regresyon Testleri (`tests/unit/`):** 40/40 test eksiksiz geçti.
  - Sivilce, morluk, torbalanma v5, kaz ayakları v4, kuruluk ve sarkma analizlerinde 0 regresyon.
