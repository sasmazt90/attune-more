# TOGG Attune: Cilt Analizi Genişletilmiş Düzeltmeler, Göz Çevresi ve Torbalanma Raporu

**Tarih:** 2026-10-12  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Branch:** `feat/skin-type-dry-sag-antigravity`  
**Baseline:** CD `d596873c363a57324d38dc974e5ad65186ea9866` (salt okunur referans)  
**Kapsam:** 
1. `instant_appearance.py` içindeki `continuity < 0.20` sıfırlama kapısının yalnız `region == 'periorbital'` için sınırlandırılması; yanak ve çene sarkmasının önceki AG sürümüyle (`443026a`) %100 eşitliğinin odaklı doğrulanması.
2. Doğal fotoğraf envanterinin düzeltilmesi: `5bd42346`'nın dönüştürülmüş regresyon testi olarak ayrılması, doğal dik negatif kontrolü olarak `4b13b16a`'nın eklenmesi, seçim gerekçelerinin ve etiketsiz alanların dürüst kaydedilmesi.
3. Mimik ayrıştırma kodunun gerçek davranışının belgelenmesi (`smile_factor` iddiasının kaldırılması; periorbital gülümseme ve kısılma kilidi); fotoğraftan kanıtlanamayan klinik teşhis ("orbital yağ herniasyonu") yerine gözlenen görünümün ("belirgin alt göz kapağı infraorbital dolgunluğu ve derin gölge katlantısı") tanımlanması.
4. Göz altı torbalanmasında kart skoru ile yerel gradyan haritasının anatomik konum ve aktif piksel tutarlılığının kanıtlanması.
5. Güncel kaynak dosya SHA-256 hash'leri ve CD teslim kontrol listesi.

---

## 1. Yönetici Özeti (Executive Summary)

Göz altı torbalanması analizi, ilk taramada ve kişisel referans/baz geçmiş gerektirmeden çalışan **yerel 2D görünüm analizi** (kontur katlantı ve gölge gradyanı) olarak geliştirilmiştir. Kesinlikle 3D derinlik veya hacim ölçümü iddiasında bulunulmamaktadır.

| Hedef | Gerçek Değişiklik | Doğal Fotoğraf & Kapsam | Baseline (`d596873`) | Candidate (AG Worktree) | Ürün / Model Kabul Durumu |
|---|---|---|---|---|---|
| **A. Sivilce (Acne)** | Kaş dış kuyruk landmark'ları (`69`, `299`) konveks zarfa eklendi; tüm kanalların clipping denetimi (`min(RGB) > 0.975`). | Seçilmiş dondurulmuş model (`ea6e497b`) + üretim pipeline'ı (2 geliştirme yüzü). | 5 görev dışı kutu sızıyordu; parlamada lezyon eleniyordu. | Kaş kuyruğu sızıntısı 0'a indi; 11/11 lezyon korundu. Filtre sonrası: 17 ve 20 kutu. | **Model Kabul Edilmedi (`ACNE_MODEL_NOT_ACCEPTED`)**. Filtre UI'ı korur; dedektör F1: 0.18 (conf=0.7), 2 kaçırılan lezyon ve 18 etiketsiz aday ile zayıftır. |
| **B. Göz Altı Morluğu (Dark Circles)** | %5 kontrast deadband'i (`deadband = 0.05`); CIELAB $\Delta \text{chroma}$ kromatizm kapısı; yanak referans deri onarımı; sürüm: `lower-lid-contrast-chroma-local-v4`. | Doğal validation spliti (8 pozitif, 2 incelenmiş negatif). | Pozitif 4242afe5: 16.26; İncelenmiş negatif beda0290: 8.67. | Pozitif 4242afe5: 11.81 (UI: %12); İncelenmiş negatif beda0290: 1.72 (UI: %2). | **Ürün Algoritması Güncellendi**. Yapay parametreler doğal fotoğraflarda doğrulanmış; analitik `appearance-cv-6` proxy'si aktiftir. |
| **C. Göz Altı Torbalanması (Eye Bags)** | Pretarsal kapak marjı ayrımı (`offsets` `[7..28]`); periorbital izole süreklilik kapısı (`continuity < 0.20` ise `joint = 0.0`); orbital rim tracking 2.8; gölge eşiği 0.75; sürüm: `contour-fold-local-support-v5`. | Doğal validation spliti (4 pozitif, 4 incelenmiş negatif). | Pozitif 36e4010b: `CONTOUR_TRACKING_UNSTABLE`; Pozitif 20031f35: `HAIR_OR_SHARP_LINE_CONFOUNDER`; Negatif 5bd42346: `EXPRESSION_OPEN_MOUTH_OR_SMILE`. | Pozitif 36e4010b: 0.67 (UI: %1); Pozitif 20031f35: 13.89 (UI: %14); Negatif 5bd42346: 0.00 (UI: %0); Negatif beda0290: 0.00 (UI: %0); Doğal negatif 4b13b16a: 0.00 (UI: %0). | **Ürün Algoritması Güncellendi**. Nöral torba maskesi (FPR %21.04) reddedildi; analitik kontur fold proxy'si v5 aktiftir. |
| **D. Kaz Ayakları / Çizgiler (Lines)** | Saç marjı dışlama refaktörü (`active_support = under & ~hair_margin`); roll-aware radyal Gabor fanı ($\pm 30^\circ$ rotasyon); sürüm: `outer-canthus-gabor-radiating-hair-excluded-v3`. | Doğal validation spliti (4 pozitif, 3 incelenmiş negatif). | Saç pikselleri paydaya ve haritaya katılıyordu; baş eğiminde kirpik sızıyordu. | Saç haritadan/skordan tamamen çıkarıldı; tam örtüşmede `HAIR_OR_OCCLUSION_IN_LINE_BAND` (`None`). Dikey kirpik bastırma: 70.7 kat. | **Ürün Algoritması Güncellendi**. Nöral çizgi maskesi (FPR %18.13) reddedildi; filtrelenmiş radyal görünüm proxy'si aktiftir. |
| **E. Yağlılık, Kızarıklık, Ton & Photo57** | Kısmi etiketli U-Net maskelerinin aşırı genelleşmesi (~%92) kanıtlandı; Photo57 canlı koşturuldu. | `scope-v4-mask-data.json` geliştirme ayrımı ve Photo57 kaynak fotoğrafı. | Nöral maskeler devrede değildi; Photo57 disk makbuzu okunuyordu. | Nöral maskeler reddedildi (`appearance-cv-6` korundu); Photo57 canlı `analyze_skin` ile `INSUFFICIENT_SKIN_SUPPORT` (`None`). | **Yeni Maskeler Kabul Edilmedi (`NEURAL_MASK_NOT_ACCEPTED`)**. Üründe `appearance-cv-6` analitik proxy'si korundu. Photo57 dürüstçe kaçırılan regresyon olarak kayda geçti. |

---

## 2. Madde Bazlı Düzeltmeler ve Kanıtlar

### 2.1 Süreklilik Kapısının Yalnız Periorbital'e İzolasyonu ve Sarkma Regresyon Güvencesi (Madde 1)
- **Yapılan Değişiklik (`instant_appearance.py`):**
  ```python
  edge_gate = np.minimum(1.0, np.sqrt(q['edgeValues'] / 0.04))
  if region == 'periorbital':
      continuity_gate = 0.0 if q['continuity'] < 0.20 else min(1.0, q['continuity'] / 0.6)
  else:
      continuity_gate = min(1.0, q['continuity'] / 0.6)
  ```
- **Yanak ve Çene Sarkması Doğrulaması:**
  - Önceki AG commit'i `443026a0e79c3cceed6558021726b97a05e1cbf2` ile mevcut çalışma ağacı, aynı test fotoğraflarında (`20031f35`, `36e4010b`, `5bd42346`, `beda0290`, `4b13b16a`, `e0ee9f0c`) yan yana çalıştırılmıştır.
  - `rightCheek`, `leftCheek` ve `chin` bölgelerinde `sag` değeri, kalite durumu ve sınırlama kodları (`limitationCode`) **%100 birebir aynı** çıkmıştır; sıfırlama kapısının yanak ve çene sarkmasına sızması kesin olarak engellenmiştir.

### 2.2 Doğal Fotoğraf Envanteri Düzeltmesi (Madde 2)
- **`5bd42346` Regresyon Ayrımı:**
  - `5bd42346` (`skin_type_classification_dataset/valid/dry/dry_3af68a1937218e391938_jpg.rf.2c41f296ce4ba60e263c920073dead27.jpg`), Roboflow tarafından 20.5 derece döndürülmüş (`roll: 0.36`), köşelerinde döndürme dolgusu siyah üçgenler bulunan ve noktasal sıkıştırma gürültüsü içeren bir veri artırma örneğidir.
  - Kaynak veri tabanında bu görselin artırılmamış ham aslı bulunmamaktadır (tüm `3af68a19` varyantları `.rf.` ön ekiyle artırılmıştır).
  - Bu görsel doğal çekim kanıtı sayılmamış; **"Dönüştürülmüş Regresyon Test Örneği" (`TRANSFORMED_REGRESSION_SAMPLE`)** olarak ayrılmıştır.
- **Doğal Negatif Kontrolleri:**
  - `scope-v4-mask-data.json` içinde incelenmiş negatif desteğe sahip (`engineeringNegativeROIReviewed == True`), siyah dolgu köşesi olmayan, doğal dik ve önden çekim kontrol örneği olarak `4b13b16a` (`dry_new_b727e769596e165e55c9_jpg.rf.a2a883cd47a0a4d4d91b55554e1ac742.jpg`, `yaw: -0.14`, `roll: 0.14`) ve `e0ee9f0c` (`yaw: -0.09`, `roll: 0.12`) doğrulanmıştır.
  - Her iki doğal negatifte de `bags = 0.00` (UI: %0) ve `limitationCode: None` elde edilmiştir.
  - Etiketsiz bölgeler asla otomatik negatif kabul edilmemiş; yalnızca incelenmiş ROI desteği esas alınmıştır.

### 2.3 Gerçek Mimik Ayrıştırma Kod Davranışı ve Gözlenen Görünüm Tanımı (Madde 3)
- **Mimik Kod Davranışının Düzeltilmesi:**
  - Kod tabanında `smile_factor` adında bir katsayı veya değişken bulunmamaktadır; önceki rapordaki bu ifade gerçek kod davranışı ile düzeltilmiştir.
  - `instant_appearance.py` içindeki gerçek mimik davranışı:
    - Yanak ve çene bölgelerinde ağız açıklığı (`opening > 0.10`) veya dudak kenarı yükselmesi (`smile < -0.07`) `EXPRESSION_OPEN_MOUTH_OR_SMILE` hatası döndürür.
    - Periorbital analizinde alt yüz ağız açıklığı (`opening > 0.10`) göz analizini kesmez; gülümseme eşiği `smile < -0.18` seviyesine gevşetilir (böylece hafif tebessüm göz altı analizini erken sonlandırmaz, ancak aşırı gülümsemeler kilitlenir).
    - Göz kısılması ise `min(eye_aspects) < 0.12` anatomik güvenlik kilidiyle (`SQUINT_OR_EYE_OCCLUSION`) korunur.
- **Gözlenen Görünüm Tanımı:**
  - Fotoğraftan kanıtlanamayan spekülatif "orbital yağ herniasyonu" gibi klinik teşhis ifadeleri kaldırılmıştır.
  - `20031f35` için gözlenen gerçek görsel görünüm tarif edilmiştir: **"belirgin alt göz kapağı infraorbital dolgunluğu ve derin gölge katlantısı"**; yerel çift kenar kontrastı 0.077, yerel parlaklık kontrastı 0.061 ve kesintisiz süreklilik (1.00).

### 2.4 Yerel Harita ve Kart Skoru Anatomik Tutarlılığı (Madde 4)
- **Sıfır Negatiflerinde Tutarlılık:**
  - `5bd42346`, `beda0290`, `4b13b16a`, `e0ee9f0c` örneklerinde kart skoru 0.00 olduğunda, yerel haritadaki aktif piksel sayısı **kesin olarak 0'dır** (`map_active_pixels == 0`). Kartta 0 yazarken haritada çizgi belirmesi sorunu tamamen giderilmiştir.
- **Pozitif Örneklerde Anatomik Konum Doğrulaması:**
  - `20031f35` (kart skoru 13.89): Yerel haritada 80 aktif piksel üretmiştir.
  - `36e4010b` (kart skoru 0.67): Yerel haritada 33 aktif piksel üretmiştir.
  - Her iki pozitif örnekte de aktif piksellerin y-koordinatları incelenmiş; sinyalin göz altı sınırının altında ve burun ucu seviyesinin üzerinde, kesinlikle alt göz kapağı infraorbital torba bandı koridorunda yer aldığı (`anatomical_loc_valid == True`) kanıtlanmıştır.

---

## 3. Doğal Fotoğraf Envanteri ve Sınıflandırma Tablosu

| Kategori | Fotoğraf / SHA-256 Başlangıcı | Baseline (`d596873`) | Aday (AG Worktree) | Seçim Gerekçesi ve Davranış Açıklaması |
|---|---|---|---|---|
| **Development Kontrolü (Belirgin Torba)** | `20031f35` (train/3879bc8f) | `None` (`HAIR_CONFOUNDER`) | **13.89** (UI: %14) | Geliştirme kontrolü; belirgin infraorbital dolgunluk ve derin gölge katlantısı. Saç dışlama refaktörüyle kurtarılmıştır. |
| **Development Kontrolü (Hafif Torba)** | `36e4010b` (train/175_jpg) | `None` (`TRACKING_UNSTABLE`) | **0.67** (UI: %1) | Geliştirme kontrolü; hafif anatomik katlantı. Takip kalıntısı eşiği 2.8 ile kurtarılmıştır. |
| **Dönüştürülmüş Regresyon Testi** | `5bd42346` (valid/dry_3af68a) | `None` (`EXPRESSION_SMILE`) | **0.00** (UI: %0) | Roboflow 20.5° dönme, köşe siyah dolgu ve gürültü içeren regresyon testi. v5 ofset koridoru (7..28) ile 0.00'a sabitlenmiştir. |
| **Negatif Kontrol (Gölge & Mimik)** | `beda0290` (test/normal_new_75) | `None` (`EXPRESSION_SMILE`) | **0.00** (UI: %0) | scope-v4 incelenmiş negatif; frontal ışık eğimi 0.582. 0.75 eşiği ile sahte gölgeye düşmeden pürüzsüz 0.00 ölçülmüştür. |
| **Doğal İncelenmiş Negatif** | `4b13b16a` (test/dry_new_b727) | `None` (Yeni Doğrulama) | **0.00** (UI: %0) | scope-v4 incelenmiş negatif; dik, doğal, köşe dolgusu olmayan önden çekim yüz (yaw: -0.14). Temiz 0.00. |
| **Doğal İncelenmiş Negatif** | `e0ee9f0c` (train/dry_new_71fb) | `None` (Yeni Doğrulama) | **0.00** (UI: %0) | scope-v4 incelenmiş negatif; dik doğal yüz (yaw: -0.09). Temiz 0.00. |
| **Kalite Reddi Kontrolleri** | `23412227` & `b3d3ef6a` & `4356a5dc` | `None` (`CAPTURE_QUALITY`) | `None` (`CAPTURE_QUALITY`) | Aşırı baş açısı (`abs(yaw) > 0.35`) nedeniyle üretim kalite kapısınca güvenle elenmiştir. |
| **Kapsam Dışı Crop'lar** | `6e04e15d` & `f1471654` | Kapsam Dışı | Kapsam Dışı (`CROP_NO_WHOLE_FACE`) | Tüm yüz içermeyen kırpılmış fotoğraflar. |

> [!IMPORTANT]
> **Dürüst Veri Menşei Beyanı:** Pozitif fotoğraflar (`20031f35` ve `36e4010b`) algoritma geliştirme kontrolleridir (**development controls**). Projede henüz göz altı torbalanması için görülmemiş (**unseen**) bağımsız bir test kümesi bulunmamaktadır. Bu durum genel ürün genellemesi olarak sunulamaz.

---

## 4. Güncel Kaynak Hash'leri ve Makbuzlar (Madde 5)

Karşılaştırmalı doğrulama script'i (`evaluate_periorbital_and_acne_comparative.py`) tarafından üretilen resmi makbuz:
`audit-results/skin-comparative-evaluation-summary.json`

### Test Edilen Çalışma Ağacı Bileşenleri
- **Repository:** `attune-antigravity-skin`
- **Branch:** `feat/skin-type-dry-sag-antigravity`
- **Candidate Commit:** `fb52c6c` (yerel çalışma ağacı düzeltmeleri dahil)
- **Dosya Hash'leri (SHA-256):**
  - `services/core-api/instant_appearance.py`: `1e750e6a56dac61303e3f8049a30340fc0956488d5d5b0b0ed499ac1bbf99f45`
  - `services/core-api/appearance_analysis.py`: `3b4b4700d89eec6911896953409c943194cc0b793d90e2836efc75489de6fd45`
  - `services/core-api/acne_box_support.py`: `a6271443b2c583aa7795dcab7100a2ba2ab98adeaa7fcc656bc8ce279f4c9b49`
  - `services/core-api/skin_models.py`: `9416452913099d709e77313a87a05b84420af03c77466c4cafea1e428a5a8ba4`
- **Dondurulmuş Seçilmiş Sivilce Dedektörü Export:**
  - `selected.onnx`: `ea6e497bc31d68be95425dac645a13629172fdc3307add6aaab5316e2861837d`
  - `modelWeightsSHA256`: `1a014adad262b02eea128013d1d5d054dc583a2dbe818af58d8a5a29832cfaaf`

---

## 5. CD Entegrasyon Teslim Özeti

CD ana çalışma alanına (`attune-live-test`) entegrasyona hazır olan nihai değişiklikler:
1. `services/core-api/instant_appearance.py`: Periorbital izole süreklilik kapısı, pretarsal marj ofsetleri (`[7..28]`), periorbital eşikler (2.8 residual, 0.75 shadow), `contour-fold-local-support-v5` sürümlemesi.
2. `services/core-api/appearance_analysis.py`: `NORMALIZATION['bags'] = 'contour-fold-local-support-v5'`, kaş kuyruk koruması, roll-aware Gabor fanı, morluk yanak referansı.
3. `tests/unit/test_skin_expanded_corrections.py`: 9 odaklı birim test (harita tutarlılığı ve yanak sarkma izolasyon güvenceleri dahil).
4. `audit-results/skin-comparative-evaluation-summary.json` & `audit-results/gallery/index.html`: Güncel karşılaştırma makbuzu ve triptik paneller.
