"""DNS and certificate flow against a local stand-in for IONOS and an ACME CA. No external call is made.

The real AttuneDomain.ps1 runs in Windows PowerShell. Only name resolution is replaced, and it reads the
stand-in's records, so a record that was never written can never appear to resolve.
"""
import base64
import hashlib
import http.server
import json
from pathlib import Path
import shutil
import subprocess
import threading
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ROOT / 'scripts/aws/windows'
PREFIX = 'publicprefix0001'
SECRET = 'not-a-real-secret-0123456789'
KEY = PREFIX + '.' + SECRET
WEB = 'attunemore.sasmaz.digital'
AAOS = 'aaos.attunemore.sasmaz.digital'
CHAIN = '-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n'

pytestmark = pytest.mark.skipif(not shutil.which('powershell'), reason='Windows PowerShell only')


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def unb64(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


class Stand:
    """State shared with the request handler."""

    def __init__(self):
        self.records = [
            {'id': 'apex', 'name': 'sasmaz.digital', 'type': 'A', 'content': '217.160.0.107', 'ttl': 3600, 'disabled': False},
            {'id': 'ns1', 'name': 'sasmaz.digital', 'type': 'NS', 'content': 'ns1.example', 'ttl': 86400, 'disabled': False},
            {'id': 'mx', 'name': 'sasmaz.digital', 'type': 'MX', 'content': 'mx.example', 'ttl': 3600, 'disabled': False},
        ]
        self.writes = []
        self.keys = set()
        self.reject_key = False
        self.fail_next_write = 0
        self.outage = False
        self.outage_hits = 0
        self.nonces = 0
        self.bad_nonce_once = True
        self.jwk = None
        self.thumbprint = None
        self.account_payload = None
        self.challenge = 'pending'
        self.acme_fail_validation = False
        self.txt_seen_at_validation = False
        self.csr = None


def handler_for(stand):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, body=None, headers=None):
            self.send_response(code)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            data = b''
            if body is not None:
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def read(self):
            return self.rfile.read(int(self.headers.get('Content-Length') or 0))

        def ionos(self, body):
            stand.keys.add(self.headers.get('X-API-Key'))
            # The real service answers 503 when this header is absent.
            if not self.headers.get('User-Agent'):
                return self.reply(503, b'<html>no user agent</html>')
            if stand.outage:
                stand.outage_hits += 1
                return self.reply(503, b'<html><head><title>The page is temporarily unavailable</title></head></html>')
            if stand.reject_key or self.headers.get('X-API-Key') != KEY:
                return self.reply(401, {'message': 'Unauthorized'})
            url = urlparse(self.path)
            parts = url.path.split('/')[2:]
            if self.command == 'GET' and parts == ['v1', 'zones']:
                return self.reply(200, [{'id': 'z1', 'name': 'sasmaz.digital', 'type': 'NATIVE'}])
            if self.command == 'GET' and parts == ['v1', 'zones', 'z1']:
                query = parse_qs(url.query)
                rows = stand.records
                if 'recordName' in query:
                    rows = [r for r in rows if r['name'] == query['recordName'][0]]
                if 'recordType' in query:
                    rows = [r for r in rows if r['type'] == query['recordType'][0]]
                return self.reply(200, {'id': 'z1', 'name': 'sasmaz.digital', 'records': rows})
            if stand.fail_next_write:
                stand.fail_next_write -= 1
                return self.reply(503, {'message': 'busy'})
            if self.command == 'POST' and parts == ['v1', 'zones', 'z1', 'records']:
                rows = json.loads(body)
                assert isinstance(rows, list)
                out = []
                for row in rows:
                    made = {**row, 'id': 'r{}'.format(len(stand.writes) + 1)}
                    stand.records.append(made)
                    stand.writes.append(('POST', row['name'], row['type']))
                    out.append(made)
                return self.reply(201, out)
            if self.command == 'PUT' and parts[:4] == ['v1', 'zones', 'z1', 'records']:
                row = next(r for r in stand.records if r['id'] == parts[4])
                row.update(json.loads(body))
                stand.writes.append(('PUT', row['name'], row['type']))
                return self.reply(200, row)
            if self.command == 'DELETE' and parts[:4] == ['v1', 'zones', 'z1', 'records']:
                row = next(r for r in stand.records if r['id'] == parts[4])
                stand.records.remove(row)
                stand.writes.append(('DELETE', row['name'], row['type']))
                return self.reply(200)
            return self.reply(404, {'message': 'not found'})

        def acme(self, body):
            base = 'http://127.0.0.1:{}/acme/'.format(self.server.server_port)
            path = self.path.split('/acme/')[1]
            nonce = {'Replay-Nonce': 'n{}'.format(stand.nonces)}
            stand.nonces += 1
            if self.command == 'GET' and path == 'directory':
                return self.reply(200, {'newNonce': base + 'nonce', 'newAccount': base + 'new-account', 'newOrder': base + 'new-order',
                                        'meta': {'termsOfService': 'https://example.test/terms.pdf'}})
            if path == 'nonce':
                return self.reply(200, None, nonce)
            envelope = json.loads(body)
            protected = json.loads(unb64(envelope['protected']))
            assert protected['alg'] == 'ES256' and protected['url'].endswith('/acme/' + path)
            if stand.bad_nonce_once:
                stand.bad_nonce_once = False
                return self.reply(400, {'type': 'urn:ietf:params:acme:error:badNonce', 'detail': 'stale'}, nonce)
            if path == 'new-account':
                stand.jwk = protected['jwk']
                canonical = '{{"crv":"P-256","kty":"EC","x":"{x}","y":"{y}"}}'.format(**stand.jwk)
                stand.thumbprint = b64(hashlib.sha256(canonical.encode()).digest())
                stand.account_payload = json.loads(unb64(envelope['payload']))
            else:
                assert protected['kid'] == base + 'acct/1'
            verify(stand.jwk, envelope)
            payload = json.loads(unb64(envelope['payload'])) if envelope['payload'] else None
            if path == 'new-account':
                return self.reply(201, {'status': 'valid'}, {**nonce, 'Location': base + 'acct/1'})
            order = {'status': 'valid' if stand.csr else 'pending', 'authorizations': [base + 'authz/1'], 'finalize': base + 'finalize/1',
                     'certificate': base + 'cert/1'}
            if path == 'new-order':
                stand.identifier = payload['identifiers'][0]['value']
                return self.reply(201, order, {**nonce, 'Location': base + 'order/1'})
            authz = {'status': stand.challenge, 'challenges': [
                {'type': 'http-01', 'url': base + 'wrong', 'token': 'tok'},
                {'type': 'dns-01', 'url': base + 'chall/1', 'token': 'tok', 'error': {'detail': 'no record'}}]}
            if path == 'authz/1':
                return self.reply(200, authz, nonce)
            if path == 'chall/1':
                value = b64(hashlib.sha256(('tok.' + stand.thumbprint).encode()).digest())
                found = [r for r in stand.records if r['name'] == '_acme-challenge.' + stand.identifier and r['content'] == value]
                stand.txt_seen_at_validation = bool(found)
                stand.challenge = 'valid' if found and not stand.acme_fail_validation else 'invalid'
                return self.reply(200, {'status': 'processing'}, nonce)
            if path == 'finalize/1':
                stand.csr = payload['csr']
                return self.reply(200, {**order, 'status': 'processing'}, nonce)
            if path == 'order/1':
                return self.reply(200, order, nonce)
            if path == 'cert/1':
                return self.reply(200, CHAIN.encode(), {**nonce, 'Content-Type': 'application/pem-certificate-chain'})
            return self.reply(404, {'detail': 'not found'}, nonce)

        def handle_any(self):
            body = self.read()
            if self.path.startswith('/dns/'):
                self.ionos(body)
            elif self.path.startswith('/acme/'):
                self.acme(body)
            elif self.path.startswith('/view'):
                query = parse_qs(urlparse(self.path).query)
                rows = [r['content'] for r in stand.records if r['name'] == query['name'][0] and r['type'] == query['type'][0]]
                self.reply(200, rows)
            else:
                self.reply(404)

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = handle_any
    return Handler


def verify(jwk, envelope):
    """Checks the ES256 signature when the optional library is present."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
    except ImportError:
        assert len(unb64(envelope['signature'])) == 64
        return
    key = ec.EllipticCurvePublicNumbers(int.from_bytes(unb64(jwk['x']), 'big'), int.from_bytes(unb64(jwk['y']), 'big'), ec.SECP256R1()).public_key()
    raw = unb64(envelope['signature'])
    signature = utils.encode_dss_signature(int.from_bytes(raw[:32], 'big'), int.from_bytes(raw[32:], 'big'))
    try:
        key.verify(signature, (envelope['protected'] + '.' + envelope['payload']).encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        pytest.fail('ACME signature did not verify')


@pytest.fixture
def stand():
    state = Stand()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler_for(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.port = server.server_port
    yield state
    server.shutdown()


def run_ps(stand, tmp_path, body, save_key=True):
    """Runs body with the module loaded. Prints JSON on the last line: {'ok': ..., 'value' or 'error': ...}."""
    root = tmp_path / 'data'
    (root / 'secrets').mkdir(parents=True, exist_ok=True)
    base = 'http://127.0.0.1:{}'.format(stand.port)
    script = tmp_path / 'driver.ps1'
    # Saved the way an operator saves it.
    save = """
$pw = ConvertTo-SecureString '{secret}' -AsPlainText -Force
New-Object Management.Automation.PSCredential('{prefix}', $pw) | Export-Clixml -LiteralPath $script:IonosKeyPath
""".format(secret=SECRET, prefix=PREFIX) if save_key else ''
    script.write_text("""
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
. '{module}'
$script:IonosApi = '{base}/dns/v1'
$script:DomainDataRoot = '{root}'
$script:IonosKeyPath = '{root}\secrets\ionos-dns.xml'
$script:IonosRetrySeconds = 0
$script:AcmeDirectories = @{{ production = '{base}/acme/directory'; staging = '{base}/acme/directory' }}
$script:AcmePollSeconds = 0
$script:DnsPollSeconds = 0
function Get-DnsAnswer([string]$name, [string]$type, [string]$server) {{
    @((Invoke-Http -Method 'GET' -Url ('{base}/view?name=' + $name + '&type=' + $type)).Text | ConvertFrom-Json) | ForEach-Object {{ $_ }}
}}
function Get-SystemAnswer([string]$name) {{ @(Get-DnsAnswer $name 'A' '') }}
{save}
try {{
    $value = & {{ {body} }}
    @{{ ok = $true; value = $value }} | ConvertTo-Json -Depth 6 -Compress
}} catch {{
    @{{ ok = $false; error = $_.Exception.Message }} | ConvertTo-Json -Compress
}}
""".format(module=WINDOWS / 'AttuneDomain.ps1', base=base, root=root, save=save, body=body), encoding='utf8')
    done = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], capture_output=True, text=True, timeout=120)
    assert SECRET not in done.stdout and SECRET not in done.stderr
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def records(stand, name):
    return [r for r in stand.records if r['name'] == name]


def sync(name, ip, home='198.51.100.9'):
    return "$zone = Get-IonosZone; Sync-DnsRecord $zone.id '{}' '{}' '{}'".format(name, ip, home)


def test_creates_then_updates_only_the_authorized_records(stand, tmp_path):
    before = [dict(r) for r in stand.records]
    assert run_ps(stand, tmp_path, sync(WEB, '3.70.1.1')) == {'ok': True, 'value': 'created'}
    assert run_ps(stand, tmp_path, sync(AAOS, '3.70.1.2')) == {'ok': True, 'value': 'created'}
    assert records(stand, WEB)[0]['content'] == '3.70.1.1' and records(stand, WEB)[0]['type'] == 'A'
    assert records(stand, AAOS)[0]['content'] == '3.70.1.2' and records(stand, WEB)[0]['ttl'] == 60
    assert run_ps(stand, tmp_path, sync(WEB, '3.70.9.9')) == {'ok': True, 'value': 'updated'}
    assert records(stand, WEB)[0]['content'] == '3.70.9.9' and len(records(stand, WEB)) == 1
    assert all(r in stand.records for r in before)
    assert {w[1] for w in stand.writes} == {WEB, AAOS}
    assert stand.keys == {KEY}


def test_no_write_when_the_record_is_already_right(stand, tmp_path):
    run_ps(stand, tmp_path, sync(WEB, '3.70.1.1'))
    count = len(stand.writes)
    assert run_ps(stand, tmp_path, sync(WEB, '3.70.1.1')) == {'ok': True, 'value': 'unchanged'}
    assert len(stand.writes) == count


@pytest.mark.parametrize('existing, word', [
    ([{'id': 'x', 'name': WEB, 'type': 'A', 'content': '8.8.4.4', 'ttl': 3600, 'disabled': False}], 'did not create'),
    ([{'id': 'x', 'name': WEB, 'type': 'CNAME', 'content': 'other.example', 'ttl': 3600, 'disabled': False}], 'CNAME other.example'),
    ([{'id': 'x', 'name': WEB, 'type': 'A', 'content': '8.8.4.4', 'ttl': 3600, 'disabled': False},
      {'id': 'y', 'name': WEB, 'type': 'A', 'content': '8.8.8.8', 'ttl': 3600, 'disabled': False}], '2 A records'),
])
def test_a_name_used_by_another_service_is_reported_not_overwritten(stand, tmp_path, existing, word):
    stand.records.extend(existing)
    snapshot = json.dumps(stand.records)
    result = run_ps(stand, tmp_path, sync(WEB, '3.70.1.1'))
    assert result['ok'] is False and word in result['error']
    assert json.dumps(stand.records) == snapshot and stand.writes == []


@pytest.mark.parametrize('name, ip, word', [
    ('www.sasmaz.digital', '3.70.1.1', 'not an authorized name'),
    ('sasmaz.digital', '3.70.1.1', 'not an authorized name'),
    (WEB, '198.51.100.9', "this PC's own address"),
    (WEB, '10.0.0.5', 'not a public address'),
    (WEB, '172.31.11.240', 'not a public address'),
    (WEB, '169.254.169.254', 'not a public address'),
    (WEB, 'not-an-ip', 'not an IPv4 address'),
    (WEB, '2001:db8::1', 'not an IPv4 address'),
])
def test_refuses_other_names_and_addresses_that_are_not_ec2(stand, tmp_path, name, ip, word):
    result = run_ps(stand, tmp_path, sync(name, ip))
    assert result['ok'] is False and word in result['error'] and stand.writes == []


def test_a_transient_failure_is_retried_without_duplicating(stand, tmp_path):
    stand.fail_next_write = 1
    assert run_ps(stand, tmp_path, sync(WEB, '3.70.1.1')) == {'ok': True, 'value': 'created'}
    assert len(records(stand, WEB)) == 1


def test_an_outage_is_reported_in_one_clear_line(stand, tmp_path):
    stand.outage = True
    result = run_ps(stand, tmp_path, 'Get-IonosZone')
    assert result['ok'] is False and 'HTTP 503' in result['error'] and 'temporarily unavailable' in result['error']
    assert '<html' not in result['error'] and stand.outage_hits == 5, 'reads are retried before giving up'


def test_a_refused_key_says_what_to_do_and_writes_nothing(stand, tmp_path):
    stand.reject_key = True
    result = run_ps(stand, tmp_path, 'Get-IonosZone')
    assert result['ok'] is False
    assert 'HTTP 401' in result['error'] and 'expired' in result['error'] and 'Export-Clixml' in result['error']
    assert stand.writes == []


def test_a_missing_key_file_never_calls_ionos(stand, tmp_path):
    result = run_ps(stand, tmp_path, 'Get-IonosZone', save_key=False)
    assert result['ok'] is False and 'missing' in result['error'] and 'Export-Clixml' in result['error']
    assert stand.keys == set()


def test_certificate_needs_an_account_created_by_the_user(stand, tmp_path):
    result = run_ps(stand, tmp_path, "$z = Get-IonosZone; New-PublicCertificate '{}' 'x' 'production' $z.id @('ns1.example')".format(WEB))
    assert result['ok'] is False and 'SetupCertificates' in result['error']
    assert stand.jwk is None and stand.writes == []


ISSUE = """
$csr = "-----BEGIN CERTIFICATE REQUEST-----`nQUJDRA==`n-----END CERTIFICATE REQUEST-----`n"
[void](Register-AcmeAccount 'production')
$z = Get-IonosZone
New-PublicCertificate '{name}' $csr 'production' $z.id @('ns1.example')
"""


def test_issues_a_certificate_and_removes_the_challenge_record(stand, tmp_path):
    result = run_ps(stand, tmp_path, ISSUE.format(name=WEB))
    assert result['ok'] is True, result
    assert 'BEGIN CERTIFICATE' in result['value']
    assert stand.account_payload == {'termsOfServiceAgreed': True}, 'no contact or personal data is sent'
    assert stand.txt_seen_at_validation
    assert unb64(stand.csr) == b'ABCD'
    assert records(stand, '_acme-challenge.' + WEB) == []
    assert stand.writes == [('POST', '_acme-challenge.' + WEB, 'TXT'), ('DELETE', '_acme-challenge.' + WEB, 'TXT')]
    assert (tmp_path / 'data/secrets/acme-production-account.xml').exists()
    assert 'kid' not in (tmp_path / 'data/secrets/acme-production-account.xml').read_text(encoding='utf-16', errors='ignore'), 'the account file is encrypted'


def test_failed_validation_still_removes_the_challenge_record(stand, tmp_path):
    stand.acme_fail_validation = True
    result = run_ps(stand, tmp_path, ISSUE.format(name=WEB))
    assert result['ok'] is False and 'failed' in result['error']
    assert records(stand, '_acme-challenge.' + WEB) == []
    assert ('DELETE', '_acme-challenge.' + WEB, 'TXT') in stand.writes


def test_no_certificate_for_any_other_name(stand, tmp_path):
    result = run_ps(stand, tmp_path, ISSUE.format(name='www.sasmaz.digital'))
    assert result['ok'] is False and 'not an authorized name' in result['error']
    assert stand.writes == []


def test_hostname_confirmation_reports_each_layer(stand, tmp_path):
    run_ps(stand, tmp_path, sync(WEB, '3.70.1.1'))
    good = run_ps(stand, tmp_path, "Confirm-Hostname '{}' '3.70.1.1' @('ns1.example') 1".format(WEB))['value']
    assert good['authoritative'] is True and good['thisPcOk'] is True
    bad = run_ps(stand, tmp_path, "Confirm-Hostname '{}' '3.70.2.2' @('ns1.example') 1".format(WEB))['value']
    assert bad['authoritative'] is False and bad['thisPcOk'] is False and bad['thisPcAnswer'] == '3.70.1.1'
