# Antigravity handoff: independent review of the release candidate

Claude implemented the fixes, ran the checks and recorded the 12 English videos. Your job is the independent
review. Do not rely on Claude's PASS labels: check the code, the videos and the evidence yourself, and report what you
find. Fixes go through a reviewed branch and affected tests and videos are rerun. Nothing merges to `main` until your
review is complete and the owner approves.

Release candidate, draft PR and evidence links: see `docs/qa/RELEASE-CANDIDATE.md`.

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

## Known limits to judge, not to assume fine

- Every Skin accuracy figure on record comes from synthetic characters, on a set also used to choose the method.
- No record of explicit owner approval was found for most Skin models. `regional.pt` is probably the R1 model the
  acceptance gate rejected. These are open owner decisions, listed in the contract.
- All recordings use reference photos, synthesized speech and scripted listeners. No physical camera, microphone or
  person. No clinical accuracy is claimed anywhere.
- AAOS runs on an emulator with simulated vehicle data.

## Reporting

Report per finding: file and line, what happens, how to reproduce, and the build you saw it on. Record your own
results; Claude must not write or override them.
