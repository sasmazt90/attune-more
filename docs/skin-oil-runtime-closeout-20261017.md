# OIL-01 — controlled runtime closeout; candidate inactive

The reviewed oil candidate built successfully, but full normal model/API inference did not run: the unchanged model-start reserve is 2,500 MiB. Normal TOGG is open on the previous verified runtime, with the candidate preserved separately. No new task, model, training, threshold search or hosted call followed this closeout.

## Result and evidence boundary

| Layer | Result |
|---|---|
| Earlier focused candidate regression | 13 tests and isolated typecheck passed; not rerun here |
| Exact patch | SHA-256 `3d45f56794b034da80f611730a5f45a6432b58d51ac4f999b903d6f42a808022`; clean apply-check passes after rollback |
| Production build | Passed in 76.187 s; summed peak RSS 930.71875 MiB; start reserve 1,600 MiB and peak budget 2,100 MiB unchanged |
| Candidate source/build/served chain | Application `14efa4123b5ffcfb2095747b99d3baf679d1a3ef`, BUILD_ID `24ZU0_wGYz9NR_v4LQkNU`; 297 deployment hashes and 26 actually served JS/approved-image hashes matched |
| Full normal model/API inference | **Not run: zero analysis requests.** No result/history acceptance claimed |
| Final normal runtime | Open on source `b2573b512595adc7cae86d7ab932abb318f61689`, BUILD_ID `PlmGO62XYbiAMR2PNNLGr`; 297 deployment hashes, both launcher hashes and 26 served asset hashes matched |
| Final source/index | Narrow rollback committed as `59ffc06a65cffa65b0baedd98161b8f63c474f30`; index/worktree clean before these documentation files |

The first API preflight found 1,695 MiB and returned before HTTP inference. A bounded, owned-window-only release kept the actual API running, but available RAM samples were 2,330 / 2,325 / 2,322 MiB; still below the unchanged reserve. The supervisor was resumed and the same shortcut/profile reopened. The user's latest requested RAM recheck measured 2,175 MiB; cleanup later measured 2,079 MiB. No further model attempt, restart, other-application closure, reserve reduction or RAM wait loop followed.

## Previously tested oil correction

These are **earlier same-source RGB-path comparisons with learned calls disabled**, not new full normal API proof. The overview previously included unmeasured periorbital support; its coverage gate also failed to inspect an unavailable nose oil measurement. The candidate uses a unique Boolean union of the five measured oil regions and oil-specific admission. Existing regional thresholds, RGB clipping, valid T-zone evidence and final Karma ordering remain unchanged.

| Source / evidence type | Overview before → after | Regional preservation |
|---|---|---|
| Recorded `e5622aba…`, operational zero support | 0.032566218 → 0 | All five regions remain 0; no biological matte truth inferred |
| Recorded `8048b762…`, visible highlight | 0.024584119 → 0.027900056 | Forehead 0.104846226 and T-zone 0.049833887 unchanged |
| Controlled clipping of 5,460 exclusive nose pixels | 0.044856459 → null / `GLARE_OR_EXPOSURE` | Nose remains unavailable; four other regions remain 0 |

The candidate versions are `visible-specular-area-fixed-v1+regional-quality-union-v2` and `oil-regional-quality-unique-visible-union-v2`. Earlier focused tests cover regional and overview history version separation. Old records were not recalculated. This does not establish temporal oil photometry, biological sebum measurement, or flash/cosmetic discrimination.

## Rollback, review decisions and continuing base

The initial controlled-stop request was rejected by automatic approval review while explicit restart authorization was missing. The human subsequently authorized only TOGG's controlled restart; that exact approval and patch identity were verified. Later, a split rollback command was rejected before execution because it omitted a guaranteed normal reopen. An accepted single try/finally rollback-and-reopen operation was used instead; no rejected operation was bypassed.

The historical `resume-rollback-and-reopen.json` is preserved unchanged, including `baselineRestored:false` and the Git exit-128 failure. The narrow reverse patch had already been staged, runtime source bytes and the prior build had been restored, and `finally` reopened normal TOGG. A redundant `git add` of the already-deleted new test path failed, preventing that script's commit and final success flag. The exact staged three-file reversal was then inspected and committed directly as `59ffc06…`. This is why **runtime recovery, the original controller error, and later index/commit completion are separate facts**. The new final receipt records `baselineRestored:true` without rewriting the old error receipt.

The continuing combined Git base is rollback commit `59ffc06…`, plus this documentation commit. It retains the preceding DRY/SEC/OIL audit history while its deployed runtime files match the prior verified source. The launcher's serving identity intentionally remains `b2573b5…`, not the newer documentation HEAD. Oil application commit `14efa41…` and the reviewed patch remain available in history. Candidate build is preserved at `.runtime/oil-resume-20261017-candidate-next`; active `.next` contains `PlmGO62XYbiAMR2PNNLGr`.

## Cleanup and remaining acceptance

All four normal roles passed PID/start/executable/command/CWD-or-profile ownership checks, both ports belonged to their recorded roles, and the supervisor was not suspended. The owned build and observer exited. The original build-child PID was reused by a different process and was preserved. Both owned compute leases were released; no process was killed during finalization. No temporary test server/profile or API inference job was created. No unrelated application was closed.

Backend data fingerprints and shortcut hashes are unchanged. The opaque Chrome permission-exceptions hash differs after the normal browser lifecycle; its semantic meaning was not inspected, restored or declared accepted. FINAL-01 visual/history/permission acceptance stays open. Models, approved images/audio, hosted-disabled configuration and other runtime methods retain the verified deployed hashes. No push, merge or external message was performed.

**Oil is inactive.** Full normal model/API acceptance remains blocked by RAM reserve. SAG's missing approved cue/live acceptance, DRY's optical misses/admission questions, SEC residual findings and FINAL-01 acceptance are not closed by this work.

Machine evidence: companion `skin-oil-runtime-closeout-20261017.json`; detailed immutable resume receipts and cleanup are under `cdc-progress/skin-oil-reliability-20261017` in the parent TOGG workspace. Original candidate report and receipts were not overwritten.
