#!/usr/bin/env bash
# Only Ubuntu 24.04 x86_64 host dependencies, never application permissions/data.
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../.." && pwd)"
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && "$(uname -m)" == x86_64 ]] || {
  echo 'BLOCKED: this runtime package manifest is audited for Ubuntu 24.04 x86_64 only' >&2
  exit 69
}
mapfile -t task_packages < <(python3 - "$task_root/tests/automotive/runtime_policy.json" <<'PY'
import json,sys
print('\n'.join(json.load(open(sys.argv[1]))['packages']))
PY
)
[[ ${#task_packages[@]} -gt 0 ]]
task_sudo=()
if [[ $(id -u) != 0 ]]; then task_sudo=(sudo); fi
"${task_sudo[@]}" apt-get update
# binutils supplies readelf for the aggregated ABI audit. No -dev packages,
# PulseAudio daemon, sound server, display server, legacy TIFF or 32-bit libraries.
"${task_sudo[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends binutils "${task_packages[@]}"
