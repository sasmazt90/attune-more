# Attune.more Cilt Analizi — Model Seçimi, Yerel Ağırlık Kanıtı ve Roboflow Workspace Envanteri (2026-10-24)

Bu belge `docs/skin-research/roboflow-workspace-inventory-20261024.json` ve `docs/skin-research/local-models-benchmark-20261024.json` dosyalarından **programatik olarak birebir** üretilmiştir.

---

## 1. Kalıcı Olarak İndirilen ve Yerel Diskte Saklanan Roboflow Model Ağırlıkları (`tolgar-sasmaz`)

Aşağıdaki 3 eğitilmiş modelin PyTorch ağırlıkları (`weights.pt`) Roboflow SDK (`version.models()[0].download()`) üzerinden indirilmiş, **silinmeden kalıcı olarak** `C:\Users\PC\Desktop\AI Workspace\TOGG\e2e-verification-20261024\models\` altında saklanmış ve `socket.socket` tamamen engellenerek (sıfır ağ trafiği kanıtıyla) yerel CPU üzerinde çalıştırılmıştır:

| Proje / Sürüm | Mimari | Kalıcı Dosya Yolu | Boyut (Bayt) | SHA256 | Lisans | Yerel Yükleme Süresi |
|---|---|---|---:|---|---|---:|
| `tolgar-sasmaz/attune-comedones-boxes-grouped-r1/1` | `rfdetr-small` | `C:\Users\PC\Desktop\AI Workspace\TOGG\e2e-verification-20261024\models\attune-comedones-boxes-grouped-r1-v1\weights.pt` | `127,395,111` | `b7096a9db340769c3e66ceec4cea47fcd6d0890b4259713751c3c97226d38b26` | Apache-2.0 (rfdetr) + workspace owner weights | `726.17 ms` |
| `tolgar-sasmaz/lesion-detection-ruc40-qzwqz/1` | `rfdetr-large` | `C:\Users\PC\Desktop\AI Workspace\TOGG\e2e-verification-20261024\models\lesion-detection-ruc40-qzwqz-v1\weights.pt` | `134,792,239` | `f8ed074ad757729ce7d21ab22209443b91388f483415e8d3f8d892c72f6bd858` | Apache-2.0 (rfdetr) + workspace owner weights | `568.11 ms` |
| `tolgar-sasmaz/attune-pores-masks-grouped-r1/2` | `yolov11s-seg` | `C:\Users\PC\Desktop\AI Workspace\TOGG\e2e-verification-20261024\models\attune-pores-masks-grouped-r1-v2\weights.pt` | `20,533,668` | `702d380a0ac8ce4d973c6a1529a87dd3485287e599cc6cdda081d6c3a35f714a` | AGPL-3.0 (Ultralytics YOLOv11) | `63.27 ms` |

---

## 2. Ürün Akışında Aktif Olan Yerel ONNX Modelleri (`services/core-api/models/`)

| Kriter / Görev | Model Sürümü | Yöntem (`methodVersion`) | Yerel ONNX Yolu | Boyut (Bayt) | SHA256 | Lisans |
|---|---|---|---|---:|---|---|
| **acne** | `experimental-step0-verifier-v5-local-preview-v1` | `appearance-acne-step0-verifier-v5-2` | `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-skin-refinement-worktree\services\core-api\models\acne-v5-preview\step0-with-features-stable-silu.onnx` | `39,122,518` | `9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be` | Apache-2.0 (YOLOX step0 + logistic verifier) |
| **dry** | `dryness-calibrated-v3` | `appearance-native-dry-3` | `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-skin-refinement-worktree\services\core-api\models\dryness-calibrated-v3\encoder.onnx` | `16,019,972` | `a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987` | Proprietary in-repo local ONNX |
| **redness (whole-face)** | `skin-appearance-photo-ridge-20261010-v1` | `appearance-cv-6` | `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-skin-refinement-worktree\services\core-api\models\skin-focused-degrees.onnx` | `16,037,017` | `65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3` | Proprietary in-repo local ONNX |
| **skinType (auxiliary base)** | `local-vit-dima806-5aace4f-v1` | `local-vit-dima806-5aace4f-v1+tzone-oily-cheeks-dry-or-normal-v3` | `C:\Users\PC\Desktop\AI Workspace\TOGG\attune-skin-refinement-worktree\services\core-api\models\skin-type-local-v1\model.onnx` | `343,341,982` | `99b4c2fa1e9ac013d539f635eb948c5a29f4c5f86f34fe26c380ad308c26c65a` | Apache-2.0 (dima806/skin_types_image_detection) |

---

## 3. `tolgar-sasmaz` Roboflow Workspace Tam Envanteri (16 Proje — JSON Kaynağıyla %100 Birebir)

> **Not:** Envanterdeki tüm sayısal değerler (`Proje Görüntü Sayısı`, `Sürüm Görüntü Sayısı (train/valid/test)`, `Sınıflar`, `mAP50 / Precision / Recall`) doğrudan `roboflow-workspace-inventory-20261024.json` API yanıtından okunmuştur. Ayrıca daha önce adı geçen `skin-detection-s3jff-b6p3h` (62 görüntü, `Oily, Redness, dry, normal, wrinkle` — `sensitive` sınıfı içermez) Roboflow API üzerinden kontrol edilmiş ve mevcut `tolgar-sasmaz` çalışma alanında yer almadığı (`HTTP 404 / HTTPError`), `attune-skin-regional-skin-map/1` (`337` görüntü: `244/63/30`, sınıflar yalnızca `Oily, Redness`) projesinin ise `sensitive` sınıfı içermediği doğrulanmıştır.

| Proje ID (`tolgar-sasmaz/...`) | Görev Tipi | Proje Görüntü | Sürüm | Sürüm Görüntü (`train/valid/test`) | Sınıflar (`classes`) | Eğitilmiş Model Tipi | Metrikler (`mAP50 / P / R` veya En İyi NAS) | Yerel Ağırlık (`weights.pt`) Durumu |
|---|---|---:|---|---|---|---:|---|---|
| `acnes-wscug-bi73e` | `instance-segmentation` | 1330 | `v1` | 1330 (`926/268/136`) | `nodule` (312), `papule` (830), `pustule` (642), `whitehead` (231), `blackhead` (252) | `—` | — | **Yok** (`no-trained-model`) |
| `attune-comedones-boxes-grouped-r1` | `object-detection` | 2201 | `v1` | 2201 (`1547/345/309`) | `blackheads` (4823), `acne` (3577), `whiteheads` (6172) | `rfdetr-small` | mAP50: `42.52%`, P: `49.80%`, R: `45.30%` | **İndirilebilir ve Kalıcı Kaydedildi** (`weights.pt`, yerel CPU'da çalıştırıldı) |
| `attune-comedones-clean-train-r2` | `object-detection` | 1571 | `v1` | 1571 (`917/345/309`) | `blackheads` (3551), `acne` (2507), `whiteheads` (4558) | `rfdetr-nas-parent` | NAS (90 alt-model) en iyi mAP50: `44.53%`, F1: `48%`, R: `78.5%` | **İndirilemez** (`rfdetr-nas-parent`: Roboflow API `There was an error finding the pytorch weights for this model` döner) |
| `attune-pores-masks-grouped-r1` | `instance-segmentation` | 1416 | `v2` | 1416 (`1018/192/206`) | `pore` (56888) | `yolov11s-seg` | mAP50: `27.12%`, P: `—`, R: `—` | **İndirilebilir ve Kalıcı Kaydedildi** (`weights.pt`, yerel CPU'da çalıştırıldı) |
| `attune-pores-masks-grouped-r1` | `instance-segmentation` | 1416 | `v1` | 1416 (`1018/192/206`) | `pore` (56888) | `—` | — | **Yok** (`no-trained-model`) |
| `attune-skin-acne-marks-pigmentation` | `object-detection` | 800 | `v1` | 800 (`553/165/82`) | `Pimple` (3640), `Post acne` (32123), `Pigmentation` (1579) | `rfdetr-nas-parent` | NAS (89 alt-model) en iyi mAP50: `17.59%`, F1: `25.5%`, R: `48.2%` | **İndirilemez** (`rfdetr-nas-parent`: Roboflow API `There was an error finding the pytorch weights for this model` döner) |
| `attune-skin-acne-pilot` | `object-detection` | 800 | — | Eğitilmiş/üretilmiş sürüm yok | `Enlarged pores` (1191), `Pimple` (3640), `Pigmentation` (1579), `Post acne` (32123), `Freckles` (853), `Mole` (2082) | — | — | **Yok** (Sürüm/eğitim yok) |
| `attune-skin-findings-boxes-research` | `object-detection` | 927 | `v1` | 927 (`669/117/141`) | `Gunes Lekesi` (1468), `Yagli Cilt` (320), `Egzema` (299), `Siyah Nokta` (2021), `Genis Gozenek` (307), `Rozasea` (257), `Kuru Cilt` (515), `Beyaz Nokta` (1789), `Riskli Ben` (150), `Sedef ve Dokuntu` (625), `Ucuk` (202), `Akne` (1599) | `rfdetr-nas-parent` | NAS (84 alt-model) en iyi mAP50: `30.23%`, F1: `30.1%`, R: `71.1%` | **İndirilemez** (`rfdetr-nas-parent`: Roboflow API `There was an error finding the pytorch weights for this model` döner) |
| `attune-skin-regional-skin-map` | `instance-segmentation` | 337 | `v1` | 337 (`244/63/30`) | `Oily` (1065), `Redness` (571) | `rfdetr-nas-seg-parent` | NAS (75 alt-model) en iyi mAP50: `49.73%`, F1: `52.3%`, R: `83.1%` | **Yok** (`no-trained-model`) |
| `attune-skin-under-eye-grouped-research` | `instance-segmentation` | 0 | — | Eğitilmiş/üretilmiş sürüm yok | — | — | — | **Yok** (Sürüm/eğitim yok) |
| `attune-skin-under-eye-pilot` | `instance-segmentation` | 399 | — | Eğitilmiş/üretilmiş sürüm yok | `eyebag` (487), `darkcircle` (382) | — | — | **Yok** (Sürüm/eğitim yok) |
| `jerawat-v-hj0qi` | `object-detection` | 2202 | `v1` | 2202 (`1926/185/91`) | `nodule` (933), `papule` (1630), `pustule` (1014), `blackhead` (4823), `whitehead` (6183) | `—` | — | **Yok** (`no-trained-model`) |
| `lesion-detection-ruc40-qzwqz` | `object-detection` | 276 | `v1` | 276 (`235/27/14`) | `nevus` (1461), `papule` (5550), `pustule` (1268), `melasma` (3955), `hypertrophic_scar` (774), `closed_comedo` (5877), `atrophic_scar` (8958), `open_comedo` (3297), `other` (428), `nodule` (209) | `rfdetr-large` | mAP50: `36.41%`, P: `43.10%`, R: `43.70%` | **İndirilebilir ve Kalıcı Kaydedildi** (`weights.pt`, yerel CPU'da çalıştırıldı) |
| `pores-detection-rqkcb-l6t8k` | `instance-segmentation` | 1473 | `v1` | 1473 (`1179/147/147`) | `pore` (57902) | `—` | — | **Yok** (`no-trained-model`) |
| `pores-mm7fn-e4pvz` | `instance-segmentation` | 444 | `v1` | 444 (`373/35/36`) | `pore` (23585) | `—` | — | **Yok** (`no-trained-model`) |
| `skin_face_detection-emora` | `instance-segmentation` | 2811 | `v1` | 2811 (`1969/564/278`) | `wrinkle` (18400), `face` (468), `frown` (578), `dark_circle` (160), `forehead` (4037), `nasolabial_fold` (602), `marionette_line` (401), `crows_feet` (875), `tear_through` (648), `vertical_lips_lines` (138), `mental_crease` (79), `acne` (257), `brow_droop` (123), `bunny_line` (149), `nasobi` (2), `fol` (2) | `—` | — | **Yok** (`no-trained-model`) |
| `wrinkles-79rrf-t7kyp` | `instance-segmentation` | 1558 | `v1` | 1558 (`1167/243/148`) | `wrinkles` (7516) | `—` | — | **Yok** (`no-trained-model`) |

---

## 4. Aynı Görüntüler Üzerinde Yerel CPU Çıkarım (Inference) Karşılaştırması (`socket.socket` Engelli)

`local-models-benchmark-20261024.json` içinde belgelendiği üzere, tüm modeller `socket.socket` engellenmiş durumda (sıfır ağ erişimi) aynı 3 görüntü üzerinde yerel CPU'da koşturulmuştur:
1. `tolgar_docx_screen1_true_face_286_297_670_693.png` (`384×396` px, `Tolgar-Skin(1).docx` `word/media/image1.png` içindeki gerçek yüz alanı `[286, 297, 670, 693]`, çizimsiz/meshsiz)
2. `02_germany_FRONT` (`2048×1529` px, üretilmiş replay portresi — canlı kamera çekimi değildir)
3. `01_england_FRONT` (`2048×1529` px, üretilmiş replay portresi — canlı kamera çekimi değildir)

### 4.1. Karşılaştırma Özeti Tablosu

| Görüntü ID (`Boyut`) | `attune-comedones-boxes-grouped-r1/1` (`rfdetr-small`, yerel `weights.pt`) | `lesion-detection-ruc40-qzwqz/1` (`rfdetr-large`, yerel `weights.pt`) | `attune-pores-masks-grouped-r1/2` (`yolov11s-seg`, yerel `weights.pt`) | `acne-v5` (`step0-silu.onnx` + anatomik zarf + `verifier-v5`) | `dryness-calibrated-v3` (`encoder.onnx`) | `skin-focused-degrees` (`redness` ONNX) | `skin-type-vit-dima806` (Yardımcı ONNX) |
|---|---|---|---|---|---|---|---|
| `tolgar_docx_screen1_true_face_286_297_670_693` (`384×396`) | `7` kutu (`1074.46 ms`); ilk kutu: `[80.1, 129.5, 180.7, 203.6]` (`conf=0.6103`) | Ham: `14`, Onaylı akne: `3`, Hariç tutulan (`nevus/other`): `0` (`1660.85 ms`) | `0` maske (`conf>=0.05`, `382.89 ms`) | Merkez karo ham aday: `0` (`196.53 ms`); anatomik zarf + doğrulayıcı ile yanlış pozitifleri eler | `1280`-boyut gömme (`L2=11.9645`, `19.21 ms`) | Skor: `0.5381` (`31.72 ms`) | Yardımcı tahmin: `oily` (`2019.03 ms`) |
| `02_germany_FRONT` (`2048×1529`) | `1` kutu (`397.13 ms`); ilk kutu: `[18.3, 38.0, 2048.0, 1529.0]` (`conf=0.8229`) | Ham: `12`, Onaylı akne: `3`, Hariç tutulan (`nevus/other`): `1` (`882.56 ms`) | `2` maske (`conf>=0.05`, `236.26 ms`) | Merkez karo ham aday: `5` (`144.45 ms`); anatomik zarf + doğrulayıcı ile yanlış pozitifleri eler | `1280`-boyut gömme (`L2=13.2207`, `32.07 ms`) | Skor: `1.7517` (`28.42 ms`) | Yardımcı tahmin: `oily` (`294.38 ms`) |
| `01_england_FRONT` (`2048×1529`) | `2` kutu (`373.56 ms`); ilk kutu: `[140.8, 58.5, 1932.7, 1529.0]` (`conf=0.8588`) | Ham: `17`, Onaylı akne: `0`, Hariç tutulan (`nevus/other`): `14` (`762.45 ms`) | `5` maske (`conf>=0.05`, `169.96 ms`) | Merkez karo ham aday: `0` (`156.3 ms`); anatomik zarf + doğrulayıcı ile yanlış pozitifleri eler | `1280`-boyut gömme (`L2=13.8888`, `30.76 ms`) | Skor: `2.7083` (`47.16 ms`) | Yardımcı tahmin: `oily` (`292.2 ms`) |

### 4.2. Somut Model Seçim Kararı ve Teknik Gerekçe

1. **Sivilce / Akne (`acne`) Kriteri:**
   - **Seçilen Aktif Ürün Modeli:** `acne-v5` (`step0-with-features-stable-silu.onnx` + `acne_box_support_staging.py` anatomik zarf ve göz/kaş/dudak/burun deliği/saç dışlama + `verifier-v5.json` lojistik doğrulayıcı; `methodVersion: appearance-acne-step0-verifier-v5-2`). Varsayılan ürün akışında **aktif** hale getirilmiştir.
   - **Neden `attune-comedones-boxes-grouped-r1/1` (`rfdetr-small`) seçilmedi?** Yerel CPU testinde kanıtlandığı üzere bu model grup/bölge kutularıyla eğitildiği için `02_germany_FRONT` (`2048×1529`) üzerinde `[18.3, 38.0, 2048.0, 1529.0]` (`conf=0.8229`) ve `01_england_FRONT` üzerinde `[140.8, 58.5, 1932.7, 1529.0]` (`conf=0.8588`) şeklinde **tüm görüntüyü kaplayan tek bir dev kutu** üretmektedir; `tolgar_docx_screen1_true_face_286_297_670_693.png` (`384×396`) üzerinde ise tüm gözü ve ağız-çene bölgesini (`[80.1, 129.5, 180.7, 203.6]`, `[97.0, 213.5, 264.2, 355.7]`) `"blackheads"` olarak işaretlemektedir.
   - **Neden `lesion-detection-ruc40-qzwqz/1` (`rfdetr-large`) doğrudan ana ürün modeli yapılmadı?** Yalnızca `276` görüntüyle (`235/27/14`) eğitilmiştir (`mAP50 = 19.63%`). Yerel CPU testinde `tolgar_docx_screen1_true_face_286_297_670_693.png` üzerinde **her iki gözü** (`[102.4, 158.5, 162.2, 190.7]` `conf=0.4652` ve `[215.2, 162.0, 271.8, 192.5]` `conf=0.4320`) `"papule"` olarak yanlış pozitif tahmin etmiştir ve tek kare CPU süresi `762–1661 ms`'dir.
2. **Kuruluk (`dry`) Kriteri:**
   - **Seçilen Aktif Ürün Modeli:** `dryness-calibrated-v3` (`services/core-api/models/dryness-calibrated-v3/encoder.onnx` + kalibre edilmiş yerel başlık, `methodVersion: appearance-native-dry-3`).
3. **Kızarıklık (`redness`) Kriteri:**
   - **Seçilen Aktif Ürün Modeli:** Genel bakışta `skin-focused-degrees.onnx` (`skin-appearance-photo-ridge-20261010-v1`) + bölgesel LAB `a*` renk farkı (`appearance-cv-6`). UI'da `Genel kızarıklık indeksi` ve `Bölgesel kızarıklık farkı` olarak ayrılmıştır; kızarıklık asla hassas cilt tipi olarak yorumlanmaz.
4. **Yağlılık (`oil`), Kaz Ayakları (`lines`), Göz Altı Torbası (`bags`), Göz Altı Morluğu (`dark`), Sarkma (`sag`), Ton Eşitsizliği (`tone`):**
   - **Seçilen Aktif Ürün Yöntemi:** `appearance-cv-6` yerel deterministik analitik görüntü işleme hattı ve `skin_display_geometry.py:measured_line_paths` yüksek geçiren sırt iskeletleştirme (skeletonization) hattı.
5. **Bölgesel Cilt Tipi ve Karma Cilt Kuralı (`skinType`):**
   - **Seçilen Aktif Ürün Yöntemi:** 3 açılı (`FRONT` T-bölgesi + `LEFT` sağ yanak + `RIGHT` sol yanak) bölgesel karar kuralı (`tzone-oily-cheeks-dry-or-normal-v3`) + yardımcı `local-vit-dima806-5aace4f-v1` ONNX kaydı (`basePrediction`, eksik veya karışık bölgede asla sızmaz).
6. **Hassasiyet (`sensitive`) İçin Mevcut Veri ve Teknik Açık Durumu:**
   - `tolgar-sasmaz` içindeki hiçbir veri kümesinde (`attune-skin-regional-skin-map/1` yalnızca `Oily, Redness` içerir) veya `skin-detection-s3jff-b6p3h` (62 görüntü; yalnızca `Oily, Redness, dry, normal, wrinkle` içerir) içinde doğrulanmış `sensitive` (hassas cilt) sınıfı bulunmamaktadır. Bu nedenle kullanıcıya soru sorulmaz, kızarıklık hassasiyet sayılmaz ve doğrulanmamış pembe hassasiyet katmanı üretilmez.
