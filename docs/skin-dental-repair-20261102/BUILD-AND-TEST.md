# Build and engineering checks

Baseline: `ea92fb442da534a5fd700608898d3891e04baf88`. Branch: `codex/skin-dental-repair-20261102`.

| Check | Result | Evidence |
|---|---|---|
| Focused Skin/Dental backend, source identity, storage, image, geometry, UI and legacy regressions | PASS: 228 passed, 1 skipped, 2 dependency deprecation warnings; 257.90 s | Private `skin-dental-tests-final.log` |
| Selected-finding source and display regression after real-browser discovery | PASS: 10 passed; 13.27 s | `skin-source-selection-tests.log`; `tests/unit/skin_dental_repair.cjs` |
| Production WEB build after source-selection fix | PASS; bounded Windows build exited 0 in 74.94 s | `build-source-bound.log` |
| Final production WEB build including persistent reassessment action | PASS; bounded build exited 0 in 90.72 s, no owned build processes remained | `build-review-final.log` |
| Android `assembleDebug` + `lintDebug` | PASS | `android-build.log` |
| Isolated-package Android build | PASS; package `more.attune.automotive.prototype.debug.repair20261102` | `android-isolated-build.log` |
| Real Java policy classes | PASS: 96 automotive policy checks, syntax for 9 source files | `android-host-checks.log` |

The isolated APK is 65,794 bytes, SHA-256 `ffa4d9a37b7dd0397b09dddc80e3a07db212aacb6be34e73d17687044e4ffd6e`. It has not replaced an installed APK. Host JVM policy checks and APK build/lint do not prove AAOS 15 runtime, vehicle, OEM, suspend/resume or physical hardware acceptance.

The WEB build uses the installed Latest's opt-in V5 mode with isolated API/preview port 8000. Existing weights and frozen thresholds are unchanged. Test-only Python dependencies were installed in a separate task directory; the installed production environment was preserved. New WEB E2E evidence and CI results are reported separately from these engineering checks.

One focused-test skip is retained as reported by pytest; no skipped check is counted as passed. The two warnings concern Starlette/httpx and NumPy/pycocotools APIs, rather than failed assertions.
