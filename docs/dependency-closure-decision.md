# Dependency closure decision — 3 October 2026

This is a proposal, not an applied migration or a clean-security result. Product and prototype audits were refreshed independently: full **7 high / 5 high**, production-only **0 / 0**. Neither lockfile is changed by this follow-up. No force, legacy peers, suppression, lowered threshold, skipped assertion, or risk exception is authorized.

## Verified blockers

- [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): braces <=3.0.3 affected; patched version **none**. Registry latest is 3.0.3. Both fast-glob 3.3.3 and micromatch 4.0.8 retain the chain. A patched target version cannot truthfully be supplied.
- Product Tailwind 3.4.19 -> fast-glob / micromatch -> braces. Tailwind 4.3.3 and @tailwindcss/postcss 4.3.3 remove this Tailwind dependency path; the existing a617a675 prototype proves only a reduction from seven to five high findings.
- eslint-config-next 15.5.27 -> @next/eslint-plugin-next 15.5.27 -> fast-glob 3.3.1 -> micromatch -> braces. The latest @next/eslint-plugin-next **16.3.8** also declares fast-glob **3.3.1**. Next 16 therefore is not a fix for this advisory.
- [ESLint support policy](https://eslint.org/version-support/): ESLint 8 EOL 2024-10-05, ESLint 9 EOL 2026-08-06. Product 8.57.1 and prototype 9.39.5 do not meet the supported-linter requirement.
- ESLint 10.12.0 requires Node ^20.19.0 / ^22.13.0 / >=24. eslint-config-next 15.5.27 accepts ESLint 7/8/9, not 10. Although config-next 16.3.8 accepts >=9, its current transitive react **7.37.5**, import **2.32.0**, jsx-a11y **6.10.2** peers exclude 10. React-hooks 7.1.1 and typescript-eslint 8.71.0 support 10; that does not make the entire chain compatible.

Fresh registry JSON, complete dependency trees and effective ESLint configuration are retained in audit-results/uat-closure-20261003. Failed incompatible chains were not reinstalled. Production audit zero does not clear development/build tooling.

## Smallest concrete alternative to investigate, requiring approval

Keep the runtime on **Next 15.5.27, React/React DOM 19.0.8**, TypeScript **5.9.3**, PostCSS **8.5.28**, MediaPipe **1.0.1**. Separately investigate replacing the two affected development chains:

| Chain | Exact candidate | Proposed scope |
|---|---|---|
| Tailwind 3.4.19 / autoprefixer 10.6.1 | tailwindcss **4.3.3**, @tailwindcss/postcss **4.3.3**, postcss **8.5.28** | PostCSS integration, CSS entry, tokens/content scanning and explicit compatibility styles. No prototype promotion. |
| ESLint 8.57.1 / eslint-config-next 15.5.27 and their transitive plugins/resolvers | @biomejs/biome **2.5.15** (registry engine >=14.21.3) | New lint configuration and mandatory pre-build lint gate; remove the old dependency path only after equivalent checks are demonstrated. No formatter rewrite. |

This changes the lint architecture and Tailwind major. It is **outside current implementation authorization**, and is not a proven safe replacement. Next 16 is unnecessary for this candidate. Runtime/provider/vehicle/health algorithms are outside the migration scope.

The present effective page configuration has **47 active rules**, including **21 Next rules**. [Biome's official rule sources](https://biomejs.dev/linter/rules-sources/) list only five corresponding Next rules (font display, document import, head element, image element, head import). The other sixteen Next checks require an explicit equivalence solution before removal of ESLint. [Biome's migration guide](https://biomejs.dev/guides/migrate-eslint-prettier/) warns that options and behavior may differ. Running its migration command alone is not parity evidence. A rule name mapping alone is also insufficient.

## Acceptance and stop conditions

1. Create a new isolated checkout from the final product commit only after explicit approval for this investigation. Preserve the current product and a617a675 prototype. Pin the candidates above; use ordinary installation, no force or legacy peers. Inspect optional native package versions and peers too.
2. Before removing old lint, export effective configurations for every relevant TS/TSX/JS/CJS/MJS file class and override. Record all active rules, severities and options. Map every check, and run positive/negative samples for hooks, accessibility, imports and all 21 Next checks. A missing or weakened check blocks promotion; do not disable it or call a new default rule set equivalent.
3. Inspect the lockfile/tree for every braces path, clean-install errors and advisories. Both **full and production-only audit must be zero** under the existing threshold. Registry metadata alone cannot prove this result. If an affected path remains, stop the candidate.
4. Preserve CSS behavior explicitly. Earlier isolated prototype evidence recorded **78 style property differences across 15 boxes**, including rounded-2xl **16px -> 14px**. Treat these as known migration risks, not accepted cosmetic changes. Compare dimensions, radii, borders, colors, disabled/hover/focus states, preflight and text wrapping at 390, 820, desktop and actual Chrome 200%.
5. Clean install, typecheck, equivalent lint, fresh production build; retain all 39/14/5/23/8, >=157 unit with zero skips, 54 safety, five dependency, twelve mental, UX, real MediaPipe poses/reference, native voice and nine Windows launcher checks. Verify normal shortcut and owned shutdown. No new paid calls are part of this investigation.
6. Present the resulting immutable diff, rule parity evidence, zero audits, full test and opened screenshot inventory for a separate promotion decision. Failure at any gate leaves this proposal unaccepted and the product unchanged.

**Required decision:** authorize only the isolated Tailwind 4.3.3 + Biome 2.5.15 feasibility/parity investigation above, with no product promotion, custom/vendor substitution or risk exception implied; or retain the current blocked draft while awaiting official compatible patched tooling. There is currently no verified exact-version drop-in solution within existing authorization. This proposal is a bounded investigation, not a guarantee that parity can be achieved. Any additional custom rule/vendor work would need a new concrete proposal.
