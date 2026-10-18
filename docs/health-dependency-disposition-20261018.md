# SEC-01-02: finite dependency maintenance disposition

**Decision: preserve the working delivery and keep the seven upstream records OPEN in maintenance. No compatible small patch is established by the retained evidence, so no package, lock, installed dependency, application, guard or deployment was changed.** This is not a fresh audit, security clearance, vulnerability suppression or a risk acceptance signed for the user.

Starting HEAD `7bd4636a461325c408143436d56156de77d68d7f`; branch `research/health-final-technical-closeout-20261017`. Normal source remains `8e8a51711ccdfb372cc7b2e60d328c888a78e8fe`, BUILD_ID `A-e1UWQmCW1DpJXm9fY46`.

## What changed since the retained parser review

Six related files were compared to that review's recorded hashes. Root `package.json`, `package-lock.json`, Tailwind config, PostCSS config and ESLint config still match. Workspace `package.json` changed only through the already accepted `cea59f7352ab2f727db9d98def408eeb37995550` finite build/lint bridge and matches its managed hash. `scripts/build_health_final.py` and `scripts/tooling/finite_job.py` match the managed guard hashes. Current dispatcher Git blob matches the subsequent `626c32bab58ebe15ba1b601f4564fd5cb4eeecea` platform compatibility correction; no working-tree change exists in it. No unexplained related drift was found.

Lock SHA-256 remains `a3059b0d66c9a65dc1237fea5220d8fa8a051d9b0dc9d81bee7093b1bafb573d`. A lock/config comparison is not a new installed-byte scan or a complete application reachability review.

The retained registry metadata is **2026-10-17T21:40:49.614Z**; retained production-trace inspection is **2026-10-17T21:41:59.342Z**, for BUILD_ID `PlmGO62XYbiAMR2PNNLGr`. Those15 traces had zero affected module/embedded-og hits. They were not rerun on current `A-e1...` and are not represented as today's trace acceptance. The old source review found no photo/chat/history/API value flowing into these tooling parsers in its inspected revision. That is bounded counterevidence, not proof that every framework entry point or future change is safe.

## Why no lock-only patch is selected

The retained audit returned7 high records propagating one [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) chain: braces, micromatch, fast-glob, chokidar, Tailwind, Next ESLint plugin and eslint-config-next. It is not seven independent CVEs. The retained metadata reports braces3.0.3/latest with no patched version. **No registry, advisory or audit request was made in this task**; this is a dated maintenance basis, not a claim about today's latest release.

| Suggested action | Concrete retained reason it is not this small fix |
|---|---|
| Upgrade Next lint packages to15.5.28 | Recorded `@next/eslint-plugin-next15.5.28` still depends on fast-glob3.3.1; eslint-config-next15.5.28 still selects that plugin. The transitive braces chain remains. |
| Force override/fix | No compatible patched braces release is established in the saved registry data. Forcing the same vulnerable version changes no algorithm; substituting an unverified major/fork/API does not establish compatibility. The audit's Tailwind4.3.3 recommendation is explicitly semver-major. |
| Delete/reinstall node_modules | The unchanged lock resolves the same dependency graph. Reinstallation is not a patch and would disturb the working environment without evidence of a repair. |
| Tailwind/CSS or lint major migration | A separately selected migration would require PostCSS/CSS/config and utility-output/layout compatibility work; a lint migration must actually remove/fix this chain rather than merely bump a parent. It is outside this bounded maintenance decision. No duration tied to an unknown upstream release is invented. |

The root postcss-selector-parser7.1.6 flat-advisory override remains preserved. It does not upgrade Tailwind's or Next's independent embedded parsers. Previous numeric-prefix/AST-depth/embedded-copy resource concerns are not marked fixed by the Job guard. No new vendor fork, downgrade, major migration, allowlist or suppression was introduced.

## Mitigation scope already delivered

Managed `artifacts/validation/tooling-resource-guard/coordinator-final-review.json` accepts the Windows resource mitigation and the platform follow-up; `overallSecurityClosed:false` and upstream count7 remain explicit. Only the existing artifacts were read through the plugin read tool; managed state directories were not opened through filesystem tools.

- On Windows, normal root/workspace **finite build/lint** and `build_health_final.py` use the existing Job boundary, aggregate committed-memory limit, deadline and owned process-tree cleanup. Recorded limits: build600s/3072MiB committed memory; lint180s/1536MiB. These are not RSS caps, parser algorithm repairs or a general sandbox.
- The `626c32b` follow-up supersedes the earlier blanket non-Windows exit conclusion: ordinary non-Windows build/lint retain baseline Next pass-through with an explicit message that Windows Job protection is absent. Explicit `--guarded` fails before spawn with78. Real Linux CI was not independently proved by the saved Windows-host dispatch controls.
- Dev/watch/start, raw Next/Tailwind/ESLint, typecheck and older unwrapped helper callers do not acquire this finite Job protection. Trusted developers can still run raw commands. The guard does not cover arbitrary process brokers or replace input trust boundaries.

The earlier10 Job controls,12 parser controls, lint/build/CSS and15 traces were **not repeated**. No new runtime PoC, model call, build, browser or test server was started.

## Maintenance item and reopening conditions

Owner: **CDC/strategist**. Disposition: **OPEN_UPSTREAM_MAINTENANCE**. The seven dated high records remain visible; overall security is not CLOSED and no audit0 claim is made. This document does not constitute user risk acceptance.

Reopen this exact item only on a concrete event:

1. A recorded official patched release/advisory fix and compatible dependency chain become available. Pin its version/metadata first; then perform only the relevant dependency/CSS/parser compatibility checks needed for that actual patch.
2. A new or changed application path is shown to expose attacker-controlled glob/selector/AST/ImageResponse input to an affected sink. Investigate that path and its trust boundary directly.
3. Tooling trust/input changes: untrusted repository config/plugins/content globs, externally supplied `next.rootDir`, or a required dev/watch/raw/non-Windows containment workflow changes the present boundary.
4. The user explicitly selects a scoped Tailwind/CSS or lint major migration with its compatibility work. A future migration is not treated as authorized by this maintenance note.

No automatic repeat audit/scan is scheduled. No patch is promised by an arbitrary future date. No remediation code is selected until the evidence for one of these triggers exists.

## Functional delivery versus security maintenance

**No non-working normal user feature has been attributed to these seven records in the available evidence.** The normal installed application therefore remains as delivered; no user-side repair or application closure is required by this decision. That statement is not fresh camera/history/clinical acceptance, does not close FINAL's browser limits, and does not clear the open tooling dependency findings.

Only this maintenance summary and its machine decision are committed. A supplemental decision was saved through the managed plugin storage at `artifacts/validation/tooling-resource-guard/dependency-disposition/decision-20261018.json`, SHA-256 `0cebc61ee046bd6113947c18b9907308d91513723986ee1c11dbf3b18624dc7d`; canonical findings were not modified. The requested checkpoint/result/index/cleanup summary is under `cdc-progress/health-dependency-disposition-20261018`. Records, consent/profile, models, voices, layout, normal processes and other applications were untouched. No install, registry refresh, build/restart, push/merge/reset/stash/clean/rebase or next task occurred.
