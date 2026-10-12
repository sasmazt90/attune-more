# TOGG Attune - Yerel Cilt Tipi Modeli ve Açıklanabilir Bölgesel Karma Kuralı v2 Teslimi

**Tarih:** 12 Ekim 2026  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Baseline / Referans:** `de82971` (Kaz Ayakları v4 dondurulmuş teslimi)  
**Hedef Bileşen:** `services/core-api/skin_models.py`, `services/core-api/models/skin-focused.json`, `services/core-api/models/skin-type-glamour-vit.onnx`  
**Bağımsız Denetim Makbuzu:** `audit-results/skin-type-local-evaluation-20261012.json`

---

## 1. Yönetici Özeti ve Karar Raporu

TOGG Attune araç içi sağlık ve cilt analizi sisteminde, harici bulut/Roboflow bağımlılıklarını tamamen ortadan kaldıran, **100% yerel (on-device), gizlilik uyumlu ve çevrimdışı** çalışan Cilt Tipi (Skin Type) sınıflandırma ve Bölgesel Karma (Karma / Combination) analiz sistemi v2 sürümüne güncellenmiştir.

1. **Aday Modeli Doğrulama ve Sürüm Bütünlüğü:**
   - **Birincil Aday:** `AishaBaliyan/glamour-ai-skin-model` (Vision Transformer, ViT-Base, MIT Lisansı, snapshot `4f232d45e5ba59664205f552c4f450a1a741470a`).
   - Orijinal ağırlık dosyası `model.safetensors` SHA-256 (`46f59b660f856c867c00289fa0ec4337a935d07a758e81175290580fb2733b8c`) ve dışa aktarılan ONNX `skin-type-glamour-vit.onnx` SHA-256 (`ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0`) doğrulanmıştır.
   - Sayısal eşdeğerlik (PyTorch vs ONNX Runtime): Gerçek yüz kırpması üzerinde maksimum logit farkı **7.152557e-07** olup zorunlu `1e-4` sınırının altındadır.
   - **Elenen Model:** `Raveem/SkinSight` (ResNet50, MIT Lisansı), yüz üzerinde aşırı yağlı sınıfına kayma ve düşük doğruluk nedeniyle elenmiştir.
2. **Model Manifesti (`skin-focused.json`) Dürüstlüğü:**
   - Eski EfficientNet validasyon/test metrikleri tamamen temizlenmiş, ViT modelinin gerçek değerlendirme sonuçları işlenmiştir.
   - Kaggle kaynaklı veri setinin laboratuvar doğrulaması ve araç içi kamera alanı kanıtlanmadığı için `accepted`, `sourceQualityAccepted`, `sourceLabelProtocolVerified` ve `cameraDomainAccepted` alanları dürüstçe `false` bırakılmış; adayın hazır olduğunu belirtmek üzere `candidateAccepted: true` tanımlanmıştır.
3. **Tek Kaynaktan Paylaşılan Ön İşleme (`preprocess_vit_face`):**
   - PIL `Image.Resampling.BILINEAR`, (224, 224), `mean=[0.5, 0.5, 0.5]`, `std=[0.5, 0.5, 0.5]` dönüşümü tekil bir fonksiyonda toplanmış; `evaluate_skin_type_local.py` ve `skin_models.infer` aynı fonksiyonu kullanmaktadır.
   - Kızarıklık (`degrees`) ImageNet ön işlemesi (`photo_input`) korunmuştur.
4. **Anatomik Bölge Maskeleri ve Köprü Hatasının Giderilmesi:**
   - `build_anatomical_skin_masks`: Sol ve sağ yanak için ayrı kapalı poligonlar oluşturulmuştur. Yanakların burun veya ağız üzerinden birleşmesi (bridging) engellenmiştir.
   - Gözler, dudaklar, burun delikleri ve kaş delikleri anatomik olarak çıkarılmıştır.
   - Yetersiz yüz/yanak alanı durumunda `INSUFFICIENT_VISIBLE_AREA` ve `quality='insufficient'` döndürülmektedir.
   - Parlama/clipping kontrolü tüm görüntü arka planı yerine yalnız gözlenen cilt destek alanı üzerinde hesaplanmaktadır.
5. **Açıklanabilir Bölgesel Karma Kuralı v2 (Ölü Bölge ve Mekânsal Destek):**
   - Zayıf model belirsizliği artık Karma üretmemektedir.
   - Karma kararı için: $\Delta_{\text{spec}} \ge 0.40$ ölü bölge (deadband), T-bölgesinde belirgin parıltı ($t_{\text{spec}} \ge 1.80$) ve yanaklarda normal/mat destek ($u_{\text{spec}} < 4.00$) şartı aranmaktadır.
   - Karma güven skoru 3 sınıflı model olasılığından ayrılarak mekânsal kontrast ve matlık oranına göre açıklanabilir biçimde hesaplanmaktadır.
6. **Veri Seti Ayrıştırması ve Gerçek Zamanlı Değerlendirme:**
   - Geliştirme/Kalibrasyon Seti (100 test örneği, 25/sınıf) ve Bağımsız Holdout Doğrulama Seti (100 valid örneği, 25/sınıf; 113 sızıntı öneki dışındaki 569 geçerli önekten seçilmiş) değerlendirilmiştir.
   - Makbuzda tüm 200 örneğin detaylı kayıtları yer almaktadır.
   - Gerçek ölçülen CPU süreleri: PyTorch ortalama 1290.95 ms, ONNX Runtime ortalama 893.75 ms (1.44x hızlanma).
   - Ağ bağlantısı engellenmiş ortamda (offline) modelin ve kuralın çalıştığı doğrulanmıştır.

---

## 2. Aday Modeller, Sürüm ve Doğrulama Bilgileri

| Parametre | Birincil Seçilen ViT Adayı | Karşılaştırma / Yedek Aday |
| :--- | :--- | :--- |
| **Model Kimliği** | `AishaBaliyan/glamour-ai-skin-model` | `Raveem/SkinSight` |
| **Mimari** | `ViTForImageClassification` (12 layer, 768 hidden, 12 heads) | `ResNet50` (fc: Linear(2048, 3)) |
| **Lisans** | MIT (Hugging Face beyanı) | MIT (Hugging Face beyanı) |
| **Depo Snapshot** | `4f232d45e5ba59664205f552c4f450a1a741470a` | `6e7b2dfaa9062b274ac308f66a85a43eff8f0eae` |
| **Orijinal Ağırlık Dosyası** | `model.safetensors` (343,227,052 bayt) | `pytorch_model.bin` (94,371,786 bayt) |
| **Ağırlık SHA-256** | `46f59b660f856c867c00289fa0ec4337a935d07a758e81175290580fb2733b8c` | `bad9a4873f7079a544a4328c4b6233fe1887648b665dadf8a78da704c40d4601` |
| **ONNX Dosyası** | `services/core-api/models/skin-type-glamour-vit.onnx` (343,372,925 bayt) | N/A |
| **ONNX SHA-256** | `ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0` | N/A |
| **Sayısal Eşdeğerlik** | `max |PyTorch - ONNX| = 7.152557e-07` (< 1e-4) | N/A |
| **Ön İşleme Standardı** | 224x224 RGB, PIL BILINEAR, mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5] | 224x224 RGB, INTER_AREA, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225] |
| **Kabul Durumu** | `accepted: false`, `candidateAccepted: true` | `REJECTED` |

---

## 3. Veri Seti Ayrıştırması ve Sızıntı Analizi

Kaggle `killa92/facial-skin-analysis-and-type-classification` veri setinde yapılan detaylı incelemede:
- **Toplam Test Dosyası:** 409 (tekil ana önek: 372)
- **Toplam Valid Dosyası:** 812 (tekil ana önek: 682)
- **Bölümler Arası Sızıntı:** Test ve valid arasında **113 adet aynı ana görüntüye ait artırılmış kopyanın (leaking prefix)** bulunduğu tespit edilmiştir.
- **Sızıntısız Valid Önekleri:** Valid kümesinde test kümesinde hiç bulunmayan **569 adet bağımsız önek** mevcuttur.

Bu doğrultuda değerlendirme iki ayrı kümede yapılmıştır:
1. **Geliştirme / Kalibrasyon Kümesi (`test`):** 100 tekil örnek (25 Kuru, 25 Normal, 25 Yağlı, 25 Karma).
2. **Bağımsız Holdout Doğrulama Kümesi (`valid`):** 100 tekil örnek (25 Kuru, 25 Normal, 25 Yağlı, 25 Karma), **test kümesiyle %0 önek örtüşmesi** olacak şekilde 569 sızıntısız önek arasından seçilmiştir.

---

## 4. Gerçek Zamanlı Değerlendirme Sonuçları

`evaluate_skin_type_local.py` betiği doğrudan üretim kodundaki `skin_models.infer()` fonksiyonunu çağırarak sonuçları üretmiştir:

### A. Geliştirme / Kalibrasyon Kümesi (100 Örnek)
- **Kapsam Oranı (Coverage):** %72.0 (72 geçerli değerlendirme, 28 kalite/parlama/geometri reddi: 20 `GLARE_OR_EXPOSURE`, 6 `LANDMARKS_MISSING`, 2 `LOW_MODEL_SUPPORT`).
- **4 Sınıflı Doğruluk (Accuracy):** %40.28 | **Dengeli Doğruluk:** %38.79 | **Macro-F1:** 0.3751
  - **Kuru (Dry):** Precision: 0.222, Recall: 0.118, F1: 0.154 (destek: 17)
  - **Normal:** Precision: 0.632, Recall: 0.667, F1: 0.649 (destek: 18)
  - **Yağlı (Oily):** Precision: 0.393, Recall: 0.500, F1: 0.440 (destek: 22)
  - **Karma (Combination):** Precision: 0.250, Recall: 0.267, F1: 0.258 (destek: 15)
- **3 Sınıflı Temel Model (Kuru/Normal/Yağlı):** Macro-F1: 0.4782 | Dengeli Doğruluk: 0.4976

### B. Bağımsız Holdout Doğrulama Kümesi (100 Örnek)
- **Kapsam Oranı (Coverage):** %66.0 (66 geçerli değerlendirme, 34 ret: 25 `GLARE_OR_EXPOSURE`, 7 `LANDMARKS_MISSING`, 2 `LOW_MODEL_SUPPORT`).
- **4 Sınıflı Doğruluk (Accuracy):** %30.30 | **Dengeli Doğruluk:** %29.68 | **Macro-F1:** 0.2734
  - **Kuru (Dry):** Precision: 0.667, Recall: 0.250, F1: 0.364 (destek: 16)
  - **Normal:** Precision: 0.231, Recall: 0.214, F1: 0.222 (destek: 14)
  - **Yağlı (Oily):** Precision: 0.324, Recall: 0.667, F1: 0.436 (destek: 18)
  - **Karma (Combination):** Precision: 0.100, Recall: 0.056, F1: 0.071 (destek: 18)
- **3 Sınıflı Temel Model (Kuru/Normal/Yağlı):** Macro-F1: 0.3426 | Dengeli Doğruluk: 0.3801

---

## 5. Kaynak ve Performans Ölçümleri (Honest CPU Timings)

| Ölçüm Parametresi | PyTorch CPU (Referans) | ONNX Runtime CPU (Üretim) | Gerçek Oran / Değer |
| :--- | :---: | :---: | :---: |
| **Model Yükleme Süresi** | ~2252 ms | ~765 ms | 2.94x daha hızlı yükleme |
| **Soğuk Çıkarım (Cold ms)** | 2252.19 ms | 764.95 ms | 2.94x |
| **Sıcak Ortalama Çıkarım (Warm ms)** | 1290.95 ms (std: 303.04 ms) | 893.75 ms (std: 167.17 ms) | **1.44x gerçek hızlanma** |
| **Süreç Bellek Kullanımı (RSS)** | - | 1734.80 MB | Model yükleme delta: +678.52 MB |
| **Çevrimdışı Çalışma (Offline)** | Soket engelli ortamda test edildi | Soket engelli ortamda test edildi | **%100 Doğrulandı (0 ağ çağrısı)** |

---

## 6. Birim Testleri ve Sözleşme Uyumu

Aşağıdaki birim testleri `pytest tests/unit/test_skin_type_local.py -v` ile eksiksiz geçmiştir:
1. `test_manifest_pins_glamour_vit`: Aday dürüstlük alanları (`candidateAccepted: True`, `accepted: False`, `sourceQualityAccepted: False`).
2. `test_onnx_file_integrity`: 343,372,925 bayt ve doğru SHA-256.
3. `test_local_sessions_load_offline`: Çevrimdışı yükleme ve oturum sağlığı.
4. `test_numerical_parity_onnx_vs_pytorch`: Gerçek yüz kırpmasında logit farkı < 1e-4 (`7.15e-07`).
5. `test_separate_anatomical_cheek_masks_and_hole_exclusions`: Yanakların burun/ağız üzerinden köprülenmemesi ve deliklerin çıkarılması.
6. `test_insufficient_visible_area_rejection`: Yetersiz yüz alanında `INSUFFICIENT_VISIBLE_AREA` ve `quality='insufficient'`.
7. `test_skin_only_highlight_clipping_gate`: Beyaz arka planın reddedilmemesi, sadece ciltteki parlamanın `GLARE_OR_EXPOSURE` üretmesi.
8. `test_regional_combination_deadband_and_decisions`: $\ge 0.40$ ölü bölge kuralı ve açıklanabilir karma güven skoru.
9. `test_offline_infer_with_blocked_sockets`: `socket.socket.connect` engellendiğinde sorunsuz çıkarım.
10. `test_end_to_end_receipt_contract`: `attach_result_receipts` uyumu (`status: 'measured'`, `reason: None`).
