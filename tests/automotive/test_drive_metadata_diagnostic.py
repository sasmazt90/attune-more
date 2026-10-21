"""Offline diagnostic contract fixtures; never claim live Drive authorization."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import yaml

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('drive_metadata_diagnostic', HERE / 'drive_metadata_diagnostic.py')
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
INFO = {'type': 'service_account', 'token_uri': diag.TOKEN_URL,
        'client_email': 'fixture@test.iam.gserviceaccount.com', 'private_key': 'FIXTURE_NOT_REAL_KEY'}
PRIVATE_ID = 'PRIVATE_FILE_ID_FIXTURE'
PRIVATE_TOKEN = 'PRIVATE_ACCESS_TOKEN_FIXTURE'


class Response(io.BytesIO):
    def __init__(self, code, body):
        super().__init__(json.dumps(body).encode())
        self.code = code


class Opener:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


class MetadataDiagnosticTests(unittest.TestCase):
    @patch.object(diag, 'assertion', return_value='PRIVATE_ASSERTION_FIXTURE')
    def test_exactly_one_metadata_get_and_one_token_exchange(self, _):
        opener = Opener(Response(200, {'access_token': PRIVATE_TOKEN}), Response(200, {'name': 'PRIVATE_NAME'}))
        row = diag.diagnose(INFO, PRIVATE_ID, opener)
        self.assertEqual(row['status'], 'PASS')
        self.assertEqual(row['httpStatus'], 200)
        self.assertEqual(row['metadataAttempts'], 1)
        self.assertEqual(len(opener.requests), 2)
        auth, metadata = opener.requests
        self.assertEqual(auth.get_method(), 'POST')
        self.assertEqual(auth.full_url, diag.TOKEN_URL)
        self.assertEqual(metadata.get_method(), 'GET')
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(metadata.full_url).query), {'fields': [diag.FIELDS]})
        self.assertIsNone(metadata.data)
        self.assertEqual(metadata.get_header('Authorization'), 'Bearer ' + PRIVATE_TOKEN)
        self.assertNotIn(PRIVATE_TOKEN, json.dumps(row))
        self.assertNotIn(PRIVATE_ID, json.dumps(row))
        self.assertNotIn('PRIVATE_NAME', json.dumps(row))

    @patch.object(diag, 'assertion', return_value='PRIVATE_ASSERTION_FIXTURE')
    def test_provider_http_errors_are_reported_without_retry_or_private_values(self, _):
        for code in (400, 401, 403, 404, 429, 500):
            with self.subTest(code=code):
                body = {'error': {'message': PRIVATE_ID + PRIVATE_TOKEN,
                                 'errors': [{'reason': 'accessNotConfigured'}, {'reason': PRIVATE_ID}],
                                 'details': [{'reason': 'SERVICE_DISABLED', 'metadata': {'consumer': 'PRIVATE_PROJECT'}}]}}
                failure = urllib.error.HTTPError('https://private.invalid/' + PRIVATE_ID, code,
                                                PRIVATE_TOKEN, {}, io.BytesIO(json.dumps(body).encode()))
                opener = Opener(Response(200, {'access_token': PRIVATE_TOKEN}), failure)
                row = diag.diagnose(INFO, PRIVATE_ID, opener)
                self.assertEqual((row['status'], row['httpStatus'], row['requestStage']), ('BLOCKED', code, 'drive-metadata'))
                self.assertEqual(row['safeGoogleReasons'], ['SERVICE_DISABLED', 'accessNotConfigured'])
                self.assertEqual(len(opener.requests), 2)
                for private in (PRIVATE_ID, PRIVATE_TOKEN, 'PRIVATE_PROJECT', 'private.invalid'):
                    self.assertNotIn(private, json.dumps(row))

    @patch.object(diag, 'assertion', return_value='PRIVATE_ASSERTION_FIXTURE')
    def test_token_failure_stops_before_drive(self, _):
        opener = Opener(Response(400, {'error': 'invalid_grant', 'error_description': PRIVATE_TOKEN}))
        row = diag.diagnose(INFO, PRIVATE_ID, opener)
        self.assertEqual(row['httpStatus'], 400)
        self.assertEqual(row['safeGoogleReasons'], ['invalid_grant'])
        self.assertEqual(row['metadataAttempts'], 0)
        self.assertEqual(len(opener.requests), 1)
        self.assertNotIn(PRIVATE_TOKEN, json.dumps(row))

    def test_configuration_rejects_external_token_endpoints_without_network(self):
        opener = Opener()
        row = diag.diagnose({**INFO, 'token_uri': 'https://untrusted.invalid/token'}, PRIVATE_ID, opener)
        self.assertEqual(row['status'], 'BLOCKED')
        self.assertEqual(opener.requests, [])

    def test_redirects_and_non_json_errors_are_not_followed_or_echoed(self):
        self.assertIsNone(diag.NoRedirect().redirect_request(None, None, 302, 'private', {}, 'https://private.invalid'))
        self.assertEqual(diag.reasons(PRIVATE_TOKEN.encode()), [])

    def test_common_field_auth_and_standard_google_status_codes_are_preserved(self):
        raw = json.dumps({'error': {'status': 'INVALID_ARGUMENT', 'message': PRIVATE_ID,
                                    'errors': [{'reason': 'invalidParameter'}, {'reason': 'authError'}]}}).encode()
        self.assertEqual(diag.reasons(raw), ['INVALID_ARGUMENT', 'authError', 'invalidParameter'])

    def test_real_openssl_signature_claims_and_temporary_key_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key, public, signature = root / 'key.pem', root / 'public.pem', root / 'signature'
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(key)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['openssl', 'pkey', '-in', str(key), '-pubout', '-out', str(public)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with patch.object(diag.tempfile, 'tempdir', directory):
                token = diag.assertion({**INFO, 'private_key': key.read_text()}, 1234567890)
            self.assertFalse(list(root.glob('attune-drive-sign-*')))
            header, body, signed = token.split('.')
            decode = lambda part: base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))
            self.assertEqual(json.loads(decode(header))['alg'], 'RS256')
            claims = json.loads(decode(body))
            self.assertEqual(claims, {'iss': INFO['client_email'], 'aud': diag.TOKEN_URL,
                                     'scope': diag.SCOPE, 'iat': 1234567890, 'exp': 1234568190})
            signature.write_bytes(decode(signed))
            subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(public), '-signature', str(signature)],
                           input=(header + '.' + body).encode(), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_workflow_has_no_installs_and_masks_variable_via_secret_forwarding(self):
        root = HERE.parents[1]
        workflow = (root / '.github/workflows/drive-metadata-diagnostic.yml').read_text()
        self.assertIn('sparse-checkout-cone-mode: false', workflow)
        self.assertIn('sparse-checkout: /tests/automotive/drive_metadata_diagnostic.py', workflow)
        self.assertIn("secrets.DRIVE_METADATA_FILE_ID", workflow)
        self.assertNotIn('vars.ATTUNE_AAOS_TTS_BUNDLE_FILE_ID', workflow)
        for forbidden in ('pip install', 'npm ', 'apt-get', 'run_emulator', 'upload-artifact', 'setup-python'):
            self.assertNotIn(forbidden, workflow)

    def test_actual_workflow_guard_rejects_wrong_source_marker_and_reruns(self):
        root = HERE.parents[1]
        workflow = yaml.load((root / '.github/workflows/drive-metadata-diagnostic.yml').read_text(), Loader=yaml.BaseLoader)
        guard = workflow['jobs']['metadata']['steps'][0]['run']
        sha = 'a' * 40
        for value, attempt, code in [('drive-metadata-only:' + sha, '1', 0),
                                     (sha, '1', 69), ('drive-metadata-only:' + 'b' * 40, '1', 69),
                                     ('drive-metadata-only:' + sha, '2', 69)]:
            with self.subTest(value=value, attempt=attempt), tempfile.TemporaryDirectory() as directory:
                import os
                env = {**os.environ, 'APPROVED_SOURCE': value, 'GITHUB_SHA': sha,
                       'GITHUB_RUN_ATTEMPT': attempt, 'GITHUB_STEP_SUMMARY': str(Path(directory) / 'summary')}
                result = subprocess.run(['bash', '-e', '-c', textwrap.dedent(guard)], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.assertEqual(result.returncode, code)
        wrapper = yaml.load((root / '.github/workflows/e2e-audit.yml').read_text(), Loader=yaml.BaseLoader)
        for name in ('aaos-emulator', 'browser-audit'):
            self.assertIn("!startsWith(inputs.expected_source_sha || '', 'drive-metadata-only:')", wrapper['jobs'][name]['if'])
        diagnostic = wrapper['jobs']['drive-metadata-diagnostic']
        self.assertEqual(diagnostic['secrets']['DRIVE_METADATA_FILE_ID'], '${{ vars.ATTUNE_AAOS_TTS_BUNDLE_FILE_ID }}')


if __name__ == '__main__':
    unittest.main()
