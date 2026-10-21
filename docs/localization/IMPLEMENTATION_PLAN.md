# EN / DE / TR localization implementation plan

## Audited integration baseline

- Repository: `sasmazt90/attune-more`; remote main: `1ee2386efd3dc30fe8d5b0d2bbf336ac7f03c98e`.
- New branch: `feature/localization-en-de-tr-20261020`, based on `7ba4dfbad8b4916de1411e1a6e2980b814a3658c`.
- All eight remote branch tips observed on 20 October 2026 are ancestors of that baseline: main, AAOS prototype, branding, health delivery, audit, remediation, live follow-up and functional integrity.
- AAOS source baseline remains `a3943b6`; run #122 and archived evidence are historical and must remain unchanged. No new metered emulator execution is authorized by this implementation.

## Source audit

The Next.js application contains 50 TSX and 65 TS source files (10,343 lines at baseline). An initial TypeScript AST inventory found 1,143 unique string/text/template values containing Turkish characters, before adding ASCII-only words, shared module metadata, backend output and audio manifests. There is no existing shared localization provider/catalog.

| Surface | Existing implementation | Required treatment |
| --- | --- | --- |
| Navigation and pages | `CockpitHeader`, nine routes, shared dialogs/components, Turkish literals and metadata | Central catalogs; persisted selector; reactive text and accessible attribute rendering |
| Clinical/state logic | Turkish quality labels are sometimes used in comparisons; stable record IDs/routes and numeric results | Translate at presentation boundaries; preserve raw state/algorithms, IDs, record bytes and thresholds |
| History/export | Browser local storage/IndexedDB, Turkish date formatting and a DOM-created print document | Locale-aware presentation; preserve records/transcripts; translate generated labels, never user-authored data |
| Consent | Versioned per-service permission IDs, distinct storage preferences and OS grants | Translate explanatory text without granting/resetting consent; preserve provider disclosure |
| Backend | FastAPI JSON, deterministic mental provider, optional consented OpenAI provider, care metadata/errors | Explicit request language; localized generated output; preserve enum/identifier/numeric fields and user text |
| Recognition | Browser SpeechRecognition hardcoded `tr-TR`; Turkish vision letter/command parser | Selected locale, target-independent EN/DE parsing, translated echo/command handling; no inference change |
| Guidance | Hash-verified approved Turkish MP3 manifest and event-driven capture/audio focus lifecycle | Preserve all files/hashes; add locale text mapping and cancellable system TTS when a matching voice actually exists |
| Streamed speech | Exact Edge Ahmet/Emel profiles, consent gate, streamed MPEG and fixed instruction cache | Preserve TR contract; explicit locale/voice selection from actual provider metadata; never silent cross-language fallback |
| Hearing | Pure tones plus hash-verified Turkish digit/noise bank | Preserve stimuli and protocol; do not substitute unvalidated translated digit recordings as equivalent measured stimuli |
| Input | Native text/datetime/number/file inputs, consent controls; no custom alphabetic keyboard | Native Unicode input; German/Turkish round-trip tests; do not add a keyboard |
| AAOS | Separate native strings, public Car UX plus independent backend gate, foreground/watchdog, destroyed WebView on pause | Native EN/DE resources; preserve gate classes/lifecycle/origin policy; no speech compatibility claim without a new runtime |

## Implementation sequence

1. Record immutable approved audio hashes and baseline ancestry outside tracked product data. Build a deterministic source/capture catalog inventory and completeness checks.
2. Add centralized source-message catalogs, locale/formatting utilities and persisted language/voice preference storage in new keys only. Use React presentation boundaries for translated text/attributes so internal Turkish state comparisons and raw clinical records retain their meanings. No DOM mutation observer, HTML replacement, page duplication, user-text translation or remount on language switch.
3. Add compact accessible selector beside status controls. Update document language/title and native browser formatting. Changing language cancels stale speech/recognition while preserving assessment progress, consent and records; it never changes vehicle state.
4. Localize all five modules, dashboard/history/care/privacy, dialogs, results/quality labels, notifications, print/export and relevant backend-generated messages. Preserve measurement units/values, limitations and safety meaning. Maintain machine-readable IDs and raw provider/storage fields.
5. Discover real matching browser/system voices and provider voice metadata. Persist voice independently per locale. Only metadata supports gender labels; unknown gender remains unknown. Empty/missing catalogs produce a visible unavailable state, never invented voices or another language. Preserve existing TR recordings and hash checks. New localized synthesis is explicitly distinguished from approved audio.
6. Add multilingual recognition/parser, backend language propagation, localized generation prompts/fallback/crisis messages and provider disclosures. Maintain existing safety rules and streaming cleanup. No paid model/TTS calls in validation.
7. Add native Android resource translations and static safety/locale tests without changing gate policy. Desktop Windows voice enumeration and AAOS spoken output remain separate physical/runtime acceptance layers.
8. Run catalog/placeholder/hardcoded-string checks, Unicode and provider/voice tests, relevant complete regressions, lint/typecheck/build, and finite actual Cloud browser checks across TR/EN/DE and 1440/768/375 widths. Preserve screenshots and exact executed/unverified status outside the source tree.
9. Recheck remote main/branch ancestry, approved audio bytes, clinical algorithm/safety diff and user data isolation. Commit/push the feature implementation and create a PR targeting main. This branch includes the unmerged AAOS baseline; describe that ancestry explicitly. Request owner approval for any eventual merge; no deployment or emulator workflow dispatch.

## Acceptance boundaries

Do not mark unavailable platform voices, unvalidated localized digit stimuli, live paid-provider output, Windows installed voices or AAOS spoken output as tested/passing. A missing required voice/localization capability or incomplete runtime check must remain explicit in the readiness report. Successful original emulator evidence cannot certify this changed build. No clinical, distribution, OEM or production certification is implied.
