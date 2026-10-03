# Reproducible lint parity experiment

Base: `f8f08d98cf23eb23c5a171b5b50411364d79adf6`. Investigation only.
Original mandatory ESLint/package/lockfile/runtime are retained. `apps/vehicle-app/biome.json` is a probe configuration; no product lint/build command switches to it.

Run from this isolated checkout with Node 22.20.0 / npm 10.9.3 / Python 3.11:

1. `npm ci`
2. `npm ci --prefix research/tailwind4-biome/toolchain`
3. `node research/tailwind4-biome/inventory.cjs`
4. `python research/tailwind4-biome/probes.py`
5. `python research/tailwind4-biome/summarize.py`

The tool package pins Biome 2.5.15 with its own lockfile. The proposed Tailwind 4.3.3 / @tailwindcss/postcss 4.3.3 are publication/engine metadata targets, not installed product replacements: the prerequisite parity gate failed.

`cases/` contains synthetic lint-invalid examples outside production source. Diagnostics preserve actual process exit codes and all diagnostics; a warning can have exit zero, and another rule's failure is not target-rule parity.

The result is **NO-GO**. `decision-data.json` has all 47 controls and `rule-table.md` is a rendered evidence table. A finite sample match is not universal equivalence; missing bookkeeping semantics are not waived. The comprehensive single decision report is produced after the immutable experiment commit, under `audit-results/tailwind4-biome-feasibility/FINAL_REPORT.md`, with the exact commit and patch hash.

No Tailwind CSS migration, original linter removal, full regression, browser screenshots, paid provider request, physical microphone capture or product promotion is performed after this gate failure. No assertion is changed, and no rule/severity is reduced in the original configuration.
