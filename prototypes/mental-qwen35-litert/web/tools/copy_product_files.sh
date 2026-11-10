#!/usr/bin/env bash
# Copies the product files the prototype runs unchanged (validator) into generated/product, with SHA-256.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
OUT="$(cd "$(dirname "$0")/.." && pwd)/generated/product"
mkdir -p "$OUT/services/core-api" "$OUT/shared/localization"
mkdir -p "$OUT/tests/unit/fixtures"
for f in services/core-api/mental_analysis.py services/core-api/mental_themes.py shared/localization/mental-themes.json shared/localization/messages.json tests/unit/fixtures/mental_spoken_summary_cases.json; do
  cp "$ROOT/$f" "$OUT/$f"
done
(cd "$ROOT" && sha256sum services/core-api/mental_analysis.py services/core-api/mental_themes.py shared/localization/mental-themes.json shared/localization/messages.json tests/unit/fixtures/mental_spoken_summary_cases.json) > "$OUT/SOURCES.sha256"
cat "$OUT/SOURCES.sha256"
