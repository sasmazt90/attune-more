# Antigravity handoff: independent review of the release candidate

Claude implemented the fixes, ran the checks and recorded the 12 English videos. Your job is the independent
review. Do not rely on Claude's PASS labels: check the code, the videos and the evidence yourself, and report what you
find. Fixes go through a reviewed branch and affected tests and videos are rerun. Nothing merges to `main` until your
review is complete and the owner approves.

Start with `docs/qa/ACCEPTANCE-REPORT-20261104.md`. Release candidate, draft PR and evidence: see `docs/qa/RELEASE-CANDIDATE.md`.

## Confirm your own AWS access first

Run these from your own terminal. Claude ran them for you once, which does not count.

```powershell
aws sts get-caller-identity --profile attune-ag
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aws\windows\Test-AgentAccess.ps1 -AwsProfile attune-ag -ExpectIngressDenied
```

Expect the role `attune-ops-verifier`, session `antigravity`. If sign-in has expired, the account owner runs
`aws login --profile attune-operator`. No access keys exist or should be created.

Start and stop with the installed tool, using your profile:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\AttuneMore\bin\AttuneControl.ps1" -Action Start -AwsProfile attune-ag -NoPause
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\AttuneMore\bin\AttuneControl.ps1" -Action Stop -AwsProfile attune-ag -NoPause
```

The hosts cost about $1.16 per hour. Stop them when you are not testing.

## What to review

| Area | Question | Where |
|---|---|---|
| Tracker | Does each QA item's status match its evidence? | `docs/qa/ATTUNE-MASTER-QA-TRACKER.md` |
| Skin model contract | Is any status overstated? Does the runtime match the records? | `docs/qa/SKIN-MODEL-CONTRACT.md`, `skin-contract-runtime.json` per platform |
| V5 and MediaPipe on AWS | Two runtime gaps were found and closed. Does the fix hold, and did results change in a way that needs owner approval? | `.gitattributes`, `tests/unit/test_model_bytes_exact.py`, `scripts/aws/deploy_host.py` |
| Dental bite gate | Is the fix a real discrimination, not a lowered threshold? Try your own open-bite and discoloured controls. | `services/core-api/dental_analysis.py`, `apps/vehicle-app/src/utils/dentalCapture.ts`, `docs/aws/evidence/dental-bite-gate-v2-20261104.json` |
| Vision | Read the per-trial matrix against the video. Real ASR, at most one "can't see it". | `vision-scoring-matrix.md` |
| Hearing | Do results avoid clinical claims? Pure-tone listener is scripted, on real audio. | `hearing-evidence.md`, `components/hearing/` |
| Mental | Language quality, latency, whole conversation. | `mental-performance.md` |
| Appointments | No false booking claim, no default city, local time. | `app/care/page.tsx`, `utils/careAppointments.ts` |
| Automotive UX | Check the real WebView, not a resized browser. Text readable, nothing covered. | `ui-measurements.md`, the AAOS videos |
| Skin labels | Do they match the owner's two references on real results? Is any label on the wrong spot or the wrong photo? Compare the stored result with what is drawn. | `skin-label-evidence.md`, `SkinFindingCallouts.tsx`, `skinCalloutLayout.ts`, `skinCalloutModel.ts`; rerun with `run_e2e.sh <web or aaos> callouts <name>` after a Skin run |
| Readiness | Does READY fail on an empty OpenAI account, without printing any response text? | `scripts/aws/host_ready.py`, `tests/aws/test_control.py` |

## What the owner asked for on Skin labels

Their brief of 2026-11-04 gave these final criteria. The two reference images came as chat attachments and are not in the repository, so
ask the owner for them.

- No long dripping lines and no numbered endpoint markers. Actual finding names are displayed.
- All findings are visible by default. Only the selected finding is visible after selection, in sync with its card.
- No label overflow in TR, EN or DE. No callout collision or off-screen placement.
- Consistent WEB and AAOS behaviour, and no changes to the underlying analysis results.
- Never transfer a finding onto the wrong photograph or facial region, and never invent coordinates.

The owner then corrected the layout from a screenshot: region arrows either side of the photo, no repeated title on the right, proportional
finding numbers, and a one-row top bar on all screens.

## Checks Claude could not finish

- **A full download of the videos back from Drive, hashed.** The files are private and Claude's browser is not signed in to Google. Sizes
  match through the Drive API, and hashes match on the Drive for desktop copy. Please download them and compare with `videos.md`.
- Your own AWS access. See above.

## Known limits to judge, not to assume fine

- Every Skin accuracy figure on record comes from synthetic characters, on a set also used to choose the method.
- No record of explicit owner approval was found for most Skin models. `regional.pt` is probably the R1 model the
  acceptance gate rejected. These are open owner decisions, listed in the contract.
- All recordings use reference photos, synthesized speech and scripted listeners. No physical camera, microphone or
  person. No clinical accuracy is claimed anywhere.
- AAOS runs on an emulator with simulated vehicle data.
- Claude reads likely Skin and Dental misses from the photos in the findings register. That is one reader's judgement, not ground truth.
- A spoken clip can be cut at a pause, and it happened on a different platform in different runs. Worth your own look.

## Reporting

Report per finding: file and line, what happens, how to reproduce, and the build you saw it on. Record your own
results; Claude must not write or override them.
