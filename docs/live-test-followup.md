# CanlÄ± test dÃ¼zeltmeleri

BaÅŸlangÄ±Ã§: main 7b3010ca5f03a55f0faa906296520d8097974acb; doÄŸrulanmÄ±ÅŸ Linux run 36955786226. Bu sonuÃ§lar yeni deÄŸiÅŸikliklerin geÃ§tiÄŸi anlamÄ±na gelmez.

## BaÅŸlangÄ±Ã§ sÄ±nÄ±flandÄ±rmasÄ±

| Belge konusu | SÄ±nÄ±f | Kaynak / sÄ±nÄ±r |
|---|---|---|
| IÅŸÄ±k ve netlik etiketleri | Kodla doÄŸrulanmÄ±ÅŸ hata | TÃ¼m kare Ã¶lÃ§Ã¼lÃ¼yordu; bilinmeyen durumda yeÅŸil etiket. Kamera piksel kalitesi klinik yeterlilik deÄŸildir. |
| SaÄŸ/sol talimatÄ± | Ek doÄŸrulama gereken gÃ¶zlem | Tek aÃ§Ä±daki talimat karÅŸÄ±ya dÃ¶nme isteÄŸiydi; screenshot yaw iÅŸaretini kanÄ±tlamaz. |
| ÃœÃ§ ayrÄ± aÃ§Ä± | Yeni Ã¼rÃ¼n gereksinimi | BaÅŸlangÄ±Ã§ta tek karÅŸÄ± aÃ§Ä±; Ã¼Ã§ aÃ§Ä± mevcutmuÅŸ gibi gÃ¶sterilmemeli. |
| Siyah sonuÃ§ / bÃ¶lge gÃ¶sterimi | Kodla doÄŸrulanmÄ±ÅŸ hata | Durdurulan video; sabit demo mesh gerÃ§ek landmark gibi gÃ¶rÃ¼nÃ¼yordu. |
| Ä°lk referans / bÃ¶lgesel not | Kodla doÄŸrulanmÄ±ÅŸ hata | Ä°lk taramada yÃ¼zde; tÃ¼m taramanÄ±n notu baÅŸka bÃ¶lgeye aktarÄ±lÄ±yordu. |
| Aksiyon oklarÄ± / hatÄ±rlatma | Hata ve yeni gereksinim | Ä°ÅŸlevsiz oklar; kapalÄ± uygulama bildirimi iÃ§in tarayÄ±cÄ± timer uygun deÄŸil. |
| Profilde ikinci gizlilik dÃ¼ÄŸmesi | TasarÄ±m gereksinimi | Ãœst menÃ¼ izin denetimi korunmalÄ±. |
| Ã‡ok turlu gÃ¶rÃ¼ÅŸme / tÃ¼m mesajlar / bitiÅŸte Ã¶zet | Kodla doÄŸrulanmÄ±ÅŸ hata ve yeni akÄ±ÅŸ | Single-shot recognition; TTS sonrasÄ± baÅŸlamama; slice(-2); erken kayÄ±t. |
| Tekrarlayan cevap / robotik ses | SaÄŸlayÄ±cÄ± ve ortam | Yerel saÄŸlayÄ±cÄ± deterministik; yapÄ±landÄ±rÄ±lmÄ±ÅŸ anahtar baÅŸarÄ±lÄ± istek demek deÄŸildir. |
| TÃ¼rkÃ§e Ã¶zet / grafik | Kodla doÄŸrulanmÄ±ÅŸ hata ve tasarÄ±m | Enum metni gÃ¶rÃ¼nÃ¼yordu; taslak yÃ¼zdeleri gerÃ§ek veri deÄŸildir. |
| Landolt boÅŸluÄŸu / yan yana dÃ¼zen | Kodla doÄŸrulanmÄ±ÅŸ hata ve tasarÄ±m | Dash boÅŸluÄŸu kardinal aÃ§Ä±yla uyuÅŸmuyordu. DÃ¶rt yÃ¶n ve mm Ã¶lÃ§Ã¼sÃ¼ korunur. |
| SeÃ§meli rapor / PDF | Kodla doÄŸrulanmÄ±ÅŸ hata ve yeni akÄ±ÅŸ | Sadece alert; otomatik tÃ¼m kategoriler; Ã¶rnek hasta kimliÄŸi. |

## DeÄŸiÅŸiklik ve doÄŸrulama notlarÄ±

- Landolt: dÄ±ÅŸ Ã§ap 100, Ã§izgi 20 ve boÅŸluk 20 birim; saÄŸda merkezlenmiÅŸ 20 birim aÃ§Ä±klÄ±ÄŸÄ± olan doÄŸrudan yay path'i. Kalibre edilmiÅŸ kÃ¼Ã§Ã¼k boyutlarda raster maske kullanÄ±lmaz. Rotasyon animasyonu yok. DÃ¶rt yÃ¶n gerÃ§ek tarayÄ±cÄ± pikselleriyle sÄ±nanÄ±r; motorun kalibre boyutu bÃ¼yÃ¼tÃ¼lmez.
- PaylaÅŸÄ±m: baÅŸlangÄ±Ã§ta tÃ¼m seÃ§imler kapalÄ±; veri olmayan kategoriler devre dÄ±ÅŸÄ±. Tek seÃ§ilmiÅŸ veri modeli Ã¶nizleme ve disposable yazdÄ±rma belgesine gider. YazdÄ±rma/PDF kaydetme iÅŸletim sistemi penceresinde kullanÄ±cÄ± iÅŸlemi; dosya indirildi veya hekime gÃ¶nderildi iddiasÄ± yok.
- Cilt: yÃ¼z kutusu kalite bÃ¶lgesi; 40â€“220 ve 4.0 eÅŸikleri korunur. BoÅŸ ROI sayÄ±sal varsayÄ±lan Ã¼retmez. SonuÃ§ aÃ§Ä±k etiketli anatomik ÅŸemadÄ±r; kamera kapalÄ±, yÃ¼z fotoÄŸrafÄ± saklanmaz. Scan overlay gerÃ§ek landmark noktalarÄ±dÄ±r, video object-contain ile aynÄ± koordinat alanÄ±ndadÄ±r.
- Referans: ilk sayÄ±sal tarama, ayrÄ± metadata; eski referans silinmez. Eski metadata yoksa veya Ä±ÅŸÄ±k/netlik uyumsuzsa delta sunulmaz. IÅŸÄ±k farkÄ± 15 piksel birimi ve netlik oranÄ± 2; yaw/pitch farkÄ± .12, roll farkÄ± .15 ve yÃ¼z Ã¶lÃ§eÄŸi farkÄ± .08, karÅŸÄ±laÅŸtÄ±rmayÄ± engelleyen muhafazakÃ¢r MVP koÅŸullarÄ±dÄ±r; klinik doÄŸrulanmÄ±ÅŸ sÄ±nÄ±rlar deÄŸildir.
- Trend: ilk referans sÄ±fÄ±r deÄŸiÅŸim noktasÄ± sayÄ±lmaz; yalnÄ±zca karÅŸÄ±laÅŸtÄ±rÄ±labilir takip deltasÄ±ndan grafik. Saat gÃ¶rÃ¼nÃ¼r, grafik Ã¶lÃ§eÄŸi deÄŸerleri kapsar.
- HatÄ±rlatma: 28 takvim gÃ¼nÃ¼; aynÄ± plan tek UID, dÃ¼zenleme/iptal. GerÃ§ek .ics dosyasÄ± DISPLAY alarm iÃ§erir, hassas saÄŸlÄ±k baÅŸlÄ±ÄŸÄ± iÃ§ermez. Ä°Ã§e aktarÄ±m ve takvim bildirimi doÄŸrulanamadÄ±ÄŸÄ± aÃ§Ä±kÃ§a gÃ¶sterilir. Uygulama kapalÄ±yken kendi servisleri Ã§alÄ±ÅŸtÄ±rÄ±lmaz. Takvime aktarÄ±lmÄ±ÅŸ kayÄ±t uygulama iÃ§i iptal ile takvimden silinmez; kullanÄ±cÄ±ya ayrÄ±ca silmesi gerektiÄŸi bildirilir.

## Korunan doÄŸrulamalar

Eski runner_v2 gÃ¶rme seÃ§icisi `circle[stroke-dasharray]` yerine `svg[data-logmar]` kullanÄ±r; aynÄ± Ã¼Ã§ doÄŸru cevap sonrasÄ± gerÃ§ek boyut kÃ¼Ã§Ã¼lme assertion korunur. Ek test dÃ¶rt yÃ¶nÃ¼n screenshot piksellerini doÄŸrular.

Test beklentisi deÄŸiÅŸikliÄŸi gerektiÄŸinde eski gÃ¼venlik amacÄ± kaldÄ±rÄ±lmaz. Ã–rneÄŸin yeni gÃ¶rÃ¼ÅŸme yaÅŸam dÃ¶ngÃ¼sÃ¼nde erken kayÄ±t bekleyen test, bitiÅŸ Ã¶ncesi sÄ±fÄ±r ve bitiÅŸ sonrasÄ± tek kayÄ±t doÄŸrulamasÄ±na dÃ¶nÃ¼ÅŸmelidir. Yeni kalÄ±cÄ± alanlar gizlilik silme listesine dahildir. Makineye Ã¶zel dosya yollarÄ± ve gerÃ§ek yÃ¼z/ses verileri repoya veya CI artifact'ine eklenmez.

CanlÄ± saÄŸlayÄ±cÄ±, gerÃ§ek TÃ¼rkÃ§e ses doÄŸallÄ±ÄŸÄ±, Ã§ok aÃ§Ä±lÄ± fixture, Windows kÄ±sayol tanÄ±tÄ±mÄ± ve final Linux matrisi tamamlanmadan bÃ¼tÃ¼n kapsam tamamlandÄ± denemez. Klinik doÄŸruluk veya gerÃ§ek araÃ§ donanÄ±mÄ± entegrasyonu iddiasÄ± yoktur.

## Ara doÄŸrulama (Windows, anahtarsÄ±z yerel saÄŸlayÄ±cÄ±)

- 114 birim testi geÃ§ti: baÅŸlangÄ±Ã§taki 111 test korunur, 3 yeni test eklenir.
- Typecheck, lint, fresh production build geÃ§ti. Lint Ã¶nceki Ã¼Ã§ uyarÄ±yÄ± bildiriyor.
- Tam ve production-only npm audit sÄ±fÄ±r bulgu; baÄŸÄ±mlÄ±lÄ±k manifest/lockfile deÄŸiÅŸmedi.
- Ä°lk/ikinci gerÃ§ek MediaPipe taramasÄ± UI Ã¼zerinden; altÄ± bÃ¶lge, kamera track sonlanmasÄ±, metadata ve gerÃ§ek bÃ¶lgesel delta doÄŸrulandÄ±.
- Takvim dosyasÄ± gerÃ§ekten indirildi; UID tekrarsÄ±zlÄ±ÄŸÄ±/iptal, depolama hatasÄ±nÄ±n iletilmesi ve demo ayrÄ±mÄ± doÄŸrulandÄ±.
- Yerel gerÃ§ek print beforeprint olayÄ±nda seÃ§ilen cilt belgesi incelendi; seÃ§ilmeyen kategoriler HTML ve metadata iÃ§inde yok. Bu kontrol Windows PDF kaydetme diyalog seÃ§iminin tamamlandÄ±ÄŸÄ±nÄ± iddia etmez.
- Yeni piksel testi PNG'yi tarayÄ±cÄ±nÄ±n yerel decoder'Ä±yla okur; Pillow ek baÄŸÄ±mlÄ±lÄ±ÄŸÄ± gerektirmez. KÃ¼Ã§Ã¼k Ã¶lÃ§eklerde raster maskeyi kaldÄ±ran doÄŸrudan Landolt yay path'i kullanÄ±lÄ±r.
- Bu ara kanÄ±t final Linux/Windows/ses/Ã§ok aÃ§Ä± kabul matrisi yerine geÃ§mez.

### SVG raster sÄ±nÄ±rÄ± iÃ§in teknik kanÄ±t

Chromium `SVGRootPainter` aÃ§Ä±klamasÄ±, SVG layout viewport'u kesirli kalÄ±rken root border box'Ä±n paint sÄ±rasÄ±nda piksele yuvarlandÄ±ÄŸÄ±nÄ± belirtir:
https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/renderer/core/paint/svg_root_painter.h

Kesirli kare Ã¶lÃ§Ã¼leri yatay/dikey farklÄ± yuvarlanabiliyor. DÄ±ÅŸ SVG viewport'u tam piksel boyutunda ve minimum iki piksel boÅŸlukludur; iÃ§ SVG'nin geniÅŸlik/yÃ¼ksekliÄŸi mevcut kalibre `optotypeSizePx` deÄŸeridir. GÃ¶rme sembolÃ¼nÃ¼n boyutu bÃ¼yÃ¼tÃ¼lmez, logMAR hesabÄ± deÄŸiÅŸmez. Runner/backlog rotasyon seÃ§icileri dÄ±ÅŸ SVG'nin gerÃ§ek dÃ¶nÃ¼ÅŸÃ¼mÃ¼ne taÅŸÄ±nÄ±r; fiziksel boyut assertion'larÄ± iÃ§teki Ã¶lÃ§Ã¼len simgede korunur. Yeni piksel testi dÃ¶rt yÃ¶ne cevap doÄŸruluÄŸunu gerÃ§ek screenshot'ta denetler.


## Follow-up implementation

Mental conversation state now lives in `useMentalConversation`: epoch and native
recognition identity gates invalidate late callbacks; only final paired messages
are summarized at finish. A separate explicit cloud checkbox controls OpenAI text
and speech requests. The browser STT checkbox explains its possible cloud transfer.
Storage consent is checked again immediately before persistence. Full transcript,
two columns, Turkish moods and real completed/consented v2 theme counts replace
early session writes and fabricated statistics. Old records remain readable and
are excluded from theme percentages when their provenance cannot be confirmed.

Configured credentials are distinct from each response's providerType. The backend
uses bounded SDK requests without automatic retries, safe failure categories and
explicit TTS consent/park checks. CI never loads the local key. No Realtime/WebRTC
architecture was introduced.

Skin now defaults to FRONT, anatomical RIGHT and LEFT stages. The preview uses raw
unmirrored coordinates; positive raw yaw corresponds to anatomical LEFT. Side
poses measure only the exposed opposite cheek. SHA-256 frame tokens reject reuse
between angles. A separate v2 reference preserves old single-front storage, and
trend points are restricted to the current scope/reference. Quality and comparison
thresholds remain unchanged. Fixture attribution: [test-fixture-provenance.md](test-fixture-provenance.md).

Test expectation changes: new start/end buttons and explicit speech consent replace
single-shot microphone controls; expected early summary writes become zero before
finish and exactly one after finish. Old single-front regression tests explicitly
choose the retained single-angle mode. New three-angle tests use three distinct
licensed video frames and actual production MediaPipe, not mocked poses.

Windows launcher source is kept under `scripts/windows-launcher`. The inherited
key environment is scrubbed. Only backend normal launches load the approved local
file. The Job Object still owns only the dedicated TOGG descendants; normal
launches expose no debugging port. The repeat-launch file-lock read bug is fixed.
The verified-mode profile and all runtime files remain separate from normal data.

## Execution evidence policy

The final execution report is generated locally under `audit-results/final-report.md`
after inspecting Actions on the exact final HEAD. Runtime artifacts and credentials
are ignored and do not enter Git. A failed Windows synthetic voice-input run was
invalidated because Chrome did not consume the specified WAV; unexpected raw
transcripts and screenshots were removed. Physical-microphone-denied explicit-track
preflight produced `not-allowed` with zero OpenAI requests. Windows native three-turn
input remains pending; it is never inferred from text/TTS or Linux native results.
Any extra paid test requires additional bounded approval. Technical playback
success does not prove Turkish voice naturalness or first audible sound.


### Newly reviewed dependency advisory

On the final fresh audit, GHSA-vfj7-8cjw-p6xm (updated 2 October 2026)
reports braces <=3.0.3 as vulnerable; the upstream advisory lists no patched
version and npm still publishes 3.0.3 as latest. The full development audit now
has seven high findings propagated through Tailwind/ESLint glob dependencies.
Production-only audit remains zero. Earlier zero counts are historical results.
We do not suppress this advisory, rename/vendor a package to hide it, or claim
zero findings. CI collects both audit reports, retains the failing zero-findings
requirement, and continues the independently runnable browser/audio matrix.
This acceptance item remains pending upstream remediation or an independently
validated dependency migration.
Source: https://github.com/advisories/GHSA-vfj7-8cjw-p6xm


### Final lifecycle and evidence refinements

The active conversation transcript occupies the right column, matching the supplied
layout. Before/after the conversation the right column shows real analysis/history;
the transcript remains available after completion. A driving transition during final
summary analysis now also invalidates the pending result, verified by a new race test.
Summary providerType is explicit, including LOCAL_DEMO_FALLBACK.

The initial native three-turn Linux check accepted the first turn but not the second.
Its next verification waits for the current recognition instance's audio-start state
and captures actual native event diagnostics on failure. No transcript event or voice
result is substituted. Acceptance remains pending until that real check succeeds.
Multi-angle tests additionally verify cancellation and corrupt-reference preservation.
Reminder and selected-preview screenshots are captured alongside existing behavior checks.


Active-panel regression expectation follows the supplied before/during layout:
no history panel during active conversation, storage count unchanged, then the
same records visible after finish. Date/time and summary occupy adjacent row
columns. Native diagnostics showed the second capture ending without a result
and subsequent no-speech events while the app kept listening; the first STT/TTS
turn succeeded. The next bounded check uses three simpler distinct synthetic
phrases and the same 48 kHz mono PCM preparation as the original native baseline,
with speech/nomatch events and distinct-transcript assertions retained.
Summary generation is bounded to 400 output tokens without SDK retries.
