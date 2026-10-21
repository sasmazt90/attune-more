"""One Drive metadata GET, no installs/downloads. Python stdlib + system OpenSSL.

One OAuth token POST is necessary first. Neither operation follows redirects or
retries. Credentials, tokens, IDs, metadata and free-text errors are never logged.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
FIELDS = 'name,size,trashed,capabilities(canDownload)'
SAFE_REASONS = frozenset({
    'accessNotConfigured', 'insufficientPermissions', 'insufficientFilePermissions',
    'notFound', 'forbidden', 'badRequest', 'invalid', 'invalidParameter', 'authError',
    'backendError', 'internalError', 'appNotAuthorizedToFile', 'domainPolicy', 'rateLimitExceeded',
    'userRateLimitExceeded', 'dailyLimitExceeded', 'downloadQuotaExceeded',
    'fileNotDownloadable', 'SERVICE_DISABLED', 'ACCESS_TOKEN_SCOPE_INSUFFICIENT',
    'IAM_PERMISSION_DENIED', 'BILLING_DISABLED', 'invalid_grant', 'invalid_client',
    'unauthorized_client', 'invalid_scope', 'invalid_request', 'access_denied',
    'temporarily_unavailable',
    'INVALID_ARGUMENT', 'UNAUTHENTICATED', 'PERMISSION_DENIED', 'NOT_FOUND',
    'RESOURCE_EXHAUSTED', 'INTERNAL', 'UNAVAILABLE',
})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def assertion(info, now):
    header = encode(b'{"alg":"RS256","typ":"JWT"}')
    claims = encode(json.dumps({'iss': info['client_email'], 'scope': SCOPE,
                               'aud': TOKEN_URL, 'iat': now, 'exp': now + 300}, separators=(',', ':')).encode())
    unsigned = (header + '.' + claims).encode('ascii')
    with tempfile.TemporaryDirectory(prefix='attune-drive-sign-') as directory:
        key = Path(directory) / 'key.pem'
        descriptor = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(info['private_key'])
        signed = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key)], input=unsigned,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=True)
    return header + '.' + claims + '.' + encode(signed.stdout)


def exchange(opener, request):
    try:
        response = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        # Only the token or small metadata/error envelope, never alt=media.
        raw = response.read(65537)
        return response.code, raw if len(raw) <= 65536 else b''


def reasons(raw):
    try:
        error = json.loads(raw).get('error', {})
        if isinstance(error, str):
            candidates = [error]
        else:
            candidates = [r.get('reason') for key in ('errors', 'details')
                          for r in error.get(key, []) if isinstance(r, dict)]
            candidates.append(error.get('status'))
        return sorted({v for v in candidates if isinstance(v, str) and v in SAFE_REASONS})
    except (ValueError, AttributeError, TypeError):
        return []


def diagnose(info, file_id, opener):
    report = {'status': 'BLOCKED', 'requestStage': 'configuration',
              'httpStatus': None, 'safeGoogleReasons': [], 'metadataAttempts': 0}
    try:
        if (info.get('type') != 'service_account' or info.get('token_uri') != TOKEN_URL
                or not isinstance(info.get('client_email'), str)
                or not info['client_email'].endswith('.iam.gserviceaccount.com')
                or not isinstance(info.get('private_key'), str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', file_id or '')):
            return report
        report['requestStage'] = 'oauth-token'
        jwt = assertion(info, int(time.time()))
        payload = urllib.parse.urlencode({'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                          'assertion': jwt}).encode()
        status, raw = exchange(opener, urllib.request.Request(TOKEN_URL, data=payload,
                               headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST'))
        report.update(httpStatus=status, safeGoogleReasons=reasons(raw))
        if status != 200:
            return report
        token = json.loads(raw)['access_token']
        if not isinstance(token, str) or not 0 < len(token) <= 8192 or not re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', token):
            report['safeGoogleReasons'] = ['INVALID_TOKEN_RESPONSE']
            return report
        report.update(requestStage='drive-metadata', httpStatus=None, safeGoogleReasons=[], metadataAttempts=1)
        url = 'https://www.googleapis.com/drive/v3/files/' + file_id + '?' + urllib.parse.urlencode({'fields': FIELDS})
        status, raw = exchange(opener, urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token}, method='GET'))
        report.update(httpStatus=status, safeGoogleReasons=reasons(raw), status='PASS' if status == 200 else 'BLOCKED')
    except Exception:
        # No raw exception, traceback, URL, credentials or provider message.
        report['safeGoogleReasons'] = ['LOCAL_OR_TRANSPORT_ERROR']
    return report


def main():
    try:
        info = json.loads(os.environ.get('ATTUNE_AAOS_DRIVE_SERVICE_ACCOUNT_JSON', ''))
        report = diagnose(info, os.environ.get('ATTUNE_AAOS_TTS_BUNDLE_FILE_ID', ''),
                          urllib.request.build_opener(NoRedirect()))
    except Exception:
        report = {'status': 'BLOCKED', 'requestStage': 'configuration', 'httpStatus': None,
                  'safeGoogleReasons': ['CONFIGURATION_UNAVAILABLE'], 'metadataAttempts': 0}
    safe = json.dumps(report, sort_keys=True)
    print(safe)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('### Private Drive metadata diagnostic\n\n```json\n' + safe + '\n```\n')
    return 0 if report['status'] == 'PASS' else 69


if __name__ == '__main__':
    raise SystemExit(main())
