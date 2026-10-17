# SEC-01-02 — dependency/parser boundary review, 2026-10-17

**Outcome: blocked for upstream dependency closure; no application code change warranted by the inspected parser path.** No lock, manifest, installed package, runtime/config, build, model, UI or record changed. This is a finite review of the existing findings, not a new whole-repository security scan or risk acceptance.

## Current facts, not copied historical status

One fresh `npm audit --json` returned exit1 and **7 high /0 moderate /0 critical**. These seven records propagate one underlying braces advisory through the graph, not seven independent CVEs. No fresh omit-dev audit was run; no new “production audit0” claim is made. Each affected installed node matches lockfilev3 and is marked dev. Current official registry metadata and [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) still show braces3.0.3/latest with no patched version. No compatible lock-only correction exists for this chain.

| Record / installed version | Introducer / actual boundary | Patch status |
|---|---|---|
| braces3.0.3 | Tailwind content-glob expansion through micromatch/fast-glob; developer-controlled build/config input | Official patch unavailable |
| micromatch4.0.8 | Tailwind direct and fast-glob; calls braces expansion | Latest retains braces |
| fast-glob3.3.3 /3.3.1 | Tailwind content resolver / Next lint configuration helper | Latest retains micromatch/braces |
| chokidar3.6.0 | Tailwind CLI watcher → braces; current scripts use Next, not this CLI | Installed affected chain; do not assert it runs on the inspected Next dev path |
| tailwindcss3.4.19 | App PostCSS plugin; fixed repository content globs | v3-lts unchanged; v4 is a CSS major migration |
| @next/eslint-plugin-next15.5.27 | get-root-dirs globSync only with settings.next.rootDir; current default uses context.cwd | New15.5.28 still declares fast-glob3.3.1 |
| eslint-config-next15.5.27 | Extends Next lint plugin | New15.5.28 retains that chain |

The old October3 assertion that chokidar necessarily runs on Next dev was broader than the inspected source supports. The lint package dependency is real, but its configurable glob sink is conditional. Historical reports are preserved; these are current source-backed refinements.

Braces length/range limits do not close recursive AST depth. Parenthesis nodes and public AST-taking compile/expand/stringify APIs also matter; a brace-character-count guard would be incomplete. No unapproved vendor guard, renamed fork, blind override, force fix, Next downgrade or CSS/lint major migration was attempted. Existing audit failure remains visible. A new15.5.28 lint version is not a fix for this reported graph, so upgrading it merely to change version numbers would not be justified here.

## Parser source-to-sink and remaining concern

Root selector parser7.1.6 is already the official [flat-selector advisory fix](https://github.com/advisories/GHSA-rj75-hqrm-r3gf). Its installed source still repeats a numeric-percent regex for every dot, so numeric-prefix work is not proven generally linear. The embedded old parser in Tailwind `peers/index.js` is used by optional CLI minification and is not replaced by the root override. Next compiled `@vercel/og` also contains an independent copy; it is relevant only if a caller exposes ImageResponse/Satori. Package bytes alone do not establish endpoint reachability.

The actual app PostCSS configuration calls Tailwind utilities from repository CSS/content. A scoped search of app JS/TS, shared packages and Python service source found no direct parser/glob/ImageResponse/next-og import or call. There are no app route files exposing such a service. All15 current production NFT traces contain zero affected-module or embedded-og paths. No photo/chat/history/API value was found flowing into a build parser. This is evidence of absent application reachability in this revision, not a generic framework-safety or future-route guarantee.

Therefore no fabricated production parser endpoint or speculative input guard was added. Build/CLI processing remains an upstream tooling resource concern. Existing test timeouts are not presented as protection for the actual build. No claim that the numeric-prefix or embedded-copy problem was fixed is made.

## Ordered verification and compatibility

1. **Syntax/import/control path:** executed the existing `tests/unit/selector_parser_controls.cjs` against the installed graph; exit0. Five selector round trips, Tailwind ordinary/prefix/important/nested CSS and the private `dist/util/unesc` import passed.
2. **Bounded trigger classes:** class, id, mixed and numeric-prefix inputs at2k/4k/8k were run in12 child processes, each with a5s actual subprocess timeout and128MiB V8 old-space flag (observed total V8 limit176MiB, not a128MiB RSS/total-heap cap). No large exhaustion payload was run. Numeric-prefix measured32.76/74.49/209.37ms; these bounded timings are observations, not a complexity proof or hardware-independent limit. The existing metadata remains `linearComplexityEstablished:false`.
3. **Legitimate behavior:** generated CSS SHA256 `e677bc4762b266f36d7213b4b15e7c6e99e03dcb11e4b84be0692e46a71cf37d` matches the existing pinned7.1.6 output. Normal selectors and Turkish/UI sources were not rewritten. No owning package/config/source changed, so a fresh typecheck/build or health-model campaign is irrelevant to this documentation-only result; the existing runtime's build identity was verified instead. This is not a new build acceptance claim.

The original unresolved braces advisory remains reproducible at the inventory/source level and has **not** been fixed. The published flat-index advisory is already patched at the root dependency; the remaining numeric-prefix/embedded paths are explicitly separate. No untrusted app request path was demonstrated. A clean overall security outcome would therefore be false.

## Identity, cleanup and handoff

Full lock/config/installed-source hashes, current graph, registry metadata, trace inventory, control timings and cleanup are in the companion JSON and the requested `cdc-progress/health-dependency-parser-closeout-20261017` folder. Codex Security `fix-finding` was used for the existing findings with one independent read-only boundary investigation and one independent candidate review; no managed scan was initiated. Explicit task output paths were used rather than inventing a scan ID/canonical scan report.

The normal runtime remains b2573b512595adc7cae86d7ab932abb318f61689 / BUILD_ID PlmGO62XYbiAMR2PNNLGr. All297 production files and both launcher hashes match; all four normal process identities are preserved. Twelve parser children and their parent exited, the exact ownership observer exited, and both task leases released. No listener/browser/profile/server was created and no normal or unrelated process was stopped. No user record, permission or profile was written. No package install, audit suppression, push or merge occurred.

The oil patch SHA256 remains `3d45f56794b034da80f611730a5f45a6432b58d51ac4f999b903d6f42a808022`. Human approval for its controlled normal restart has now arrived, but oil activation is deliberately not performed in parallel with this SEC task. Its production build/API activation remains the next sequential handoff. That approval does not authorize unreviewed security changes.

Remaining: upstream braces patch or a separately scoped compatible replacement decision; parser residual resource concern; oil build/API handoff; open SAG same-voice/live, DRY optical/admission and FINAL-01 visual/history/semantic permission items. No next task or new investigation campaign starts here.

Independent review found no concrete production bypass or compatibility regression. Its micromatch version-list labeling correction was applied from retained registry evidence. The invoking wrapper/inherited NODE_OPTIONS and a small nested-child check establish the old-space flag; the observed total V8 heap limit176MiB is reported separately. This is not a hard RSS limit or a deployed input guard.
