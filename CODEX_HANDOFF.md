# CODEX_HANDOFF — Cilt analizi (bulgular, belirginlik, sonuç ekranı)

Hazırlayan: Claude (Claude Code, bulut oturumu `6c3a640c`). Hazırlanma: 2026-10-26, Europe/Berlin.
Bu belge yeni özellik içermez; mevcut kodu, analiz betiklerini, model bağımlılıklarını ve kanıtları devreder.
Belirsiz ya da doğrulanamayan her şey açıkça öyle işaretlenmiştir.

## 1. Repo ve teslim kimliği

| Alan | Değer | Doğrulama |
|---|---|---|
| Repo | `https://github.com/sasmazt90/togg-health-mvp` (GitHub `https://github.com/sasmazt90/attune-more` adresine yönlendiriyor: yeniden adlandırılmış) | `git remote -v`; HTTP 301 yönlendirmesi gözlendi |
| Görünürlük | **Doğrulanamadı.** Oturumun GitHub API erişimi reddedildi (HTTP 403). `.gitignore` başlığı "Public Repository" diyor; bu yüzden repo **herkese açık kabul edildi** | — |
| Teslim branch'i | `claude/skin-validated-20261025` | `git branch` |
| Taban commit | `babe9b6970b011f65d642600aaa0ca2fd2b7f316` (uzak `feat/skin-product-refinement` ucu; ondan önce `main` = `7463eef112c5a40f7cd01192b6d1f4e9fa6ab285`) | `git ls-remote` |
| Teslim commit'i | Bu belgeyi içeren commit; tam SHA teslim mesajında ve `git log -1` çıktısında. Kod + araştırma içeriği `1f033329abdb38cab3b57837e7949a81d8588fa9` ile aynıdır; son commit yalnızca bu belgeyi ekler | `git log` |
| Push | **Yapılmadı.** Bu oturumdan push reddediliyor ("Claude doesn't have GitHub access … for your organization"). Repo herkese açık kabul edildiği için teslim **git bundle + SHA-256** ile yapıldı | add_repo yanıtı |
| Çalışma dizini | Bulut konteyneri: `/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad/repo/claude-skin` (geçici; Codex erişemez) | — |

Bundle'ı alma (önkoşul: `babe9b6` commit'ini içeren bir klon, örn. `feat/skin-product-refinement`):

```bash
sha256sum -c attune-skin-handoff.bundle.sha256
git bundle verify attune-skin-handoff.bundle
git fetch attune-skin-handoff.bundle claude/skin-validated-20261025:claude/skin-validated-20261025
git checkout claude/skin-validated-20261025
```

## 2. Commit'ler ve değişen dosyalar

| Commit | Özet |
|---|---|
| `99eb085` | Bölgesel cilt tipi haritası v3 (sunucu karar modülü + fotoğraf üzerinde bölge boyası) |
| `963b532` | Koyu ten için hassasiyet kanıt kuralı (SCIN ile kontrol edildi), params 20261025d |
| `952e1f8` | Bölgesel sınıflandırıcı (DINOv2 + skaler özellik, lojistik regresyon; 170 sentetik karakter), 3 açı birleştirme, `/skin` bağlantısı |
| `1b6287d` | Bölge renkleri, "Dengeli" etiketi, kesinleştirilemedi bilgisi, Sağ/Sol profil adları, TR/EN/DE |
| `c756a1a` | Kesinleştirilemedi penceresi: ölçülen nedenler ve öneriler |
| `5a98639` | Sonuç ekranı "yüz haritası": bulgular, belirginlik barı, geçmiş grafiği, skor aralığına göre öneriler |
| `0e99e07` | Genel bakış: cilt tipi kartı, bulgu ızgarası, bulgunun tüm yüzde gösterimi |
| `6daed91` | Egzama/sedef eğilimi ve pullanma bulguları + öneriler; sıkı genel bakış kartları |
| `879a822` | "Rozasea eğilimi" (kızarıklık alanı barı), "Egzama/sedef eğilimi", skorsuz bulgularda bölge adı |
| `6018728` | Genel bakışta sayfa başına 2×2 bulgu kartı |
| `1f03332` | Araştırma kodu teslimi (`research/skin-findings`, veri ve ağırlık yok) |
| (son) | Bu belge |

### Sunucu (`services/core-api`)

| Dosya | Amaç |
|---|---|
| `regional_skin_v3.py` (yeni) | Bölge başına yağlı/kuru/normal/ölçülemedi + hassas kararı. RF-DETR dedektörleri, sakal/kırışıklık maskeleme, ITA ten grubu standardizasyonu, `k_classifier.json` (DINOv2 + skaler → LR). `load_runtime()` model paketi yoksa `FileNotFoundError` atar |
| `regional_attach.py` (yeni) | v3 sonucunu `/api/local-health/skin` ve `/skin/fuse-multi-angle` yanıtına `general.regionalSkinMap` olarak ekler; paket yoksa ya da hata olursa sonucu değiştirmeden bir durum koduyla döner (koddaki açıklama; çalıştırılarak doğrulanmadı) |
| `local_health.py` | Yukarıdaki iki bağlama çağrısı |
| `models/regional-skin-v3/params.json` | Eşikler, dedektör dosya eşlemesi (`skinmap.pt`, `findings.pt`, `acnes.pt`, `regional.pt`, `wrinkles.pt`) |
| `models/regional-skin-v3/k_classifier.json` | **Model ağırlığı (LR katsayıları, 134 KB)** — Git'te. Bkz. §8 |
| `tools/regional_k/*` | Bölgesel sınıflandırıcıyı eğitme/dışa aktarma/çapraz doğrulama araçları |

### Ön yüz (`apps/vehicle-app/src`)

| Dosya | Amaç |
|---|---|
| `utils/skinFindings.ts` (yeni) | Bulgu tipleri ve alanları (§5), sayfa modeli (T-bölgesi = alın + burun, Göz çevresi, Sağ/Sol profil, Dudak ve çevresi), `viewFindings`, `overviewFindings`, `inconclusiveFindings`, `validFindings`, fotoğraf etiket noktaları (`FINDING_ANCHOR`, `anchorPoint`), alan çizimleri (`findingAreaPath`) |
| `utils/skinRecommendations.ts` (yeni) | Öneri aralıkları (Docs belgesinden üretildi), `recommendationBand`, `findingScore` |
| `utils/skinTypePaint.ts` (yeni) | Bölgesel cilt tipi boyası, renkleri, etiketleri |
| `utils/skinOverview.ts` | Sayfa sırası: overview, forehead (T-bölgesi), periorbital, rightCheek, leftCheek, chin; etkin cilt tipi |
| `components/skin/SkinResultView.tsx` | Sonuç ekranı düzeni, sekmeler, fotoğraf etiketleri, Genel bakış seçimi |
| `components/skin/SkinFacePanel.tsx` | Fotoğraf, bölge boyası, bulgu katmanı, T-bölgesi çerçeveleme |
| `components/skin/SkinFindingCallouts.tsx` (yeni) | Fotoğraf yanındaki etiketler (≥1280 px), dar ekranda buton satırı |
| `components/skin/SkinFindingCard.tsx` (yeni) | Bulgu kartı: oklar, Belirginlik / Kapladığı alan barı, sayı aralığı, geçmiş grafiği |
| `components/skin/SkinDateRangeDialog.tsx` (yeni) | Geçmiş için tarih aralığı |
| `components/skin/SkinRecommendationsDialog.tsx` (yeni) | Öneriler penceresi |
| `components/skin/SkinInconclusiveDialog.tsx` (yeni) / `SkinInconclusiveFindingsDialog.tsx` (yeni) | Kesinleştirilemedi pencereleri, "Tekrar tara" |
| `components/skin/SkinFindingsPanel.tsx` (yeni) | Sağ sütun: bulgu kartı / Genel bakış (cilt tipi kartı, 2×2 bulgu ızgarası) |
| `components/skin/SkinRecordDetail.tsx`, `SkinRegionSummary.tsx`, `data/skinDemoFixture.ts` | Bölge adları ve cilt tipi gösterimi uyumu |
| `app/skin/page.tsx` | `findingsHistory` (localStorage `togg_health_skin_history`), `scanAt`, `onRescan` bağlantısı |
| `shared/localization/messages.json` | Yeni TR/EN/DE metinler (anahtar = sha256(normalize(tr))[:16]) |

### Araştırma (`research/skin-findings`)

Analiz betikleri (olduğu gibi), kayıtlı sonuç tabloları, kör belirginlik derecelendirmeleri, sentetik veri üreticisi ve
`MODEL_MANIFEST.json`. Üretim kodu değildir. Ayrıntı: `research/skin-findings/README.md`.

## 3. Çalıştırma, test ve sürümler

| Bileşen | Sürüm |
|---|---|
| Node / npm | **22.20.0 / 10.9.3** zorunlu (`scripts/tooling/verify_package_manager.cjs` başka sürümü reddeder) |
| Python | 3.13 (bulutta 3.13.17 ile çalıştırıldı) |
| Ön yüz | Next.js 15.5.27, React 19 |
| Araştırma / bölgesel model çalışma zamanı | rfdetr 1.11.2, torch 2.14.1, torchvision 0.29.1, transformers 5.20.2, scikit-learn 1.9.1, mediapipe 0.10.32, numpy 2.2.6, opencv 4.12 |

```bash
npm ci                         # kökte
npm run typecheck              # = apps/vehicle-app: next typegen && tsc --noEmit
npm run lint
npm run build
npm run dev                    # http://127.0.0.1:3000
pip install -r services/core-api/requirements.txt
python -m pytest tests/unit -q
cd services/core-api && uvicorn main:app --host 127.0.0.1 --port 8000   # ön yüzün varsayılan yerel API'si
# Windows paketleri: Start-Health-Final.ps1 / Stop-Health-Final.ps1 (scripts/health-final-api.py, port 8311)
```

Bölgesel cilt tipi haritasının sunucuda çalışması için model paketi gerekir (§7): `ATTUNE_REGIONAL_V3_DIR` altında
`params.json`, `k_classifier.json`, `skinmap.pt`, `findings.pt`, `acnes.pt`, `regional.pt`, `wrinkles.pt` ve
`dinov2-small/` (ya da `ATTUNE_DINOV2_DIR`). Paket bu teslimde yoktur.

### Ortam değişkenleri (yalnızca isimler)

- Sunucu: `ATTUNE_REGIONAL_V3_DIR`, `ATTUNE_DINOV2_DIR`, `ROBOFLOW_API_KEY`, `ATTUNE_ROBOFLOW_API_KEY`,
  `ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH`, `ATTUNE_EXPERIMENTAL_ACNE_V5`, `ATTUNE_TRUSTED_ORIGINS`, `ATTUNE_DATA_DIR`,
  `ATTUNE_LOAD_LOCAL_ENV`, `OPENAI_API_KEY` (ruh sağlığı modülü)
- Ön yüz: `NEXT_PUBLIC_ATTUNE_DEMO_MODE`, `NEXT_PUBLIC_ATTUNE_ACNE_V5`, `NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT`,
  `NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT`, `ATTUNE_MENTAL_TTS_BACKEND_URL`, `ATTUNE_MENTAL_TTS_FRONTEND_ORIGIN`, `ATTUNE_MENTAL_TTS_TOKEN`
- Araştırma: `OPENAI_API_KEY` (dosyadan, `ATTUNE_GEN_ENV`), `ATTUNE_IMAGE_MODEL`, `ATTUNE_IMAGE_QUALITY`,
  `ATTUNE_AGE_INDEPENDENT`, `ATTUNE_TARGET`, `ATTUNE_SUBTLE`, `ATTUNE_PIGMENT`, `ATTUNE_MAX_PENDING`, `ATTUNE_YAW_FRAC`,
  `ROBOFLOW_API_KEY` (ağırlık indirme), `CP`, `BASE`, `TAG`, `TASK`

### Çalıştırılan kontroller

Ortam: bulut konteyneri (Linux), temiz ayrı checkout (`git clone` + `git checkout 1f03332`), Node 22.20.0 / npm 10.9.3,
Python 3.13.17. Tarih: 2026-10-26, 11:46–11:56 Europe/Berlin. Kayıtlar: `claude-progress/handoff-20261026/checks/`.

| Kontrol | Commit | Sonuç | Kayıt |
|---|---|---|---|
| `npm ci` | 1f03332 | Geçti (çıkış 0); **1 kritik güvenlik açığı** bildirimi | `claude-progress/handoff-20261026/checks/01_npm_ci.txt` |
| `npm run typecheck` | 1f03332 | Geçti | `claude-progress/handoff-20261026/checks/02_typecheck.txt` |
| `npm run lint` | 1f03332 | Geçti (uyarı/hata yok) | `claude-progress/handoff-20261026/checks/03_lint.txt` |
| `npm run build` | 1f03332 | Geçti | `claude-progress/handoff-20261026/checks/04_build.txt` |
| `python -m pytest tests/unit -q` | 1f03332 | **Başarısız: 10 başarısız, 1412 geçti, 45 atlandı** (4 dk 35 sn) | `claude-progress/handoff-20261026/checks/05_pytest_unit.txt` |
| Başarısız dosyalar taban commit'te (`babe9b6`, aynı node_modules) | babe9b6 | 6 başarısız, 21 geçti | `claude-progress/handoff-20261026/checks/06_pytest_failed_on_base.txt` |

Başarısızlıkların ayrımı:

- **Tabanda da başarısız (bu branch'ten önce de vardı, 6):** `test_acne_objectness_features.py` 5 test (ortamda `yolox`
  Python paketi yok) ve `test_localization.py::test_catalog_and_actual_frontend_behavior` (tabanda 22 eksik katalog mesajı).
- **Bu branch'in getirdiği gerilemeler (4 test + 2 yeni çeviri hatası):**
  1. `test_skin_overview_contract.py::test_new_overview_and_old_six_views_stay_distinct`: 7 sayfa bekliyor, artık 6 var
     (T-bölgesi birleştirmesi, `SKIN_VIEW_ORDER`).
  2. `test_skin_approved_layout.py::test_existing_layout_styles_and_visible_content_are_preserved`,
  3. `test_skin_product_refinements.py::test_frontend_blockers_3_4_5_three_angle_fusion_and_localization`,
  4. `test_skin_result_presentation.py::test_face_framing_and_score_rounding`: üçü de `tests/unit/ts_loader.js` içinde
     `Cannot find module './SkinInconclusiveDialog'` (test yükleyicisi yeni bileşen yollarını çözmüyor; uygulama build'i
     ise geçiyor). Test sözleşmeleri yeni arayüze göre güncellenmedi.
  5. `test_localization.py`: tabandaki 22 hataya ek olarak 2 yeni eksik mesaj: `"Bu taramada öne çıkan bir bulgu yok."`
     (katalogda noktasız hali var) ve takvim gün kısaltması `"Ça"`. Tabandaki `"T-bölgesi alın, burun ve çeneyi kapsar."`
     hatası bu branch'te yok.
- Bir test (`test_skin_product_refinements.py::test_python_and_typescript_multi_angle_fusion_parity`) tabanda başarısız, bu branch'te geçiyor.

Gerilemeler teslimi temiz göstermek için düzeltilmedi.

Hiç çalıştırılmayanlar:
- `tests/e2e/*` (Playwright sözleşme testleri). Eski arayüze göre yazıldılar (`data-skin-indicator`, `'nose'` sayfası, 7 sayfa); yeni ekranla **uyumsuz olmaları beklenir**. Güncellenmedi.
- Sunucu uçtan uca (`/api/local-health/skin`) gerçek fotoğrafla: model paketi ve yerel özel bağımlılıklar (Windows `health-final-private-deps.ps1`) olmadan çalıştırılamadı.
- Windows launcher, kamera, araç ekranı, mikrofon: hiç test edilmedi.

## 4. Gerçek akış ve örnek veri — durum

| Akış | Durum | Kanıt |
|---|---|---|
| Launcher → kamera → çekim → API → model → sonuç ekranı → geçmiş kaydı | **TEST EDİLMEDİ** (bu teslimde) | Gerçek tarama hiç yapılmadı |
| Bölgesel cilt tipi haritası (`general.regionalSkinMap`) üretimi | **EKSİK (paket yok)** / kod mevcut | `regional_attach.py`; model paketi teslimde yok |
| `general.findings` üretimi ve arayüze taşınması | **EKSİK** | Sunucuda `general.findings` üreten kod yok (`grep` ile doğrulandı). Arayüz yalnızca okuyor (`page.tsx` 986. satır civarı) |
| Belirginlik (`severity`), alan (`areaPct`), işaretler (`markers`) üretimi | **EKSİK** | Yalnızca araştırma betiklerinde; modeller dışa aktarılmadı |
| 20° kare yakalama | Kısmen mevcut (önceki çalışma) | Uygulama sol/sağ tek kare yakalıyor, yaw kapısı 12–45° (`skinMultiAngle.ts`) |
| ~25° ikinci kare yakalama | **EKSİK** | "Ön + 20° + ~25°" kurguları için her yana ikinci kare yok |
| Sivilce ve ben sayımı | **EKSİK** (doğrulanmadı) | Kova doğruluğu yalnızca %61; nokta düzeyinde doğrulama yok |
| Gerçek fotoğraf doğrulaması | **EKSİK** | Seçilen bulgu yöntemlerinin hiçbiri gerçek fotoğrafta doğrulanmadı. Eski dedektör sınıfları SCIN'de zayıftı (egzama AUC 0,58) |
| TR/EN/DE | Örnek veriyle arayüz testi: TAMAM | Playwright ile 6 sayfa + pencereler tarandı; EN'de Türkçe metin bulunmadı, DE metinleri Almanca |
| Ekran boyutları | Örnek veriyle arayüz testi: kısmen | 1600×1000 ve 1180×900 ekran görüntüsü; 1024 ve araç ekranı test edilmedi |
| Erişilebilirlik | **TEST EDİLMEDİ** | Yalnızca aria-label'lar eklendi; denetim yapılmadı |
| Güncel otomatik testler | Kısmen | §3; yeni bileşenler için birim testi yazılmadı; e2e eski |

"Örnek veriyle arayüz testi": `apps/vehicle-app/src/app/skin-preview/` geliştirme sayfası ve sentetik bir karakterin
fotoğrafıyla yapıldı. Bu sayfa ve fotoğraf **teslimde yoktur** (sentetik veri setinin parçası). Gerçek tarama başarısı
değildir.

**Önemli kullanıcı riski:** Sunucu `general.findings` göndermediğinde sonuç ekranı bulgu kartları yerine
"Bu taramada öne çıkan bir bulgu yok." yazar. Bu, gerçekte analiz yapılmamışken "bulgu yok" izlenimi verir.

## 5. API alanları (`general.findings`)

`general.findings = { version: string, findings: SkinFinding[] }` — **sunucu henüz üretmiyor; sözleşme önerisidir**
(`apps/vehicle-app/src/utils/skinFindings.ts`).

| Alan | Anlam | Birim / aralık | Eksik değer davranışı |
|---|---|---|---|
| `id` | Bulgu türü (`eyeBags`, `darkCircles`, `hoodedEyelids`, `downturnedCorners`, `crowsFeet`, `foreheadLines`, `acne`, `acneMarks`, `melasma`, `mole`, `spots`, `redness`, `rosacea`, `eczema`, `flaking`, `coldSore`) | — | Bilinmeyen id → `validFindings` kaydı reddeder |
| `region` | Sunucu bölgesi: `forehead`, `nose`, `periorbital`, `rightCheek` (görüntünün solu), `leftCheek`, `chin` | — | — |
| `status` | `seen` / `notSeen` / `inconclusive` | — | `notSeen` hiç gösterilmez |
| `causes` | Kesinleştirilemedi nedenleri: `LIGHTING`, `ANGLE`, `COVER` | — | Boşsa LIGHTING + ANGLE varsayılır |
| `severity` | **Belirginlik**: bulgunun görüldüğü referans yüzler arasındaki sıra (persentil). 0 = en hafif, 100 = en belirgin | 0–100, sayı | Yoksa bar `areaPct` ile, o da yoksa gösterilmez |
| `areaPct` | Bölgenin görünür derisinde bulgunun kapladığı yüzde (kızarıklık, melazma). Rozasea'da aynı bölgedeki kızarıklık alanı kullanılır | 0–100 | Yoksa bar yok |
| `countRange` | Sayı aralığı: sivilce `1-2`,`3-5`,`6-10`,`11-20`,`20+`; ben/leke `1-3`,`4-10`,`10+` | metin | Kesin sayı değildir |
| `markers` | Fotoğrafta işaret noktaları `{x, y, r?}` | `pose` fotoğrafının kaynak pikselleri | Poz farklıysa işaretler çizilmez |
| `pose` | `FRONT` / `RIGHT` / `LEFT` | — | Yoksa FRONT kabul edilir |

Ayrımlar:
- **Model güveni** yalnızca "var / yok" kararında eşikle karşılaştırılır; kullanıcıya hiç gösterilmez ve belirginlik değildir.
- **Belirginlik** fotoğraftaki görünürlüğün göreli sırasıdır. Doğrulama "doğru cevabı" Claude'un kör 1–3 derecelendirmesidir.
- **Klinik şiddet** ölçülmez; dermatolog etiketi yoktur. Arayüz "tanı değildir" der.

## 6. Bulgu eşlemesi: model/betik → giriş → ön işleme → karar → API → arayüz

Tüm sonuçlar **sentetik** karakterlerde (OpenAI görüntü API, 340 onaylı karakter) elde edildi. Eşik yalnızca eğitim
kişilerinde seçildi (`research/skin-findings/scripts/thr_rule.py`, `thr_prev`: her daha yüksek eşikte beklenen
kesinlik ≥ 0,80, p0 = min(0,25, eğitim yaygınlığı)); değiştirilmeden test kişilerine uygulandı. Ancak yöntem ve çekim
kurgusu seçimi aynı test sonuçlarına bakılarak yapıldı; **bağımsız, hiç kullanılmamış bir doğrulama kümesi yoktur**.
"Test" = 80 sabit kişi (pilot32 ∪ val28) ya da iç içe tekrarlı kişi düzeyinde çapraz doğrulama. ~25° pozu yalnızca test
kişilerinde var.

| Bulgu (arayüz) | Betik / yöntem | Giriş, açı | Ön işleme | Karar (test) | Belirginlik | API → arayüz |
|---|---|---|---|---|---|---|
| Göz altı torbası | `fa4.py`: DINOv2-small CLS+ortalama yama (768) + LR (C=0,02), 10 kat topluluk | Ön + ~25° | MediaPipe 478 nokta, `under_L/R` kırpıntı (pad 0,03 yüz genişliği), 224 px | eşik 0,94; P 1,00 R 0,50 (9/18, 80 kişi) | `sev_final.py` Ridge(α=1000) DINOv2 alt göz, ön+20°; uyum ρ=0,62; persentil | `eyeBags`/`periorbital` → Göz çevresi kartı + bar |
| Göz altı morluğu | `darkcircle.py`, `eye_grid3.py`: ışık düzeltmeli renk kıyası (`light.py`, Delaunay normal + Huber ışık) | Ön | Alt göz bandı vs aynı taraf yanak, Lab | eşik ~0,82; P 0,89 R 0,46 (140 kişi, iç içe) | Ridge DINOv2 + renk farkı; ρ=0,72 | `darkCircles` |
| Göz kapağı düşüklüğü | `eye_fair3.py`: geometri (açıklık, kaş–kapak, kıvrım) + DINOv2 kapak, iki göz | Ön | — | P 0,83 R 0,79 (140 kişi) | Ridge(α=300) DINOv2 kapak; ρ=0,73 | `hoodedEyelids` (uzman işaretli) |
| Göz kuyruğu düşüklüğü | `eye_fair3.py`: geometri (iç–dış köşe eğimi) + DINOv2 | Ön | — | P 0,82 R 0,51 (140 kişi) | **Tanımlanmadı** (eğim ölçüsü var, 0–100 eşlemesi yok) | `downturnedCorners` |
| Kaz ayakları | `fa4.py` DINOv2 `corner_L/R` + LR | Ön + 20° | pad 0,05 | eşik 0,94; P 0,94 R 0,81 | Ridge(α=1000); ρ=0,70 | `crowsFeet` |
| Alın çizgileri | `alin_repro.py` DINOv2 `forehead` + LR (yaşa bağlı olmayan 190 karakter) | Ön + 20° | — | P 0,86 R 0,85 (190 kişi, iç içe) | Ridge(α=300); ρ=0,60 | `foreheadLines` (T-bölgesi) |
| Uçuk | `fa4.py` DINOv2 `lip` + LR | Ön + 20° + ~25° | pad 0,04 | eşik 0,80; P 0,90 R 0,69 | Yok (ρ=0,32 yetersiz) | `coldSore` (uzman), barsız |
| Akne izi | `fa4.py` DINOv2 yanak + çene | Ön + 20° | — | eşik 0,97; P 0,83 R 0,83 (**yalnızca 22 kişi, 6 pozitif**) | Ridge(α=300); ρ=0,42 (3 aralık) | `acneMarks` |
| Sivilce | `lesion_eval.py` (TASK=Sivilce): dedektör özelliklerinin öğrenilmiş birleşimi (findings Akne + acnes alt tipleri) | Ön + 20° | `features2.py`, `kx_pipeline.sh` | eşik 0,60; P 0,86 R 1,00 (6 pozitif) | `countRange` (doğrulanmadı) | `acne` |
| Melazma | `det_prev.py`: findings dedektörü (Güneş Lekesi kutuları), yanak | Ön + 20° + ~25° | — | eşik 0,54; P 0,86 R 0,67 | `areaPct` (**tanımı/üretimi yok**) | `melasma` |
| Ben | `det_prev.py`: Riskli Ben | Ön + ~25° | — | eşik 0,58; P 1,00 R 0,40 | `countRange` (doğrulanmadı) | `mole` (uzman) |
| Rozasea eğilimi | `det_prev.py`: Rozasea | Ön + 20° | — | eşik 0,69; P 1,00 R 0,82 | Kızarıklık `areaPct` | `rosacea` (uzman) |
| Kızarıklık | `redness_prev.py`: dedektör (skinmap Redness + findings) | Ön + 20° + ~25° | — | eşik 0,54; P 0,89 R 1,00 | `areaPct` (**tanımı/üretimi yok**) | `redness` |
| Egzama/sedef eğilimi | `ecz_flake2.py`: DINOv2 bölge kırpıntıları, bölge etiketli LR | Ön + 20° | — | P 0,85 R 0,69 (340 kişi, iç içe); bölge P 0,90 R 0,42 | Yok | `eczema` (uzman) |
| Pullanma | `ecz_flake2.py` (kuru bölge + egzama/sedef etiketi; hafif kuru kişiler hariç) | Ön + 20° | — | P 0,92 R 0,78; bölge P 0,96 R 0,37 | Yok | `flaking` |
| Türü belirlenemeyen leke | — (Güneş lekesi %80 kesinliğe ulaşmadı: P 0,41) | — | — | **Tanımlanmadı** | — | `spots` |

Kayıtlı tablolar: `research/skin-findings/results/` (`fa4.md`, `eye_fair3.md`, `eye_grid3_rerun.md`, `det_prev.md`,
`redness_prev.md`, `lesion_eval_*.md`, `alin_repro.md`, `ecz_flake2.md`, `sev_*.md`). 2026-10-26 sabahı `det_prev`,
`redness_prev`, `lesion_eval`, `alin_repro`, `eye_grid3` ve `ecz_flake2` yeniden çalıştırıldı; `eye_grid3` çıktısı
kayıtlı olanla birebir aynı. `det3.md`, `det4.md`, `fa3.md` kaydedilmemiş satır içi betiklerle üretilmişti.

Belirginlik: Claude 292 pozitif yüzü (7 bulgu: torba 48, morluk 54, kapak 31, kaz 45, alın 34, akne izi 38, uçuk 42) ölçümleri görmeden 1–3 derecelendirdi (`research/skin-findings/ratings/`).
Ridge modelleri bu derecelendirmelere karşı kişi düzeyinde 5 kat × 20 tekrar ile değerlendirildi; α iç içe değil, sonradan
sabitlendi (hafif iyimserlik). Skor = katlar dışı tahminin pozitifler içindeki persentili.

## 7. Model manifesti ve erişim

Ayrıntılı manifest: `research/skin-findings/MODEL_MANIFEST.json` (ad, dosya, sürüm, boyut, SHA-256, konum, lisans,
çalışma zamanı). SHA-256 değerleri 2026-10-26'da yeniden hesaplanıp doğrulandı.

| Model | Boyut | SHA-256 (ilk 16) | Konum | Gerekli mi |
|---|---|---|---|---|
| findings (RF-DETR Small) | 127,5 MB | c8d94801bf86c65a | **Yalnızca bulut konteyneri** | Evet |
| skinmap (RF-DETR Seg Small) | 133,8 MB | bc4e8aab0866ece0 | **Yalnızca bulut konteyneri** | Evet |
| acnes (RF-DETR Seg Small) | 133,8 MB | 5db24d92049c0d33 | **Yalnızca bulut konteyneri** | Evet |
| regional (RF-DETR Small) | 127,4 MB | b23cd0ed5a18caa6 | **Yalnızca bulut konteyneri** | Evet |
| wrinkles (RF-DETR Seg Small) | 133,8 MB | ba5c527859c1cb59 | **Yalnızca bulut konteyneri** | Evet |
| facebook/dinov2-small | 88,2 MB | ae1e99fcefd534ed | Hugging Face (herkese açık, Apache-2.0) | Evet |
| face_landmarker.task | 3,8 MB | 64184e229b263107 | Repo | Evet |
| k_classifier.json | 134 KB | a7ab0b05686d4d96 | Repo (Git) | Evet |
| Bulgu LR'leri, belirginlik Ridge'leri | — | — | **Dosya olarak yok**; betikler her seferinde yeniden eğitir | Evet |

RF-DETR ağırlıkları Roboflow çalışma alanından (`tolgar-sasmaz`) `research/skin-findings/scripts/dl_weights.py` ile
indirildi; eğitim verisi lisansları **doğrulanmadı** (bir kısmı Roboflow Universe kaynaklı).

**Teslim engelleri**
1. RF-DETR ağırlıkları, sentetik veri seti (≈2,9 GB), gömme/özellik önbellekleri ve SCIN alt kümesi yalnızca geçici bulut
   konteynerinde. Konteyner kapanınca silinir. Codex erişemez.
2. Bulgu sınıflandırıcıları ve belirginlik modelleri dışa aktarılmadı; üretim için dondurulmuş eşikler ve dosyalar yok.
3. Yetkili özel aktarım seçenekleri (kullanıcı onayı gerekir, hiçbiri yapılmadı):
   (a) ağırlıkları sahibi olarak Roboflow'dan `dl_weights.py` ile yeniden indirmek (`ROBOFLOW_API_KEY`);
   (b) veri setini ve önbellekleri kullanıcının **özel** Hugging Face dataset reposuna ya da Google Drive klasörüne yüklemek;
   (c) kullanıcının sağlayacağı özel bir depolama hedefi.

## 8. Bilinen eksikler, riskler ve kabul engelleri

Bunlar denetimden muaf değildir; Codex hata, risk veya kabul engeli olarak raporlayabilir.

1. **Sunucu `general.findings` üretmiyor** → gerçek taramada hiçbir bulgu görünmez ve ekran "öne çıkan bulgu yok" der (yanıltıcı).
2. Bulgu ve belirginlik modelleri dışa aktarılmadı; eşikler üretim için dondurulmadı.
3. Model ağırlıkları ve veri seti teslim edilemedi (§7).
4. ~25° ikinci kare yakalama yok; seçilen bazı kurgular buna dayanıyor (torba, uçuk, melazma, ben, kızarıklık).
5. Sivilce/ben sayımı doğrulanmadı; `areaPct` (kızarıklık, melazma) tanımlanmadı; göz kuyruğu belirginliği tanımlanmadı; "türü belirlenemeyen leke" tanımlanmadı.
6. Tüm doğruluk sonuçları sentetik veriye dayanıyor; gerçek fotoğraf doğrulaması yok; bağımsız doğrulama kümesi yok; bazı test grupları çok küçük (akne izi 6, sivilce 6 pozitif).
7. Belirginlik doğru cevabı Claude'un kör derecelendirmesi; dermatolog etiketi yok.
8. Öneri içerikleri (Docs: "Cilt Bulguları: Belirginliğe Göre Öneriler") **dermatolog incelemesinden geçmedi**.
9. Kullanıcı kabulü yapılmadı.
10. `k_classifier.json` (model ağırlığı) commit `952e1f8` ile Git geçmişinde. "Model ağırlıklarını Git'e ekleme" kuralıyla çelişiyor; geçmiş yeniden yazılmadı, karar kullanıcıya bırakıldı.
11. Birim testlerinde bu branch'in getirdiği 4 gerileme ve 2 yeni çeviri hatası var (§3). e2e testleri eski arayüze göre; yeni bileşenlere birim testi yok; erişilebilirlik denetlenmedi.
12. `npm ci` 1 kritik güvenlik açığı bildiriyor (ayrıntı `claude-progress/handoff-20261026/checks/01_npm_ci.txt`; bu teslimde değiştirilmedi).
13. Geçmiş grafiği yalnızca `general.findings` içeren eski kayıtlarla çalışır; mevcut kayıtlarda yoktur.

## 9. Geri dönüş

- Bu branch'teki tüm Claude değişikliklerinden önceki sürüm: `babe9b6970b011f65d642600aaa0ca2fd2b7f316` (`feat/skin-product-refinement`).
- Yüz haritası sonuç ekranından önceki son durum (bölgesel cilt tipi haritası dahil): `c756a1a07fcd7f11ce5888fd980c5745435918ef`.
- `main`: `7463eef112c5a40f7cd01192b6d1f4e9fa6ab285`.

## 10. Codex inceleme komutu (kopyala/yapıştır)

```text
Görev: Attune.more reposunun claude/skin-validated-20261025 branch'ini (taban babe9b6) bağımsız olarak incele ve test et.
Kodu değiştirme; bulguları dosya:satır, yeniden üretme adımı ve önem derecesiyle raporla.
Önce CODEX_HANDOFF.md ve research/skin-findings/README.md, MODEL_MANIFEST.json dosyalarını oku.
Bilinen eksikler dahil her şeyi hata, risk veya kabul engeli olarak raporlayabilirsin; hiçbir madde denetimden muaf değildir.

1. Teslim doğrulaması: bundle SHA-256 ve `git bundle verify`; HEAD SHA'nın belgedekiyle eşleşmesi.
2. Kurulum ve otomatik kontroller (Node 22.20.0 / npm 10.9.3, Python 3.13): npm ci, npm run typecheck, npm run lint,
   npm run build, python -m pytest tests/unit -q. Sonuçları belgedeki §3 ile karşılaştır.
3. Sunucu sözleşmesi: /api/local-health/skin yanıtında general.findings üretilip üretilmediğini kontrol et; üretilmiyorsa
   arayüzün bu durumda kullanıcıya ne gösterdiğini değerlendir. regional_skin_v3 model paketi yokken davranışı test et.
4. Araştırma kodu: §6 tablosundaki her bulgu için betik → giriş/açı → eşik → API alanı eşlemesinin koda uyduğunu, eşik
   seçiminin yalnızca eğitim kişilerinde yapıldığını ve test/eğitim ayrımını kontrol et. Sentetik veri, kör
   derecelendirme ve gerçek fotoğraf kanıtlarının ayrı tutulduğunu doğrula.
5. Arayüz (örnek veriyle arayüz testi olarak etiketle): localStorage togg_health_latest_skin içine general.findings
   içeren bir kayıtla /skin sonuç ekranı; sekmeler, oklar, fotoğraf etiketleri, belirginlik barı (değer barın ucunda),
   Genel bakış (cilt tipi kartı, 2×2 kart, oklar 4'erli kaydırır), Öneriler (skor aralığına göre), Kesinleştirilemedi ve
   Tekrar tara, Geçmiş + tarih aralığı. TR/EN/DE (localStorage attune.language.v1), 1280/1180/1024 genişlik, dokunma
   alanları ≥44 px, dialog odak ve Escape, konsol hataları.
6. Güvenlik/gizlilik: commit geçmişinde anahtar, .env, kişisel fotoğraf, model ağırlığı (k_classifier.json dahil).
7. e2e testleri (tests/e2e/*skin*) yeni arayüzle çalışıyor mu?

Rapor formatı: Bulgu | Önem (Kritik/Yüksek/Orta/Düşük) | Kabul engeli mi | Dosya:satır | Yeniden üretme | Öneri.
Gerçek tarama ile örnek veri testlerini ayrı başlıklarda raporla.
```

## 11. İlerleme kaydı

`claude-progress/handoff-20261026/status.json` (teslim paketinde ve bu branch'te). Bulut konteynerindeki kopya geçicidir.
