# Local QA runtime and acceptance harness

Everything needed to reproduce the Skin performance measurements and the WEB/AAOS module
journeys from a clean checkout. Machine-local locations stay in two JSON files outside the
repository; nothing here reads an install directory by a hard-coded path or changes one.

## Machine-local configuration

| File | Template | Purpose |
|---|---|---|
| `local-runtime.json` | `scripts/qa/local-runtime.example.json` | Python and verified model directories |
| `aaos-config.json` | `scripts/qa/aaos/aaos-config.example.json` | Android SDK, AVD home, AVD name, package |

Environment for the journeys:

| Variable | Meaning |
|---|---|
| `ATTUNE_QA_PLAYWRIGHT` | Path to a Playwright package (default: `playwright`) |
| `ATTUNE_QA_FIXTURES` | Controlled media: `skin-native-input`, `vision-native-input`, `synthetic-speech` |
| `ATTUNE_QA_OUT` | Evidence directory |
| `ATTUNE_QA_LANG` | `tr`, `en` or `de` |
| `ATTUNE_QA_RECORD` | `0` disables tab recording (its encoder would disturb a performance run) |
| `ATTUNE_QA_CAPTURE_DIR` | Stores the Skin request bodies for `skin_api_bench.py`; contains photos, never archive it |
| `ATTUNE_QA_AAOS_CONFIG` | Path to `aaos-config.json` |

## Services

```sh
python scripts/qa/qa_services.py start --workdir DIR --runtime-config local-runtime.json
python scripts/qa/qa_services.py stop --workdir DIR
```

The launcher replaces the former undocumented `outputs/run_repair_backend.py`. Native thread
lanes are not a launcher setting: `services/core-api/local_native_worker.py` assigns them
before any native library loads, so a launcher value cannot change the worker. Build the
frontend first with `NEXT_PUBLIC_ATTUNE_ACNE_V5=1`; ports 3000 and 8000 are the defaults the
build's content security policy and the Android debug shell expect.

## Performance

| Tool | Use |
|---|---|
| `perf/run_condition.py` | Runs a command under the sampler and attributes resources per step |
| `perf/resource_monitor.py` | Per-process memory/CPU/faults plus Windows paging counters; no payloads |
| `perf/skin_api_bench.py` | Real prepare → poses → fusion over HTTP with per-field output digests |
| `perf/runtime_variant.py` | Runtime options applied from outside the product, one process per variant |
| `perf/pose_profile.py` | Slowest functions of one pose on the exact worker path |
| `perf/ballast.py` | Memory-only or CPU-only load, to separate the two causes |
| `perf/bench_series.py` | Tagged API benchmarks under the sampler, one after another |
| `perf/report_e2e_run.py` | Attributes a browser run: API timeline plus resource trace |
| `perf/output_parity.py` | Compares the worker output of two checkouts field by field |
| `perf/skin_recovery.py` | A cancelled or vehicle-stopped analysis leaves no orphan or late result |
| `perf/guard_probe.py` | The reserve guard on the real worker path, without exhausting the host |

## Journeys

| Script | Boundary |
|---|---|
| `e2e/skin-journey.cjs` | Real browser and inference: three poses, fusion, results, history, delete |
| `e2e/vision-journey.cjs`, `e2e/hearing-journey.cjs` | Real browser, two complete assessments |
| `e2e/mental-lifecycle.cjs`, `e2e/mental-boundaries.cjs` | Real browser, **mocked provider** |
| `e2e/*-boundaries.cjs` | Interruption boundaries; dispatched events are labelled in the evidence |
| `e2e/dental-journey.cjs` | Cross-module regression through the shared native worker |
| `e2e/module-i18n.cjs` | TR/EN/DE entry surfaces; reports any leftover source-language sentence |
| `aaos/aaos_session.py` | Boots the read-only AVD and installs the debug shell |
| `aaos/aaos-native-gates.cjs` | PARK/DRIVE, stale data, background, Back, keys, permissions |
| `aaos/aaos-hearing.cjs` | Real WebView, real PCM into the guest mixer, synthetic listener |
| `aaos/aaos-vision.cjs` | Unmodified no-camera boundary, then **injected camera and recognizer** |
| `aaos/aaos-mental.cjs` | Unmodified no-ASR boundary, then **scripted recognizer and mocked provider** |
| `aaos/aaos-language-sync.cjs` | Native toolbar language after real navigations from the shell's Home button |
| `aaos/gate_probe.py` | Watches the AAOS WebView while the host runs other work |

A journey result only speaks for its boundary. Injected or mocked layers are named in the
evidence and never count as camera, microphone, speech-service, provider or human-listening
acceptance. Clinical or model accuracy is out of scope for all of these.
