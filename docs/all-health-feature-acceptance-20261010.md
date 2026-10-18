# TOGG Attune — feature acceptance, 2026-10-10

Frontend BUILD_ID: `_YWFLetSYj_oTN7LuFj4H`. Delivery SHA is in the final delivery report.

This inventory covers all five visible modules and shared paths. CONTROLLED_PATH_VERIFIED means the real production state/calculation/storage path ran with controlled callbacks, photographic or PCM fixtures. It is not physical user acceptance. LIMITED_NATURAL is a functioning appearance path with limited natural evidence. OPEN/FAIL rows remain unaccepted. No HTTP 200 or model-file existence promotes a row to natural acceptance.

Full feature fields: local `audit-results/all-health-20261010/feature-acceptance.csv` and `.json`. Earlier 307 bullets remain historical scope in `requirements-coverage.json`; the current focused request has 460 mapped bullets in `focused-requirements-coverage.json`. Neither mapping is an aggregate PASS. Frozen model/criterion decisions: `skin-focused-results-20261010.md`. Personal source images/documents remain ignored.

## Göz

Production chain: `app/vision/SpokenLetterPage.tsx → visionInference/visionTracking/visionFlow/visionAnswerMemory/spokenVision.ts`.
Inputs: raw camera frames; actual landmarks/hand pixels; target-scoped ASR callbacks.
Sources/rights: MediaPipe SDK/task Apache-2.0; licensed engineering video; fixed Ahmet Edge speech.
Result/history: valid LetterTrial → healthRecords → healthHistorySeries; eye/size/device/method partitions.

| ID / feature | Actual method and unit | Evidence | Final status / required input |
|---|---|---|---|
| F001 Kamera/yüz edinimi | real FaceLandmarker/HandLandmarker, raw frames; startup state; face count / source pixels | vision-negative; vision-motion | CONTROLLED_PATH_VERIFIED |
| F002 Işık/netlik/güncellik | raw-frame quality and timestamp gates; no preview CSS input; quality state / milliseconds | vision-negative; vision-memory | CONTROLLED_PATH_VERIFIED |
| F003 Göreli mesafe | rigid head anchors, hysteresis and baseline scale; mouth motion excluded; ratio; never cm | vision-motion; vision-memory | SOURCE_OR_CHECK_REVIEW |
| F004 Anatomik sağ/sol | MediaPipe anatomical indices; mirror is presentation only; RIGHT / LEFT | vision24; vision-memory | SOURCE_OR_CHECK_REVIEW |
| F005 Ekrana bakış | screen gaze allowed; head framing/relative distance still gated; validity state | vision24; vision-motion | SOURCE_OR_CHECK_REVIEW |
| F006 Sabit kamera/harf alanı | fixed preview transform; equal letter frame; source/crop mapping; CSS px / source pixels | vision-size; responsive | CONTROLLED_PATH_VERIFIED |
| F007 Rastgele hedef/rotasyon/ayna | session target generation plus SVG transform; letter / orientation | vision24; vision-transform | SOURCE_OR_CHECK_REVIEW |
| F008 SVG gerçek boyutu/kesilmeme | rendered bounding/path/stroke measurements under native zoom; CSS px | vision-size; vision-transform | SOURCE_OR_CHECK_REVIEW |
| F009 Harf→yön / yön→harf / birleşik | target-scoped parser and accumulator; Turkish forms incl. baş aşağı R; letter / orientation | vision-memory | SOURCE_OR_CHECK_REVIEW |
| F010 Kelimeyle kodlama/düzeltme | literal/coded-letter parser; correction replaces current target component; letter / orientation | vision-memory | SOURCE_OR_CHECK_REVIEW |
| F011 Birleşik ayna/dönüşüm | independent rotation + reflection parsing and scoring; transform | vision-memory; vision-transform | SOURCE_OR_CHECK_REVIEW |
| F012 Parçalı yanıt belleği | retain known component, ask missing component only; target-scoped values | vision-memory | SOURCE_OR_CHECK_REVIEW |
| F013 Gecikmiş olay izolasyonu | recognition/session/target generation guards; ignored stale callback | vision-memory | SOURCE_OR_CHECK_REVIEW |
| F014 Yönerge sırasında yanıt | ASR callback gate permits visible current target while system prompt plays; valid response | vision-memory | SOURCE_OR_CHECK_REVIEW |
| F015 Sistem sesi/yankı reddi | instruction text and prompt-span response isolation; ignored echo | vision-memory; audio-focus | CONTROLLED_PATH_VERIFIED |
| F016 Yanlış anlaşılmış yanıt ilerlemesi | valid incorrect answer increments trial, resets correct streak; valid wrong trial | vision24; vision-memory | SOURCE_OR_CHECK_REVIEW |
| F017 Göremiyorum | valid unable-to-read target outcome; technical blocker separate; valid incorrect trial | vision24; vision-memory | SOURCE_OR_CHECK_REVIEW |
| F018 Teknik geçersizlik | blocked conditions pause without wrong-reading score; invalid; excluded denominator | vision-memory; vision-negative | CONTROLLED_PATH_VERIFIED |
| F019 İki doğru sonrası %50 küçülme | actual sequence 120,120,60,60,30,30,15; zoom cannot compensate; CSS px | vision-size | SOURCE_OR_CHECK_REVIEW |
| F020 İki yanlışta büyüme | two wrong streak reset and actual next SVG size; CSS px | vision-size | SOURCE_OR_CHECK_REVIEW |
| F021 İki göz 24 deneme | RIGHT 12 + LEFT 12 with real state/parser/SVG/save path; trial count | vision24; vision-size | SOURCE_OR_CHECK_REVIEW |
| F022 Harf/yön/ortalama skor | separate valid denominators; average of two scores; empty denominator null; % task performance | vision24; vision-memory | SOURCE_OR_CHECK_REVIEW |
| F023 Duraklat/devam/yeni konum/mute/bitir | owned media/recognition cancellation and baseline reset; session state | vision-memory; audio-focus | CONTROLLED_PATH_VERIFIED |
| F024 İki göz sonuç/geçmiş | result carousel and one actual complete record; no dioptri/logMAR conversion; % / CSS px | vision24; dental-history | CONTROLLED_PATH_VERIFIED |
| F025 Göz yumma | personal eyelid geometry/blink + palm coverage / local template change; uncertain stays blocked; closed / covered / uncertain | vision-memory controlled cases; document-pixels original compressed images failed baseline | OPEN_NATURAL_POSITIVE; fresh native open-baseline and paired closed/covered frames for each anatomical side; old compressed DOCX preview cannot prove current physical acceptance |
| F026 El ile örtme | personal eyelid geometry/blink + palm coverage / local template change; uncertain stays blocked; closed / covered / uncertain | vision-memory controlled cases; document-pixels original compressed images failed baseline | OPEN_NATURAL_POSITIVE; fresh native open-baseline and paired closed/covered frames for each anatomical side; old compressed DOCX preview cannot prove current physical acceptance |
| F027 Opak cisim ile örtme | personal eyelid geometry/blink + palm coverage / local template change; uncertain stays blocked; closed / covered / uncertain | vision-memory controlled cases; document-pixels original compressed images failed baseline | OPEN_NATURAL_POSITIVE; fresh native open-baseline and paired closed/covered frames for each anatomical side; old compressed DOCX preview cannot prove current physical acceptance |

## Cilt

Production chain: `app/skin/page.tsx → skinSnapshot/skinOverview/appearanceMeasurements.ts → POST /api/local-health/skin → appearance_analysis.py / skin_general.py / skin_models.py → skinIndicators`.
Inputs: source RGB, source mesh/exclusions, actual landmark anatomy, pose/quality/detail; pinned accepted models only.
Sources/rights: MediaPipe Apache-2.0; skin-scan MIT; CC-BY-4.0 eye and publisher Apache-2.0 skin research data; per-model registry and notices.
Result/history: new overview + six regions; old six-region records unchanged; photo opt-in; method/normalization/model/region/unit partitions.

| ID / feature | Actual method and unit | Evidence | Final status / required input |
|---|---|---|---|
| F028 Ton eşitsizliği | CIE LAB local chromatic Δ to regional median; quality/skin exclusions; fixed 0–100 normalization; relative color index → % presentation | natural-skin; controlled reference tests | LIMITED_NATURAL; uniform illumination bias reduced; mixed directional light remains |
| F029 Kızarıklık eğilimi | regional CIELAB a* excess above percentile25 + fixed deadband/scale; no raw red-channel severity; relative color index → % presentation | natural-skin; controlled warm/matte/exposure tests | LIMITED_NATURAL; natural ground-truth redness vs colored directional light paired sources missing |
| F030 Yağlı görünüm | specular local intensity/contrast/desaturation under valid exposure; mask area fraction; % visible highlight area | controlled shiny/matte/clipping tests; natural-skin | OPEN_NATURAL_POSITIVE; usable whole-face shiny positive and bright-matte/flash/ter/cosmetic paired hard negatives |
| F031 Sivilce görünümü | accepted native-tile YOLOX source boxes only; same accepted candidates drive count/card/marks; no center-surround fallback; unique candidate count; box-covered eligible area % separately | focused YOLOX frozen final test; Faster-RCNN runtime-budget incomplete; independent-domain review; final skin API | MODEL_ACCEPTANCE_RECORDED_SEPARATELY; rejected candidate gives null, no fabricated localization; no full Faster-RCNN comparison metric; dataset boxes are not pixel masks or clinical truth |
| F032 Sarkma | instant anatomical contour deviation AND supported folds; pose/expression/illumination/detail gates; instant appearance index → % presentation | natural-skin + Lao contours; controlled shadow/shape/expression negatives | LIMITED_NATURAL; broader native poses/neutral expressions with visible contour/fold positives; some bands still null |
| F033 Cilt kuruluğu | multi-scale fine bright flake components; pore/hair dark-ring exclusion; texture alone not dryness; % eligible flake-candidate area | controlled flake/pores/JPEG/lines; natural-skin | OPEN_NATURAL_POSITIVE; native whole-face visible flakes + pores/JPEG/wrinkle/shine confounders; acquired partial scalp/eyelid sources are unsuitable |
| F034 Göz altı morluğu | lower-lid skin vs adjacent skin relative luminance; eyes/lashes/brows excluded; relative contrast index → % presentation | natural-skin; controlled lower-band/shadow tests | LIMITED_NATURAL; paired lighting/pose sources; directional-shadow ambiguity remains |
| F035 Göz altı torbaları | supported lower-eye contours/folds independent of dark-color signal; instant appearance index → % presentation | natural-skin / Lao; controlled dark-only negatives | LIMITED_NATURAL; additional neutral positive/negative native pose comparisons |
| F036 Kaz ayakları | outer-canthus directional Gabor multiscale line evidence; expression/detail gates; directional line index → % presentation | natural-skin / Lao; controlled hair/texture/expression tests | LIMITED_NATURAL; broader native corners with visible lines vs pore/compression negatives |
| F037 Genel Bakış ve 1/7 | FRONT source photo/analysis identity; actual observed union/global targets; initial view has no stacked mesh; four-class label + nine independent %/null | skin; skin-history; focused source contract | CONTROLLED_PATH_VERIFIED; global output is not copied into regional or pixel targets |
| F038 Dört sınıflı cilt tipi | two finite photo-only candidates R18/B0; grouped validation selection, temperature and frozen test; accepted ONNX only; Normal / Kuru / Yağlı / Karma or null | focused type-final-test and type-export; current registry | MODEL_ACCEPTANCE_RECORDED_SEPARATELY; not patient-independent; source expert protocol unverified; camera-domain acceptance separate |
| F039 Maskeli görünüm dereceleri | 18 train-only normalized frozen-feature ridge heads; invalid target-only mask; per-target constants and existing analytic comparison; 0–5 ordinal → 0–100 presentation; whole photo only | focused degrees-final-test and degrees-export; current registry | MODEL_ACCEPTANCE_RECORDED_SEPARATELY; no local map inferred from global grade; elasticity not sagging; dehydration not biological moisture; acne grade never replaces detector candidates |
| F040 Torba segmentasyonu | SMP UNet lower-lid RGB ROI; nonrectangular polygon plus boundary support; rect/box-only excluded; independent domain gate; true predicted pixel mask / eligible area % if accepted | focused bags final test and export; independent-domain review | MODEL_ACCEPTANCE_RECORDED_SEPARATELY; restricted annotated-support Dice cannot establish whole-ROI specificity; rejected model does not replace existing contour path |
| F041 Üç poz capture | actual FRONT/RIGHT/LEFT quality/pose/capture path; source RGB + actual pose | skin | CONTROLLED_PATH_VERIFIED |
| F042 Altı anatomik ağ | only visible selected region; projected source-pixel mesh; paired eye bands; source pixels | skin; skin-history | CONTROLLED_PATH_VERIFIED |
| F043 T-Bölgesi kapsamı | forehead + nose only; no chin signal; actual eligible area | skin; unit region contracts | CONTROLLED_PATH_VERIFIED |
| F044 Yakın fotoğraf ve gerçek arka plan | capture snapshot crop saved; RGB unchanged; no active background removal; original/cropped source RGB | skin; skin-history | CONTROLLED_PATH_VERIFIED |
| F045 Lokal harita/çember/dolgu | same actual signal/candidates as card; photoId + region + criterion guard; source pixels / eligible area | skin; skin-history | CONTROLLED_PATH_VERIFIED |
| F046 Yüzde ve degrade | fixed criterion-specific conversion; rounding only presentation; green→orange→red; % presentation, not confidence | skin; responsive; unit presentation contracts | CONTROLLED_PATH_VERIFIED |
| F047 Ölçülemeyen alan | explicit null/limitation; invalid quality never healthy zero; null / reason | natural-skin; unit appearance references | SOURCE_OR_CHECK_REVIEW |
| F048 Fotoğraflı geçmiş | photo opt-in default off; IndexedDB same poses/maps/mesh; reopen; local durable images + numeric data | skin-history; skin-wipe | CONTROLLED_PATH_VERIFIED |
| F049 Zaman içinde değişim popup | actual compatible record timestamps and criterion values; no personal old-reference gate on first scan; criterion-specific units | unit skin trend/history selectors; skin-history | CONTROLLED_PATH_VERIFIED |
| F050 Gözlem notu | selected actual region observation derived by live result adapter, not demo object; short appearance text | unit live skin adapter contracts; skin-history | CONTROLLED_PATH_VERIFIED |
| F051 Önerilen aksiyonlar | actual region actions, care handoff and local follow-up reminder; no treatment/diagnosis; action / external handoff | unit skin action contracts; care | CONTROLLED_PATH_VERIFIED |
| F052 Hatırlatma ve takvim | local chosen date, default28days; ICS export, cancellation and due notice; no false OS-notification claim; local date/time / ICS | unit reminder contracts; source chain review | SOURCE_OR_CHECK_REVIEW |

## Diş

Production chain: `app/dental/page.tsx → dentalCapture/dentalUpload → POST /api/local-health/dental[-upload] → dental_analysis/dental_upload.py`.
Inputs: actual four capture frames/landmarks or oriented uploaded RGB; actual enamel/gum/lip masks.
Sources/rights: YOLOX code Apache-2.0; dataset CC BY 4.0; D/d original Scientific Data definitions; exact shipped ONNX hash in manifest.
Result/history: views/pose/sourceType/coordinates/model hash/threshold → healthRecords; upload geometry version separated.

| ID / feature | Actual method and unit | Evidence | Final status / required input |
|---|---|---|---|
| F053 Çürük D | actual unchanged YOLOX-S ONNX mouth tensor; class D is permanent-tooth caries; candidate count; confidence separate | dental-camera; dental-natural; old protected D metrics only model context | LIMITED_NATURAL; matched natural stain/filling/food hard negatives beyond present portraits |
| F054 Çürük d | same ONNX class d is primary-tooth caries; original data ages10–24; candidate count | dental-camera; prior held-out d P=.517 R=.476 F1=.496 is not final-build acceptance | FAIL_WEAK_CLASS; commercial permitted primary-tooth native labeled images/hard negatives; under10 domain absent in original data |
| F055 Birikim görünümü | tooth-gum border + irregular texture/gradient + yellow support; per-view measured area, no fake multiview match; % visible border candidate area | dental-camera; dental-natural; dental-negative | OPEN_NATURAL_POSITIVE; native positive deposit borders vs stain/food/filling/reflection pairs; 4 poses are not automatic matching |
| F056 Görünür dizilim | marker watershed, reliable contours, row fitted axes/residual/projected overlap; <3 contours null; degrees; residual/overlap ratios separate | dental-camera; dental-natural; dental-history | LIMITED_NATURAL; native crowding/regular-row pairs and reliable contours; cannot infer hidden teeth/3D occlusion |
| F057 FRONT/RIGHT/LEFT/BITE | actual rigid pose / temporal capture / tooth visibility and bite geometry; source captures / pose | dental-camera | CONTROLLED_PATH_VERIFIED |
| F058 Doğal ton/dudak/dil/payda | actual open inner-mouth denominator and colored enamel/gum exclusion; visible tooth fraction | dental-camera; dental-negative | CONTROLLED_PATH_VERIFIED |
| F059 Netlik/parlama/örtülme | raw tooth detail / clipping / obstruction; gates retained; quality state | dental-negative; dental-natural | SOURCE_OR_CHECK_REVIEW |
| F060 Kamera sabit crop | preview independent of physical pose/analysis; source crop mapping; source vs preview pixels | dental-camera; responsive | CONTROLLED_PATH_VERIFIED |
| F061 Tam portre yükleme | optional actual MediaPipe photo landmarks → inner mouth; no camera permission; native RGB + source bounds | dental-natural; dental-history | CONTROLLED_PATH_VERIFIED |
| F062 Kısmi ağız fotoğrafı | local enamel/gingiva ROI when no full face; original pixels preserved; native RGB + source bounds | dental-history | CONTROLLED_PATH_VERIFIED |
| F063 EXIF/format/boyut | signature/decoder limits; EXIF transpose; no transparent/animated/huge decode; source pixels / bytes | dental-history; unit upload contracts | CONTROLLED_PATH_VERIFIED |
| F064 İptal/dosya değişimi | generation guard + AbortController; stage-bounded model preparation/backend deadline; cancelled; no record | dental-history; dental-natural timeout review | CONTROLLED_PATH_VERIFIED |
| F065 Kutular ve kaynak kaydı | same actual ONNX boxes/contours + orientedPhoto photoId/pose/sourceType; native source pixels | dental-natural; dental-camera; dental-history | CONTROLLED_PATH_VERIFIED |
| F066 Yöntem uyumluluğu | upload geometry/method version and model hash/decision threshold partition trends; count / degrees / border % | dental-history; unit history contracts | CONTROLLED_PATH_VERIFIED |

## İşitme

Production chain: `app/hearing/page.tsx → hearingAudio/hearingProtocol/hearingProgress.ts`.
Inputs: AudioContext PCM/channel/gain/time; actual user response timestamp or controlled button fixture.
Sources/rights: existing fixed Ahmet bank/Edge voice; Web Audio implementation; bank RMS/hash manifest.
Result/history: actual valid trials/reversals/ear/frequency/SNR → healthRecords → separate dBFS/dB SNR series.

| ID / feature | Actual method and unit | Evidence | Final status / required input |
|---|---|---|---|
| F067 AudioContext kullanıcı eylemi | context starts after user gesture, owned session audio lease; context state | hearing-tone; audio-focus | CONTROLLED_PATH_VERIFIED |
| F068 Stereo sağ/sol PCM | independent source PCM channel with exact gain/ramp; PCM / RMS | hearing-tone; hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F069 Kullanıcı kanal onayı | left/right confirmation before task; no inferred physical hearing; confirmed channel | hearing-tone | SOURCE_OR_CHECK_REVIEW |
| F070 Cihaz değişimi/kopması | device/visibility/session guards stop pending source nodes; stopped state | audio-focus; unit hearing/audio contracts | CONTROLLED_PATH_VERIFIED |
| F071 Güvenli genlik/ramp/dur | bounded digital gain; discomfort/end immediately owns stop; dBFS / ms | hearing-tone; audio-focus | CONTROLLED_PATH_VERIFIED |
| F072 Saf ses frekans/kulak planı | 7 stages per ear incl. repeated frequency; actual 14-stage plan; Hz / ear | hearing-tone; hearing-threshold | SOURCE_OR_CHECK_REVIEW |
| F073 Adaptif eşik | heard/unheard step/reversal algorithm and actual rendered gain; no clinical calibration; dBFS | hearing-threshold | SOURCE_OR_CHECK_REVIEW |
| F074 Sunum/yanıt zamanları | source started/ended and timestamped response window; milliseconds | hearing-tone; hearing-threshold | SOURCE_OR_CHECK_REVIEW |
| F075 Sessiz/erken/geç/çoklu basış | catch trials and window validity; double press ignored; valid trial / false alarm count | hearing-tone | SOURCE_OR_CHECK_REVIEW |
| F076 Öngörülemez aralık/tohum | session-specific random gaps/catch placement; bounded ramps; milliseconds / session seed | hearing-tone | SOURCE_OR_CHECK_REVIEW |
| F077 Yanıtsız/sınır/ölçülemeyen eşik | deadline advances; range/floor/censored or null threshold explicit; dBFS / null / state | hearing-tone; hearing-threshold | SOURCE_OR_CHECK_REVIEW |
| F078 Tekrar ölçüm tutarlılığı | same frequency repeat delta from actual measured thresholds; dBFS difference | hearing-threshold | SOURCE_OR_CHECK_REVIEW |
| F079 Saf ses grafik/legend/kayıt | actual ear/frequency thresholds, separate failures; one save; dBFS / Hz | hearing-threshold; dental-history | CONTROLLED_PATH_VERIFIED |
| F080 Türkçe sayı bankası | pinned digit/noise files; content/RMS/hash manifest; digit / PCM RMS | hearing-din24; delivery assets | SOURCE_OR_CHECK_REVIEW |
| F081 SNR/RMS/clipping | actual speech/noise RMS scaling + combined PCM peak limit; dB SNR / RMS / peak | hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F082 Yönerge ve ilk geri sayım | native instruction ended then 5→1 then stimulus; later no repeated countdown; seconds / order | hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F083 Üç sayı/sıralama/tuş takımı | three actual played digit IDs compared with ordered submitted answer; correct digits / triplet | hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F084 24 geçerli gönderim | trial token and submission lock; invalid/double not counted; 24 trials | hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F085 Sayı/üçlü/geçerli skor | correct digits and triplets / actual valid denominators; % task performance | hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F086 Adaptif SNR/banka eşiği | adaptive SNR reversal estimate only when sufficient; uncalibrated bank-specific; dB SNR / null | hearing-din24 | SOURCE_OR_CHECK_REVIEW |
| F087 Dur/yeniden başlat/ses çakışması | owned audio cancellation, generation guards, one result record; stopped / unique record | hearing-din24; audio-focus | CONTROLLED_PATH_VERIFIED |
| F088 Sonuç ve uzman bağlamı | actual performance summary; hearing service specialty, no disease grade; task result / hearing service | hearing-din24; care | CONTROLLED_PATH_VERIFIED |

## Ruh

Production chain: `app/mental/page.tsx → useMentalConversation → /api/mental/converse|summary|speech → main/mental_provider/conversation_control/session_memory.py`.
Inputs: consented text or ASR callback, session-bound context; server-only existing key.
Sources/rights: existing authorized OpenAI integration; three finite personal-free calls; approved Emel Edge voice.
Result/history: summary and transcript independent opt-ins; actual duration/mood only; mentalHistory/backend records.

| ID / feature | Actual method and unit | Evidence | Final status / required input |
|---|---|---|---|
| F089 Hizmet/mikrofon/bulut/kayıt izinleri | separate consent gates and revoke cleanup; consent state | mental-control; mental-asr | SOURCE_OR_CHECK_REVIEW |
| F090 Başlat/Türkçe ASR | actual recognition lifecycle; controlled browser ASR callbacks; no hidden typed transcript; text / lifecycle | mental-asr | SOURCE_OR_CHECK_REVIEW |
| F091 Yazılı giriş/backend | real existing server provider request; visible providerType, no silent demo; Turkish text | mental-live finite calls; mental-control | SOURCE_OR_CHECK_REVIEW |
| F092 Bağlam | session generation + completed prior turns; controlled 0/2/4 frontend contexts; live second request prior context; ordered turns | mental-control; mental-live ledger | SOURCE_OR_CHECK_REVIEW |
| F093 Türkçe yanıt/Emel | actual provider answer and existing exact Emel native audio ended; text / playback lifecycle | mental-live screens; mental-asr | SOURCE_OR_CHECK_REVIEW |
| F094 Kullanıcı/sistem sesi ayrımı | mute ASR while agent audio; rearm owned generation after ended; ignored echo / user text | mental-asr | SOURCE_OR_CHECK_REVIEW |
| F095 Parçalı/gecikmiş yanıt | recognition/session sequence guards and interim/final isolation; current session text | mental-asr | SOURCE_OR_CHECK_REVIEW |
| F096 Mute/duraklat/devam | cancel pending audio/recognition; pending finish resumes finish rather than microphone; session state | mental-asr; mental-control | SOURCE_OR_CHECK_REVIEW |
| F097 Bitir/iptal | actual completed lifecycle; explicit farewell fullmatch maps finish; crisis priority retained; completed + mic stopped | mental-control; mental-live finish screen | SOURCE_OR_CHECK_REVIEW |
| F098 Sağlayıcı/ağ hatası | visible actual provider failure; no invented reply; error cannot replay entry guidance; error state | mental-control; mental-asr | SOURCE_OR_CHECK_REVIEW |
| F099 Gerçek özet | actual third bounded live summary; missing duration/mood stays null; summary / actual duration | mental-live ledger/screens; mental-control; unit corrections | SOURCE_OR_CHECK_REVIEW |
| F100 Özet/transkript ayrılığı | independent toggles; opt-out excludes transcript; default summary-on respected; local record text | mental-control; mental-live scoped review | SOURCE_OR_CHECK_REVIEW |
| F101 Geçmiş/silme | consented completed record only; isolated records/delete/wipe; date / themes / count | mental-control; dental-history | CONTROLLED_PATH_VERIFIED |
| F102 Kriz / normal gündelik ifade | explicit crisis guard before farewell; controlled positive/negative phrases; support response / no false lock | unit crisis/conversation contracts | SOURCE_OR_CHECK_REVIEW |
| F103 İlaç/teşhis sınırı | existing provider constraints, safety route and bounded input/session; safe response policy | unit provider/crisis contracts; limited live sample, not universal guarantee | SOURCE_OR_CHECK_REVIEW |
| F104 Süre/uzunluk/döngü | bounded request/session turn limits; no indefinite automated live calls; seconds / turns | mental-control; unit provider contracts | SOURCE_OR_CHECK_REVIEW |
| F105 Psikolog yönlendirmesi | mental service context into care specialty; psychology service | care | CONTROLLED_PATH_VERIFIED |
| F106 Fiziksel mikrofon/telaffuz | actual ASR/TTS technical lifecycle is separate from human speech accuracy and auditory acceptance; human speech / pronunciation | no new physical human session; callbacks and native playback only | OPEN_PHYSICAL; single final physical natural-speech/auditory session after independent work; no repeated interim tester requests |

## Ortak

Production chain: `healthModules/healthRecords/skinPhotoHistory/healthHistorySeries/audioGuidance; app/profile/privacy/care/page.tsx; scripts/windows-launcher/start_togg.pyw`.
Inputs: actual local records, explicit consents, vehicle state, source IDs, fixed audio assets or external provider response.
Sources/rights: existing project/runtime notices; no new paid model/cloud provider; external provider rights not bypassed.
Result/history: same central five-module IDs; local profile preserved; isolated fixture stores only.

| ID / feature | Actual method and unit | Evidence | Final status / required input |
|---|---|---|---|
| F107 Merkezi beş modül/menü | HEALTH_MODULES canonical labels/order; dropdown/footer unchanged; module ID / label | responsive; preparation-guidance | CONTROLLED_PATH_VERIFIED |
| F108 Kokpit/geçmiş carousel | single row cards and arrows; modal details only; no permanent below-card panel; navigation state | dental-history; responsive | CONTROLLED_PATH_VERIFIED |
| F109 Grafik tarih/kriter/bölge filtreleri | read-only real-record selectors; compatible method/device/unit grouping; module-specific units | dental-history; unit history series | CONTROLLED_PATH_VERIFIED |
| F110 Tooltip kullanıcı metni | date/time/criterion/region/value only; formulas remain info area; no new technical text; % / count / degree / dBFS / dB SNR | dental-history; responsive | CONTROLLED_PATH_VERIFIED |
| F111 Null ve bağımsız skorlar | null graph points remain null; no meaningless aggregate pie or unit conversion; null / correct units | unit history contracts; dental-history | CONTROLLED_PATH_VERIFIED |
| F112 Paylaşım önizleme/çıktı | explicit preview consent and parked gate; real sanitized local record export/print; does not send messages; record text / printable summary | unit healthShare contracts; source UI review | SOURCE_OR_CHECK_REVIEW |
| F113 Açık demo ayrılığı | normal live route never creates demo records; optional explicit demo remains visibly labelled and separate; demo/live source type | unit live-mode contracts; actual skin/dental/mental paths | CONTROLLED_PATH_VERIFIED |
| F114 Fotoğraf izinleri | local durable opt-in default off; source images never numeric history payload; explicit consent | skin-history; skin-wipe | CONTROLLED_PATH_VERIFIED |
| F115 Tek fotoğraf+sayısal silme | durable IndexedDB backup + local intent journal; commit/rollback/recover before reads; atomic record deletion | skin-history; unit quota/crash/restart tests | CONTROLLED_PATH_VERIFIED |
| F116 Tüm kayıt/harita silme | coordinated five-module local data, backend wipe; user real store unchanged; isolated deletion | skin-wipe; dental-history | CONTROLLED_PATH_VERIFIED |
| F117 Kota/yarım yazım/hata | failed journal does not delete photos; recovered pending transaction; explicit storage failure; failure; no false saved state | unit atomic deletion; skin-history | CONTROLLED_PATH_VERIFIED |
| F118 Genel sayfalar sessiz | guidance only prep/active; dedup/mute/route cleanup; no menu TTS; silent / native audio | preparation-guidance; audio-focus | CONTROLLED_PATH_VERIFIED |
| F119 Exact Ahmet/Emel ses profili | first four Ahmet / mental Emel, -10% -10Hz; same files and hashes; voice profile | delivery assets; mental-asr; vision-negative | CONTROLLED_PATH_VERIFIED |
| F120 Yerel yüz/el model hazırlığı | byte-identical existing float16 v1 tasks + SDK1.0.1 WASM served by local product; no new weights/thresholds; SHA256 / init and inference ms | vision-negative cold external URLs blocked; dental-natural; skin | CONTROLLED_PATH_VERIFIED |
| F121 Sabit göz yönerge bankası | same approved PROMPTS/Ahmet rate/pitch; checked text/profile/hash; streaming native audio; dynamic mental speech still separate; actual MP3 / voice identity | vision-negative; unit fixed bank integrity/transport; delivery | CONTROLLED_PATH_VERIFIED |
| F122 Kamera/ses sayfa çıkışı | owned stream/audio/recognition cancelled; unrelated Chrome preserved; resource lifecycle | audio-focus; skin; dental-history | CONTROLLED_PATH_VERIFIED |
| F123 Park koşulu | actual vehicle speed state gate; rejected work does not create analysis; parked / blocked | unit route contracts; care | CONTROLLED_PATH_VERIFIED |
| F124 Beş doğru uzmanlık | care origin→specialty mapping; no dental/hearing psychologist fallback; specialty | care | CONTROLLED_PATH_VERIFIED |
| F125 Canlı uzman/müsaitlik | read-only real external provider; blocked request visibly unavailable, never fabricated slots; external result / unavailable | care external request log | OPEN_EXTERNAL |
| F126 Dış sağlayıcı yönlendirme | correct existing provider URL; blocked fallback card honestly calls external booking; external link; not booked | care | CONTROLLED_PATH_VERIFIED |
| F127 Production güvenlik | current pinned runtime; production audit excludes dev; server-only key and local origin gates; audit count / endpoint policy | npm-audit-production; unit routes/runtime security | SOURCE_OR_CHECK_REVIEW |
| F128 Dev güvenlik bulguları | actual npm report retained; seven high and two moderate remain; no unsafe forced major downgrade; 7 high + 2 moderate | npm-audit.json | OPEN_DEV_DEPENDENCIES |
| F129 Masaüstü/dar/gerçek %200 | owned Chrome native zoom; source dimensions independent; no CSS zoom surrogate claimed native; native viewport / zoom | vision-size; responsive; final screens | CONTROLLED_PATH_VERIFIED |
| F130 Kısayol→launcher→source→build | normal owned profile; served chunk/model/audio hash exact chain; committed-source match; SHA / BUILD_ID / SHA256 | delivery.json after commit | SOURCE_OR_CHECK_REVIEW |
