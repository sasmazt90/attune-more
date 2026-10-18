# CARE-READY — finite public-handoff candidate

The missing CARE behavior is implemented and tested in a selective patch, **not activated in normal TOGG**. Starting combined HEAD was `6a00f3178382cd612a5f1e0251299c663f3f1ec8`, after rollback `59ffc06…`. No applicable AGENTS.md was present in the inspected workspace/ancestor paths. Normal serving source remains `b2573b512595adc7cae86d7ab932abb318f61689`, BUILD_ID `PlmGO62XYbiAMR2PNNLGr`. Oil application `14efa41…` and its archived build were not applied or modified.

## Existing contract and concrete changes

Existing code already had a provider interface, explicit demo labels, full source timestamp parsing, user time windows, referral context, a frontend abort/deadline/generation check, parked UI, confirmation and public handoff rather than booking. These were not rebuilt as a new integration.

The candidate repairs these observed gaps:

| Gap | Candidate behavior |
|---|---|
| Browser-only DoktorTakvimi search; UI ignored its empty-result handoff URL | Default public search links use existing cards, without browser scraping. DoktorTakvimi/Doktorsitesi cover configured Turkish cities; Doctolib.de covers configured German cities. Istanbul is never silently replaced with Berlin |
| Public search could look like a discovered physician/time | `PUBLIC_SEARCH_ONLY`, unknown consultation type, null date/time, null window fit and no invented physician, calendar conflict or travel duration |
| Arbitrary extracted anchor or redirect URL could become bookingUrl | Exact HTTPS source hosts, source-ID consistency, restricted path/query, no credentials, foreign domain, redirect query or nonstandard port; matching frontend link boundary |
| Missing/invalid source time could use the user's timezone | Naive source time uses source zone; manual window uses user zone. Invalid, nonexistent or ambiguous naive local dates do not match. An invalid slot becomes profile-only, not a verified time |
| API performed external search before validating manual windows | Validate first; reject malformed windows/timezone/duration before provider selection. Backend parked/disconnect checks apply before and after search |
| Browser blocked/empty/network outcomes collapsed | `ACCESS_BLOCKED`, `EMPTY_RESULT`, `NETWORK_ERROR`, `TIMEOUT`, `SOURCE_ERROR`, `CONFIGURATION_REQUIRED` remain distinct; public links may remain available, never silent demo slots |
| No configured partnership seam | Code-owned adapter registry plus normalized result contract; no API endpoint/account/key is configured or claimed connected today |
| Late/changed search | Existing abort/generation behavior retained; aborted response cannot replace state. Leaving parked state aborts search and clears results; partial manual window is rejected locally |

Only five candidate files are in `docs/patches/care-ready-20261018.patch`: `care_provider.py`, the CARE payload/handler in `main.py`, existing care page, a small `careLinks.ts` utility and focused tests. Active runtime source files were not edited. No UI panel, checkbox, image, font/layout, health model, speech, menu or central permission flow was added or changed.

## Source verification and coverage

Official public pages were read through the web tool only. No browser automation, login, CAPTCHA bypass, scraping campaign, booking, message or private health/photo/record transfer occurred. The intended Turkish source is **Doktorsitesi.com**, not an assumed similarly spelled domain.

Representative location + specialty URLs were verified on official pages: [DoktorTakvimi dermatology/Istanbul](https://www.doktortakvimi.com/dermatoloji/istanbul), [Doktorsitesi dermatology/Istanbul](https://www.doktorsitesi.com/uzmanlik-alanlari/dermatoloji/istanbul), and [Doctolib dermatology/Berlin](https://www.doctolib.de/hautarzt/berlin). Official specialty links also confirmed [Doktorsitesi clinical psychology](https://www.doktorsitesi.com/uzmanlik-alanlari/klinik-psikolog), [KBB](https://www.doktorsitesi.com/uzmanlik-alanlari/kulak-burun-bogaz-hastaliklari), [audiology](https://www.doktorsitesi.com/uzmanlik-alanlari/odyoloji), and [dentistry](https://www.doktorsitesi.com/uzmanlik-alanlari/dis-hekimi). Doctolib's [KBB/Berlin](https://www.doctolib.de/facharzt-fur-hno/berlin), [psychiatry/Berlin](https://www.doctolib.de/psychiatrie-und-psychotherapie/berlin) and [psychological psychotherapy/Berlin](https://www.doctolib.de/psychologischer-psychotherapeut-psychotherapeutin/berlin) paths were confirmed; guessed short paths were replaced before delivery.

DoktorTakvimi's general [psychology/Istanbul](https://www.doktortakvimi.com/psikoloji/istanbul) list is broader than clinical psychology: the clinical referral therefore retains the exact specialty/city in an encoded public search query instead of asserting a narrower verified profile category. Its audiology path follows the official `odyoloji-dil-konusma-ve-ses-bozukluklari` category. Two exploratory URLs could not be read; no availability or successful URL claim was made from those failures.

Configured city templates are Istanbul/Ankara/Izmir and Berlin/Hamburg/Muenchen/Koeln/Frankfurt. **Not every generated city/specialty URL was opened individually.** Unsupported city/specialty yields empty result rather than another city. No Doctolib audiology equivalence was invented. These are directory/search URLs; no real current date+time was established by this audit. Window tests use declared synthetic timestamps, never portrayed as real appointments.

## Configuration seam

`ATTUNE_CARE_PROVIDER=public` is the candidate default; missing API config preserves public handoff. `browser` explicitly selects the existing read-only browser implementation. `partner` requires a named code-registered adapter; absent registration returns public links with `CONFIGURATION_REQUIRED`. No dynamic imports, user-provided endpoint or secret file are accepted. Future adapters receive only specialty/city and an 8-second transport budget; an actual adapter must enforce that budget in its real transport. There is no partner transport to test today. Demo requires all of: explicit `demo` mode, `ATTUNE_CARE_ALLOW_DEMO=1` and explicit demo request selection. Request flag alone cannot activate demo.

## Focused acceptance and preserved runtime

**42 tests passed in 1.75 s.** They cover public profile/search without time, actual full source timestamp with distinct user/source zones, malformed/ambiguous windows, partial/bad dates, source-bound URLs, missing config, explicit demo only, separate source errors/empty results, no invented travel/calendar, parked admission, disconnect and vehicle change. Tests execute the exact staged production payload class and handler AST through ASGI TestClient without importing unrelated main/model/credential/persistence modules. This is selected-handler contract evidence, **not a deployed normal API POST or browser acceptance**.

The two changed frontend files passed semantic TypeScript checking against the existing dependency graph, with zero diagnostics; 15 runtime link cases passed. No emit, install or production build occurred. The guarded single check took 8.094 s with peak summed RSS 331.7265625 MiB; its owned process and observer exited and both leases released. Source pin/hash and clean patch apply-check passed.

Normal API GET identity/OpenAPI verified the actual source/build and `/api/care/match` route. No normal CARE POST was made: that older deployed path would launch browser automation. All 297 deployed source/model/build hashes, launcher hashes, shortcut and backend data fingerprints matched. The same four owned normal roles/ports remain open; no normal restart or profile/record/permission change occurred. Existing Computer Use URL restrictions were respected; visual acceptance remains **OPEN FINAL-01**. No Playwright/CDP workaround was used.

No temporary browser/profile/listening server/model worker was created. Only the owned TypeScript process/observer and existing lease helper were used; finally cleanup and PID/start/exe/argv/CWD/port evidence are in `cdc-progress/care-ready-20261018/cleanup.json`. CARE had no dependency on the earlier health-ui API PID11684 and did not perform overlapping process cleanup; the coordinator's separate RAM cleanup receipt is referenced there.

## Delivery boundary

The patch and machine evidence are saved in this local documentation commit, without push/merge/reset/stash/clean/rebase. The user has authorized the combined normal delivery. CARE application/build and normal API acceptance are scheduled for the combined FINAL-01 delivery, rather than being blocked on new user approval. This finite source-preparation turn intentionally did not restart/build the normal application; allowed browser acceptance also remains open. Oil, SAG, DRY, SEC and FINAL open items are not closed here. This finite CARE turn does not initiate them or another task.
