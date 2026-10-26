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
| Göz kuyruğu düşüklüğü | Geometri + DINOv2 (`eye_fair3.py`) | Ön | Eğim sırası % (pozitifler arasında; derecelendirmeyle doğrulanmadı, AUC 0,66) | P 0,82 R 0,51. Kurulu eşik 0,668 (araştırma ort. 0,82); **kullanıcı 0,668'i onayladı** (2026-10-26) |
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

## 5d. Codex düzeltme turu (inceleme: d6474d9) — düzeltmeler, dosya:satır, kanıt

Bu bölüm teslim commit'indeki satır numaralarını verir. Codex yeniden incelemeden kabul sayılmaz.

| # | Codex bulgusu | Düzeltme (dosya:satır) | Test kanıtı |
|---|---|---|---|
| 1 | Nokta yoksa otomatik `count=1 / countAtLeast` | `services/core-api/skin_findings_v1.py:269` — sayım yapıldıysa (bölge okunabilir + dedektör kutu listesi var) `count=0`, `countPose`; yapılamadıysa sayı yok, `countUnavailable='COUNT_NOT_RUN'` | `tests/unit/test_skin_findings_v1.py::test_counts_never_double_count_and_melasma_area` (0 / sayılamadı / FRONT'tan sayıldı) |
| 1b | Eski `countAtLeast` kayıtlarından kesin sonuç | Kayıtlar değişmez. `skinHistorySummary.ts:50` `measureOf` → `exact=false, why=NO_EXACT_COUNT`; karşılaştırma `incomparable`, ortalamaya girmez; `skinRecommendations.ts:123` bant yok (0 sayı da bantsız) | `test_skin_history_summary.py::test_states_scope_versions_and_legacy_counts` |
| 1c | 8 → 3 kesin fark | `compareMeasures` (`skinHistorySummary.ts:87`) | `…::test_reviewer_counter_examples` (↓ 5, önceki 8) |
| 2a | Önceki 8, yeni inconclusive → "Görülmedi" | Durumlar ayrıldı: seen / notSeen / inconclusive / unavailable / missing. Yalnız tüm kapsamda `notSeen` = ölçülmüş yokluk → `unknownNow` | `…::test_reviewer_counter_examples` (1) |
| 2b | Aynı kayıtların ortalaması 4 | `skinAverages` (`skinHistorySummary.ts:142`): bilinmeyen tarama ortalamaya 0 olarak girmez → 8 (1 tarama) | (2) |
| 2c | Önceki inconclusive, yeni 8 → "Yeni / yoktu" | `noPrevious` → "önceki taramada ölçülemedi" | (3) |
| 2d | severity 80 / areaPct 20 → "alan %50" | Tür (sayı · görünüm skoru · belirginlik · eski alan %) ve yöntem sürümü aynı olmadıkça karşılaştırma/ortalama yok (`DIFFERENT_MEASURE` / `DIFFERENT_METHOD`) | (4) |
| 2e | unavailable / FUSION_FAILED / [] → "Bulgu görülmedi" | `recordSummary` (`skinHistorySummary.ts:132`) → `not-measured` ("Bulgular ölçülemedi"); boş `findings` da ölçülmüş yokluk değildir | (5) |
| 2f | Bölge kapsamı | Kapsam = bulgunun her iki kayıtta satırı olan bölgeleri; biri ölçülmemişse `PARTIAL_REGIONS`. Sayfa/genel bakışta ölçülemeyen bölge `incomplete` ile yazılır (`skinFindings.ts:151`); sayılamayan bölge varsa toplam sayı gösterilmez (`:152`) | `…::test_states_scope_versions_and_legacy_counts` |
| 2g | Tutarlılık | Grafik (`SkinFindingCard.tsx` `History`), modül kartı, tablo, ayrıntı ve öneri aynı `measureOf` / `compareMeasures` kurallarını kullanır | `tests/e2e/skin_health_history_ui.py`, `current_skin_findings_sample_ui.py` |
| 3 | Yan pozların fotoğrafı saklanmıyor (`INVALID_OVERVIEW_SOURCE`) | `apps/vehicle-app/src/app/skin/page.tsx:572` — genel sonuç yalnız FRONT karesine yazılır, LEFT/RIGHT'tan kaldırılır. `skinPhotoHistory.ts` doğrulamaları değişmedi | `tests/unit/skin_photo_three_pose_storage.cjs` (+ pytest sarmalayıcısı), `tests/e2e/skin_photo_storage.py` (gerçek tarama, IndexedDB) — sonuç §6 |
| 5 | Kesinleştirilemeyen bulgu geçmişte kayboluyor (sivilce notSeen + rozasea inconclusive → "Bu taramada görülen bulgu yok"; sivilce 3 + rozasea inconclusive → ayrıntıda rozasea yok) | `skinHistorySummary.ts` `compareRecords`: güncel kayıtta `inconclusive` satırı olan her bulgu ayrıntıya girer; daha önce görülmüş olma şartı yok (analiz `unavailable` değilse). `recordSummary` yeni `inconclusive` listesini döndürür ve bu liste doluysa `none-seen` vermez. `RecordHistory.tsx` `SkinRowSummary`: "Rozasea eğilimi · Kesinleştirilemedi" çipi (2'den fazlaysa "N bulgu kesinleştirilemedi"). `SkinRecordComparison.tsx`: kesinleştirilemeyen bulgu varken "görülen bulgu yok" yazılmaz | `test_skin_history_summary.py::test_inconclusive_findings_stay_visible_in_history`, `tests/e2e/skin_history_inconclusive_ui.py` (örnek veri, TR/EN/DE) |
| 6 | Sunucu 50, istemci 51 (usablePx=40000, affectedPx=10201, intensity=8 → 50,5) | Tek yuvarlama kuralı: `skin_appearance.py` `round_half_up`, `skinAppearance.ts` `roundHalfUp` (§5e). İkisi de 51 verir | `test_skin_history_summary.py::test_appearance_rounding_parity_server_client` (karşı örnek + 10 bölge / 4 havuz Python↔TS birebir eşitlik; kayıt → geçmiş → ekran 51) |
| 4 | Görünüm skoru | §5e | `…::test_appearance_score_contract_and_comparison`, `test_skin_findings_v1.py::test_appearance_raw_values_shared_mask_and_unavailable` |

## 5e. Görünüm skoru — hesap sözleşmesi `appearance-v1`

**Kaynak:** `services/core-api/skin_appearance.py`, istemci kopyası `apps/vehicle-app/src/utils/skinAppearance.ts`. Python ile TS'nin aynı sonucu verdiği (eşlik) testle doğrulanır.

**Girdi:** her bölge tek pozdan alınır (FRONT: alın, burun, çene · LEFT: sağ yanak · RIGHT: sol yanak). Hepsi mevcut ışık düzeltmeli görüntüden (`skin_findings_det.light_redness`) gelir:
- `usablePx`: bölgenin kullanılabilir cilt pikselleri.
- `affectedPx`: a* > am + 4 olan pikseller; am = tüm yüzün kullanılabilir cildinin medyan a* değeri, yani referans cilt. Bu gerçek bir piksel maskesidir; tespit kutusu kullanılmaz.
- `intensity`: etkilenen piksellerde ortalama (a* − am), CIE a* birimi.

**Birleştirme** (sayfa / tüm yüz):
- alan = Σ affectedPx / Σ usablePx; yoğunluk = etkilenen piksellerle ağırlıklı ortalama.
- Bölgesel yüzdeler toplanmaz. Ölçülmeyen bölge varsa sonuç `partial` olur ve karşılaştırılmaz.

**Skor:** `score = round_half_up(100 · sqrt(min(1, alan/0,50) · min(1, yoğunluk/16)))`.
- **Yuvarlama (sunucu, kayıt ve ekran aynı):** `round_half_up(x, d) = floor(x·10^d + 0,5) / 10^d`. Python'da `skin_appearance.round_half_up`, TS'de `skinAppearance.roundHalfUp`. Python `round()` (yarımı çifte yuvarlar) ve `Math.round` artık kullanılmaz. `areaPct` ve `intensity` 2 ondalığa aynı kuralla yuvarlanır. Skor saklanan 2 ondalıklı yoğunluktan hesaplanır, böylece her yeniden hesap aynı sayıyı verir. Formül, sabitler, ağırlıklar ve tespit eşikleri değişmedi.
- Sabit ölçek. Her fotoğrafta yeniden kurulmaz; ilk tarama 100 sayılmaz.
- Alan veya yoğunluk artarken azalmaz; etkilenen piksel yoksa 0'dır.
- Sabitler (0,50 ve 16 a*) okunur bir ölçek için seçilmiş mühendislik değerleridir; klinik olarak doğrulanmadı.
- Skor tespit olasılığı, etkilenen alan yüzdesi ya da hastalık şiddeti değildir.

**Saklanan alanlar:** her satırda `appearance = {version, usablePx, affectedPx, areaPct, intensity, score}`. Eski `areaPct` ve `toneDiff` aynen korunur; eski skorlar yeni skora dönüştürülmez.

**Bulgu bazında:**

| Bulgu | Durum |
|---|---|
| Kızarıklık, rozasea, egzama/sedef | Hesaplanır. Üçü aynı bölgesel kırmızı maskeyi kullanır; satırda `appearanceSharedWith` ve ekranda "Aynı bölgesel kızarıklık ölçümü: …" yazar, bağımsız ölçüm gibi sunulmaz. Değer yoksa `MEASURE_NOT_AVAILABLE`. |
| Melazma | **unavailable** (`AFFECTED_MASK_NOT_AVAILABLE`). Mevcut çıktı yalnız tespit kutusu kapsamı (`findings_Gunes_Lekesi_cov20`); etkilenen piksel maskesi yok. Kutu alanı "İşaretli leke kutularının kapladığı alan" diye ayrıca gösterilir, etkilenen cilt alanı sayılmaz. **Engel.** |
| Düz akne izi | **unavailable** (`AFFECTED_MASK_NOT_AVAILABLE`). Akne izi DINOv2 sınıflandırıcı + belirginlik modelidir; maske yok. Mevcut belirginlik çubuğu korunur. **Engel.** |
| Gözenek | Modelde "Genis Gozenek" sınıfı var, ama uygulamada ve sunucuda kullanılan bir gözenek ölçümü yok (kodda arandı). Talimat gereği dokunulmadı. |

**Ekran:**
- Bu bulgularda çubuk görünüm skorunu gösterir; ham alan ve renk yoğunluğu ayrı satırdadır.
- Aynı yöntemle önceki taramaya göre değişim yalnız "Görünüm skoru N puan azaldı." / "… arttı." / "… değişmedi." şeklinde yazılır; göreli yüzde yok.
- Eski öneri eşikleri yeni skora uygulanmaz: bu bulgularda öneri bandı seçilmez.

## 5c. Sonuç ekranı ve Sağlık Geçmişim (kullanıcı onaylı, 2026-10-26)

**Sonuç ekranı:**
- Fotoğrafın altında ve çevresinde bulgu etiketi yok. Seçili bulgu fotoğrafın üzerinde işaretlenir: alan boyanır, lezyon için daire çizilir.
- "Akne türleri" satırları düğmedir. Bir türe dokununca fotoğrafta yalnız o türün daireleri kalır (`data-skin-marker-type`); aynı türe tekrar dokununca hepsi geri gelir.
- E2E bunu çizilen işaretlerle doğrular.

**Sağlık Geçmişim** (`components/RecordHistory.tsx`, `HealthHistoryOverview.tsx`, `skin/SkinRecordComparison.tsx`, `utils/skinHistorySummary.ts`):
- **Cilt modül kartı:** son 3 bulgulu taramanın ortalaması.
  - Sayılar (sivilce, ben): o bulguyu ölçen her taramada ortalanır; ölçüp görmeyen tarama 0 sayılır, ölçülemeyen tarama hesaba katılmaz.
  - Yüzdeler: bulgunun görüldüğü taramaların ortalaması.
  - Cilt tipi: en sık görülen.
- **Kayıt tablosu:** tüm modüllerin tekil analizleri satır satır: Tarih, Saat, Modül, Özet. Cilt özeti: cilt tipi + ilk iki bulgu + "+N bulgu".
- Satıra dokunmak ayrıntıyı açar. En sağdaki çöp kutusu siler; onay penceresi aynıdır.
- Erişilebilir adlar ("Sonucu Aç", "… kaydını sil: …") ve `data-record-id` / `data-record-category` korunmuştur.
- **Cilt ayrıntı penceresi:** her görülen bulgu tek satırda; "Son tarama" değeri ve "Önceki taramaya göre" değişim. Karşılaştırma **bir önceki taramaya** göredir, ortalamaya göre değildir.
  - Değişim türleri: ↑/↓ fark, "= aynı", "Yeni", "Görülmedi".
  - Önceki taramada ölçülemeyen bulgu için değişim gösterilmez.
- **"Sonuç ekranında aç":** `/skin?view=record&id=…` o kaydı tam sonuç ekranında açar.
  - Fotoğraf: en son tarama için bellekteki fotoğraf. Diğer kayıtlarda, ayrı fotoğraf saklama onayı varsa cihazda saklanan fotoğraf (`loadSkinPhotos`), yoksa fotoğrafsız.
- Bulgusu olmayan eski cilt kayıtları eski ayrıntı görünümünü (`SkinRecordDetail`) kullanır.
- **Testler:** `tests/unit/test_skin_history_summary.py`, `tests/e2e/skin_health_history_ui.py` (örnek veri, TR/EN/DE); gerçek kamera E2E'si de yeni kaydı tabloda açar.

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

Düzeltme etkiyi azaltıyor ama tamamen gidermiyor (K-074'te 1 kayıp, K-258'de 1 fazla kalıyor).

**Kullanım şekli (kullanıcı kararı, 2026-10-26):** Araç kamerası profili ve kart kalibrasyonu bir açık iş değil, **OEM'lerle anlaşılan noktada uygulanacak yöntemdir**. Her OEM / araç modeli / kabin kamerası için bir kez yapılır:
1. OEM, kameranın YUV matrisini ve aralığını (veri sayfası / ISP ayarı) verir.
2. Kart OEM'in kabininde, kendi ışığında çekilir.
3. `fit_profile.py` veya servis uç noktası profili üretir; profil araç yazılımıyla dağıtılır (`ATTUNE_CAMERA_PROFILE`).

**Yazılım hazırdır:** ham kare yolu, profil okuma, renk düzeltmesi, kart, uydurma, kalite kapıları ve testler. Gerçek bir OEM kamerasıyla henüz uygulanmadı; bu, OEM anlaşmasıyla gelecek adımdır.

## 6. Doğrulama

### 6.0 Codex düzeltme turu (bu teslim) — ayrı ayrı raporlanmıştır

**Ek tur (Codex: kesinleştirilemeyen bulgu + yuvarlama, 2026-10-26)** — test edilen kod bu teslim commit'idir.
- Birim: `test_skin_history_summary.py` 5/5 (yeni: `test_inconclusive_findings_stay_visible_in_history`, `test_appearance_rounding_parity_server_client`); ilgili set (history, findings_v1, findings_i18n, findings_ui, localization, photo three-pose) 35/35. Tüm `tests/unit`: 1453 geçti, 45 atlandı, 6 başarısız (tabanda da başarısız olan aynı 6: yolox ×5, özel model.onnx ×1).
- `tsc --noEmit` temiz · `npm run lint` uyarı/hata yok · `npm run build` başarılı · `scripts/localization/check.cjs` failures=[].
- Örnek veriyle arayüz (model çıktısı değil): `tests/e2e/skin_history_inconclusive_ui.py` (yeni, TR/EN/DE) PASS; `skin_health_history_ui.py` PASS; `current_skin_findings_sample_ui.py` PASS.
- Gerçek model inference (sahte kamera y4m, K-217 sentetik karakter; fiziksel kamera DEĞİL): `current_skin_contract.py --chromium --software-gpu --skip-native-zoom` PASS. Kayıt = API yanıtı (görünüm alanları dahil); 14 appearance satırının her biri ham değerlerinden aynı skoru veriyor. Windows native zoom adımı çalıştırılmadı.
- Çalıştırılmayanlar: fiziksel kamera, Windows launcher, araç ekranı (§6.5, §8).

Kanıt dosyaları: `claude-progress/realpath-20261026/codex-fixes-20261026/`. Fotoğraf içermez.

**Otomatik testler:**
- `pytest tests/unit`: 1450 geçti, 45 atlandı, 6 başarısız. Başarısızların hepsi tabanda da başarısız:
  - `test_acne_objectness_features` ×5: `yolox` modülü yok;
  - `test_hosted_skin_type_runtime`: bu dizindeki özel `model.onnx`; temiz klonda geçer.
- Yeni/güncellenen testler:
  - `test_skin_history_summary.py`: 3 test; Codex karşı örneklerinin hepsi adıyla.
  - `test_skin_findings_v1.py`: 10 test; 0 sayım, sayılamadı ve sunucu görünüm skoru.
  - `skin_photo_three_pose_storage.cjs`: 9/9. Düzeltme öncesi `page.tsx` ile bilerek başarısız olur.
  - `test_skin_findings_i18n.py`: 5 test. Geçmiş girdileri artık yöntem sürümü taşıdığı için fikstür güncellendi; hiçbir kontrol gevşetilmedi.
- `tsc --noEmit`: 0 hata. `npm run lint`: temiz. `npm run build`: başarılı. Yerelleştirme kontrolü: PASS.

**Örnek veriyle arayüz** (model çıktısı değil; Chromium):
- `current_skin_findings_sample_ui.py`: PASS.
- `skin_health_history_ui.py`: PASS (TR/EN/DE). Melazma ve ben için önceki kayıtta satır yok; değişim "önceki taramada ölçülemedi" olarak gösterilir, "Yeni" denmez.
- `skin_i18n_screens.py`: PASS (TR/EN/DE).

**Fotoğraf saklama** (`tests/e2e/skin_photo_storage.py`):
- Gerçek uygulama ve sahte kamera aygıtıyla gerçek tarama; IndexedDB kaydı. Sonuç: (a), (b), (c) ve (d) PASS.
- Düzeltme öncesi derlemede (a) ve (b) FAIL oluyordu ("Cilt fotoğrafı kaydedilemedi").
- (d)'deki izin kapalı kontrolü uygulamanın kendi yazma fonksiyonuyla yapıldı; ikinci bir gerçek tarama yapılmadı.

**Gerçek model inference** (`current_skin_contract.py`, K-217, ham kare yolu, fixture renk profili): PASS, 169 s.
- API → kayıt → sonuç ekranı → yeniden açılan kayıt → Sağlık Geçmişim tablosu ve ayrıntı → "Sonuç ekranında aç" zinciri boyunca kayıt, API'nin birleşik bulgularıyla birebir aynıdır.
- Görünüm skoru, gerçek çıktı:
  - Sağ yanak kızarıklık / rozasea: 71 (alan %56,73, yoğunluk +8,07; ortak maske notuyla).
  - Sol yanak kızarıklık: 57 (%38,45, +6,67).
- Eski "1+" yerine ölçülmüş 0: burunda sivilce 0 (`countPose` FRONT), uçuk 0.

**Sahte kamera fiziksel kamera değildir.** Fiziksel kamera, araç ekranı ve Windows launcher bu turda da **TEST EDİLMEDİ**.

**Yeniden üretme** (sunucular :8000 ve :3000'de; `ATTUNE_REGIONAL_V3_DIR` model paketi; `ATTUNE_CAMERA_PROFILE=tests/e2e/fixtures/camera-profile-fixture-bt601.json`):
```
python3 -m pytest -q tests/unit
python3 tests/e2e/current_skin_findings_sample_ui.py --chromium
python3 tests/e2e/skin_health_history_ui.py --chromium
python3 tests/e2e/skin_i18n_screens.py --chromium
SKIN_E2E_Y4M=<K-217 y4m> python3 tests/e2e/skin_photo_storage.py
SKIN_E2E_EXPECT_RAW=1 SKIN_E2E_Y4M=<K-217 y4m> python3 tests/e2e/current_skin_contract.py --chromium --software-gpu --skip-native-zoom
```
y4m dosyası `tests/e2e/make_skin_y4m.py FRONT.png SIDE1.png SIDE2.png out.y4m 20 0.34` ile üretilir; fotoğraflar Git'te değildir.


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

**Bu turdan (Codex düzeltmeleri):**
- **A. Melazma ve düz akne izi görünüm skoru:** mevcut çıktılarda etkilenen cilt alanını piksel düzeyinde ayıran bir maske yok. Skor `unavailable` (`AFFECTED_MASK_NOT_AVAILABLE`); yeni yöntem veya eğitim yapılmadı.
- **B. Gözenek:** kullanılan bir ölçüm yok; talimat gereği dokunulmadı.
- **C. Skor sabitleri:** (0,50 alan · 16 a*) mühendislik seçimidir; klinik veya dermatolog doğrulaması yok. Görünüm skoru için öneri bandı tanımlı değil (eski bantlar uygulanmadı).
- **D. Ölçülmüş 0 ile "görüldü" çelişkisi:** sınıflandırıcı bulguyu "görüldü" derken sayım 0 olabilir (ör. uçuk 0). Bu durum, doğrulanmamış "1+" yerine gerçek sayımı gösterir.
- **E. Kabul katmanları:** fiziksel kamera, araç ekranı, Windows launcher, gerçek fotoğraf ve klinik doğrulama yapılmadı. Codex bağımsız incelemesi bekleniyor.


1. **Eşik ve kamera hattı:** Eşikler araştırma PNG'lerinde seçildi. Ham kare + profil yolu eklendi (§5b). Araç kamerası profili ve kart kalibrasyonu açık iş değildir: OEM ile anlaşma aşamasında, OEM'in kabin kamerası için uygulanacak yöntemdir ve yazılımı hazırdır (§5b).
   - Uygulamanın gönderdiği PNG orijinalden ort. 1,4/255 farklı. PNG kayıpsız olduğundan fark kodlamadan önce oluşuyor; büyük olasılıkla tarayıcının YUV420→RGB dönüşümü (kanıtlanmadı).
   - Etki: K-217 rozasea 0,757 (Python/ffmpeg ile aynı y4m) → 0,48–0,54 (uygulama yolu); eşik 0,69.
   - Eşikler P≥0,8 sınırına yakın olduğundan küçük renk kaymaları kararı çeviriyor.
   - Ölçülen neden: tarayıcının yanlış renk matrisi (§5b). Kullanıcı ham kare (1) ve araç kalibrasyonunu (3) onayladı; ikisi kuruldu. Beyaz denge kilidi, kare ortalama ve eşik yeniden doğrulaması kullanıcı kararıyla yapılmayacak.
2. **Göz kuyruğu eşiği — KARAR VERİLDİ:** Kurulu eşik 0,668 (araştırma ortalaması 0,82). Kullanıcı 2026-10-26'da 0,668'de kalmasını onayladı. Daha yüksek eşiğe göre daha fazla yanlış pozitif beklenmesi bilinen bir ödünleşimdir; açık engel değildir.
3. **Göz altı morluğu belirginliği:** Araştırmada seçilen model yerine gömme-only kol kullanıldı (ρ 0,75 yerine 0,66).
4. **mediapipe gereksinimi:** Sunucuda mediapipe yoksa sivilce ve kızarıklık kararları araştırmadan sapabilir (testte 1 eşik geçişi).
5. **Bağımsız doğrulama yok:** Gerçek fotoğraf, klinik doğrulama ve dermatolog incelemesi yok. Öneri içerikleri de incelenmedi.
6. **Doğrulanmamış değerler:** Sayımlar, alt türler, alanlar, ton farkı ve sıralar doğrulanmadı. Seçilen bulgu ama işaretlenmeyen lezyon durumunda "1+" gösterilir.
7. **Sağlık Geçmişim — ÇÖZÜLDÜ (kullanıcı onaylı tasarım, 2026-10-26):** bkz. §5c.
8. **`/skin/regional-fuse` güveni:** İstemcinin gönderdiği poz sayılarına güvenir (imza yok).
9. **Test edilmeyenler:** Fiziksel kamera, Windows launcher, araç ekranı, erişilebilirlik denetimi ve kullanıcı kabulü.
10. **Git geçmişi:** `k_classifier.json` (model ağırlığı) Git geçmişinde duruyor.
11. **Güvenlik açığı:** `npm ci` 1 kritik açık bildiriyor.
12. **Ortama bağlı test:** `test_hosted_skin_type_runtime` bu dizindeki özel `model.onnx` yüzünden başarısız; temiz klonda geçiyor.
13. **Tabandan gelen hatalar:** `test_acne_objectness_features` (yolox yok). `test_localization` artık geçiyor (cilt kataloğu kimlikleri düzeltildi).
16. **Kalibrasyon kartı referansı (OEM uygulamasında):** Nominal değerler; OEM uygulamasında sertifikalı kart değerleri veya ölçülmüş referans kullanılmalı. Kalibrasyon uç noktası servis bayrağıyla açılır, kimlik doğrulaması yok (servis modu varsayımı).
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
7. Kamera renk yolu: tests/unit/test_camera_color.py; ATTUNE_CAMERA_PROFILE=tests/e2e/fixtures/camera-profile-fixture-bt601.json ile
   SKIN_E2E_EXPECT_RAW=1 current_skin_contract.py (her pozda cameraColor.source=raw-yuv); scripts/camera-calibration/check_skin_effect.py.
   Kalibrasyon uç noktasının ATTUNE_CAMERA_CALIBRATION olmadan 403 verdiğini ve profilin yalnız kapılar geçince yazıldığını doğrula.
8. Diller: tests/unit/test_skin_findings_i18n.py, tests/unit/test_localization.py, tests/e2e/skin_i18n_screens.py (TR/EN/DE, Türkçe satır ve taşma yok).
Rapor: Bulgu | Önem | Kabul engeli mi | Dosya:satır | Yeniden üretme | Öneri.
```

## 11. İlerleme kaydı ve kanıtlar

- `claude-progress/realpath-20261026/status.json`: aşama kaydı.
- `claude-progress/realpath-20261026/e2e-v2/`: E2E kanıt JSON'ları; fotoğraf içermez.
- Videolar ve ekran görüntüleri teslim paketinde; Git'te değil, çünkü sentetik yüzler içeriyor.
