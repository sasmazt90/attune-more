# Codex devri — Diş Sağlığı (2026-10-27, tur 2)

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
| 6 | Kapanış gösterilemeyen kullanıcı (ör. ön açık kapanış) için çıkış yok | (Tur 2'de #17 ile genelleştirildi: her pozda 15 s.) BITE adımında 20 s sonra “Kapanış görünümünü atla”; backend 3 pozu (`FRONT,RIGHT,LEFT`) kabul eder, `missingViews:['BITE']`; dizilim “Kapanış görünümü alınmadı” (sağlıklı/0 değil) | E2E `skip-bite`: 3 görünüm, kayıt + geçmiş BITE “Alınmadı”. |
| 7 | Atla düğmesi ile döngü yarışı: kapanan yüz modeli “Yüz modeli yanıt vermedi” hatası verip analizi iptal ediyordu (yalnız yeni düğmede) | Döngü `skipped` bayrağını kontrol eder (tur 2: oturum mührü, #10) | E2E `skip-bite` ilk koşu hata, düzeltme sonrası 200. |
| 8 | Sonuç ekranı tüm yüzü gösterdiği için işaretler okunmuyor; FRONT/yan pozlarda dizilim yokken “konturlar ayrılamadı” deniyordu | Backend her kamera görünümüne `quality.roi` (iç ağız sınırı) ekler; UI aynı fotoğrafı bu bölgeye kırpar, işaretler kaynak pikselde kalır; yan pozlarda “Kapanış görünümünde ölçülür” | `data-dental-crop`, `data-dental-photo` E2E kontrolleri; geçmişte fotoğraf kimliği kayıtla eşleşiyor. |
| 9 | “Diş taşı birikimi” etiketi doğrulanmamış renk sezgiselini diş taşı gibi sunuyor | Etiket “Birikim görünümü” (bilgi metni: diş taşı tanısı değildir). `test_dental_adult_scope.py` sabitlenmiş etiket güncellendi | **Kullanıcı onayı gerekir** (tek satır geri alınabilir: `DENTAL_ACCUMULATION_LABEL`). |

Yeniden üretilip **hata bulunmayan** yaşam döngüsü durumları (önceki kodda da doğru): park
durumundan çıkış, kamera izni geri çekme, işleme izni geri çekme (izin kapısı sayfayı
kaldırıyor), kayıt/silme (sayısal kayıt + IndexedDB fotoğrafı birlikte silindi).

## 2b. Tur 2 — Codex bulguları ve araç içi çekim (hata → düzeltme → test)

| # | Hata (önce yeniden üretildi) | Düzeltme | Test / kanıt |
|---|---|---|---|
| 10 | **Codex P2 — atla yarışı:** `captureDental` beklerken “Atla” → önce 3 pozla, sonra tamamlanan BITE ile 4 pozla ikinci analiz | `utils/dentalCaptureSession.ts`: kaynak listesinin tek sahibi; liste bir kez mühürlenir, analiz mühürlü ve dondurulmuş kopyayı kullanır (`analyze(run,sources)`); mühürden sonra biten çekim `closed` döner, listeye giremez, ikinci analiz başlatamaz | Birim: `tests/unit/dental_capture_session.cjs` (gecikmeli `captureDental`). Tarayıcı: `dental_cloud_flow.cjs skip-race` — `crypto.subtle.digest` BITE çekiminde bekletilir, bu sırada “Atla” basılır. **903567a derlemesi: FAIL** (istekler `[F,R,L]` + `[F,R,L,B]`, biri 429); **bu dal: PASS** (tek istek `[F,R,L]`). |
| 11 | **Codex P2 — kayıt hatası görünmüyor:** yalnız “kaydedil/saklanamadı” içeren mesajlar görünürdü | Ayrı `saveNote` durumu; her kayıt hatası görünür `role=alert` ile gösterilir. Fotoğraf izni açıkken fotoğraf saklanmadıysa “fotoğraf saklanamadı” (sessiz “yalnız sayısal” değil) | E2E `DENTAL_FAULT=block-photo-store`: uygulama hatayı gösterir, test **exit 1** ile başarısız olur. |
| 12 | E2E betiği bekleme hatasını yutuyor, `historyPhotoCheck` ve tarayıcı hatalarını yalnız kaydediyordu | Senaryo tablosu + assertion'lar; herhangi bir başarısızlıkta exit 1: istek sayısı/pozlar, benzersiz foto, API durumu, yanıt görünümü↔kendi fotoğrafı, `missingViews`, ekrandaki ölçülen sayısı, her slaytın görüntüsü = analiz edilen yakalama, kayıt kimliği, fotoğraf izni (izin açıkken IDB'de kayıt anahtarı zorunlu), geçmişte kendi fotoğrafı/hiç fotoğraf, silme, iptal/park/izin geri çekme, beklenmeyen konsol/sayfa hatası | Kasıtlı hatalar: `block-photo-store` ve `swap-photo-id` → ikisi de **exit 1**. İlk koşuda betik kendi yükleme beklentisindeki eksikliği de yakaladı (düzeltildi, yeniden koşuldu). |
| 13 | **Araç içi yanlış ret — ince dudak/doğal gülümseme:** dişler görünürken FRONT “Ağzınızı rahatça açın” (dudak açıklığı 0.10 < 0.12) | `DENTAL_GATES.minLipOpening=0.06` (dudaklar ayrık); asıl ölçüt mine görünürlüğü kapısı (değişmedi: sütunların ≥%30'u, mine ≥ 0.008·w²) | Kapı laboratuvarı + `dental-natural-public.y4m`: **903567a FRONT'ta 150 s takılı kaldı (FAIL)**, bu dal 4/4 pozu tamamladı, backend 4/4 geçerli. |
| 14 | **Araç içi yanlış ret — yana dönünce:** baş dönerken doğal yatıklık (roll 12–13°) ve kameranın göz hizası dışında olması (pitch 17–21°) poz kapısında red | Pitch ≤ 24°, roll ≤ 15° (önce 12.6°/8.6°); yan poz 12°'den başlar (FRONT ≤12° ile arada ölü bölge yok; MediaPipe yaw'ı görünür ~30° dönüşü 17° okuyor) | `tests/unit/dental_vehicle_gates.cjs` (eski kodda başarısız), `test_acne_pose_contract.cjs` diş satırları güncellendi. |
| 15 | **Ölçek:** sabit 150 piksel mine alt sınırı küçük görüntüde dişleri “örtülü” sayıyor; yan pozda 2B ağız genişliği kısaldığı için “daha belirgin görünmeli” | Mine miktarı ağız genişliğine göreli; ölçek kapısı (≥65 px) landmark derinliğiyle **anatomik (3B) ağız genişliği** üzerinden — istemci ve backend aynı | `test_gate_scale_uses_anatomical_mouth_width`; kapı laboratuvarı. |
| 16 | Backend yeniden doğrulaması, istemcinin kabul ettiği düşük çözünürlüklü ince-dudak karelerini 3×3 morfolojik açma yüzünden “dişler görünmüyor” sayıyordu (görünüm “Ölçülemedi” olurdu) | Backend kapısı istemciyle aynı piksel sınıflamasını kullanır (`gate_enamel`); analiz maskeleri değişmedi | Kapı laboratuvarı: istemci kabullerinde backend uyumu 81/85 → **85/85**. |
| 17 | Alınamayan görünüm kullanıcıyı sonsuz döngüde tutuyordu (yalnız BITE atlanabiliyordu) | Her pozda 15 s sonra “Bu görünümü atla”; atlanan poz `missingViews` ile “Alınmadı” taşınır; tüm pozlar atlanırsa sonuç yok, hata + yeniden tarama. Backend sıralı, boş olmayan her alt kümeyi kabul eder (`valid_dental_poses`) | E2E `skip-side` (RIGHT atlandı → `[F,L,B]`, geçmişte RIGHT “Alınmadı”), `skip-bite`; birim: oturum ve rota testleri. |

**Kapı laboratuvarı** (`scripts/dental_gate_lab/`, sonuç `claude-progress/dental-20261027/round2/gate-lab-report.json`):
10 Wikimedia portresi + 4 sentetik portre, araç kamerası ölçeği varsayımıyla yeniden çerçevelendi
(1920×1080'de yüz %16/22/30, 1280×720'de %14/18/24; yalnız ölçek/kaydırma). Uygulamanın gerçek
istemci kapısı Chromium'da çalıştırıldı (landmark'lar uygulamanın `face_landmarker.task` modeliyle,
Python çalışma zamanında).
- Beklenen pozların kabulü: **49/102 → 85/102**; açık ağzın kapanış sayılması **0 → 0**; istemcinin kabul ettiği karelerde backend uyumu **85/85**.
- Hâlâ reddedilenler: parlak stüdyo ışığında kırpılmış mine (`SALIVA_OR_GLARE`, kapı değiştirilmedi), landmark'ı dişlerin dışına düşen bir yüz (doğru red), 1280×720'de yüz %14 iken ağız <65 px (ölçek yetersiz), >45° dönüş.
- Bu kareler araç kamerasıyla çekilmemiştir; **fiziksel kamera kanıtı değildir**. Ölçek oranları varsayımdır.
- Kapı düzeltmeleri modelin ön/yan görünümlerdeki düşük başarısını (D kesinlik 0.54 / duyarlılık 0.34) **çözmez**; yalnız çekimin alınabilmesini sağlar.

Yönlendirme metinleri ve sesleri değiştirilmedi (önceden kaydedilmiş seslerle uyum); yeni kapılar bu yönergelere uyan kullanıcıyı (rahat açık ağız veya dişleri gösteren gülümseme) kabul eder. Ayna, retraktör, yardımcı kişi, aşırı yaklaşma veya ağzı zorlama istenmez.

## 3. Raporlar (ayrı ayrı)

### 3a. Örnek/sentetik veriyle ve sanal kamerayla arayüz/akış testi
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

### 3c. Gerçek modelle API ve kayıt/geçmiş E2E (temiz süreç, tur 2)
- `next build` + `next start` (3310), temiz `ATTUNE_DATA_DIR` ile `uvicorn main:app` (8310), anahtar/ücretli servis yok. Karşılaştırma için 903567a derlemesi 3311'de.
- Sonuçlar: `claude-progress/dental-20261027/round2/e2e-results.json`, `e2e-matrix.log`.

| Senaryo | Girdi | Beklenen | Sonuç |
|---|---|---|---|
| camera | `dental-ordered.y4m` (sentetik) | 4 poz, foto izni açık → foto saklanır, geçmişte kendi fotoğrafı, silme | PASS (31 kontrol) |
| no-photo-permission | aynı | yalnız sayısal, IDB'de anahtar yok, geçmişte fotoğraf yok | PASS |
| skip-bite | `dental-no-bite.y4m` | açık ağız kapanış sayılmaz; atla → `[F,R,L]`, BITE alınmadı | PASS |
| skip-side | `dental-no-right.y4m` | RIGHT atla → `[F,L,B]`, RIGHT alınmadı | PASS |
| skip-race | `dental-skip-race.y4m` + gecikmeli digest | tek analiz `[F,R,L]` | **903567a: FAIL**, bu dal: PASS |
| partial-response | gerçek yanıt, BITE yetersiz | 3 ölçüldü, BITE ölçülemedi, işaret yok | PASS |
| cancel / park-change / revoke-camera / revoke-consent | — | istek yok, kamera durur | PASS ×4 |
| upload ×8 | yakın çekim ön/sağ/sol, portre, EXIF(6), okluzal, 2 Wikimedia portresi | 200, kaydet/geçmiş/sil | PASS ×8 |
| upload negatif | `negative_6.jpg` | 422 `TEETH_NOT_VISIBLE_OR_NON_COLOR_IMAGE` | PASS |
| upload yakın çekim kapanış | `dental_front_bite.jpg` | 422 `TONGUE_OCCLUSION` (**bilinen yanlış red**, açık bulgu 3) | mevcut davranış |
| doğal pozlar (gerçek kişi portreleri, sanal kamera) | `dental-natural-public.y4m` | 4 poz | **903567a: FAIL (FRONT'ta takılı)**, bu dal: PASS |
| kasıtlı hata | `block-photo-store`, `swap-photo-id` | test başarısız olmalı | exit 1 ×2 ✔ |

### 3d. Fiziksel kamera ve AAOS/araç testi
**Yapılmadı.** Cloud'da fiziksel kamera ve AAOS emülatörü çalıştırılmadı. Gerçek araç kamerasının çözünürlüğü,
montaj açısı ve ışığıyla `vehicle-capture-v2` sınırları (pitch 24°, roll 15°, yan 12–45°, dudak 0.06, 3B ağız ≥65 px),
`incisal-contact-v1` eşiği (0.04, %60), atlama süresi (15 s) ve toplam tarama süresi doğrulanmalıdır.
Denenmeyen anatomiler: sakal/bıyık, diş teli, eksik/protez diş, belirgin kapanış bozukluğu, çocuk; bunlar doğrulanmış sayılmaz.

## 4. Açık hatalar, model sınırları, doğrulanmamış katmanlar
1. **Model sınırı (engel):** ürünün kamera görünümlerinde D kesinlik 0.54 / duyarlılık 0.34 (n=31 görüntü, 38 lezyon). Yeniden eğitim başlatılmadı; kullanıcı kararı gerekir.
2. Birikim görünümü ve dizilim metrikleri etiketli veriyle doğrulanmadı; sentetik düz dişlerde dizilim 25°/39° gibi yüksek dağılım verdi.
3. Yükleme yolunda TONGUE_OCCLUSION, yüz landmark'ı olmayan yakın çekimlerde dudakları dil sayıyor (`dental_front_bite.jpg` yakın çekimi reddedildi). Kapı gevşetilmedi; ayrı karar/çalışma gerekir.
4. Yükleme kapısı BLURRY (Laplasyen < 12) yüksek çözünürlüklü profesyonel fotoğrafların bir kısmını reddediyor (çözünürlüğe bağlı ölçüm). Değiştirilmedi.
5. Önceden var olan ve bu dalda değişmeyen başarısız testler (main'de de başarısız): `pytest tests/unit` 12 başarısız + 9 hata (torch/pycocotools gerektiren cilt/akne araştırma testleri), 6 `.cjs` cilt/paylaşım testi. Diş testleri 48/48 + 3 `.cjs` geçti.
8. Kırpılmış (aşırı parlak) minede `SALIVA_OR_GLARE` reddi (kapı laboratuvarında 1 portre) — kapı değiştirilmedi; fiziksel kamerada güneşli kabinde gözlenmeli.
9. MediaPipe Python ve WASM çalışma zamanları arasında landmark farkı olabilir; kapı laboratuvarı Python landmark'ları kullanır, sanal kamera E2E'leri WASM'ı.
6. `tests/e2e/dental_*.js|py` eski Windows kanıt yollarına bağlı; Cloud'da çalıştırılamadı. Yerine `tests/e2e/dental_cloud_flow.cjs`.
7. `components/DentalSourceView.tsx` artık kullanılmıyor; eski kapanış doğrulayıcısı (`scripts/verify_dental_closeout.py`) dosya listesine bağlı olduğu için silinmedi.

## 5. Yeniden üretme komutları
```bash
# Ortam: Node 22.20.0 + npm 10.9.3, Python 3.11+/3.13
npm ci && pip install -r services/core-api/requirements.txt
python -m pytest tests/unit/test_dental_*.py -q
node tests/unit/dental_bite_contact_parity.cjs
node tests/unit/dental_capture_session.cjs && node tests/unit/dental_vehicle_gates.cjs
npm run typecheck && npm run lint && npm run build
ATTUNE_TOOL_PYTHON=python3 node scripts/localization/check.cjs
# Model doğruluğu (özel veri Git dışında):
python scripts/dental_heldout_product_eval.py --data-root <özel-kök> \
  --split <özel-kök>/training/dataset-split.json --out heldout-product-eval.json
# E2E (backend 8310 + next start 3310 çalışırken):
# (her başarısızlıkta exit 1)
node tests/e2e/dental_cloud_flow.cjs <fikstür.y4m> <çıktı> camera|no-photo-permission|skip-bite|skip-side|skip-race|partial-response|cancel|park-change|revoke-camera|revoke-consent
DENTAL_EXPECT=200 node tests/e2e/dental_cloud_flow.cjs - <çıktı> upload:<foto>
DENTAL_FAULT=block-photo-store node tests/e2e/dental_cloud_flow.cjs <fikstür.y4m> <çıktı> camera   # beklenen: exit 1
# Kapı laboratuvarı: scripts/dental_gate_lab/README.md
```

## 6. Kullanılan girdiler ve hash'ler
Bkz. `claude-progress/dental-20261027/status.json` → `inputs`. Fotoğraflar, veri seti,
y4m fikstürleri ve ekran görüntülerinin fotoğraf içeren olanları Git'e eklenmedi.
