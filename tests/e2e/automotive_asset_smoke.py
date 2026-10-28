"""Local HTTP integrity, WASM compilation and audio decode in desktop Chrome.

No capture, inference, playback, speech provider or Android capability is tested.
Requires the same isolated frontend as automotive_web_smoke.py.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'apps/vehicle-app/public'


def asset_rows():
    models = json.loads((PUBLIC / 'mediapipe/manifest.json').read_text())
    guidance = json.loads((PUBLIC / 'audio/guidance/manifest.json').read_text())
    originals = json.loads((PUBLIC / 'audio/user-approved/tr-en-de-20261020-v1/manifest.json').read_text())
    return [
        *[{'url': '/mediapipe/' + entry['path'], 'sha256': entry['sha256'],
           'kind': 'wasm' if entry['path'].endswith('.wasm') else 'model-or-loader'} for entry in models['files']],
        *[{'url': entry['url'], 'sha256': entry['sha256'], 'kind': 'audio'}
          for entry in [*guidance['entries'].values(), *originals['recordings']]],
    ]


def run():
    out = Path(os.environ.get('ATTUNE_AAOS_EVIDENCE', '/tmp/attune-aaos-web-smoke'))
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        executable = os.environ.get('ATTUNE_CHROME_EXECUTABLE')
        browser = pw.chromium.launch(executable_path=executable, channel=None if executable else 'chrome',
                                     headless=True, args=['--mute-audio', '--no-sandbox'])
        try:
            context = browser.new_context()
            def local_only(route):
                uri = urlsplit(route.request.url)
                if uri.hostname in ('localhost', '127.0.0.1') and uri.port in (3000, 8000):
                    route.continue_()
                else:
                    route.abort('blockedbyclient')
            context.route('**/*', local_only)
            page = context.new_page()
            page.goto('http://localhost:3000', wait_until='domcontentloaded')
            rows = page.evaluate("""async assets => {
                const rows = [], audio = new AudioContext();
                try {
                    for (const asset of assets) {
                        const row = {...asset, status: 'FAIL', runtime: 'desktop-chrome'};
                        try {
                            const response = await fetch(asset.url);
                            row.httpStatus = response.status;
                            if (!response.ok) throw Error('Asset HTTP ' + response.status);
                            const bytes = await response.arrayBuffer();
                            row.bytes = bytes.byteLength;
                            row.actualSha256 = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
                                .map(n => n.toString(16).padStart(2, '0')).join('');
                            if (row.actualSha256 !== asset.sha256) throw Error('Manifest hash mismatch');
                            if (asset.kind === 'wasm') { await WebAssembly.compile(bytes); row.compiled = true; }
                            if (asset.kind === 'audio') {
                                const decoded = await audio.decodeAudioData(bytes);
                                if (!(decoded.duration > 0)) throw Error('Empty audio');
                                row.decodedDuration = decoded.duration;
                            }
                            row.status = 'PASS';
                        } catch (error) { row.error = String(error); }
                        rows.push(row);
                    }
                } finally { await audio.close(); }
                return rows;
            }""", asset_rows())
            (out / 'browser-assets.json').write_text(json.dumps(rows, indent=2) + '\n')
            assert rows and all(row['status'] == 'PASS' for row in rows), [row for row in rows if row['status'] != 'PASS']
            print(f'PASS {len(rows)} HTTP/hash/WASM/audio-decode checks in desktop Chrome; no Android/media acceptance')
        finally:
            browser.close()


if __name__ == '__main__':
    run()
