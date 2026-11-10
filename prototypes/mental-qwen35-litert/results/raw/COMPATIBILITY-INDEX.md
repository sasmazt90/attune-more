# Compatibility evidence index (KOL B, 2026-11-10)

Model: litert-community/Qwen3.5-2B @ f24013ba…, Qwen3.5-2B_int8.litertlm, SHA-256 c2438cb9…7c49 (2,119,843,840 B).
Browser: Chromium (Chrome for Testing) 153.0.8010.12 headless, 4 vCPU x86_64 VM, no GPU, no KVM. Every browser run
blocked all non-loopback requests (`blockedExternalRequests`).

| File | Platform | Runtime | Result |
| --- | --- | --- | --- |
| web_probe_cpu.json | WEB WASM CPU | @litert-lm/core 0.19.0 | FAIL engine-create: Failed to get external weight (tensor 231) |
| web_probe_cpu_blob.json | WEB WASM CPU, model as Blob | 0.19.0 | FAIL, same |
| web_probe_gpu_swiftshader.json | WEB WebGPU on SwiftShader (software emulation) | 0.19.0 | PASS functional only: engine 137 s, first chunk 138.6 s, "The capital of France is Paris.", decode 0.076 tok/s, RSS 13.3 GB |
| web_probe_cpu_nightly.json | WEB WASM CPU | 0.20.0-nightly.20261109 (comparison only) | FAIL, same external-weight error |
| web_probe_cpu_rev895.json | WEB WASM CPU, previous revision 895dd827 (weights in graph) | 0.19.0 | FAIL: failed to create XNNPACK runtime → Aborted() at ~4.7 GB |
| web_probe_cpu_rev895_1024.json | same, maxNumTokens 1024 | 0.19.0 | FAIL, same |
| smoke_host.json | HOST Linux CPU (not on-device) | litert-lm-api 0.19.1 | PASS: engine 9.7 s / 7.5 s, reply 1.3 s, RSS 3.56 GB |
| leak_host.json | HOST Linux CPU | 0.19.1 | same Engine: new conversation ignored its system prompt 0/2, 0/2; fresh Engine 2/2, 2/2; no literal content leak |
| cancel_probe.json (Evidence) | HOST Linux CPU | 0.19.1 | conversation behaviour after cancel_process() |
| AAOS | — | litertlm-android 0.19.1 | APK built (more.attune.prototype.mentalqwen, 107.5 MB, SHA-256 3e7188af…); run BLOCKED: no KVM, no device |
