#!/usr/bin/env bash
# Validate Actions expressions, contexts, reusable calls and YAML before builds.
set -euo pipefail

version=1.7.7
archive_sha256=023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757
tool_dir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/attune-actionlint.XXXXXXXX")
trap 'rm -rf -- "$tool_dir"' EXIT

curl --fail --silent --show-error --location --retry 0 --proto '=https' \
  "https://github.com/rhysd/actionlint/releases/download/v${version}/actionlint_${version}_linux_amd64.tar.gz" \
  --output "$tool_dir/actionlint.tar.gz"
printf '%s  %s\n' "$archive_sha256" "$tool_dir/actionlint.tar.gz" | sha256sum --check -
tar -xzf "$tool_dir/actionlint.tar.gz" -C "$tool_dir" actionlint

# This guard checks Actions semantics. Existing checks cover Python and app code.
"$tool_dir/actionlint" -color -shellcheck= -pyflakes=
