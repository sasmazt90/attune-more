#!/usr/bin/env bash
# Apply only on the specifically approved EC2 host after the source/model bundle is staged.
# Does not start services, purchase infrastructure, change DNS, or accept SDK licenses.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run as root on the approved host via SSM.' >&2; exit 1; }
role="${1:?Usage: install_host.sh web|aaos}"
[[ "$role" == web || "$role" == aaos ]]
[[ -d /opt/attune/.git && -d /opt/node/bin ]]
id attune >/dev/null 2>&1 || useradd --create-home --shell /bin/bash attune
install -d -o attune -g attune -m 0700 /var/lib/attune /var/lib/attune/evidence
install -d -m 0750 -o root -g caddy /etc/attune /etc/attune/tls
# Install Caddy 2.10.2 from its official signed distribution separately; verify binary provenance.
command -v caddy >/dev/null
caddy version
if [[ "$role" == web ]]; then
  apt-get update
  apt-get install -y libglib2.0-0 libgomp1
  : "${ATTUNE_PYTHON311:?Path to reviewed Python 3.11 runtime required (not Ubuntu 24.04 default)}"
  "$ATTUNE_PYTHON311" -m venv /opt/attune-venv
  /opt/attune-venv/bin/pip install -r /opt/attune/services/core-api/requirements.txt -r /opt/attune/tests/requirements-skin-runtime.txt
  /opt/attune-venv/bin/pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cpu
  /opt/attune-venv/bin/pip install 'uvicorn[standard]'
  /opt/attune-venv/bin/pip check
  # Missing model assets fail closed: verify the reviewed manifest before enabling units.
  : "${ATTUNE_ASSET_MANIFEST:?Reviewed asset manifest required}"
  /opt/attune-venv/bin/python /opt/attune/scripts/aws/verify_assets.py --root /opt/attune --manifest "$ATTUNE_ASSET_MANIFEST" --output /var/lib/attune/evidence/assets.json
  install -m 0644 /opt/attune/infra/aws/config/attune-api@.service /opt/attune/infra/aws/config/attune-web@.service /opt/attune/infra/aws/config/attune-capture.service /etc/systemd/system/
  echo 'Provide root-owned api-web.env (PORT=8000), api-aaos.env (PORT=8001), capture.env, TLS files and Caddy environment; then validate and enable units.'
else
  apt-get update
  apt-get install -y qemu-kvm cpu-checker xvfb x11vnc novnc websockify x11-utils ripgrep openjdk-21-jdk unzip pulseaudio pulseaudio-utils
  usermod -a -G kvm attune
  install -m 0644 /opt/attune/infra/aws/config/attune-aaos.service /opt/attune/infra/aws/config/attune-audio.service /etc/systemd/system/
  : "${ATTUNE_PYTHON311:?Path to reviewed Python 3.11 runtime required}"
  "$ATTUNE_PYTHON311" -m venv /opt/attune-venv
  /opt/attune-venv/bin/pip install fastapi==0.135.4 starlette==1.3.1 "uvicorn[standard]"
  echo 'Install verified official SDK; review licenses; run prepare.sh as attune; provide aaos.env and TLS/mTLS files.'
fi
systemctl daemon-reload
# Operator validates certificates and hashes before explicitly enabling any service.
