"""Model files checked by hash must have the same bytes on every platform.

The V5 verifier was stored with converted line endings, so its hash passed on Windows and failed on
Linux, and the acne chain reported itself unavailable on every Linux host. Git attributes now keep
these bytes exact. This test reads what a checkout really contains, on the platform running it.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
FOLDER = ROOT / 'services/core-api/models/acne-v5-preview'
HASH = '0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb'
MANIFEST_HASH = 'a9f939deb312cfc957d8456fc865e1d3a6f21a5d4e0ba227b94bedb1413a8fe0'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_v5_verifier_bytes_match_the_hash_the_loader_requires():
    source = (ROOT / 'services/core-api/experimental_acne_v5.py').read_text('utf8')
    assert "V5_HASH='" + HASH + "'" in source
    assert sha((FOLDER / 'verifier-v5.json').read_bytes()) == HASH


def test_v5_manifest_bytes_and_declared_hash():
    raw = (FOLDER / 'manifest.json').read_bytes()
    assert sha(raw) == MANIFEST_HASH
    assert json.loads(raw)['verifier']['sha256'] == HASH


def test_deploy_records_exactly_these_hashes():
    source = (ROOT / 'scripts/aws/deploy_host.py').read_text('utf8')
    assert source.count(HASH) == 1 and source.count(MANIFEST_HASH) == 1


def test_git_stores_these_files_without_conversion():
    for name in ('manifest.json', 'verifier-v5.json'):
        path = 'services/core-api/models/acne-v5-preview/' + name
        done = subprocess.run(['git', 'check-attr', 'text', path], cwd=ROOT, capture_output=True, text=True)
        if done.returncode != 0:
            return  # Not a git checkout, as in a source archive. The byte tests above still apply.
        assert done.stdout.strip().endswith('unset'), done.stdout
