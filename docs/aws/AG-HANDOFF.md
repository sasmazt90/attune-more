# Antigravity handoff: independent review and acceptance

You verify independently. Do not change the working branch while Claude is implementing on it.
Report defects; fixes go through separate reviewed pull requests. Your results are yours, and
Claude must not write or override them.

## Before anything else: confirm your own AWS access

Run these from your own terminal. Claude ran them for you once, which does not count.

```powershell
aws sts get-caller-identity --profile attune-ag
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aws\windows\Test-AgentAccess.ps1 -AwsProfile attune-ag -ExpectIngressDenied
```

Expect the role `attune-ops-verifier`, session `antigravity`. If sign-in has expired, the account
owner runs `aws login --profile attune-operator`. No access keys exist or should be created.

Start and stop with the installed tool, using your profile:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\AttuneMore\bin\AttuneControl.ps1" -Action Start -AwsProfile attune-ag -NoPause
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\AttuneMore\bin\AttuneControl.ps1" -Action Stop -AwsProfile attune-ag -NoPause
```

Instances cost about $1.16 per hour. Stop them when you are not actively testing.

## What changed from earlier sessions

- Public IPs change on every start. Do not hard-code them. Use the hostnames, mapped to the current
  IPs from the START report or `--host-resolver-rules`. DNS for them does not exist yet.
- Old helper scripts in `/var/lib/attune/qa/*.py` have the old IPs baked in and will not work unchanged.
- The private CA was replaced. Its public certificate is `%LOCALAPPDATA%\AttuneMore\attune-private-ca.crt`.
- The real AAOS viewport is 1280x517, not 1280x800. See [evidence/aaos-viewport-20261103.json](evidence/aaos-viewport-20261103.json).

## Phase 4: review the candidate, before merge

Review the exact commit named in the pull request, not an earlier deployment. Check:

1. All changes in the pull request, including what it inherits from #22.
2. Deployed source matches: `/var/lib/attune/evidence/release-provenance.json` on both hosts.
3. Frontend build, backend unit tests, Android and AAOS tests, automotive safety tests.
4. Source, consent and privacy checks.
5. No model weight, threshold or calibration changed. The diff should show no change under
   `services/core-api/models` and no change to `DENTAL_GATES`, `BITE_CONTACT` or `LETTER_RULES` values
   other than the added `notVisibleAllowance`.
6. No secret or private health data committed.
7. PARK and DRIVE behavior in the native app. The native toolbar layout changed; its restrictions must not have.

Report findings with severity. Do not merge. The owner approves the merge.

## Phase 5: ten new English videos, after merge

Only start once the approved release is on `main`. Deploy that exact commit first:

```powershell
python scripts\aws\deploy_release.py --profile attune-ag --commit <full main SHA>
```

| Module | WEB | AAOS |
|---|---|---|
| Skin, Vision, Dental, Hearing, Mental | 1 each | 1 each |

### Inputs

| Module | WEB | AAOS |
|---|---|---|
| Skin | `Char11-1/2/3.png` (Drive IDs in the owner's brief) | `Char49-1/2/3.png` |
| Dental | FRONT `Male-Dental-4`, RIGHT `Male-Dental-1`, LEFT `Male-Dental-3`, BITE `Male-Dental-2` | The same Male set |
| Vision | `Female-Vision-1/3/2` | `Male-Vision-1/3/2` |
| Mental | `Mental-Health-1` to `5`, in order | The same |
| Hearing | Controlled DIN listener | The same |

Determine Skin FRONT, RIGHT and LEFT from the image content, not the filename number. Most inputs are
in `/opt/attune-staging/inputs` on the hosts. `Char11` is not on the hosts yet.

Why the Male Dental set on AAOS: `Female-Dental-4` shows a closed bite but fails the contact gate
([evidence](evidence/dental-bite-gate-20261104.json)). All four Male views pass both gates. The gate
was not changed. Report this as a known limitation, not as a pass for that photo.

### Vision must be realistic

`scripts/qa/realistic/vision_realistic.py` reads the drawn letter, speaks an answer through the real
microphone path and compares scores. `--scenario full` is 24 trials; `--scenario stop` proves the second
"I can't see it" stops safely. `make_vision_speech.py` creates the clips. You may use these or write your
own. Requirements either way:

- Correct and plausibly wrong answers, real OpenAI ASR, the Android microphone route on AAOS.
- At most one "I can't see it" per assessment, across both eyes.
- Expand "Results by size" for both eyes. Check saved history against what was said.
- A run that is all "I can't see it" must not be accepted.

Known: ASR on the Android microphone path heard "B" as "D" on every attempt. The app keeps asking and
does not score it. A person would then say a code word, which is what the harness does. Report how often
this happens.

### Skin accuracy: the owner's specific concern

A real visible acne lesion was previously missed. Look for that specifically. Keep these separate:

1. Detected and classified.
2. Detected but not subclassified. "Unclassified spots" is acceptable and not a failure by default.
3. Visible supported lesion not detected: potential false negative. Report every one.
4. Finding with no support in the image: potential false positive.

No ground-truth labels exist for these images. Do not invent accuracy percentages.

### Report separately for every module and platform

| Dimension | Values |
|---|---|
| Functional E2E | PASS, PARTIAL, FAIL |
| Results completeness | PASS, PARTIAL, FAIL |
| Automotive or web responsive UI | PASS, PARTIAL, FAIL |
| Analysis accuracy | PASS, PARTIAL, FAIL, NOT VERIFIED |
| Physical acceptance | PASS, NOT RUN, BLOCKED |
| Video evidence | PASS, PARTIAL, FAIL |

A completed results screen does not prove a finding is correct. During AAOS recording also check the items
in section 5.3 of the owner's brief, and take screenshots of anything a video cannot show clearly.

## Phase 6: delivery

Create `Attune.more / Independent AWS E2E English / YYYY-MM-DD` in Drive with the videos in per-platform
folders, SHA-256 manifest, screenshots, input mapping, runtime and source commits, UX audit, accuracy
observations, per-module missing measurements, Vision transcript with expected and actual scores, Dental
four-view verification, defects with severity and the final report. Then stop both instances with the tool
and confirm `stopped` through the API.
