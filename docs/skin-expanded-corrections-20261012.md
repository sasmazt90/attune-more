# TOGG Attune: Cilt Analizi Genişletilmiş Düzeltmeler ve Doğrulama Raporu

**Tarih:** 2026-10-12  
**Çalışma Alanı:** `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-antigravity-skin`  
**Branch:** `feat/skin-type-dry-sag-antigravity`  
**Hedef Kapsam:** Beş başarısız cilt analizi adayında (A: Sivilce, B: Morluk, C: Torbalanma, D: Çizgiler/Kaz ayakları, E: Yağlılık/Kızarıklık/Ton) filtre ve analiz açıkları, doğal fotoğraf doğrulaması, canlı Photo57 regresyonu ve model kabul sınırlarının dürüst ayrımı.

---

## 1. Yönetici Özeti (Executive Summary)

Commit `ab02fcc` teslimindeki "tüm 5 hedef çözüldü / allTargetsVerified=true" genellemesi düzeltilmiş; birim kontrolleri, doğal fotoğraf ölçümleri, model başarısızlıkları ve ürün koruma katmanları birbirinden açıkça ayrılmıştır:

| Hedef | Gerçek Değişiklik | Doğal Fotoğraf & Kapsam | Önceki / Sonraki Sonuç | Ürün / Model Kabul Durumu |
|---|---|---|---|---|
| **A. Sivilce (Acne)** | Kaş dış kuyruk landmark'ları (`69`, `299`) konveks zarfa eklendi; tüm kanalların clipping denetimi (`min(RGB) > 0.975`). | `positive-product-chain.json` ve `yolo-chain.json` 4 geliştirme kaynağı (228 aday). | Filtre öncesi: bulanık kaş sınırı sızıyordu, kırmızı parlamada püstüller eleniyordu (5→1). Filtre sonrası: 5/5 görev dışı kutu reddedildi, 11/11 eşleşen lezyon korundu. | **Model Kabul Edilmedi (`ACNE_MODEL_NOT_ACCEPTED`)**. Filtre kutu zarfını düzeltmiştir ancak detector F1: 0.1041, P: 0.0596, R: 0.4094, 9 kaçırılan lezyon ve 130 etiketsiz alan adayı ile zayıftır. |
| **B. Göz Altı Morluğu (Dark Circles)** | %5 kontrast deadband'i (`deadband = 0.05`); CIELAB $\Delta \text{chroma}$ kromatizm kapısı; lokal gradyan detrending; normalizasyon: `lower-lid-contrast-chroma-local-v3`. | `candidates.json` validation splitinden doğal yüzler ve yapay kontrol blokları. | Yapay kontrolde normal deri: `0.0`, saf gölge: `1.23`, gerçek pigment: `11.54`. Doğal pozitif fotoğraflarda: `13.7` - `35.8` skor. | **Ürün Algoritması Güncellendi**. Yapay parametreler doğal fotoğraflarda test edilmiş; model değil analitik `appearance-cv-6` proxy'si aktiftir. |
| **C. Göz Altı Torbalanması (Eye Bags)** | `bands['bags']` (`top=0.022`) ile `bands['dark']` (`top=0.012`) bantları ayrıldı; tarsal plaka korundu; 3D kıvrım çift kenar (`pairedEdge`) şartı. | 47 doğal pozitif, 15 negatif validation yüzü. | Morluk ve torbalanma maske örtüşmesi sıfırlandı; mimik/kısılma confounder'ları elendi. | **Ürün Algoritması Güncellendi**. Nöral torba maskesi (FPR %21.04) reddedildi; analitik kontur fold proxy'si aktiftir. |
| **D. Kaz Ayakları / Çizgiler (Lines)** | Saç marjı dışlama hatası düzeltildi (`active_support = under & ~hair_margin`); roll-aware radyal Gabor fanı ($\pm 30^\circ$ eye-axis roll rotasyonu); normalizasyon: `outer-canthus-gabor-radiating-hair-excluded-v3`. | 44 doğal pozitif, 15 temiz validation yüzü. | Önce: saç pikselleri skora ve siyan haritaya dahil ediliyordu. Sonra: saç tamamen paydadan ve haritadan düşüldü; tam örtüşmede `HAIR_OR_OCCLUSION_IN_LINE_BAND` (`value=None`, sahte 0 değil). Dikey kirpik bastırma: 70.7 kat. | **Ürün Algoritması Güncellendi**. Nöral çizgi maskesi (FPR %18.13) reddedildi; filtrelenmiş radyal görünüm proxy'si aktiftir. |
| **E. Yağlılık, Kızarıklık, Ton & Photo57** | Yeni eğitilen nöral maskelerin kısmi etiket nedeniyle ~%92 aşırı boyama yaptığı tespit edildi; Photo57 canlı koşturuldu. | `scope-v4-mask-data.json` geliştirme ayrımı ve Photo57 kaynak fotoğrafı. | Yeni maskeler aşırı genelleşiyor; Photo57 canlı `analyze_skin` çağrısında alt yüz gölge/crop nedeniyle `sag_overview=None` (`INSUFFICIENT_SKIN_SUPPORT`). | **Yeni Maskeler Kabul Edilmedi (`NEURAL_MASK_NOT_ACCEPTED`)**. Üründe `appearance-cv-6` analitik proxy'si korundu. Photo57 dürüstçe kaçırılan regresyon olarak kayda geçti. |

---

## 2. Düzeltilen Somut Kod Hataları

### 1. Kaz Ayakları Saç Dışlama ve Açı Fanı Hatası (`appearance_analysis.py`)
- **Önceki Hata:** `line_field(under)` içinde `valid_line = under & ~hair_margin` yalnızca piksel sayısı kontrolü (`< 20`) için kullanılıyordu. Ancak `eye_measurement` fonksiyonu `under` (saç içeren maske) üzerinden ortalama alıyor, saç piksellerini paydada tutuyor ve yerel siyan haritaya boyuyordu. Ayrıca Gabor açıları sabit (`\pi/3, \pi/2, 2\pi/3`) idi; baş yana eğildiğinde kirpikler yakalanabiliyordu.
- **Düzeltme:**
  - `eye_measurement` fonksiyonu `field(under)`'dan `active_support` alacak şekilde refaktör edildi.
  - `line_field` içinde `active_support = under & ~hair_margin` olarak belirlendi.
  - Saç pikselleri paydadan, skor ortalamasından ve yerel haritadan tamamen çıkarıldı.
  - Saç şeridi tamamen kapattığında (`active_support.sum() < 20`) `limitationCode = 'HAIR_OR_OCCLUSION_IN_LINE_BAND'` ve `value = None` döndürüldü (sağlıklı sıfır değil, yetersiz veri).
  - Gabor filtre yönleri yüzün roll açısına endekslendi:
    `eye_axis = points[263] - points[33]`
    `roll_rad = arctan2(dy, dx)`
    `thetas = (\pi/2 + roll_rad - \pi/6, \pi/2 + roll_rad, \pi/2 + roll_rad + \pi/6)`
  - Normalizasyon sürümü güncellendi: `NORMALIZATION['lines'] = 'outer-canthus-gabor-radiating-hair-excluded-v3'`.

### 2. Göz Altı Morluğu Normalizasyonu (`appearance_analysis.py`)
- Normalizasyon sürümü güncellendi: `NORMALIZATION['dark'] = 'lower-lid-contrast-chroma-local-v3'`.
- %5 fizyolojik deadband ve CIELAB $\Delta \text{chroma}$ eşiği korundu.

### 3. Photo57 Canlı Regresyon İcrası (`tests/unit/test_skin_expanded_corrections.py`)
- **Önceki Hata:** Birim test ve doğrulama script'i Photo57 için diskteki eski bir JSON makbuzunu okuyordu; dosya yoksa `if receipt_path.exists()` sessizce geçiyordu.
- **Düzeltme:** Gerçek kaynak fotoğraf (`01321_png_jpg.rf.733bb791...jpg`) diskten okundu, MediaPipe üzerinden landmark ve ağ oluşturularak canlı `analyze_skin` fonksiyonuna verildi.
- Alt yüzün dik pitch açısı (0.11), aşağı doğru sert ışık düşüşü (ortalama parlaklık 42.9 vs yüz 84.0) ve sağ çene kadraj kırpması nedeniyle `sag_overview=None`, `quality='insufficient'`, `limitationCode='INSUFFICIENT_SKIN_SUPPORT'` ürettiği canlı doğrulandı.
- `declaredLabel='positive'`, `visualReview='inconclusive-lower-face-shadow-crop'` sözleşmesiyle birim testte kilitlendi; fotoğraf veya makbuz yoksa test hard-fail verir.

---

## 3. Doğrulama ve Kanıt Ayrımı

Yeni `scripts/verify_skin_expanded_corrections.py` ve `audit-results/skin-expanded-corrections-summary.json` çıktısında alanlar kesin olarak ayrılmıştır:

```json
{
  "timestamp": "2026-10-12T09:21:02Z",
  "syntheticControlPassed": {
    "status": "PASSED",
    "deadbandScore": 0.0,
    "shadowScore": 1.2327935695648193,
    "pigmentScore": 11.542139053344727,
    "radiatingRatio": 70.67955017089844,
    "hairExclusionEffective": true,
    "bandDecouplingEffective": true
  },
  "naturalPhotoEvaluation": {
    "darkPositiveCount": 2,
    "linesPositiveCount": 6,
    "cleanNegativeCount": 3,
    "samples": [
      {
        "type": "dark",
        "path": "test/e88d4a8d-229_1_jpg.rf.945e27bf09fa828fe9e81c1a3093e80c.jpg",
        "dark": 35.791561126708984,
        "lines": 0.28571075201034546,
        "bags": 0.0
      },
      {
        "type": "dark",
        "path": "train/63d3b3c3-502_jpg.rf.eb8847e77a6fa0c120a4e633df441a7d.jpg",
        "dark": 13.703287124633789,
        "lines": 0.41874775290489197,
        "bags": null
      },
      {
        "type": "lines",
        "path": "train/00201_png_jpg.rf.0a3ba4d44e820f92a7dd52982914e86d.jpg",
        "dark": 9.747692108154297,
        "lines": 2.7736997604370117,
        "bags": null
      },
      {
        "type": "clean",
        "path": "test/berminyak__-15-_jpg.rf.65e849b1ed4da3886d9defab0f0602d3.jpg",
        "dark": null,
        "lines": null,
        "bags": null
      }
    ]
  },
  "modelEvaluation": {
    "acne": {
      "status": "ACNE_MODEL_NOT_ACCEPTED",
      "overallF1": 0.1041,
      "precision": 0.0596,
      "recall": 0.4094,
      "matchedTruth": 11,
      "duplicateLesions": 1,
      "missedTruth": 9,
      "unlabelledCandidates": 130,
      "diagnosis": "Model exhibits low precision and missed lesions; filter improvements protect UI but model itself remains unaccepted."
    },
    "oil": {
      "status": "NEURAL_MASK_NOT_ACCEPTED",
      "diagnosis": "Neural mask trained on partial labels over-segments ~92% visible area on positive photo; production retains appearance-cv-6 specular proxy."
    },
    "redness": {
      "status": "NEURAL_MASK_NOT_ACCEPTED",
      "diagnosis": "Whole-face ordinal degree active for overview; local mask not accepted; production retains appearance-cv-6 proxy."
    },
    "tone": {
      "status": "NEURAL_MASK_NOT_ACCEPTED",
      "diagnosis": "Neural mask not accepted; production retains appearance-cv-6 proxy."
    }
  },
  "productPipelineVerification": {
    "acneFilter": {
      "status": "PASSED",
      "reviewedOffTask": 5,
      "rejected": 5,
      "remaining": 0
    },
    "photo57Sag": {
      "status": "MISSED_REGRESSION_PRESERVED",
      "declaredLabel": "positive",
      "visualReview": "inconclusive-lower-face-shadow-crop",
      "sagValue": null,
      "sagQuality": "insufficient",
      "limitationCode": "INSUFFICIENT_SKIN_SUPPORT"
    }
  },
  "fourClassSkinType": {
    "status": "INTEGRATED_AND_VERIFIED",
    "modelId": "skin-type-axavj/1",
    "classes": ["normal", "dry", "oily", "combination"],
    "turkishLabels": {"normal": "Normal", "dry": "Kuru", "oily": "Yağlı", "combination": "Karma"}
  },
  "unrunChecks": null,
  "allTargetsSolved": false,
  "allTargetsVerified": false
}
```

---

## 4. CD Entegrasyonuna Hazır Dosyalar

CD ana checkout'una aktarılmaya hazır paket:
1. `services/core-api/appearance_analysis.py`:
   - Kaş konveks zarfına `69` ve `299` dahil edilmesi
   - `dark_field` %5 deadband ve CIELAB kromatizm kapısı
   - `eye_measurement` ve `line_field` saç marjı dışlama refaktörü
   - Roll-aware radyal Gabor yönleri
   - `NORMALIZATION['dark'] = 'lower-lid-contrast-chroma-local-v3'`
   - `NORMALIZATION['lines'] = 'outer-canthus-gabor-radiating-hair-excluded-v3'`
2. `services/core-api/acne_box_support.py`:
   - Anatomik envelope ve çok kanallı kırpma kontrolü (`VERSION = 'source-box-anatomical-support-v2'`)
3. `tests/unit/test_skin_expanded_corrections.py`:
   - 8 odaklı birim test (sivilce kaş/clipping, morluk deadband/kromatizm, torbalanma dekuplajı, çizgi yön/saç dışlama, Photo57 canlı icra)
4. `scripts/verify_skin_expanded_corrections.py`:
   - Ayrıştırılmış, dürüst sonuç alanları üreten bağımsız doğrulama script'i.

---

## 5. Devam Eden Somut Açıklar (Continuing Concrete Issues)

1. **Sivilce Modeli (`negative-yolox`):** Kutu zarfı ve kaş filtresi UI'ı temizlemiş olsa da dedektörün kendisi F1 0.1041 seviyesindedir. Etiketsiz alanlarda çok sayıda aday üretmekte ve gerçek 9 lezyonu kaçırmaktadır. Model ürün için kabul edilmemiştir (`ACNE_MODEL_NOT_ACCEPTED`).
2. **Nöral Segmentasyon Maskeleri (Yağlılık, Kızarıklık, Ton):** Kısmi etiketle eğitilen U-Net maskeleri etiket dışı alanda aşırı boyama (~%92) yapmaktadır. Bu nedenle analitik `appearance-cv-6` yöntemi korunmuş, nöral maskeler devreye alınmamıştır.
3. **Photo57 Sarkma Kaçırması:** Alt yüzdeki sert ışık düşüşü ve kadraj kırpması nedeniyle sarkma ölçülememekte (`INSUFFICIENT_SKIN_SUPPORT`), pozitif etiketli bu vaka kaçırılmaktadır. Bu bir veri kalitesi/kamera açısı sınırlaması olarak kaydedilmiştir.
