# PR #5 review corrections and functional completion decision

2026-10-21, Europe/Berlin. Starting source `013e1ba7b2fce0d20a43cc3d26c0e3b63d32d67a`; feature `feature/localization-en-de-tr-20261020`; main `1ee2386efd3dc30fe8d5b0d2bbf336ac7f03c98e`.

**The owner's latest request supersedes the earlier narrower prototype merge classification. EN/DE scored digit functionality and genuinely dynamic female speech are product acceptance blockers. No narrower prototype-only merge is authorized.** Physical OEM acceptance and actual headless hidden-tab state remain separate limitations, not independent merge blockers.

## Review corrections

| Finding | Correction | Verification |
| --- | --- | --- |
| [P1](https://github.com/sasmazt90/attune-more/pull/5#discussion_r4331149647): negated English crisis phrases | `shared/localization/english-crisis.json`, `mental_text_rules.py` and `crisisDetector.ts` use the same bounded rules. Known reassurance/history masks only its own phrase; an independent current-risk clause or explicit urgent danger still wins. Ambiguous/conditional/history-only references are UNCERTAIN, not a clinical imminent-intent conclusion. TR/DE keyword rules and existing 112 wording remain. | Actual frontend/backend parity, keyless API cases, positive/negative/ambiguous TR/EN/DE cases, Turkish Unicode and prior German safety/termination cases. Local emergency processing still precedes optional context/network work. |
| [P2](https://github.com/sasmazt90/attune-more/pull/5#discussion_r4331149655): Turkish-only support flag | `professional_support_suggested(reply, selected_language)` requires an ordinary recommendation/benefit cue and profession/support term in the same unquoted, non-negated clause. Supports psychologist/psychological support, Psychologe/Psychologin/psychologische Unterstützung and Turkish forms. Mere profession mentions and quoted/negated suggestions do not activate it. | Actual provider adapter with explicitly stubbed generated output; no paid/live generation. Existing boolean response contract retained. This flag does not assign emergency escalation. |
| Stale Hearing status note | Removed the EN/DE note claiming new digit stimuli were already in use. The accurate unavailable status and both scored-entry gates remain. | Production build and existing Hearing regressions; no algorithm, stimulus or permission change. |

English examples:

| Input | Deterministic result |
| --- | --- |
| `I don't want to die.` / `I am no longer suicidal.` | Reassurance; no emergency classification |
| `I want to die.` / `I feel suicidal.` / `I don't want to live anymore.` | Current risk signal; existing 112 route |
| `I used to feel suicidal, but I don't anymore.` | Historical/UNCERTAIN; no imminent-risk claim |
| `I don't want to die, but I'm afraid I might hurt myself.` | Independent current risk wins; 112 route |
| `I used to feel suicidal, and I still do.` | Continuing current risk; 112 route |
| `I'm not sure whether I'm suicidal.` / conditional reassurance | UNCERTAIN; no automatic imminent-intent diagnosis |

These are bounded deterministic engineering rules, not a clinical classifier or proof of understanding every natural-language utterance. Uncertainty is not labelled unconditional safety. Existing backend/cloud-consent and automotive admission controls remain unchanged.

## Hearing: actual evidence and remaining blocker

The reference is the existing experimental `digital-hearing-v1` protocol and unchanged TR `ahmet-digits-20261008-v1` bank. It already documents `auditoryAcceptance: pending`, `clinicalValidation: false`, and uncalibrated hardware; this assessment neither upgrades nor invalidates its historical engineering acceptance.

- Sequence: three crypto-random digits, each 0–9; exact ordered three-digit answer. Only a fully completed current presentation token can be scored once. Incomplete/cancelled output does not become a miss.
- PCM: mono 48 kHz reference digits; builder trims at 1.5% of peak with 20 ms padding, normalizes whole-trimmed-window RMS to −24 dBFS and rejects peak ≥0.8. Existing noise is speech-spectrum shaped. The triplet retains 180 ms inter-digit gaps and a 30 ms whole-mixture edge ramp.
- Mixing: unchanged −15 to +15 dB SNR, whole-presentation-window RMS definition, mixture RMS target 0.015 and peak ceiling 0.08. No headphone dB SPL/HL calibration is inferred from those digital numbers.
- Scoring: unchanged 24 valid trials, 4→2 dB adaptation, last six reversals, existing convergence/boundary exclusions, exact answer capture and digital longitudinal interpretation. Pure-tone calibration assumptions, channel confirmation, algorithms and timing remain unchanged.

All thirty approved source digit exports were decoded and measured read-only. They are stereo; none directly matches the reference mono/level requirements. Downmixed raw RMS ranges: TR −37.31 to −20.13 dBFS; EN −29.31 to −25.06; DE −26.78 to −23.37. This is a packaging/processing difference, not evidence that the approved spoken content is defective.

Twenty traceable EN/DE **engineering candidates** and two speech-shaped noise files were created only under the isolated Cloud evidence directory, using the existing reference processing algorithm. Original bytes/hashes remain unchanged. Candidate RMS is −24.00000042 to −23.99999972 dBFS; peaks are 0.24790–0.43323. These are not activated assets or approved clinical stimuli.

Actual production Web Audio components decoded these candidate files, mixed/played triplets at −15/0/+15 dB SNR and confirmed natural completion and cancellation: eight component checks passed. The production scorer was exercised separately with 24 explicitly synthetic answer fixtures. No human recognition, actual product keypad completion or clinical threshold acceptance is claimed. Actual EN/DE `HearingAudio.loadBank()` still rejects before any file fetch.

**Missing for scored activation:** an accepted language-specific masked-digit intelligibility/level-equalization and noise specification with pass tolerances, plus qualified acoustic acceptance of the derived stimuli. The supplied content approval and digital normalization measurements do not provide that evidence. Clinical equivalence, if claimed, additionally needs language-specific psychometric/reference and calibrated headphone/device evidence. No such evidence or qualified acceptance was available here; no paid expert/service or physical-device campaign was started. EN/DE scored Hearing remains a genuine product blocker, not completed localization. Guidance and pure-tone functionality remain separate.

## Dynamic Mental speech

The documented browser speech API was queried in actual Cloud Chrome 155.0.8059.84 after bounded voice discovery: **zero voices**. Web Speech also has no standardized gender field; no gender was guessed. The optional local provider has no installed `espeak-ng`, and no local choices were returned. Installing a mechanical variant would not establish the requested natural female speech experience.

No authorized documented no-cost live speech resource/entitlement is configured. Existing `edge-tts` consumer integration is not accepted as evidence of a supported authorized service API and was not invoked. No paid API, undocumented endpoint, microphone capture or personal text transmission occurred.

TR/EN arbitrary live speech remains unverified through a legitimate eligible runtime; DE is still blocked, and no authorized natural female alternative was actually available in this environment. Fixed Emel/Ada/Katja and Ahmet/Andrew/Stefan recordings remain unchanged and retain prior playback acceptance. Fixed clips and keyless local-demo replies are never presented as arbitrary live LLM speech. The owner's earlier Windows microphone success remains historical user-reported evidence; it was not repeated or relabelled as latest-source verification.

**Required remedy:** provide an eligible browser/system runtime with an independently verified appropriate female voice, or an authorized supported speech service with a verified free entitlement, then verify real arbitrary-text synthesis/playback and its interruption/consent/safety lifecycle. No untested substitution or new infrastructure was added.

## Validation and AAOS authorization

Focused review/integration regression: **170 passed**, including the new bilingual source parity, actual API routing, multilingual recommendation cases, existing German/Unicode/priority cases, consent/motion and original-file preservation. Counts overlap prior runs. Isolated production build/typecheck/lint pass with six pre-existing warnings. Full old suites are reused; automatic exact-head CI is checked after push.

The owner freshly verified GitHub Free, Actions 0/2,000 minutes, storage 0/0.5 GB, billable usage $0 and reset in twelve days. They explicitly renewed authorization for one final-source run within free allowance. Use only standard `ubuntu-24.04`, 40 minutes maximum, 50 MiB artifacts including ZIP overhead, one-day retention, no retries or paid services. Stop on quota/billing restriction.

The prepared AAOS workflow retains exact-source guarding, historical 17 checks plus native TR/EN/DE sync, 27 route visits, all 194 AAC decodes and 15 fixed-audio configurations. Actual execution/results must be recorded separately against the immutable final SHA; no emulator PASS is inferred here. The connector exposes no workflow-dispatch method, and a normal configured CLI read-only API preflight returned `Get https://api.github.com/repos/sasmazt90/attune-more: Forbidden`; no network policy or credential bypass is permitted.

Cloud evidence: `/workspace/attune-pr5-completion-20261021/`, including focused logs, source measurements, candidate provenance, real component receipts, voice inventory and immutable-source execution/CI status. No original source audio or Turkish scored bank is changed.

## Merge decision

PR #5 remains Ready for Review. Resolve verified P1/P2 threads after the corrected commit and evidence are published, and recheck new findings and repository rules. **Do not merge** until final-source AAOS evidence and the requested Hearing/dynamic-speech product requirements pass. A narrower prototype may be considered only after its software/runtime gates pass and the owner separately approves that narrower scope. Main remains unchanged; no deployment is authorized or performed.
