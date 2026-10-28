# PR #13 — final Vision localization audit

Scope: Turkish, English and German display localization only. No speech-recognition,
eye-detection, scoring, assessment-flow, layout or feature change. PR #13 remains
draft, unmerged and undeployed. Audit baseline:
`e59f929dd3c0ea9c361a6834738057d45b3086d9`. Tested implementation:
`5f0deb484ddd0bc69adbc13e2589a10b9a4a53a0`.

## Findings and corrections

The previous inventory check passed despite missing ASCII-only labels and generated
sentences. The actual translation engine returned Turkish for eye instructions,
result labels, camera freshness and history read failures. It translated only the
outer “Detected” sentence, leaving the nested answer description in Turkish.
German per-eye progress combined “Rechts/Links” with “Auge”, producing the wrong
adjective form. The Turkish mute notice used the English word “Header”, and the
carousel accessibility description bypassed translation.

Corrections use the existing catalog and its bounded, source-specific templates.
The translation engine itself is unchanged. No broad delimiter-splitting or user
transcript translation was introduced. Raw heard text is still the user's original
transcript. Nine answer-description templates cover the actual rotation/mirror
phrases and unknown orientation; the retained unknown-letter value already has a
translation. Full eye-instruction entries also cover appended condition messages.

There are **28 corrected catalog entries**. The table gives every exact corrected
TR source/template, its EN/DE text, and affected screen. `{0}` is the existing
runtime value (letter/unknown-letter, condition guidance, or question number), not
literal on-screen text. [Machine-readable corrections](vision-localization-evidence/corrected-strings.json)
include prior sources and prior translations. [Before/after derived output](vision-localization-evidence/before-after.json)
records 416 corrected outputs among 468 generated cases.

| Affected screen | TR | EN | DE |
| --- | --- | --- | --- |
| Camera freshness status | Kamera karesi bekleniyor | Waiting for a camera frame | Warten auf ein Kamerabild |
| Results and history score cards/table | Toplam ortalama skor | Overall average score | Mittlerer Gesamtwert |
| Results and history size table | Harf boyutu | Letter size | Buchstabengröße |
| Muted-output interruption | Seslendirme kapalı. Üst çubuktaki hoparlörü açıp devam edin. | Speech output is muted. Enable the speaker in the top bar and resume. | Die Sprachausgabe ist stummgeschaltet. Aktivieren Sie den Lautsprecher in der oberen Leiste und setzen Sie die Aufgabe fort. |
| Result/history carousel accessibility | Kaydırılabilir kartlar | carousel | Karussell |
| Partial/clarified answer summary | {0} · düz | {0} · upright | {0} · aufrecht |
| Partial/clarified answer summary | {0} · düz ve aynalı | {0} · upright and mirrored | {0} · aufrecht und gespiegelt |
| Partial/clarified answer summary | {0} · sağa yatmış | {0} · tilted right | {0} · nach rechts geneigt |
| Partial/clarified answer summary | {0} · sağa yatmış ve aynalı | {0} · tilted right and mirrored | {0} · nach rechts geneigt und gespiegelt |
| Partial/clarified answer summary | {0} · baş aşağı | {0} · upside down | {0} · auf dem Kopf |
| Partial/clarified answer summary | {0} · baş aşağı ve aynalı | {0} · upside down and mirrored | {0} · auf dem Kopf und gespiegelt |
| Partial/clarified answer summary | {0} · sola yatmış | {0} · tilted left | {0} · nach links geneigt |
| Partial/clarified answer summary | {0} · sola yatmış ve aynalı | {0} · tilted left and mirrored | {0} · nach links geneigt und gespiegelt |
| Partial/unrecognized answer summary | {0} · yön anlaşılmadı | {0} · orientation not understood | {0} · Ausrichtung nicht verstanden |
| Eye-closure/coverage instruction | Sağ gözünüzü test ediyoruz. Sol gözünüzü kapatın veya örtün. Açık gözünüzle harf alanına bakın. | We are testing your right eye. Close or cover your left eye. Look at the letter area with your open eye. | Wir testen Ihr rechtes Auge. Schließen Sie Ihr linkes Auge oder decken Sie es ab. Schauen Sie mit dem offenen Auge auf den Buchstabenbereich. |
| Eye instruction with dynamic condition guidance | Sağ gözünüzü test ediyoruz. Sol gözünüzü kapatın veya örtün. Açık gözünüzle harf alanına bakın. {0} | We are testing your right eye. Close or cover your left eye. Look at the letter area with your open eye. {0} | Wir testen Ihr rechtes Auge. Schließen Sie Ihr linkes Auge oder decken Sie es ab. Schauen Sie mit dem offenen Auge auf den Buchstabenbereich. {0} |
| Per-eye question progress | Sağ göz · {0}/12 | Right eye · {0}/12 | Rechtes Auge · {0}/12 |
| Eye-closure/coverage instruction | Sol gözünüzü test ediyoruz. Sağ gözünüzü kapatın veya örtün. Açık gözünüzle harf alanına bakın. | We are testing your left eye. Close or cover your right eye. Look at the letter area with your open eye. | Wir testen Ihr linkes Auge. Schließen Sie Ihr rechtes Auge oder decken Sie es ab. Schauen Sie mit dem offenen Auge auf den Buchstabenbereich. |
| Eye instruction with dynamic condition guidance | Sol gözünüzü test ediyoruz. Sağ gözünüzü kapatın veya örtün. Açık gözünüzle harf alanına bakın. {0} | We are testing your left eye. Close or cover your right eye. Look at the letter area with your open eye. {0} | Wir testen Ihr linkes Auge. Schließen Sie Ihr rechtes Auge oder decken Sie es ab. Schauen Sie mit dem offenen Auge auf den Buchstabenbereich. {0} |
| Per-eye question progress | Sol göz · {0}/12 | Left eye · {0}/12 | Linkes Auge · {0}/12 |
| Vision history read error | Göz Sağlığı: kayıtlar okunamadı; veriler korunuyor. | Vision Health: records could not be read; data is preserved. | Augengesundheit: Einträge konnten nicht gelesen werden; die Daten bleiben erhalten. |
| Condition pause placeholder | Göz kontrolü nedeniyle duraklatıldı. | Paused for the eye check. | Wegen der Augenprüfung pausiert. |
| Condition pause placeholder | Baş pozu kontrolü nedeniyle duraklatıldı. | Paused for the head-position check. | Wegen der Kopfhaltungsprüfung pausiert. |
| Condition pause placeholder | Netlik kontrolü nedeniyle duraklatıldı. | Paused for the sharpness check. | Wegen der Schärfeprüfung pausiert. |
| Condition pause placeholder | Işık kontrolü nedeniyle duraklatıldı. | Paused for the lighting check. | Wegen der Beleuchtungsprüfung pausiert. |
| Condition pause placeholder | Görüntü kontrolü nedeniyle duraklatıldı. | Paused for the image check. | Wegen der Bildprüfung pausiert. |
| Condition pause placeholder | Kadraj kontrolü nedeniyle duraklatıldı. | Paused for the framing check. | Wegen der Bildausschnittsprüfung pausiert. |
| Condition pause placeholder | Mesafe kontrolü nedeniyle duraklatıldı. | Paused for the distance check. | Wegen der Abstandsprüfung pausiert. |

Previous sources replaced in component display text:

- `Seslendirme kapalı. Header hoparlörünü açıp devam edin.` →
  `Seslendirme kapalı. Üst çubuktaki hoparlörü açıp devam edin.` (two display sites).
- Literal accessibility description `karusel` → localized
  `Kaydırılabilir kartlar` / `carousel` / `Karussell`.

All other product edits are catalog entries. Static results/history labels keep
their existing Turkish wording; score calculations and record contents do not change.

## Audit coverage and results

| Check | TR | EN | DE |
| --- | --- | --- | --- |
| Preparation, initial camera/model loading and instructions for both eyes | PASS | PASS | PASS |
| Camera/eye status, closure, hand/object cover, wrong eye, light/framing/distance/stale frame guidance | PASS | PASS | PASS |
| Listening, processing, partial-letter/orientation/reverse/repeat clarifications and silence | PASS | PASS | PASS |
| Network retry, persistent error, pause, muted output, permission/camera/model/playback errors | PASS | PASS | PASS |
| Progress through both eyes, completion, results, history and read error | PASS | PASS | PASS |
| Mobile 390×844 and consent withdrawal | PASS | PASS | PASS |
| Actual-source translation regression: 463 dynamic assertions + 48 display statuses per language | PASS | PASS | PASS |
| Approved recording mapping and exact script text, 11 events per language | PASS | PASS | PASS |

The new regression fails against the immutable pre-audit catalog on the mixed
English/Turkish partial-answer sentence. It passes with the corrections. The 463
assertions per language cover all six letters/unknown letter, rotations/mirroring,
missing components, four clarification types plus conditions-invalid guidance,
49 paired eye states, both eye instructions with condition suffixes and all 12
per-eye question numbers. Source-derived status/error/dialog/notice strings have
real translations; inventory exemptions cannot hide these displayed fallbacks.

Local checks: **79 focused Vision/localization/language tests passed**, no failures.
Typecheck, lint (no warnings/errors), production build and complete catalog
inventory/placeholder/ID checks pass. The final regression also checks all 33
approved Vision script mappings. Original audio files/manifests are unchanged.

Browser evidence uses the actual production application and localization/rendering
infrastructure. Camera pixels/model outputs and recognition events are fixtures.
Approved audio is played natively at 4× only to shorten this text audit. Fixture
camera banners are localized too. No physical testing was required or performed.
Each locale passes **43 browser stages** and produces **31 screenshots** (93
images total), completes 24 answers across both eyes, opens results/history and
exercises error states independently. A leak scanner checks visible text and accessibility labels
against distinctive foreign-language phrases; explicit translation assertions and
screenshot inspection supplement it. This is bounded regression evidence, not a
claim that language can be inferred perfectly from arbitrary user input.

The initial browser harness needed two corrections: distinguish Turkish-specific
characters from ASCII `i` under Unicode case folding, and scope alerts to the
Vision root rather than Next.js's empty route announcer. These were test-only
issues; the final runs below are the complete reruns.

Evidence and screenshots:
[TR browser log](vision-localization-evidence/tr-browser.json),
[EN browser log](vision-localization-evidence/en-browser.json),
[DE browser log](vision-localization-evidence/de-browser.json).
[Validation summary](vision-localization-evidence/validation.json) records counts,
provenance and implementation CI. The final evidence/report commit is identified
by the PR head and its separate CI run.

| Locale | Dynamic instruction | Clarification | Recognition error | Results | History | Mobile |
| --- | --- | --- | --- | --- | --- | --- |
| TR | [image](vision-localization-evidence/tr-instruction.png) | [image](vision-localization-evidence/tr-clarification.png) | [image](vision-localization-evidence/tr-error.png) | [image](vision-localization-evidence/tr-results.png) | [image](vision-localization-evidence/tr-history.png) | [image](vision-localization-evidence/tr-mobile.png) |
| EN | [image](vision-localization-evidence/en-instruction.png) | [image](vision-localization-evidence/en-clarification.png) | [image](vision-localization-evidence/en-error.png) | [image](vision-localization-evidence/en-results.png) | [image](vision-localization-evidence/en-history.png) | [image](vision-localization-evidence/en-mobile.png) |
| DE | [image](vision-localization-evidence/de-instruction.png) | [image](vision-localization-evidence/de-clarification.png) | [image](vision-localization-evidence/de-error.png) | [image](vision-localization-evidence/de-results.png) | [image](vision-localization-evidence/de-history.png) | [image](vision-localization-evidence/de-mobile.png) |
