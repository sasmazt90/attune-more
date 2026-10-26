# CODEX_HANDOFF — Cilt analizi: kayıp bulgu modelleri geri kuruldu, gerçek veri yolu

Hazırlayan: Claude (bulut oturumu `6c3a640c`). Güncelleme: 2026-10-26, Europe/Berlin.

Önceki teslimde (a1d3db4) yalnız 3 bulgu ölçülebiliyordu. Diğer 12 bulgunun karar modelleri ve tüm belirginlik
modelleri araştırmada hiç kaydedilmemişti. Kullanıcı bu turda bunların **aynı araştırma tarifleriyle yeniden
kurulmasını onayladı**. Kurulum şu kurallarla yapıldı:
- yeni veri, yeni model türü, hiperparametre araması, ücretli çağrı veya RF-DETR eğitimi yok;
- önbellekteki aynı özellikler, aynı etiketler, aynı katlar/tohumlar ve aynı eşik kuralı (`thr_prev`) kullanıldı.

Yalnızca kanıtlanan kapsam "TAMAM" sayıldı.

## 1. Teslim kimliği

| Alan | Değer |
|---|---|
| Repo | `sasmazt90/togg-health-mvp` (yeni adı `attune-more`). Görünürlük doğrulanamadı; herkese açık kabul edildi |
| Branch | `claude/skin-validated-20261025` (main'e merge yok, geçmiş yeniden yazılmadı) |
| Taban | `babe9b6970b011f65d642600aaa0ca2fd2b7f316` |
| Teslim commit'i | Teslim mesajındaki tam SHA |
| Push | Yapılmadı: repo (yeni adı `sasmazt90/attune-more`) herkese açık ve oturumun yazma izni yok. Teslim **git bundle + SHA-256** ile |
| Model dosyaları | Git'te **değil**: `findings-v2.tar.gz` (model paketine, yani `ATTUNE_REGIONAL_V3_DIR` altına açılır) + önceki 5 RF-DETR ağırlığı + dinov2-small |

```bash
sha256sum -c attune-skin-camera-color.bundle.sha256 && git bundle verify attune-skin-camera-color.bundle
git fetch attune-skin-camera-color.bundle claude/skin-validated-20261025:claude/skin-validated-20261025
tar -xzf findings-v2.tar.gz -C "$ATTUNE_REGIONAL_V3_DIR"          # -> $ATTUNE_REGIONAL_V3_DIR/findings-v2/*.json
```

**Çalışma zamanı paketleri** (RF-DETR paketiyle birlikte, `requirements.txt` dışında):
- rfdetr 1.11.2, torch, transformers;
- **mediapipe 0.10.32**: sivilce ve kızarıklıkta araştırmayla birebir bölge sınırları için gerekir. Yoksa istemci noktalarıyla çalışan yedek yola düşer: sapma artar ve kızarıklık ölçüsü üretilmez.
- scipy, opencv: mevcut.

**Kamera renk profili** (yeni, §5b): `ATTUNE_CAMERA_PROFILE=/yol/profil.json` araç kamerasının YUV matrisini/aralığını ve renk düzeltmesini verir. Tanımlı değilse renk düzeltmesi yapılmaz ve ham kare, karenin kendi etiketiyle çevrilir. E2E için `tests/e2e/fixtures/camera-profile-fixture-bt601.json` (yalnız test kamerası; araç profili değildir).

## 2. Bu turdaki commit'ler

| Commit | Özet |
|---|---|
| `fd3f183`, `a1d3db4` | Önceki tur: gerçek veri yolu (`general.findings`, `/skin/regional-fuse`), 4 arayüz hatası |
| `289d61b` | 7 DINOv2-kırpıntı sınıflandırıcısı (torba, kaz ayakları, uçuk, akne izi, alın çizgileri, egzama/sedef, pullanma) |
| `2edec5a` | Belirginlik (6 bulgu), sayım = işaretlenen lezyon, melazma alanı, pullanma sırası, "Görüldü" yerine değer |
| `e776aaa` | Yanlışlıkla eklenen geliştirme önizleme sayfasının çıkarılması |
| `1e40147` | Göz bulguları (morluk, kapak, kuyruk) |
| `8f38ac5` | Sivilce + kızarıklık; sivilce alt türleri; kızarıklık, rozasea ve egzama için alan/ton farkı |
| `e7f8c01` | Nodül satırı; E2E'ye video kaydı ve "her kartta sayı" kontrolü |
| `2ff9bd6` | Akne türleri açılır-kapanır bölüm (toplam satırı yok), sayı geçmişi grafiği, time-lapse E2E videosu |
| `ed63de9` | findings-v2 devir belgesi ve E2E kanıtları |
| (son) | Ham kamera karesi + sunucuda renk dönüşümü, araç kamerası renk kalibrasyonu, cilt arayüzü TR/EN/DE |

## 3. Veri yolu

```
Kamera → MediaPipe (tarayıcı) → poz kapıları (ön, yanlar 12–45°) → her poz POST /api/local-health/skin
  sunucu analyze_photo: RF-DETR × 5, bölgesel cilt tipi + findingEvidence/Boxes (dedektör), findingScores (DINOv2 kırpıntı LR),
                        severityTerms (Ridge satır terimleri), eyeScores/eyeMeasures (göz), findingDet (sivilce/kızarıklık) — yalnız sayılar
  → üç poz: POST /api/local-health/skin/regional-fuse → skin_findings_v1.findings_from_maps → general.findings
  → sağlık kaydı → sonuç ekranı → /skin?view=latest
```

## 4. Bulgu başına durum

Kayıtlı modellerin SHA-256 değerleri:
- `research/skin-findings/export/FINDINGS_V2_MANIFEST.json`;
- ayrıca her tarama sonucunun `findings.models` alanında, çalışma anında hesaplanmış olarak.

| Bulgu | Model (kaynak tarif) | Açı | Gösterilen değer | Karar doğrulaması (sentetik) |
|---|---|---|---|---|
| Göz altı torbası | DINOv2 alt göz kırpıntısı + LR ens. (`fa4.py`) | Ön + 20° | Belirginlik % (Ridge, ρ nested 0,58) | 80 test kişisi: P 0,89 R 0,44, **birebir tekrar** |
| Kaz ayakları | `fa4.py` köşe kırpıntıları | Ön + 20° | Belirginlik % (ρ 0,67) | P 0,94 R 0,81, birebir |
| Uçuk | `fa4.py` dudak kırpıntısı | Ön + 20° | İşaretlenen uçuk sayısı; işaret yoksa "1+" | P 1,00 R 0,54, birebir |
| Akne izi | `fa4.py` yanak/çene | Ön + 20° | Belirginlik % (ρ 0,41) | 22 kişi: P 0,83 R 0,83, birebir |
| Alın çizgileri | DINOv2 alın, tüm 190 kişide kurulu (`alin_repro.py`) | Ön + 20° | Belirginlik % (ρ 0,60) | iç içe CV: P 0,86 R 0,85 |
| Egzama/sedef eğilimi | `ecz_flake2.py` bölge LR (340 kişi) | Ön + 20° | Işık düzeltmeli kızarık alan % + ton farkı | iç içe CV: P 0,85 R 0,69 |
| Pullanma | `ecz_flake2.py` (290 kişi) | Ön + 20° | Pul dokusu (c_flake) sırası % | iç içe CV: P 0,92 R 0,78 |
| Göz altı morluğu | Işık düzeltmeli renk (`eye_grid3.py`) | Ön | Belirginlik % (gömme-only kol, ρ 0,66; araştırmada seçilen kombinasyonun bir girdisi yeniden üretilemedi) | iç içe CV: P 0,89 R 0,46, birebir |
| Göz kapağı düşüklüğü | Geometri + DINOv2 (`eye_fair3.py`) | Ön | Belirginlik % (ρ 0,69) | P 0,83 R 0,79, birebir |
| Göz kuyruğu düşüklüğü | Geometri + DINOv2 (`eye_fair3.py`) | Ön | Eğim sırası % (pozitifler arasında; derecelendirmeyle doğrulanmadı, AUC 0,66) | P 0,82 R 0,51. **Kurulu eşik 0,668 araştırma ort. 0,82'den düşük** (§8) |
| Sivilce | Dedektör özellik birleşimi LR (`lesion_eval.py`) | Ön + 20° | Lezyon sayısı + alt türler (siyah nokta, beyaz nokta, papül, püstül, nodül, tanımlanamayan; toplam = toplam) | P 0,86 R 1,00 (6 pozitif), birebir |
| Kızarıklık | Dedektör LR (`redness_prev.py`) | Ön + 20° | Kızarık alan % + cilde göre ton farkı | P 0,86 R 0,97, birebir (eski belgedeki 0,89/1,00 ~25° satırıydı) |
| Ben | findings.pt `Riskli Ben` ≥ 0,58 | Ön + 20° | İşaretlenen ben sayısı | P 1,00 R 0,30 |
| Melazma | findings.pt `Gunes Lekesi` ≥ 0,54 | Ön + 20° | Leke kutularının yanak alanı % | P 0,83 R 0,56 |
| Rozasea eğilimi | findings.pt `Rozasea` ≥ 0,69 | Ön + 20° | Kızarık alan % + ton farkı | P 1,00 R 0,82 |
| Türü belirlenemeyen leke | — | — | `unavailable / NOT_VALIDATED` | %80 kesinliğe hiç ulaşmadı |

Notlar:
- **Test kümesi:** "80 test kişisi" yöntem seçiminde de kullanıldı; **bağımsız doğrulama değildir**. Tüm sonuçlar sentetik veridir.
- **Doğrulanmamış değerler:** Sayımlar, alt tür ayrımı, alanlar, ton farkı ve sıralar gerçek etiketle doğrulanmadı.
- **Sayım kuralı:**
  - Skoru ≥ 0,35 olan kutular sayılır (araştırmadaki n35 tanımı); bir konum tek lezyon sayılır.
  - Her bölge tek fotoğraftan sayılır: alın, burun ve çene ön fotoğraftan; yanaklar onları gösteren yan fotoğraftan.
  - Gösterilen sayı, çizilen işaret sayısına eşittir.
- **Belirginlik:** Claude'un kör 1–3 derecelendirmesine karşı Ridge modeli. Değer, sentetik pozitifler arasındaki sıradır (persentil); klinik şiddet değildir.

## 5. Arayüz

- **Değerler:** Görülen her bulgu bir sayı veya yüzde gösterir ("Görüldü" metni yok).
- **Sivilce kartı:** Toplam sayı kartın tepesinde. Alt türler "Akne türleri" başlıklı, başlangıçta kapalı, tıklanınca açılan bölümde (ayrı toplam satırı yok; satırların toplamı = üstteki sayı).
- **Geçmiş grafiği:** Sayılan bulgularda (sivilce, ben, uçuk) tarihe göre sayı; diğerlerinde belirginlik %. Tarih aralığı seçicisi her ikisinde çalışır.
- **Kızarık bölgeler:** "Cilt tonunuza göre kırmızılık farkı" satırı gösterilir.
- **Öneri bandı:** Sayıdan veya yüzdeden seçilir. Değer yoksa bant seçilmez.
- **Diller:** Cilt sonuç ekranındaki tüm metinler TR/EN/DE.
  - `test_localization` geçiyor; `test_skin_findings_i18n.py` her kart, diyalog ve bandı EN/DE çizerek Türkçe kalmadığını denetliyor.
  - `tests/e2e/skin_i18n_screens.py`: üç dilde ekran görüntüsü, Türkçe satır yok, taşan buton/sekme metni yok.
  - Almanca uzun etiketler kısaltıldı (ör. "Augenpartie", "Weißköpfchen").
- **Önceki tur düzeltmeleri korundu:** tarih aralığı, tam gün filtresi, işaretlerin kendi pozunda çizilmesi, etiket boşlukları.

## 5b. Kamera renk yolu ve araç kalibrasyonu (kullanıcı onaylı öneriler 1 ve 3)

**Bulunan neden (ölçüldü):**
- E2E'nin yazılım GPU'sunda Chrome kamera karesini NV12 olarak veriyor ve **BT.709** diye etiketliyor; test videosu ise BT.601 (OpenCV) ile kodlanmış.
- Tarayıcı yanlış matrisle çeviriyor: yüzde R/G yaklaşık +2,5/255.
- Ham karenin Y düzlemi videoyla bayt bayt aynı; BT.601 ile sunucuda çevrilince fark 0,16'ya iniyor.
- GPU bayrağı olmadan Chrome I420 veriyor (etiketsiz) ve doğru çeviriyor. Yani sorun karenin etiketine bağlı.

**1 — Ham kare** (`utils/skinRawFrame.ts`, `services/core-api/camera_color.py`):
- Tuvale çizilen karenin aynısı WebCodecs `VideoFrame` ile alınır; I420/NV12 düzlemleri + renk etiketi /skin isteğine `rawFrame` olarak eklenir. Kayda yazılmaz.
- Sunucu önce PNG kimliğini doğrular, sonra ham kareyi çevirir. Matris önceliği: araç profili → kare etiketi → BT.601 sınırlı aralık. Boyut aynı olmalı.
- Analiz edilen piksellerin hash'i `cameraColor.analyzedPhotoSHA256`; yanıttaki `photoId` istemcinin kimliği olarak kalır.
- Tarayıcı ham kare veremezse (WebCodecs yok, GPU dokusu, başka format) eski PNG yolu sürer: `cameraColor.source='browser-rgb'`.

**3 — Araç başına renk kalibrasyonu** (`camera_calibration.py`, `scripts/camera-calibration/`):
- `make_chart.py`: basılabilir A4 kart (4 ArUco işaret + 24 renk yaması, 300 dpi PNG + PDF).
- `fit_profile.py` veya servis uç noktası `POST /api/local-health/skin/camera-calibration` (yalnız `ATTUNE_CAMERA_CALIBRATION=1` iken açık): karttan doğrusal ışıkta 3×3 renk matrisi + ofset uydurur.
- Kalite kapıları (mühendislik seçimi, cilt sonucuyla doğrulanmadı): 4 işaret, ≥20 kullanılabilir yama, ΔE00 ort. ≤3 / maks. ≤8, birini-dışarıda-bırak ort. ≤4. Geçmezse profil yazılmaz.
- Varsayılan referans renkleri ColorChecker Classic nominal sRGB değerleridir. Ev yazıcısı bunları tam basmaz; üretimde sertifikalı kart değerleri veya spektrofotometreyle ölçülmüş değerler `--reference` ile verilmeli.

**Kalibrasyonun etkisi (sentetik, `check_skin_effect.py`):** Aynı yüz noktalarıyla üç durum: orijinal / simüle kamera renk kayması / kayma + karttan uydurulan düzeltme.
- Kart üzerinde ΔE00 3.67 → 0.24.

| Kişi | Orijinal görülen | Kaymalı | Düzeltilmiş |
|---|---|---|---|
| K-217 | 11 | 7 (kayıp: eyeBags/periorbital, foreheadLines/forehead, rosacea/nose, rosacea/rightCheek; fazla: —) | 11 (kayıp: —; fazla: —) |
| K-074 | 7 | 4 (kayıp: redness/nose, rosacea/nose, rosacea/rightCheek; fazla: —) | 6 (kayıp: redness/nose; fazla: —) |
| K-258 | 3 | 4 (kayıp: —; fazla: downturnedCorners/periorbital) | 4 (kayıp: —; fazla: downturnedCorners/periorbital) |

Düzeltme etkiyi azaltıyor ama tamamen gidermiyor (K-074'te 1 kayıp, K-258'de 1 fazla kalıyor). Gerçek kamera ve gerçek kartla denenmedi.

## 6. Doğrulama

### 6.1 Otomatik
- Bu tur sonu `pytest tests/unit`: 1446 geçti, 45 atlandı, 6 başarısız (yolox ×5, özel model.onnx ×1; tabanda da başarısız). Yeni: `test_camera_color.py` 12, `test_skin_findings_i18n.py`.
- Önceki tur `pytest tests/unit`: 1427 geçti, 45 atlandı, 7–8 başarısız. Başarısızların **hepsi taban `babe9b6`'da da başarısız** (temiz klonda denendi):
  - `test_acne_objectness_features` ×5: `yolox` modülü yok;
  - `test_hosted_skin_type_runtime`: bu dizindeki özel `model.onnx`;
  - `test_localization`: tabandan gelen eksik mesajlar (bu turda eksik sayısı azaldı, yeni eksik yok);
  - `test_skin_neutral_capture` ses testi: zaman aşımına bağlı, tekrar çalıştırmada geçti.
- Cilt bulgusu testleri (`test_skin_findings_v1.py` 10, `test_skin_findings_ui.py` 4): geçti.
- `tsc --noEmit`: 0 hata. `npm run lint`: uyarı/hata yok. `npm run build`: başarılı.

### 6.2 Örnek veriyle arayüz testi (model çıktısı değil)
`tests/e2e/current_skin_findings_sample_ui.py --chromium`: **PASS**. Elle yazılmış kayıt (değerler örnektir):
- genel bakış kartları (sivilce, rozasea, melazma, ben), çubuk üstünde değer, ölçülemeyen/kesinleştirilemeyen sayıları;
- sivilce: sayı 7; "Akne türleri" kapalı açılıyor, satırlar = alt türler, toplamları 7, "Toplam" satırı yok; sayı geçmişi 3 tarama;
- rozasea geçmişi, tarih aralığı (başlangıç değişir, bitiş seçilebilir), tam gün filtresi (önceki akşam hariç);
- değer yoksa bant yok; ben bandı sayıdan.

### 6.3 Gerçek model inference testi
Bu test sahte kamera aygıtıyla yapıldı; **fiziksel kamera değildir**. Sentetik fotoğraflardan üretilen y4m oynatıldı ve **video kaydı alındı**.
`tests/e2e/current_skin_contract.py --chromium --software-gpu --skip-native-zoom`: kamera → /skin ×3 → /skin/regional-fuse → kayıt → sonuç ekranı → yeniden açılan kayıt. Her poz gerçek RF-DETR + DINOv2 + kayıtlı modellerle. Her görülen kartta sayı/yüzde kontrolü.

| Kişi | Sonuç | Süre | Görülen (kamera yolu) | Ölçülemeyen |
|---|---|---|---|---|
| K-217 | PASS | 351 s | sivilce alın 3 papül + burun 1+; kızarıklık sağ %57,5 / +5, sol %38,8 / +3; kaz ayakları %15; uçuk 1+ | spots |
| K-074 | PASS | 174 s | rozasea burun %29,4 / sağ %36,9 / sol %34,8 (ton +3); kızarıklık iki yanak; göz kuyruğu %60,6 | spots |
| K-258 | PASS | 223 s | sivilce alın 3 (1 papül, 2 tanımlanamayan) + burun 1+; göz kapağı %0,6 | spots |

**Ham kare yoluyla K-217** (`SKIN_E2E_EXPECT_RAW=1`, fixture profili): **PASS**, 228 s.
- 3 pozun hepsi `raw-yuv`: NV12, kare etiketi bt709, profil bt601 ile çevrildi; tarayıcı RGB'sinden ortalama fark 0,58–0,62.
- Görülenler: sivilce alın 3 + burun 1+, kızarıklık sağ %56,7 / +5 ve sol %38,5 / +3, rozasea sağ yanak %56,7 / +5, kaz ayakları %13,3, alın çizgileri %4, uçuk 1+, göz kuyruğu %0.
- Tarayıcı yoluna göre **alın çizgileri ve rozasea geri geldi**. Torba hâlâ görülmüyor. Göz kuyruğu yeni çıktı, belirginliği %0 (eşik sınırında; §8.2).

Yeni arayüzle (2ff9bd6) K-217 tekrar koşuldu: **PASS**, aynı bulgular ve değerler (`e2e-v2/K-217-newui-*`); süre 954 s, çünkü aynı anda pytest çalışıyordu.

Kamera yolu ile doğrudan yol arasındaki farklar (§8.1):
- K-217: doğrudan yolda ayrıca torba, alın çizgileri ve rozasea görülüyor; kamera yolunda eşik altında kaldılar.
- K-258: doğrudan yolda alında 4 papül; kamera yolunda 3 lezyon (1 papül + 2 tanımlanamayan).

Video: her koşuda `run-timelapse.mp4` (1,5 s'de bir kare). Canlı Playwright videosu CPU'yu doldurup /skin 45 s bütçesini aşırdığı için (504) varsayılan time-lapse; `--video-full` ile canlı video alınabilir.

### 6.4 Doğrudan model kontrolü
Orijinal sentetik fotoğraflar, sunucunun kendi koduyla çalıştırıldı:
- K-217 (etiketler: uçuk, torba, morluk, kaz ayakları, alın): uçuk, kaz ayakları, torba, alın çizgileri, rozasea, sivilce ve kızarıklık "görüldü". Morluk görülmedi.
- K-258: sivilce (alında 4 papül), göz kapağı düşüklüğü.
- K-040: uçuk, kaz ayakları, torba, göz kapağı.
- Bu kişilerin bir kısmı eğitim kümesindendir; bu kontroller doğruluk kanıtı değildir.

### 6.5 Fiziksel kamera, Windows launcher, araç ekranı
**TEST EDİLMEDİ.**

## 7. Model manifesti

Hash'ler:
- `research/skin-findings/export/FINDINGS_V2_MANIFEST.json`: 20 dosya.
- `research/skin-findings/MODEL_MANIFEST.json`: 5 RF-DETR modeli, DINOv2 ve diğerleri.

Raporlar:
- `REPORT_dino.json`, `REPORT_sev.md`, `REPORT_eye.md`, `REPORT_det.md`;
- tekrar ve eşdeğerlik (parity) betikleri: `research/skin-findings/export/`.

Özellik eşdeğerliği:
- DINOv2 kırpıntıları: |Δ| 0.
- Göz özellikleri: 140/140 kişide eşit.
- Sivilce ve kızarıklık: mediapipe ile 0,003 olasılık içinde.

## 8. Açık engeller

1. **Eşik ve kamera hattı:** Eşikler araştırma PNG'lerinde seçildi. Ham kare + profil yolu eklendi (§5b); gerçek araç kamerası profili ve kalibrasyonu yapılmadı.
   - Uygulamanın gönderdiği PNG orijinalden ort. 1,4/255 farklı. PNG kayıpsız olduğundan fark kodlamadan önce oluşuyor; büyük olasılıkla tarayıcının YUV420→RGB dönüşümü (kanıtlanmadı).
   - Etki: K-217 rozasea 0,757 (Python/ffmpeg ile aynı y4m) → 0,48–0,54 (uygulama yolu); eşik 0,69.
   - Eşikler P≥0,8 sınırına yakın olduğundan küçük renk kaymaları kararı çeviriyor.
   - Ölçülen neden: tarayıcının yanlış renk matrisi (§5b). Kullanıcı ham kare (1) ve araç kalibrasyonunu (3) onayladı; ikisi kuruldu. Beyaz denge kilidi, kare ortalama ve eşik yeniden doğrulaması kullanıcı kararıyla yapılmayacak.
2. **Göz kuyruğu eşiği:** Onaylanan kural kurulu eşiği 0,668 verdi; araştırma ortalaması 0,82. Bu yüzden daha fazla yanlış pozitif beklenir. Eşik değiştirilmedi; karar kullanıcıya bırakıldı.
3. **Göz altı morluğu belirginliği:** Araştırmada seçilen model yerine gömme-only kol kullanıldı (ρ 0,75 yerine 0,66).
4. **mediapipe gereksinimi:** Sunucuda mediapipe yoksa sivilce ve kızarıklık kararları araştırmadan sapabilir (testte 1 eşik geçişi).
5. **Bağımsız doğrulama yok:** Gerçek fotoğraf, klinik doğrulama ve dermatolog incelemesi yok. Öneri içerikleri de incelenmedi.
6. **Doğrulanmamış değerler:** Sayımlar, alt türler, alanlar, ton farkı ve sıralar doğrulanmadı. Seçilen bulgu ama işaretlenmeyen lezyon durumunda "1+" gösterilir.
7. **Sağlık Geçmişim penceresi:** Eski bölge görünümünde; bulguları göstermiyor. Kayıt bulguları taşıyor ve `/skin?view=latest` bunları gösteriyor. Tasarım kararı bekliyor.
8. **`/skin/regional-fuse` güveni:** İstemcinin gönderdiği poz sayılarına güvenir (imza yok).
9. **Test edilmeyenler:** Fiziksel kamera, Windows launcher, araç ekranı, erişilebilirlik denetimi ve kullanıcı kabulü.
10. **Git geçmişi:** `k_classifier.json` (model ağırlığı) Git geçmişinde duruyor.
11. **Güvenlik açığı:** `npm ci` 1 kritik açık bildiriyor.
12. **Ortama bağlı test:** `test_hosted_skin_type_runtime` bu dizindeki özel `model.onnx` yüzünden başarısız; temiz klonda geçiyor.
13. **Tabandan gelen hatalar:** `test_acne_objectness_features` (yolox yok). `test_localization` artık geçiyor (cilt kataloğu kimlikleri düzeltildi).
16. **Kalibrasyon kartı referansı:** Nominal değerler; basılan kartın ölçülmesi gerekir. Kalibrasyon uç noktası servis bayrağıyla açılır, kimlik doğrulaması yok (servis modu varsayımı).
17. **Ham kare boyutu:** /skin isteği poz başı ~4 MB büyüdü (PNG + NV12). Yerel ağda ölçülmedi; 45 s bütçe içinde kaldı (228 s / 3 poz toplam E2E).
15. **/skin süre bütçesi:** Sunucu bütçesi 45 s; bu ortamda poz başı ~6–8 s. Yavaş araç donanımında aşılabilir; ölçülmedi.
14. **Önceki turdaki yanlış bilgi:** K-236 "etiketsiz" diye yazılmıştı; yanlış. K-236'nın uçuk ve yanak sarkması etiketleri var.

## 9. Geri dönüş

- Bu turdan önce: `a1d3db4f479a471204e3f42694cbc2d258fddc50`.
- Tüm Claude değişikliklerinden önce: `babe9b6`.

## 10. Codex inceleme komutu

```text
Görev: claude/skin-validated-20261025 (taban babe9b6) teslimini bağımsız denetle; kodu değiştirme.
CODEX_HANDOFF.md §3–§8 ve research/skin-findings/export/REPORT_* dosyalarını oku. Bilinen engeller muaf değildir.
1. Bundle SHA-256 + git bundle verify; findings-v2.tar.gz hash'lerini FINDINGS_V2_MANIFEST.json ile karşılaştır.
2. npm ci / typecheck / lint / build; pytest tests/unit.
3. Yeniden kurulan modellerin araştırma tablolarını birebir tekrarladığını export betikleriyle doğrula
   (export_dino.py, export_eye.py, export_det.py, export_sev.py) — yeni veri/hiperparametre kullanılmadığını kontrol et.
4. Üretim özellik eşdeğerliği (parity betikleri) ve mediapipe yokken davranış.
5. Ekranda değer kuralları: her görülen bulguda sayı/yüzde; sivilce alt türleri toplamı = toplam; uydurma değer yok.
6. E2E: tests/e2e/current_skin_contract.py (gerçek inference, video) ve current_skin_findings_sample_ui.py (örnek veri) ayrı raporla.
Rapor: Bulgu | Önem | Kabul engeli mi | Dosya:satır | Yeniden üretme | Öneri.
```

## 11. İlerleme kaydı ve kanıtlar

- `claude-progress/realpath-20261026/status.json`: aşama kaydı.
- `claude-progress/realpath-20261026/e2e-v2/`: E2E kanıt JSON'ları; fotoğraf içermez.
- Videolar ve ekran görüntüleri teslim paketinde; Git'te değil, çünkü sentetik yüzler içeriyor.
