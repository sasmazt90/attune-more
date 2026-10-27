# Codex devri — Diş Sağlığı (2026-10-27)

Bu belge, `fix/dental-flow-ui-20261027` dalındaki Diş Sağlığı çalışmasının bağımsız
Codex incelemesi içindir. **Nihai kabul verilmemiştir**; kabul, Codex incelemesi ve
fiziksel kamera/AAOS testinden sonra kullanıcıya aittir.

- Taban: `main` @ `def0bef883d869700d610cc8d5de17e543b7032d`
- Dal: `fix/dental-flow-ui-20261027` (main'e merge edilmedi)
- Durum kaydı: `claude-progress/dental-20261027/status.json`
- Kapsam dışı ve dokunulmayanlar: Cilt, Kulak, Göz, Mental davranışları; AAOS/native host,
  WebView köprüsü, OEM entegrasyonu; model ağırlıkları, manifest, eşikler; eğitim/veri üretimi.

## 1. Gerçekte yüklenen model ve sonuç alanlarının kaynağı

| Alan | Kaynak | Not |
|---|---|---|
| `caries` (Çürük adayı) | Eğitilmiş ONNX `services/core-api/models/dental-yolox-s.onnx` | SHA-256 `eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03` (manifest `modelHash` ile ve kullanıcının verdiği hash ile aynı). Manifest `dental-yolox-s.json` SHA-256 `caf99b66…5da5`, değişmedi. |
| `accumulation` (Birikim görünümü) | Model değil; `calculus_candidates` renk/doku/gradyan sezgiseli (`dental-border-cv-v2`) | Etiketli doğrulaması yok. |
| `alignment` (Ön diş dizilimi) | Model değil; `contours_and_alignment` marker-watershed kontur yön dağılımı | Yalnız BITE (kamera) veya iki sıra görünen yüklemede. Etiketli doğrulaması yok. |
| Önizleme/örnek veri | Ürün yolunda yok | Sonuçlar yalnız backend yanıtından çizilir. |

Çalışma zamanı zinciri (`dental_analysis.model_candidates`), eğitim kodu
(`scripts/train_dental_yolox.py`) ile karşılaştırıldı:
- Renk sırası: `cv2.imdecode` → **BGR**; eğitim `cv2.imread` → BGR. ✔
- Ön işleme: sol-üst hizalı letterbox, dolgu 114, `min(320/h,320/w)`, normalizasyon yok. ✔
- Girdi: ağız içi ROI + %15 kenar (kamera) / yüklemede tespit edilen bölge; koordinatlar `/ratio + origin` ile kaynak fotoğrafa döner. ✔ (EXIF yönü 6 olan kontrol fotoğrafında işaretler doğru dişlerde.)
- Decoder: çıktı `(1,2100,7)` = `cx,cy,w,h,obj,D,d`; skor `obj*cls`, `argmax` sınıf. ✔
- Eşik: manifest `confidenceThreshold=0.35` (kodda da sabit doğrulanıyor). NMS: sınıf bazlı `cv2.dnn.NMSBoxes(…, 0.35, 0.45)`; eğitim değerlendirmesi `postprocess(…, .001, .45)` — eşik-sonra-NMS ile NMS-sonra-eşik tutulan küme için eşdeğer. Manifestte NMS alanı yok; 0.45 kodda sabit. ✔
- Sınıflar: `D` kalıcı diş çürük adayı, `d` süt dişi çürük adayı — şiddet değil. Ürün `adult-permanent-D-only-v1` politikasıyla yalnız `D` gösterir.
- Ek ürün filtresi: kutu merkezi ağız maskesinde ve kutunun ≥%65'i maskede olmalı (eğitim değerlendirmesinde yok; kamera yolunda recall'u etkileyebilir).

## 2. Hata → düzeltme → kanıt

| # | Hata (önce yeniden üretildi) | Düzeltme | Kanıt |
|---|---|---|---|
| 1 | `calculus_candidates` her bileşen için tam kare tarıyor (`tooth.sum()` + `labels==i`); büyük yüklemelerde 10 s+ (gözlenen bir test görüntüsünde dakikalar), 30 s yerel bütçeyi aşma | Toplam bir kez; kontur her bileşenin kendi kutusunda `offset` ile | Eski/yeni çıktı 9 gerçek görüntüde byte-düzeyinde aynı; 9.9 s → 0.4 s. `tests/unit/test_dental_bite_contact.py::test_border_candidates_identical_to_previous_implementation` (eski uygulama kahin olarak) |
| 2 | BITE kapısı dudak açıklığı `≤ 0.32` ile kapanışı “doğruluyor”: açık ağızlı kareler (FRONT sentetik: 0.33 ↔ yan pozlar 0.29) kapanış sayılabiliyor; geniş gülümsemeli gerçek kapanış (>0.32) reddediliyor. Kullanıcı şikâyeti: kapanış kapısı uzun sürüyor | `incisal_contact` (`incisal-contact-v1`): merkez ±%25 sütunlarda mine dudak orta çizgisinin iki yanında ve dikey mine boşluğu ≤ 0.04×ağız genişliği; sütunların ≥%60'ı. Backend ve istemci aynı kural (`DENTAL_BITE_CONTACT`). Yükleme yolu değişmedi (`pose_check=False`) | Sentetik kareler: açık ağız boşluk 0.118 → red; kapanış 0.0 → kabul. Birim: `test_dental_bite_contact.py`, eşdeğerlik `tests/unit/dental_bite_contact_parity.cjs`. E2E `no-bite` fikstürü: BITE adımında açık ağız kabul edilmedi. Yükleme yolu kabul sayısı değişmedi (153/347). |
| 3 | Tek görünüm backend'de ölçülemezse (`quality.valid=false`) istemci tüm 4 pozu “Diş sonucu ve kaynak geometrisi doğrulanamadı” ile atıyor | `validateDentalView` ölçülemeyen görünümü katı şekilde (null değer, işaret yok, gerekçe zorunlu) kabul eder; UI “Ölçülemedi” + gerekçe + yeniden tarama daveti; hiç ölçülen görünüm yoksa hata | Gerçek backend yanıtıyla düğüm testinde önce `REJECTED`, sonra kabul. `dental_bite_contact_parity.cjs` (eski doğrulayıcıyla başarısız olduğu doğrulandı). E2E `partial-response`. |
| 4 | Aynı kare iki poza atanabiliyor (görüntü donması/döngü) → tarama sonunda 422 `DUPLICATE_CAPTURE` | İstemci aynı `photoId`'yi ikinci poza eklemez, beklemeyi sürdürür | İlk bulut E2E'de FRONT ve BITE aynı `photoId` → 422 (kayıt: `claude-progress/dental-20261027/e2e`). Düzeltme sonrası tüm koşularda 4 farklı `photoId`. |
| 5 | Tutma süresi tek bir başarısız karede sıfırlanıyor; ayrıca anlık kare yakalanıyor | Tek geçici kare toleransı (`DENTAL_HOLD_GRACE_FRAMES=1`; hareket/yüz kaybı her zaman sıfırlar); tutma süresince **tamamen geçerli** en net kare (kendi landmark'larıyla) kaydedilir | Sentetik “her 4. kare bulanık” kapanış: main 3 sıfırlama, ~7.7 s; dal 0 sıfırlama, ~4.2 s. Statik pozlarda tutma→yakalama süresi değişmedi (~1.6–2.2 s). |
| 6 | Kapanış gösterilemeyen kullanıcı (ör. ön açık kapanış) için çıkış yok | BITE adımında 20 s sonra “Kapanış görünümünü atla”; backend 3 pozu (`FRONT,RIGHT,LEFT`) kabul eder, `missingViews:['BITE']`; dizilim “Kapanış görünümü alınmadı” (sağlıklı/0 değil) | E2E `skip-bite`: 3 görünüm, kayıt + geçmiş BITE “Alınmadı”. |
| 7 | Atla düğmesi ile döngü yarışı: kapanan yüz modeli “Yüz modeli yanıt vermedi” hatası verip analizi iptal ediyordu (yalnız yeni düğmede) | Döngü `skipped` bayrağını kontrol eder | E2E `skip-bite` ilk koşu hata, düzeltme sonrası 200. |
| 8 | Sonuç ekranı tüm yüzü gösterdiği için işaretler okunmuyor; FRONT/yan pozlarda dizilim yokken “konturlar ayrılamadı” deniyordu | Backend her kamera görünümüne `quality.roi` (iç ağız sınırı) ekler; UI aynı fotoğrafı bu bölgeye kırpar, işaretler kaynak pikselde kalır; yan pozlarda “Kapanış görünümünde ölçülür” | `data-dental-crop`, `data-dental-photo` E2E kontrolleri; geçmişte fotoğraf kimliği kayıtla eşleşiyor. |
| 9 | “Diş taşı birikimi” etiketi doğrulanmamış renk sezgiselini diş taşı gibi sunuyor | Etiket “Birikim görünümü” (bilgi metni: diş taşı tanısı değildir). `test_dental_adult_scope.py` sabitlenmiş etiket güncellendi | **Kullanıcı onayı gerekir** (tek satır geri alınabilir: `DENTAL_ACCUMULATION_LABEL`). |

Yeniden üretilip **hata bulunmayan** yaşam döngüsü durumları (önceki kodda da doğru): park
durumundan çıkış, kamera izni geri çekme, işleme izni geri çekme (izin kapısı sayfayı
kaldırıyor), kayıt/silme (sayısal kayıt + IndexedDB fotoğrafı birlikte silindi).

## 3. Raporlar (ayrı ayrı)

### 3a. Örnek/sentetik veriyle arayüz ve akış testi
- Girdiler kullanıcı tarafından sentetik olarak işaretli; klinik kanıt değildir.
- Kamera: `--use-file-for-fake-video-capture` ile y4m (1920×1080, 3 fps), gerçek MediaPipe yüz modeli ve gerçek kalite/poz/sabitlik kapıları. Not: dosya adları kamera perspektifinde; `dental_left_full` uygulamanın anatomik **sağ** pozunu, `dental_right_full` anatomik **sol** pozu karşılıyor.
- Sonuç: FRONT→RIGHT→LEFT→BITE 4/4 yakalandı; kaydet → geçmişten aç (kendi fotoğrafları, `photoId` eşleşmesi) → sil (kayıt 0, IDB anahtarı yok) PASS.
- Sentetik görüntülerdeki işaret sayıları doğru cevap kabul edilmedi (BITE'ta 1 aday işaretlendi; etiket yok).

### 3b. Etiketli veriyle model doğruluğu (eğitim yok, eşik yok, ayrım yeniden oluşturulmadı)
`scripts/dental_heldout_product_eval.py` — `dataset-split.json` SHA-256
`2b599595…6b784` manifestteki `inventorySHA256` ile aynı; 347 test görüntüsü.

| Yol | Sınıf | TP | FP | FN | Kesinlik | Duyarlılık | F1 |
|---|---|---|---|---|---|---|---|
| Ürün decoder'ı (tüm kare) | D | 898 | 223 | 160 | 0.801 | 0.849 | 0.824 |
| | d | 30 | 28 | 33 | 0.517 | 0.476 | 0.496 |
| — yalnız ön/yan görünümler (31 görüntü) | D | 13 | 11 | 25 | **0.542** | **0.342** | 0.419 |
| | d | 0 | 2 | 7 | 0 | 0 | 0 |
| — okluzal görünümler (316) | D | 885 | 212 | 135 | 0.807 | 0.868 | 0.836 |
| Ürün yükleme yolu (kapılar dahil, yalnız D) | D (kabul edilen 153) | 413 | 71 | 62 | 0.853 | 0.869 | 0.861 |

- Ürün decoder'ı dondurulmuş manifest sayılarını **birebir** üretti.
- Yükleme yolu 194/347 fotoğrafı reddetti (TONGUE_OCCLUSION 125, BLURRY 64, …); reddedilen fotoğraf sonuç üretmez, negatif sayılmaz. Tüm test D'lerine göre duyarlılık 0.39.
- Sınırlamalar korunur: hasta bağımsızlığı doğrulanmadı (`patientIndependent=false`), etiketsiz görüntüler hariç → sağlıklı özgüllüğü ölçülmedi, klinik doğrulama yok.

### 3c. Gerçek modelle API ve kayıt/geçmiş E2E (temiz süreç)
- `next build` + `next start` (3310), temiz `ATTUNE_DATA_DIR` ile `uvicorn main:app` (8310), anahtar/ücretli servis yok.
- Matris ve sonuçları: `claude-progress/dental-20261027/e2e/summary.json`.

| Senaryo | Girdi | Sonuç |
|---|---|---|
| Kamera 4 poz + kaydet + geçmişten aç + sil | `dental-ordered.y4m` | API 200, 4/4 ölçüldü, kayıt fotoğrafları `photoId` ile eşleşti, silmede kayıt 0 / IDB anahtarı 0 — PASS |
| Fotoğraf saklama izni kapalı | aynı | Yalnız sayısal kayıt; geçmişte 4 görünüm de “Bu kayıtta fotoğraf saklanmadı” (canlı tarama fotoğrafı gösterilmedi) — PASS |
| Kapanış gösterilemiyor → atla | `dental-no-bite.y4m` (BITE adımında yalnız açık ağız) | Açık ağız kapanış sayılmadı; 20 s sonra atla; API 200 (3 görünüm); geçmişte BITE “Alınmadı” — PASS |
| Bir görünüm ölçülemedi | gerçek yanıt, BITE backend'in yetersiz şekline çevrildi | 3 ölçüldü + 1 “Ölçülemedi” (gerekçe + yeniden tarama daveti), kayıt/geçmiş korunur — PASS |
| Park durumundan çıkış (tarama sırasında) | — | Kamera durdu, istek yok, “Diş taraması yalnız PARK durumunda yapılır.” — PASS |
| Kamera izni geri çekme | — | Kamera durdu, istek yok — PASS |
| İşleme izni geri çekme | — | İzin kapısı sayfayı kaldırdı, kamera durdu, istek yok — PASS |
| Yükleme: yakın çekim ön/sağ/sol, portre, EXIF(6), okluzal | 6 dosya | 200, kırpma doğru kaynakta, EXIF yönü doğru, kayıt/geçmiş/silme — PASS |
| Yükleme: dişsiz negatif | `negative_6.jpg` | 422 `TEETH_NOT_VISIBLE_OR_NON_COLOR_IMAGE`, sonuç yok — PASS |
| Yükleme: yakın çekim kapanış | `dental_front_bite.jpg` | 422 `TONGUE_OCCLUSION` — **yanlış red (açık bulgu 3)** |

### 3d. Fiziksel kamera ve AAOS/araç testi
**Yapılmadı.** Cloud'da fiziksel kamera ve AAOS emülatörü çalıştırılmadı. Kapanış kapısının gerçek
kullanıcıdaki süresi ve `incisal-contact-v1` eşiği (0.04, %60) gerçek kamerayla doğrulanmalıdır.

## 4. Açık hatalar, model sınırları, doğrulanmamış katmanlar
1. **Model sınırı (engel):** ürünün kamera görünümlerinde D kesinlik 0.54 / duyarlılık 0.34 (n=31 görüntü, 38 lezyon). Yeniden eğitim başlatılmadı; kullanıcı kararı gerekir.
2. Birikim görünümü ve dizilim metrikleri etiketli veriyle doğrulanmadı; sentetik düz dişlerde dizilim 25°/39° gibi yüksek dağılım verdi.
3. Yükleme yolunda TONGUE_OCCLUSION, yüz landmark'ı olmayan yakın çekimlerde dudakları dil sayıyor (`dental_front_bite.jpg` yakın çekimi reddedildi). Kapı gevşetilmedi; ayrı karar/çalışma gerekir.
4. Yükleme kapısı BLURRY (Laplasyen < 12) yüksek çözünürlüklü profesyonel fotoğrafların bir kısmını reddediyor (çözünürlüğe bağlı ölçüm). Değiştirilmedi.
5. Önceden var olan ve bu dalda değişmeyen başarısız testler (main'de de başarısız): `pytest tests/unit` 12 başarısız + 9 hata (torch/pycocotools gerektiren cilt/akne araştırma testleri), 6 `.cjs` cilt/paylaşım testi. Diş testleri 46/46 geçti.
6. `tests/e2e/dental_*.js|py` eski Windows kanıt yollarına bağlı; Cloud'da çalıştırılamadı. Yerine `tests/e2e/dental_cloud_flow.cjs`.
7. `components/DentalSourceView.tsx` artık kullanılmıyor; eski kapanış doğrulayıcısı (`scripts/verify_dental_closeout.py`) dosya listesine bağlı olduğu için silinmedi.

## 5. Yeniden üretme komutları
```bash
# Ortam: Node 22.20.0 + npm 10.9.3, Python 3.11+/3.13
npm ci && pip install -r services/core-api/requirements.txt
python -m pytest tests/unit/test_dental_*.py -q
node tests/unit/dental_bite_contact_parity.cjs
npm run typecheck && npm run lint && npm run build
ATTUNE_TOOL_PYTHON=python3 node scripts/localization/check.cjs
# Model doğruluğu (özel veri Git dışında):
python scripts/dental_heldout_product_eval.py --data-root <özel-kök> \
  --split <özel-kök>/training/dataset-split.json --out heldout-product-eval.json
# E2E (backend 8310 + next start 3310 çalışırken):
node tests/e2e/dental_cloud_flow.cjs <fikstür.y4m> <çıktı-klasörü> camera|skip-bite|partial-response|park-change|revoke-camera|revoke-consent|no-photo-permission
node tests/e2e/dental_cloud_flow.cjs - <çıktı> upload:<foto.jpg>
```

## 6. Kullanılan girdiler ve hash'ler
Bkz. `claude-progress/dental-20261027/status.json` → `inputs`. Fotoğraflar, veri seti,
y4m fikstürleri ve ekran görüntülerinin fotoğraf içeren olanları Git'e eklenmedi.
