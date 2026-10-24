# Attune.more Cilt ve Diş Analizi — Model Envanteri, Seçim Gerekçesi ve Yerel Ağırlık Doğrulaması (2026-10-24)

Bu belge, kendi Roboflow çalışma alanımızdaki (`tolgar-sasmaz`) **tüm 16 projenin** makine tarafından doğrulanmış envanterini, yerel ONNX ağırlıklarımızı, sınıf/metrik/eşik karşılaştırmalarını, ağırlık dışa aktarım (`weights.pt` / ONNX) testlerini ve sıfır ek inference maliyetli (`0 TL / çağrı`) ürün mimarisini kayıt altına alır.

Ham makine çıktıları:
- [`docs/skin-research/roboflow-workspace-inventory-20261024.json`](file:///C:/Users/PC/Desktop/AI%20Workspace/TOGG/attune-skin-refinement-worktree/docs/skin-research/roboflow-workspace-inventory-20261024.json)
- [`docs/skin-research/roboflow-weight-export-audit-20261024.json`](file:///C:/Users/PC/Desktop/AI%20Workspace/TOGG/attune-skin-refinement-worktree/docs/skin-research/roboflow-weight-export-audit-20261024.json)

---

## 1. Kendi Roboflow Çalışma Alanımız (`tolgar-sasmaz`) — Tam Envanter (16 Proje)

| # | Proje ID (`version`) | Görev Türü | Model Mimarisi | Görüntü (`train / valid / test`) | Sınıflar (`declaredClassList`) | Genel Metrikler (`mAP50 / P / R`) | Sınıf Bazlı `mAP50` (Valid / Test) | Yerel Ağırlık İndirme Durumu (`weights.pt` / ONNX) | Ürün Kararı |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `attune-comedones-boxes-grouped-r1/1` (`--e79545` / `comedones_grouped_r1`) | `object-detection` | `rfdetr-small` | `781` (`544 / 155 / 82`) | `acne`, `blackheads`, `whiteheads` | `42.52% / 64.91% / 43.0%` | Valid: `acne 58.20%`, `blackheads 43.51%`, `whiteheads 25.86%`<br>Test: `acne 62.59%`, `blackheads 27.62%`, `whiteheads 33.42%` | **İndirilebilir (`weights.pt`)**: `127,395,111 B`, SHA256 `b7096a9db340769c...` (`OrderedDict`, 487 tensör). REST ONNX export kapalı (`HTTP 400`); yerel dönüşüm için `rfdetr` paketi gerekir. | **Aday / Deneysel**: `acne` sınıfı (`62.59%` test mAP50) güçlüdür; `blackheads`/`whiteheads` ayrımı düşüktür. Ürün akışında bulut çağrısı kapalıdır; yerel CPU'da `acne-v5-step0-silu-opset17` ONNX modeli aktiftir. |
| 2 | `attune-comedones-clean-train-r2/1` | `object-detection` | `rfdetr-nas` | `839` (`544 / 169 / 126`) | `acne`, `blackheads`, `whiteheads` | `35.14% / 57.69% / 36.11%` | Valid: `acne 45.28%`, `blackheads 43.62%`, `whiteheads 16.53%`<br>Test: `acne 57.66%`, `blackheads 28.08%`, `whiteheads 33.03%` | **Engelli (`RoboflowError`)**: Roboflow `rfdetr-nas` ağırlıklarını dışa aktarmaya izin vermiyor (`There was an error finding the pytorch weights`). | **Reddedildi**: Hem `grouped-r1/1` sürümünden daha düşük mAP50 (`35.14%` vs `42.52%`) hem de yerel ağırlık dışa aktarımı kapalı (ücretli bulut inference gerektirir). |
| 3 | `attune-pores-masks-grouped-r1/2` (`--e79545` / `pores_seg_r1`) | `instance-segmentation` | `yolov11s-seg` | `1517` (`1159 / 241 / 117`) | `pore` | `27.12% / 44.33% / 33.68%` (Test mAP50: `25.64%`) | Valid: `pore 27.12%`<br>Test: `pore 25.64%` | **İndirilebilir (`weights.pt`)**: `20,533,668 B`, SHA256 `702d380a0ac8ce4d...` (`ultralytics` YOLO11s-seg checkpoint). | **Reddedildi (Ürün Akışı)**: Tek sınıf (`pore`), düşük mAP50 (`25.64%` test) ve bulut çağrısında yüksek gecikme/timeout riski nedeniyle ürün yolundan çıkarıldı; yalnızca opt-in araştırma modunda tutulur. |
| 4 | `attune-skin-acne-marks-pigmentation/1` | `object-detection` | `rfdetr-nas` | `3220` (`2727 / 323 / 170`) | `acne_scar`, `dark_spot`, `freckle`, `keloid`, `melasma`, `PIH`, `PIE`, `skin_lesion`, `solar_lentigo` | `64.61% / 67.22% / 60.06%` | Valid: `PIE 87.34%`, `PIH 78.66%`, `acne_scar 74.08%`, `melasma 68.58%`, `dark_spot 68.23%`, `freckle 65.17%`, `keloid 32.02%`, `skin_lesion 6.66%` | **Engelli (`RoboflowError`)**: `rfdetr-nas` ağırlıkları Roboflow tarafından dışa aktarılamıyor. | **Reddedildi (Yerel Çalışmama Nedeniyle)**: Pigih/PIH/PIE/leke metrikleri iyi olmasına rağmen Roboflow ağırlık indirmeyi engellediği ve bulut API kredisi tükettiği için sıfır maliyetli yerel ürün akışına alınamaz. |
| 5 | `attune-skin-findings-boxes-research/1` | `object-detection` | `rfdetr-nas` | `3513` (`2975 / 322 / 216`) | `acne`, `acne_marks`, `blackhead`, `comedone`, `cyst`, `nodule`, `papule`, `pustule`, `scar`, `whitehead` | `46.57% / 47.45% / 47.59%` | Valid: `acne 80.52%`, `acne_marks 81.90%`, `cyst 66.0%`, `nodule 54.09%`, `pustule 42.33%`, `papule 41.29%`, `blackhead 38.67%`, `scar 33.42%`, `whitehead 27.49%`, `comedone 0.0%` | **Engelli (`RoboflowError`)**: `rfdetr-nas` ağırlık dışa aktarımı kapalı. | **Reddedildi (Yerel Çalışmama + Çakışan Sınıflar)**: `comedone 0%` ölü sınıf içerir ve `rfdetr-nas` ağırlıkları indirilemediği için yerel çalıştırılamaz. |
| 6 | `attune-skin-regional-skin-map/1` (`--e79545` / `oily_redness_seg`) | `instance-segmentation` | `rfdetr-nas-seg` | `62` (`43 / 12 / 7`) | `Oily`, `Redness` | `51.84% / 57.14% / 57.14%` | Valid (`12` görüntü!): `Oily 34.81%`, `Redness 68.86%`<br>Test (`7` görüntü!): `Oily 19.62%`, `Redness 24.44%` | **Engelli (`RoboflowError`)**: `rfdetr-nas-seg` ağırlık dışa aktarımı kapalı. | **Reddedildi**: Yalnızca 62 görüntüyle eğitilmiş, test setinde (`7` görüntü) `Oily mAP50 = 19.62%`, `Redness mAP50 = 24.44%` ve yerel ağırlık dışa aktarımı kapalı. Ürün parlama (`shine`) hesabına karıştırılması tamamen kaldırıldı. |
| 7 | `lesion-detection-ruc40-qzwqz/1` (`--e79545` / `lesion_pathology`) | `object-detection` | `rfdetr-large` | `785` (`628 / 157 / 0`) | `atrophic_scar`, `closed_comedo`, `hypertrophic_scar`, `melasma`, `nevus`, `nodule`, `open_comedo`, `other`, `papule`, `pustule` | `36.41% / 51.0% / 36.11%` | Valid: `melasma 69.64%`, `pustule 46.23%`, `papule 45.67%`, `nodule 44.36%`, `closed_comedo 32.16%`, `open_comedo 21.11%`, `atrophic_scar 19.38%`, `hypertrophic_scar 0.0%`, `nevus 0.0%` | **İndirilebilir (`weights.pt`)**: `134,792,239 B`, SHA256 `f8ed074ad757729c...` (`OrderedDict`, 509 tensör). | **Reddedildi (Ürün Akışı)**: Test split'i (`0` görüntü) yoktur, `nevus`/`hypertrophic_scar` `0%` mAP50'dir ve yerel `acne-v5` ile birleştirildiğinde çift sayım (double-counting) üretmektedir. Ürün akışından çıkarıldı. |
| 8 | `acne-detection-2-e2juf-fbx7y` | `object-detection` | — | `905` (`0` versiyon) | `acne`, `acne_marks`, `blackhead`, `papule`, `purulent`, `whitehead` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok. |
| 9 | `acne-k8i87-57b3d` | `object-detection` | — | `454` (`0` versiyon) | `acne_scars`, `blackhead`, `cystic`, `flat_wart`, `folliculitis`, `keloid`, `milium`, `papular`, `purulent`, `sebo-crystan-conglo`, `syringoma`, `whitehead` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok. |
| 10 | `acne-new-model-x6jfv-lcfsw` | `object-detection` | — | `1349` (`0` versiyon) | `blackheads`, `dark spot`, `nodules`, `papules`, `pustules`, `whiteheads` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok. |
| 11 | `attune-periorbital-zones` | `instance-segmentation` | — | `0` (`0` versiyon) | — | Boş proje | — | Yok | Boş proje. |
| 12 | `attune-skin-texture-lines` | `instance-segmentation` | — | `0` (`0` versiyon) | — | Boş proje | — | Yok | Boş proje. |
| 13 | `blackhead-and-whitehead-nf79d-s1d2j` | `object-detection` | — | `202` (`0` versiyon) | `blackhead`, `whitehead` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok. |
| 14 | `pore-6917m-2fdff` | `instance-segmentation` | — | `539` (`0` versiyon) | `pores` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok. |
| 15 | `skin-detection-s3jff-b6p3h` | `instance-segmentation` | — | `62` (`0` versiyon) | `Oily`, `Redness`, `dry`, `normal`, `wrinkle` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok (`attune-skin-regional-skin-map` kaynak veri kümesi). |
| 16 | `skin-problem-v2-gl8eb-h5n1t` | `instance-segmentation` | — | `1818` (`0` versiyon) | `acne_scar`, `dark_spot`, `freckle`, `keloid`, `melasma`, `pih`, `pie`, `skin_lesion`, `solar_lentigo`, `wrinkle` | Eğitilmiş versiyon yok | — | Yok | Eğitimli versiyon yok. |

---

## 2. Ürün Akışında Aktif Yerel Modeller (`services/core-api/models/`) — %100 Yerel CPU, 0 TL Ek Ücret

Ürün akışında hiçbir ücretli bulut API çağrısı, Roboflow hosted inference kredisi veya abonelik kullanılmaz. Aktif tüm modeller yerel diskteki ONNX/kalibrasyon ağırlıklarıyla `onnxruntime` (`CPUExecutionProvider`) üzerinde çalışır:

| Görev / Kart | Model Kimliği (`modelId` / `version`) | Yerel Dosya Yolu | Boyut (Byte) | SHA256 Özeti | Lisans & Maliyet | Ürün Akışındaki Rolü |
|---|---|---|---|---|---|---|
| Gözlük / Ön Kontrol | `skin-eyewear-framefind-v1` | `services/core-api/models/skin-eyewear-framefind-v1.onnx` | `13,205,405` | `30a794b838dc0df3b47ffdb76beaa62eb3a8185950c9f727d3ba407fb29a9788` | Yerel ONNX, `0 TL` | Gözlük çerçevesi tespiti ve periorbital kalite kilidi. |
| Akne / Lezyon Tespiti | `acne-v5-step0-silu-opset17` | `services/core-api/models/acne-v5-preview/step0-with-features-stable-silu.onnx` | `35,969,899` | `6674a237645c1c97b38796574c048b99c62f53a2a19098d8b7917b54ef080ff8` | Yerel YOLOX ONNX, `0 TL` | Bölgesel akne nokta (`points`) ve yoğunluk tespiti (`FRONT`, `LEFT`, `RIGHT` açı sözleşmesiyle). |
| Kuruluk / Pullanma (`dry`) | `calibrated-material-v3-c04-clean` (`appearance-native-dry-2`) | `services/core-api/models/dryness-calibrated-v3/encoder.onnx` + `head.json` | `46,912` (`encoder.onnx`) + `21,499` (`head.json`) | `d19248867bf0759caebccde20ff96187b931b9ffaa6d7fa77f717caab84903e2` | Yerel ONNX + Lojistik Kalibrasyon, `0 TL` | Bölgesel kuruluk/pullanma yüzdesi ve maskesi (`appearance_native_dryness.py`). |
| Göz Altı Torbası (`bags`) | `skin-focused-degrees-v1` | `services/core-api/models/skin-focused-degrees.onnx` | `25,356,317` | `20408867fa6b3bf0d677c3c6f2f60dbeb2d05408ebff339c93ee2b5f7a5a7f61` | Yerel ONNX, `0 TL` | Göz altı torbası varlık maskesi (`bags`). |
| Global Cilt Tipi Baz Kaydı | `local-vit-dima806-5aace4f-v1` | `services/core-api/models/skin-type-local-v1/model.onnx` | `343,273,465` | `34a083ff14c5f80157bf43511622a406150ec0d192b10eb2a72bb8cb2f8decf5` | Apache-2.0 (`dima806/skin_types_image_detection`), `0 TL` | Yalnızca `basePrediction` ve `decisionTrace.baseValue` denetim kaydı için çalışır; nihai `skinType.value` kararına **asla sızmaz**. |
| Diş Analizi | `dental-yolox-s-v1` | `services/core-api/models/dental-yolox-s.onnx` | `35,952,078` | `785eb267763ffdf406b4205b6d8eb188424d58796bb3fb43a6fb525dd2fb56aa` | Yerel YOLOX-S ONNX, `0 TL` | Diş plak/diş eti/renk/taş lokal analizi. |

---

## 3. Hassasiyet (`sensitive`) İçin Otomatik Görüntü Değerlendirmesi ve Teknik Açık Raporu

Kullanıcı gereksinimi doğrultusunda:
1. **Kullanıcıya soru sorulmaz:** `"Cildiniz hassas mı?"` veya benzeri hiçbir beyan sorusu/butonu arayüzde veya API'de yer almaz.
2. **Kızarıklık (`redness`) hassasiyet sayılmaz:** `SENSITIVE_REDNESS_MIN` eşiği tamamen kaldırılmıştır. Kızarıklık indeksi (`redness`) yüzü pembe (`sensitive`) boyamak veya cilt tipini `"Hassas"` ilan etmek için kullanılmaz.
3. **Mevcut model envanteri incelemesi:**
   - Roboflow çalışma alanımızdaki 16 projenin hiçbirinde doğrulanmış bir `sensitive` / reaktif cilt sınıfı bulunmamaktadır (`attune-skin-regional-skin-map/1` yalnızca `Oily` ve `Redness` sınıflarına sahiptir).
   - Yerel ONNX modellerimiz arasında da (`skin-type-local-v1` yalnızca `dry`, `normal`, `oily` sınıflarına sahiptir) görüntüden doğrudan cilt bariyeri reaktivitesini / nörosensöriyel hassasiyeti ölçen kalibre edilmiş bir model yoktur.
4. **Teknik açık bildirimi:** Görüntüden güvenilir bölgesel hassasiyet sonucu üretilemediği için sistem sahte/doğrulanmamış pembe hassasiyet haritası üretmez; bu durum karar izinde açıkça teknik sınır olarak tutulur.

---

## 4. Bölgesel Cilt Tipi Kuralı, Eşik Durumu ve 3-Açı Birleştirme (`FRONT + LEFT + RIGHT`)

### 4.1 Kalibre Edilmemiş Hipotez Eşikleri (`THRESHOLD_STATUS = "uncalibrated-hypothesis"`)
- **Pozitif Yağlılık Eşiği (`OIL_POSITIVE_MIN`)**: `>= 2.0%` (`appearance-cv-6` parlama veya kabul edilmiş yağ ölçümü)
- **Negatif Yağlılık Üst Sınırı (`OIL_NEGATIVE_MAX`)**: `<= 1.0%`
- **Pozitif Kuruluk Eşiği (`DRY_POSITIVE_MIN`)**: `>= 2.0%` (`appearance-native-dry-2` yerel kalibre kuruluk modeli)
- **Negatif Kuruluk Üst Sınırı (`DRY_NEGATIVE_MAX`)**: `<= 1.0%`
- **Ara Sinyal Bandı (`1.0% < v < 2.0%`)**: Bölge durumu `'unknown'` (`INTERMEDIATE_BAND_UNKNOWN`) olur; genel cilt tipi `'Belirlenemedi (Ara sinyal bandı)'` (`limitationCode = "INTERMEDIATE_BAND_UNDETERMINED"`, `value = None`) döner.
- **Negatif Kanıt Kuralı (`ACCEPTED_NEGATIVE_METHODS = set()`)**: Mevcut parlama (`appearance-cv-6`) ve kuruluk (`appearance-native-dry-2`) yöntemleri düşük sinyalin (`<= 1.0%`) gerçekten `"normal"` cilt olduğunu kanıtlamak üzere kalibre edilmediğinden, kabul edilmiş negatif kanıt yöntemi verilmediğinde düşük sinyalli bölgeler `'normal'` yerine `'unevaluated'` (`'Değerlendirilmedi'`, `NEGATIVE_EVIDENCE_METHOD_NOT_ACCEPTED`) olarak işaretlenir. Kabul edilmiş negatif yöntem sağlandığında simetrik olarak `<= 1.0%` `'normal'` döner.
- **Global ViT Etiketi Sızdırmazlığı**: Bölgesel desen kısmi veya çelişkili olduğunda (ör. alın yağlı, çene kuru) global ViT tahmini (`basePrediction.value`) nihai `value` alanına **asla sızmaz** (`value = None`, `limitationCode = "MIXED_REGIONAL_PATTERN_UNDETERMINED"`, `displayValue = "Karışık desen (Belirlenemedi)"`).

### 4.2 Üç Açı Birleştirme (`fuse_multi_angle_skin` / `fuseMultiAngleSkinOverview`)
- **T-Bölgesi (`forehead`, `nose`, `chin`)**: `FRONT` çekiminden (`sourcePose = "FRONT"`, `sourcePhotoId = front.photoId`) alınır. T-bölgesinin yağlı sayılması için 3 alt bölgenin tamamı ölçülmüş olmalı, hiçbiri `'unknown'` olmamalı ve **en az 2/3'ü (`>= 2`) yağlı olup en az biri `forehead` veya `nose`** olmalıdır.
- **Sağ Yanak (`rightCheek`)**: Kullanıcının başını sola çevirdiği `LEFT` çekiminden (`sourcePose = "LEFT"`, `sourcePhotoId = left.photoId`) alınır.
- **Sol Yanak (`leftCheek`)**: Kullanıcının başını sağa çevirdiği `RIGHT` çekiminden (`sourcePose = "RIGHT"`, `sourcePhotoId = right.photoId`) alınır.
- **Görsel Katman Garantisi (`SkinFacePanel.tsx`)**: Yan açı (`LEFT` veya `RIGHT`) fotoğrafı görüntülendiğinde, `FRONT` fotoğrafına ait yanak sonucu yan fotoğrafa **asla** boyanmaz; her bölgenin SVG katmanında `data-source-pose` ve `data-source-photoid` öznitelikleri doğrulanır.
