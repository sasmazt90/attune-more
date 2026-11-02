import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize(("api", "preview", "origins"), [
    ("", "", "http://localhost:8000"),
    ("8011", "", "http://127.0.0.1:8011"),
    ("8000", "8000", "http://127.0.0.1:8000"),
    ("8011", "8305", "http://127.0.0.1:8011 http://127.0.0.1:8305"),
    ("65536", "8305/anything", "http://localhost:8000"),
])
def test_preview_policy_matches_client_loopback_origins(api, preview, origins):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, NEXT_PUBLIC_ATTUNE_ACNE_V5="1",
               NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT=api, NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT=preview)
    script = "import config from './apps/vehicle-app/next.config.mjs';console.log(JSON.stringify(await config.headers()))"
    value = subprocess.check_output(["node", "--input-type=module", "-e", script], cwd=root, env=env, text=True)
    assert json.loads(value)[0]["headers"] == [{
        "key": "Content-Security-Policy",
        "value": f"connect-src 'self' {origins}; object-src 'none'; base-uri 'self'; form-action 'none'",
    }]
