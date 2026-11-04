#!/usr/bin/env bash
# Runs the speech timing with the service token from the host's own files. Never prints it.
set +x
OUT=/var/lib/attune/evidence/$1; mkdir -p "$OUT"
R=/opt/attune/scripts/qa/realistic; [ -d /var/lib/attune/qa/dev ] && R=/var/lib/attune/qa/dev
set -a; . /etc/attune/api-web.env >/dev/null 2>&1; set +a
export PORT_VALUE="${PORT:-8000}"
if [ -z "${ATTUNE_MENTAL_TTS_TOKEN:-}" ]; then set -a; . /etc/attune/web-web.env >/dev/null 2>&1; set +a; fi
unset OPENAI_API_KEY
/opt/attune-venv/bin/python $R/tts_distribution.py --port "$PORT_VALUE" --unit attune-api@web --normal "${2:-10}" --out "$OUT/tts-distribution.json" 2>&1 | grep -v -i 'token\|bearer' | cut -c1-260
chown -R attune:attune "$OUT"
