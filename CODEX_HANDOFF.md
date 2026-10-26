# CODEX_HANDOFF — Cilt analizi: gerçek veri yolu (bulgular, sonuç ekranı, geçmiş)

Hazırlayan: Claude (bulut oturumu `6c3a640c`). Güncelleme: 2026-10-26, Europe/Berlin.
Bu teslim, Codex'in önceki denetiminde bulunan kopuklukları ve 4 arayüz hatasını giderir. Gerçek kamera taramasından
gelen model çıktılarını yeni sonuç ekranına bağlar. Yeniden eğitim, yeni model, veri üretimi veya ücretli çağrı **yapılmadı**.
Yalnızca kanıtlanan kapsam "TAMAM" olarak işaretlendi. Diğer her şey "EKSİK" ya da "TEST EDİLMEDİ" olarak bırakıldı.

## 1. Teslim kimliği

| Alan | Değer |
|---|---|
| Repo | `sasmazt90/togg-health-mvp` (yeni adı `sasmazt90/attune-more`; görünürlük doğrulanamadı, herkese açık kabul edildi) |
| Branch | `claude/skin-validated-20261025` (main'e merge yok, geçmiş yeniden yazılmadı) |
| Taban | `babe9b6970b011f65d642600aaa0ca2fd2b7f316` |
| Teslim commit'i | Teslim mesajındaki tam SHA (`git log -1`) |
| Push | Yapılamadı: oturumun GitHub erişimi reddediliyor. Teslim **git bundle + SHA-256** ile yapıldı |

```bash
sha256sum -c attune-skin-handoff.bundle.sha256
git bundle verify attune-skin-handoff.bundle        # önkoşul: babe9b6 içeren klon
git fetch attune-skin-handoff.bundle claude/skin-validated-20261025:claude/skin-validated-20261025
```

## 2. Bu turdaki commit'ler

| Commit | Özet |
|---|---|
| `fd3f183` | Sunucu `general.findings`, `/skin/regional-fuse`, istemci zinciri, üç durum ayrımı, 4 arayüz hatası, test sözleşmeleri |
| (son) | E2E'nin bulduğu 2 hata (yan poz haritaları birleştirmeye gitmiyordu; etiket boşlukları fotoğrafı eziyordu), yeni E2E'ler, bu belge, ilerleme kaydı |

Önceki commit'ler (`99eb085` … `0a57885`) için §11'deki eski teslim notuna bakın. O notun "gerçek akış yok" maddeleri bu belgede güncellendi.

## 3. Veri yolu (artık bağlı)

```
Kamera (getUserMedia 1920x1080 ideal) → MediaPipe yüz noktaları (tarayıcı) → poz kapıları: ön |yaw| küçük, yanlar 12–45°
  → her poz: POST /api/local-health/skin  (fotoğraf + noktalar)
       sunucu: regional_skin_v3.analyze_photo → regionalSkinMap { regions, raw, findingEvidence, findingBoxes, models{sha256} }
       ön poz: general.findings = {status:'unavailable', reason:'REQUIRED_POSES_MISSING'}  (tek fotoğraf yeterli değil)
  → üç poz bitince: POST /api/local-health/skin/regional-fuse  {maps:{FRONT,LEFT,RIGHT}}  (yalnız sayılar, fotoğraf yok)
       sunucu: fuse_maps (cilt tipi haritası) + skin_findings_v1.findings_from_maps (bulgu kararları, eşikler sunucuda)
  → istemci: general.regionalSkinMap / skinType / findings = sunucu yanıtı (eski istemci kuralı artık haritayı kurmuyor)
  → sağlık kaydı (togg_health_latest_skin, togg_health_skin_history; fotoğraf yok) → sonuç ekranı → /skin?view=latest
```

| Codex bulgusu | Düzeltme | Dosya |
|---|---|---|
| Sunucu `general.findings` üretmiyor | `skin_findings_v1.py` (yeni); `regional_attach.attach/fuse/fuse_regional` | `services/core-api/` |
| `overviewFromResponse` findings taşımıyor | `findings` alanı (doğrulanarak) eklendi | `utils/skinOverview.ts` |
| Üç açılı akış sunucu birleştirmesini çağırmıyor | `finishMultiScan` → `fuseRegionalOnServer`; poz haritaları `snapshot.regionalSkinMap` içinde tutuluyor | `app/skin/page.tsx`, `utils/appearanceMeasurements.ts`, `utils/skinSnapshot.ts` |
| Eksik/başarısız analiz "bulgu yok" gösteriliyor | `findingsState`: `missing` / `unavailable` / `measured`; ayrı metinler + "N bulgu ölçülemedi" penceresi | `SkinFindingsPanel.tsx`, `SkinUnmeasuredFindingsDialog.tsx` (yeni) |

Ekranda görülen durumlar ve metinleri:
- **Ölçülmedi (`missing`):** kayıtta bulgu analizi yok. Metin: "Bu kayıtta bulgu analizi yok; bulgular ölçülmedi."
- **Ölçülemedi (`unavailable`):** "Bulgular bu taramada ölçülemedi." ve nedeni. Bulgu bazında neden, "N bulgu ölçülemedi" penceresinde gösterilir.
- **Kesinleştirilemedi (`inconclusive`):** bölge hiçbir fotoğrafta okunamadı. Mevcut "N bulgu kesinleştirilemedi" penceresi ve "Tekrar tara" kullanılır.
- **Ölçüldü, görülmedi:** "Ölçülen bulgular bu taramada görülmedi."
- **Görüldü:** kart gösterilir. Skor, alan ya da sayı yoksa bar ve yüzde çizilmez. Kartta "Belirginlik, alan ve sayı bu sürümde ölçülmüyor." yazar.

## 4. Bulgu başına durum (model, açı, çıktı, doğrulama)

Ortak: `findings.pt` = RF-DETR Small, SHA-256 `c8d94801…75c99`. Karar, kayıtlı dedektörün bölge içi en yüksek kutu skoru ile
eşiğin karşılaştırılmasıdır. Eşik kaynağı `research/skin-findings/results/det_prev.md` (`thr_prev`, yalnızca 260 eğitim kişisi).
**Skor ölçeği doğrulaması:** üretim `model_evidence` ile araştırma önbelleği aynı 12 fotoğrafta (60 bölge) karşılaştırıldı.
Kullanılan bölgelerde medyan |Δ| = 0. Bu doğrulama **araştırma PNG'leri** üzerindedir. Kamera yolu için bkz. §6.3.

| Bulgu | Model / anahtar | Desteklenen açı (uygulama) | Çıktı alanları | Doğrulama durumu |
|---|---|---|---|---|
| Ben (`mole`) | findings.pt `Riskli Ben`, yanaklar, eşik 0,58 | Ön + iki yan (yaw 12–45°) — üçü zorunlu | `status`, `pose`, `readFrom`, `markers[{x,y,r,pose}]` | Sentetik, Ön+20°, 80 test kişisi: P 1,00 R 0,30. Bu küme yöntem seçiminde de kullanıldığı için **bağımsız doğrulama değildir**. İşaret konumu doğrulanmadı. Gerçek fotoğraf yok |
| Melazma (`melasma`) | `Gunes Lekesi`, yanaklar, 0,54 | Ön + iki yan | `status`, `pose`, `readFrom` | Sentetik, Ön+20°: P 0,83 R 0,56 (aynı uyarılar) |
| Rozasea eğilimi (`rosacea`) | `Rozasea`, 5 bölge, 0,69 | Ön + iki yan | `status`, `pose`, `readFrom` | Sentetik, Ön+20°: P 1,00 R 0,82 (aynı uyarılar) |
| Göz altı torbası, göz altı morluğu, göz kapağı düşüklüğü, göz kuyruğu düşüklüğü, kaz ayakları, alın çizgileri, uçuk, akne izi, sivilce, kızarıklık, egzama/sedef, pullanma | Karar modelleri (DINOv2/LR, geometri/LR, renk/LR, dedektör birleşimi LR) **hiç kaydedilmemiş** | — | `unavailable[{id, reason:'MODEL_NOT_AVAILABLE'}]` | Çalıştırılamaz. Yeniden eğitim onay bekliyor |
| Türü belirlenemeyen leke (`spots`) | — | — | `reason:'NOT_VALIDATED'` | %80 kesinliğe ulaşmadı |

Bu sürümde **sayı, alan ve belirginlik üretilmiyor** (`countRange`, `areaPct`, `severity` alanları hiç gönderilmez):
- **Belirginlik:** Ridge modelleri kaydedilmemiş.
- **Kızarıklık/melazma alanı:** dedektör kutusu doğrulanmış bir alan ölçüsü değil.
- **Sivilce/ben sayımı:** nokta düzeyinde doğrulanmadı. Sivilce kararı da kayıp modele bağlı.

Eksik değer hiçbir zaman 0 veya düşük skor sayılmaz. Öneri bandı da seçilmez ("Bu taramada belirginlik veya sayı ölçülmediği için düzeye göre öneri gösterilemiyor.").

### Açı eşlemesi (Adım 3)

| | Araştırma | Uygulama |
|---|---|---|
| Ön | `front` | `FRONT` |
| Yan, burun görüntünün sağına | `side_1` (≈ −20° Python matrisi), görüş `pos`, görünür yanak: kişinin sağ yanağı | `LEFT` ("Anatomik sol"), E2E'de `noseToImageRight` = +0,09…+0,10 |
| Yan, burun görüntünün soluna | `side_2`, görüş `neg`, görünür yanak: sol yanak | `RIGHT` ("Anatomik sağ"), `noseToImageRight` = −0,08…−0,09 |
| ~25° ikinci yan kare | `wide_1/2` | **Yok.** Bu yüzden ~25° kare gerektiren hiçbir yöntem kullanılmadı. Üç bulgunun eşik ve P/R değerleri "Ön + 20°" satırlarındandır |

Uygulamanın yan kapısı 12–45°'dir. Araştırmadaki "20°" pozları sentetik görüntülerde yaklaşık 18–23° ölçüldü. Çekim davranışı değiştirilmedi.

## 5. Arayüz hataları (Codex) — yeni tasarım korunarak

| Hata | Düzeltme | Test |
|---|---|---|
| Başlangıç değişince bitiş seçilemiyor | `nextRange`: birinci dokunuş yeni aralığı başlatır, ikinci dokunuş bitirir. Daha erken bir gün seçilirse uçlar yer değiştirir | `test_skin_findings_ui.py::test_date_range…`, örnek veri E2E |
| Filtre başlangıçtan 12 saat önceyi kapsıyor | `inDayRange`: yerel gün başı 00:00 dahil, bitiş gününün ertesi 00:00 hariç | aynı; E2E'de D−3 22:00 taraması aralık dışında kalıyor |
| Farklı pozların işaretleri karışıyor | `markersOnPhoto`: her işaret kendi `pose` değerini taşır. Pozu bilinmeyen işaret hiç çizilmez | birim + gerçek E2E (K-032: sol profilde yalnız RIGHT işareti) |
| Eksik skor/sayı en düşük banda düşüyor | `recommendationBand` → `null`. Tek bantlı bulgular etkilenmez | birim + E2E |
| (E2E ile bulundu) Yan poz haritaları birleştirmeye gitmiyordu | `snapshot.regionalSkinMap` | gerçek E2E: `fuse.poses == FRONT,LEFT,RIGHT` |
| (E2E ile bulundu) 1600 px ekranda etiket boşlukları fotoğrafı ~30 px'e eziyordu | Boşluklar yalnızca fotoğrafa ≥360 px kalıyorsa kullanılır. Kalmıyorsa mevcut "fotoğraf altında etiket satırı" görünümü kullanılır | gerçek E2E: her sayfada fotoğraf genişliği ≥300 px |

## 6. Doğrulama

Ortam: bulut konteyneri (Linux). Node 22.20.0 / npm 10.9.3, Python 3.13.
Sunucu `ATTUNE_REGIONAL_V3_DIR` ile kayıtlı model paketini kullandı. Ön yüz `next build && next start` ile çalıştı. Tarayıcı Playwright Chromium.

### 6.1 Otomatik kontroller

| Kontrol | Sonuç |
|---|---|
| `npm run typecheck` | Geçti |
| `npm run lint` | Geçti (uyarı yok) |
| `npm run build` | Geçti |
| `pytest tests/unit` | 1423 geçti, 45 atlandı, **7 başarısız**: 5 `test_acne_objectness_features` (tabanda da; `yolox` yok), 1 `test_localization` (tabandan 43 eski eksik), 1 `test_hosted_skin_type_runtime` (ortama bağlı, §8.11). Branch'in kendi gerilemesi yok (önceki turun 4 gerilemesi düzeltildi). Kayıt: `claude-progress/realpath-20261026/pytest_unit.txt` |
| `node scripts/localization/check.cjs` | Yeni eksik yok. Tabandan gelen 43 hata sürüyor (taban: 44) |

Güncellenen eski arayüz sözleşmeleri (silinmedi, ölçüt gevşetilmedi):
- `test_skin_overview_contract`: 7 sayfa yerine onaylı 6 sayfa kontrol ediliyor; sıra birebir doğrulanıyor.
- `test_skin_approved_layout` ve `test_skin_product_refinements`: bölge boyası artık nokta (landmark) konturlarıyla kontrol ediliyor. "Dengeli" sarı, yanlış poz veya fotoğrafa boya yok, ölçülemeyen bölgede renk yok.
- `ts_loader.js`: kardeş bileşen çözümleme eklendi.

Yeni testler: `test_skin_findings_v1.py` (5) ve `test_skin_findings_ui.py` (3).

### 6.2 Örnek veriyle arayüz testi (model çıktısı DEĞİL)

`tests/e2e/current_skin_findings_sample_ui.py`, elle yazılmış örnek bir kaydı normal `/skin?view=latest` yolundan açar. Sonuç: **GEÇTİ**. Kontrol edilenler:
- 2×2 kartlar ve barın ucundaki değer,
- sayfa kartları ve geçmiş grafiği (3 tarama),
- tarih aralığında başlangıcı değiştirip bitişi seçme,
- tam gün filtresi,
- `%61–80` ve `1–3` bantları,
- skorsuz bulguda "bant yok" uyarısı.

### 6.3 Gerçek model inference testi (sahte kamera aygıtı, fiziksel kamera DEĞİL)

`tests/e2e/current_skin_contract.py` yeni arayüze göre yeniden yazıldı. Chrome sahte kamerası, sentetik bir kişinin üç fotoğrafından üretilen y4m dosyasını oynatır (`tests/e2e/make_skin_y4m.py`; 1920×1080, yüz genişliği kare genişliğinin %34'ü).
- Poz, kalite ve model sonucu taklit edilmedi.
- Kayıtlı modeller çekirdek API'de çalıştı. Yanıtta 7 dosyanın SHA-256 değeri vardı ve MODEL_MANIFEST ile eşleşti.

Her geçen koşuda doğrulananlar:
- 3 ayrı foto ve 3 poz,
- ön pozda `REQUIRED_POSES_MISSING`,
- tek bir `regional-fuse` çağrısı (FRONT, LEFT, RIGHT),
- kayıt `general.findings` ve `regionalSkinMap` değerlerinin sunucu yanıtıyla birebir aynı olması,
- geçmişin ilk satırı = sonuç,
- localStorage'da `data:image` olmaması,
- ekrandaki kartlar, sekme sayıları ve "N bulgu ölçülemedi" sayısının kayıtla aynı olması,
- `/skin?view=latest` ile yeniden açılan kaydın aynı bulguları göstermesi.

| Sentetik kişi (araştırma etiketi) | Sonuç | Görülen bulgular (sunucu) | Süre |
|---|---|---|---|
| K-032 (ben etiketli) | GEÇTİ | ben: sağ yanak (LEFT, 1 işaret), sol yanak (RIGHT, işaretler FRONT+RIGHT); cilt tipi Karma | ~180 sn |
| K-074 (rozasea etiketli) | GEÇTİ | rozasea: burun, sağ yanak, sol yanak; Normal ve hassas | ~180 sn |
| K-217 (rozasea etiketli) | GEÇTİ (akış) | **hiçbiri** — bkz. aşağıdaki risk | ~175 sn |
| K-236 (etiketsiz) | **BAŞARISIZ (çekim)** | Ön poz 600 sn içinde kabul edilmedi. Uygulama "Göz çevresi doğrulanamadı" / "Bu poz güvenilir ölçülemedi veya önceki kareyle aynı" diyerek yeniden başlattı. Sabit (değişmeyen) kare ve göz kontrolü olası nedenler; çözülmedi | — |

**Önemli risk: eşik kamera yolunda kırılgan.**
- K-217, araştırma görüntüsünde rozasea "görüldü" çıkıyor. Python ile aynı fikstür karesinde (YUV 4:2:0 kod çözümü dahil) sağ yanak skoru 0,757.
- Uygulamanın gerçekten gönderdiği PNG'de aynı bölge 0,48–0,54 çıktı. Bu PNG, fikstür karesinden ortalama yalnızca 1,4/255 piksel farkı taşıyor (Chrome'un YUV→RGB dönüşümü).
- Sonuç: 0,69 eşiğinin altında kalıyor ve bulgu görülmüyor.
- Eşik araştırma PNG'lerinde seçildi; kamera renk hattında **doğrulanmadı**. Eşik değiştirilmedi, çünkü bunun için doğrulama gerekir.
- Kanıt: `claude-progress/realpath-20261026/e2e/` (skorlar), `e2e/sent_probe.py` ve `yuv_probe.py` çıktıları (teslim paketinde).

### 6.4 Fiziksel kamera, Windows launcher, araç ekranı

**TEST EDİLMEDİ.** Windows 200 % yerel yakınlaştırma yakalaması E2E içinde korunuyor; bu ortamda `--skip-native-zoom` ile atlandı (`proof.json`: "NOT RUN").

### Yeniden üretme

```bash
cd services/core-api && ATTUNE_REGIONAL_V3_DIR=<model paketi> uvicorn main:app --host 127.0.0.1 --port 8000
npm run build && (cd apps/vehicle-app && npx next start --hostname 127.0.0.1 -p 3000)
python tests/e2e/make_skin_y4m.py K-032-front.png K-032-side_1.png K-032-side_2.png audit-fixtures/three-angle.y4m 15 0.34
python tests/e2e/current_skin_contract.py [--chromium] [--software-gpu] [--skip-native-zoom]   # Windows'ta zoom dahil
python tests/e2e/current_skin_findings_sample_ui.py [--chromium]
python -m pytest tests/unit -q
```

Sentetik fotoğraflar, model paketi ve y4m dosyaları Git'te değildir (önceki teslimdeki varlık paketleri).

## 7. Model manifesti (bu turda çalışma anında doğrulandı)

API yanıtındaki `regionalSkinMap.models` alanı, yüklenen dosyaların SHA-256 değerini her taramada hesaplar. Değerler `research/skin-findings/MODEL_MANIFEST.json` ile eşleşti:

| Dosya | SHA-256 |
|---|---|
| findings.pt | c8d94801bf86c65a4ff0c3c1e5ae663aaa4774fdccd4b31d4782aeed33675c99 |
| skinmap.pt | bc4e8aab0866ece0048a7306284e1bf26ef5ba31bf56ba8834ff2e2494d2a4a5 |
| acnes.pt | 5db24d92049c0d335665a883ebd83dda115608a63594ccd2c336f504060abe15 |
| regional.pt | b23cd0ed5a18caa679a5a77607e855ef263483f712edd34d4ddeb215ce557365 |
| wrinkles.pt | ba5c527859c1cb59ff6244b674eee1caca07984c28b8b4426ce8c1acb412f7b2 |
| params.json | 5d1dc44de3fb4e3b150151eb642d0c152aa2fdc0161d4d7acbcc78f2847cd330 |
| k_classifier.json | a7ab0b05686d4d9664c115fa324589e492fc7e8829e4f9ef4488354b25688a54 |
| dinov2-small (HF `facebook/dinov2-small`, rev ed25f3a) | model.safetensors ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1 (çalışma anı manifestine dahil değil) |
| face_landmarker.task | 64184e22… (repo) |

## 8. Açık engeller (denetimden muaf değil)

1. **Kayıp modeller:** 12 bulgu için LR/Ridge karar modelleri ve tüm belirginlik modelleri kaydedilmemiş. Bunlar `unavailable` olarak gösteriliyor. Yeniden eğitim önerisi kullanıcı onayı bekliyor; başlatılmadı.
2. **Eşik kırılganlığı:** Kamera renk hattında eşik doğrulanmadı (§6.3, K-217). Gerçek kamera kalibrasyonu ve doğrulama gerekli.
3. **Bağımsız doğrulama yok:** 80 kişilik test kümesi yöntem seçiminde de kullanıldı. Tüm sonuçlar sentetik; gerçek fotoğraf veya klinik doğrulama yok; dermatolog incelemesi yok.
4. **Sayı, alan, belirginlik ve işaret konumu** doğrulanmadı ve üretilmiyor.
5. **Çekim:** K-236 fikstüründe ön poz kabul edilmedi (§6.3). ~25° ikinci kare yok.
6. **Sağlık Geçmişim penceresi** (`SkinRecordDetail`, eski bölge karuseli) bulguları göstermiyor. Kayıt bulguları taşıyor ve `/skin?view=latest` yeni ekranda gösteriyor. Geçmiş penceresinin yeni tasarıma alınması tasarım kararı gerektiriyor; yapılmadı.
7. **Kimlik doğrulama:** `/skin/regional-fuse` istemcinin gönderdiği poz kanıt sayılarına güveniyor. Karar sunucuda veriliyor, ancak sayıları sunucunun kendisi ürettiği doğrulanmıyor (imza yok).
8. Fiziksel kamera, Windows launcher, araç ekranı, erişilebilirlik denetimi, kullanıcı kabulü: **TEST EDİLMEDİ**.
9. `k_classifier.json` (model ağırlığı) commit `952e1f8` ile Git geçmişinde; geçmiş yeniden yazılmadı.
10. `npm ci` 1 kritik güvenlik açığı bildiriyor (değiştirilmedi).
11. Ortama bağlı test: `test_hosted_skin_type_runtime::test_degrees_remain_independent_of_hosted_failure`, bu çalışma dizininde git-ignore edilmiş özel `models/skin-type-local-v1/model.onnx` bulunduğu için başarısız. Temiz checkout'ta (tabanda) geçiyor. Kod değişikliğinden kaynaklanmıyor.
12. Tabandan gelen hatalar: `test_acne_objectness_features` (5; `yolox` yok) ve `test_localization` (43 eski eksik mesaj).

## 9. Geri dönüş

- Bu turdan önceki durum: `0a578852b4e5865f038985d4c65b1bc5a249cfbe`.
- Tüm Claude değişikliklerinden önce: `babe9b6`.

## 10. Codex inceleme komutu

```text
Görev: claude/skin-validated-20261025 (taban babe9b6) teslimini bağımsız denetle; kodu değiştirme.
CODEX_HANDOFF.md §3–§8'i oku. Her madde denetlenebilir; bilinen engeller muaf değildir.
1. Bundle SHA-256, git bundle verify, HEAD SHA.
2. npm ci / typecheck / lint / build; pytest tests/unit (§6.1 ve §8.11-12 ile karşılaştır).
3. Sunucu: /api/local-health/skin yanıtında regionalSkinMap.findingEvidence ve ön pozda general.findings
   (REQUIRED_POSES_MISSING); /skin/regional-fuse ile three-pose findings; paket yokken davranış.
4. İstemci: finishMultiScan'in sunucu birleştirmesini kullandığını, eski istemci kuralının haritayı kurmadığını,
   missing/unavailable/measured ayrımını ve hiçbir yerde skor/sayı/alan uydurulmadığını kontrol et.
5. Codex'in 4 arayüz hatası + E2E ile bulunan 2 hata (§5).
6. E2E: örnek veri testi ve gerçek inference testi ayrı raporlanmalı; fiziksel kamera ayrı.
7. §6.3 eşik kırılganlığı: aynı fikstürde Python yolu ile uygulama yolu skorlarını karşılaştır.
Rapor: Bulgu | Önem | Kabul engeli mi | Dosya:satır | Yeniden üretme | Öneri.
```

## 11. İlerleme kaydı ve kanıtlar

- `claude-progress/realpath-20261026/status.json`: bu turun aşamaları.
- `claude-progress/realpath-20261026/e2e/`: her koşunun `proof.json` ve `api-calls.json` dosyaları; fotoğraf içermez.
- Ekran görüntüleri (sentetik yüzler) teslim paketindedir; Git'te değildir.
- Önceki tur: `claude-progress/handoff-20261026/`.
