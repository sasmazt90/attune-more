#!/usr/bin/env bash
# Run through SSM on an approved existing host, after staging the verified bundle.
# Does not start any service or change provider secrets.
set -euo pipefail
[[ "$(id -u)" == 0 ]]
role="${1:?Usage: bootstrap_runtime.sh web|aaos}"
python3 /opt/attune/scripts/aws/host_identity.py --role "$role"
: "${ATTUNE_RUNTIME_ROOT:?Verified runtime archive directory required}"
: "${ATTUNE_RUNTIME_MANIFEST:?Path/bytes/SHA-256 manifest required}"
python3 /opt/attune/scripts/aws/verify_assets.py --root "$ATTUNE_RUNTIME_ROOT" \
  --manifest "$ATTUNE_RUNTIME_MANIFEST" --output "$ATTUNE_RUNTIME_ROOT/verification.json"
[[ ! -e /opt/node && ! -e /opt/python311 ]] || {
  echo 'Existing runtime found: inspect/reuse it before bootstrap; refusing overwrite.' >&2; exit 1;
}
mkdir -p /opt/node /opt/python311
tar -xJf "$ATTUNE_RUNTIME_ROOT/node-v22.20.0-linux-x64.tar.xz" --strip-components=1 -C /opt/node
tar -xzf "$ATTUNE_RUNTIME_ROOT/python-3.11-runtime.tar.gz" -C /opt/python311
install -m 0755 "$ATTUNE_RUNTIME_ROOT/caddy" /usr/local/bin/caddy
[[ "$(/opt/node/bin/node --version)" == v22.20.0 ]]
/opt/python311/bin/python3.11 -c 'import sys; assert sys.version_info[:2] == (3, 11)'
/usr/local/bin/caddy version | grep -q '^v2.10.2 '
