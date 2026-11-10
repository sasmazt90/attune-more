#!/usr/bin/env python3
"""Real-path timing of the normal-closing summary on the WEB host, cold and warm, with synthetic conversations.

Starts a separate API process from a branch checkout (port --port, loopback only) with the product API's own
environment, except for its port, a fresh random speech token and a CORS origin for an optional test frontend. The
product services are not touched. Then, over HTTP to that process:

  * POST /api/mental/analyze-session with spokenSummary=true, as the normal closing sends it: one real provider
    call returning summaryText (screen/history) and the short spokenSummary, validated by the server.
  * POST /api/mental/neural-speech with speakerProfile female-calm-v1: the same endpoint, verification and resident
    worker the closing uses, for the short line and for both parts of the written summary.

"cold" is the first female-calm-v1 request of a freshly started API process after its start-up warm-up (the official
model) has finished, as for the first closing after a service start. Each language gets two fresh processes: one whose
first request is the short line, one whose first request is the first long part. All later requests are warm.

Conversations are synthetic and non-personal. Outputs: realpath.json and one WAV per speech row (<label>.wav). No
secret or environment value is written or printed; only environment variable names are counted.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import signal
import subprocess
import time
import urllib.error
import urllib.request
import wave

# Synthetic, non-personal conversations (user turns are what the spoken line must be grounded in).
CONVERSATIONS = {
    'tr': [
        [('user', 'Son haftalarda işte tempo çok yoğun, akşamları kafamı boşaltamıyorum.'),
         ('assistant', 'Bu yoğunluk akşamlarınızı nasıl etkiliyor?'),
         ('user', 'Geç yatıyorum ve uykum sık sık bölünüyor. Kısa yürüyüşler biraz iyi geliyor.'),
         ('assistant', 'Yürüyüşlerin iyi geldiğini fark etmeniz değerli.'),
         ('user', 'Bu hafta en az iki akşam yürümeyi deneyeceğim.')],
        [('user', 'Yakında başka bir şehre taşınıyorum ve bu değişiklik beni yoruyor.'),
         ('assistant', 'Taşınmanın en çok hangi yanı sizi yoruyor?'),
         ('user', 'Yeni bir düzen kurmak ve arkadaşlarımdan uzaklaşmak beni kaygılandırıyor.'),
         ('assistant', 'Bu kaygıyı paylaşabildiğiniz biri var mı?'),
         ('user', 'Bir arkadaşımla telefonda konuşmak beni rahatlatıyor.')],
    ],
    'en': [
        [('user', 'Work has been very intense in recent weeks and I cannot switch off in the evenings.'),
         ('assistant', 'How does this pressure affect your evenings?'),
         ('user', 'I go to bed late and my sleep keeps getting interrupted. Short walks help a little.'),
         ('assistant', 'It is valuable that you noticed the walks help.'),
         ('user', 'This week I will try to walk on at least two evenings.')],
        [('user', 'I am moving to another city soon and the change is wearing me out.'),
         ('assistant', 'Which part of the move tires you most?'),
         ('user', 'Setting up a new routine and being far from my friends makes me anxious.'),
         ('assistant', 'Is there someone you can share this worry with?'),
         ('user', 'Talking with a friend on the phone calms me down.')],
    ],
    'de': [
        [('user', 'Bei der Arbeit ist das Tempo seit Wochen sehr hoch und abends kann ich nicht abschalten.'),
         ('assistant', 'Wie wirkt sich dieser Druck auf Ihre Abende aus?'),
         ('user', 'Ich gehe spät ins Bett und mein Schlaf wird oft unterbrochen. Kurze Spaziergänge helfen etwas.'),
         ('assistant', 'Es ist wertvoll, dass Sie bemerkt haben, dass die Spaziergänge helfen.'),
         ('user', 'Diese Woche versuche ich, an mindestens zwei Abenden spazieren zu gehen.')],
        [('user', 'Ich ziehe bald in eine andere Stadt und die Veränderung erschöpft mich.'),
         ('assistant', 'Welcher Teil des Umzugs ermüdet Sie am meisten?'),
         ('user', 'Eine neue Routine aufzubauen und weit weg von meinen Freunden zu sein, macht mich unruhig.'),
         ('assistant', 'Gibt es jemanden, mit dem Sie diese Sorge teilen können?'),
         ('user', 'Mit einer Freundin zu telefonieren beruhigt mich.')],
    ],
}
FIRST_PART_MIN_WORDS = 6


def speech_parts(text):
    """Port of speechParts() in mentalNeuralSpeech.ts."""
    sentences = [s for s in re.split(r'(?<=[.!?…])\s+|(?<=[.!?…]["\'”’)])\s+', text.strip()) if s]
    at, first = 1, sentences[0] if sentences else ''
    while at < len(sentences) and len(first.split()) < FIRST_PART_MIN_WORDS:
        first += ' ' + sentences[at]
        at += 1
    rest = ' '.join(sentences[at:])
    return [first, rest] if rest else [text]


def product_api_environment(port):
    """Environment of the running product API (attune-api@web) process, read in memory only."""
    for pid in filter(str.isdigit, os.listdir('/proc')):
        try:
            cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        if any(b'uvicorn' in c for c in cmd) and b'main:app' in cmd and b'--port' in cmd and cmd[cmd.index(b'--port') + 1] == str(port).encode():
            raw = Path(f'/proc/{pid}/environ').read_bytes()
            return dict(item.decode().split('=', 1) for item in raw.split(b'\0') if b'=' in item), int(pid)
    raise SystemExit('PRODUCT_API_PROCESS_NOT_FOUND')


def descendants(root):
    children = {}
    for pid in filter(str.isdigit, os.listdir('/proc')):
        try:
            ppid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        children.setdefault(ppid, []).append(int(pid))
    found, stack = [], [root]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def cpu_seconds(pids):
    total, tick = 0.0, os.sysconf('SC_CLK_TCK')
    for pid in pids:
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            total += (int(fields[11]) + int(fields[12])) / tick
        except (OSError, IndexError, ValueError):
            pass
    return total


class TestApi:
    def __init__(self, source, base_env, port, log, token=None):
        self.port, self.token = port, token or secrets.token_hex(32)
        user = pwd.getpwnam('attune')
        env = dict(base_env)
        env.update(PORT=str(port), ATTUNE_MENTAL_TTS_TOKEN=self.token, ATTUNE_LOAD_LOCAL_ENV='0',
                   ATTUNE_TRUSTED_ORIGINS='http://127.0.0.1:3190', HOME=user.pw_dir)

        def drop():
            os.setgid(user.pw_gid)
            os.initgroups('attune', user.pw_gid)
            os.setuid(user.pw_uid)
        self.started = time.time()
        self.proc = subprocess.Popen(['/opt/attune-venv/bin/uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port),
                                      '--workers', '1', '--no-access-log'], cwd=str(Path(source) / 'services/core-api'), env=env,
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, preexec_fn=drop,
                                     start_new_session=True)

    def wait_ready(self, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/api/vehicle/state', timeout=2) as r:
                    if r.status == 200:
                        return round(time.time() - self.started, 3)
            except (OSError, urllib.error.URLError):
                time.sleep(0.3)
        raise RuntimeError('TEST_API_NOT_READY')

    def wait_warm(self, timeout=240):
        """Start-up warm-up has finished when the resident worker exists and its CPU time stops growing."""
        deadline, last, quiet = time.time() + timeout, None, 0
        while time.time() < deadline:
            pids = descendants(self.proc.pid)
            now = cpu_seconds(pids)
            if pids and last is not None and now - last < 0.05:
                quiet += 1
                if quiet >= 6:
                    return {'seconds': round(time.time() - self.started, 3), 'workerCpuSeconds': round(now, 2)}
            else:
                quiet = 0
            last = now
            time.sleep(0.5)
        raise RuntimeError('TEST_API_NOT_WARM')

    def post(self, path, body, language, auth=False, timeout=180):
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}?language={language}', method='POST',
                                         data=json.dumps(body, ensure_ascii=False).encode(),
                                         headers={'Content-Type': 'application/json',
                                                  **({'Authorization': 'Bearer ' + self.token} if auth else {})})
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data, status, headers = response.read(), response.status, dict(response.headers)
        except urllib.error.HTTPError as error:
            data, status, headers = error.read(), error.code, dict(error.headers)
        return status, headers, data, round(time.perf_counter() - started, 3)

    def stop(self):
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait(10)
        except ProcessLookupError:
            pass
        return descendants(self.proc.pid)


def wav_seconds(raw):
    with wave.open(io.BytesIO(raw)) as w:
        return round(w.getnframes() / w.getframerate(), 6), w.getframerate(), w.getnchannels(), w.getsampwidth()


def words(text):
    return len(text.split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--port', type=int, default=8190)
    parser.add_argument('--product-port', type=int, default=8000)
    parser.add_argument('--languages', default='tr,en,de')
    parser.add_argument('--short-only', action='store_true', help='short spoken lines only (one process per language)')
    parser.add_argument('--third-conversation', action='store_true',
                        help='add a third conversation per language (the first different-topic conversation of spoken_summary_probe)')
    args = parser.parse_args()
    if args.third_conversation:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from spoken_summary_probe import DIVERSE
        for language, conversations in CONVERSATIONS.items():
            conversations.append(DIVERSE[language][0])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    base_env, product_pid = product_api_environment(args.product_port)
    run_id = 'closing-realpath:' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + ':' + secrets.token_hex(3)
    result = {'schema': 'attune-mental-closing-realpath-v1', 'runId': run_id, 'host': 'WEB (this host)', 'shortOnly': args.short_only,
              'scope': __doc__.strip().split('\n\n')[0], 'productApiPid': product_pid,
              'environmentVariableCount': len(base_env), 'cpus': os.cpu_count(), 'loadBefore': os.getloadavg(),
              'processes': [], 'analyses': [], 'tts': []}
    progress = out / 'progress.json'
    log = (out / 'test-api.log').open('ab')

    def save():
        (out / 'realpath.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', 'utf-8')
        progress.write_text(json.dumps({'at': time.time(), 'tts': len(result['tts']), 'analyses': len(result['analyses'])}))

    def speak(api, label, text, language, scenario_start, process_index):
        status, headers, data, seconds = api.post('/api/mental/neural-speech', {'text': text, 'language': language,
                                                  'speechConsent': True, 'speakerProfile': 'female-calm-v1'}, language, auth=True)
        row = {'label': label, 'language': language, 'profile': 'female-calm-v1', 'text': text,
               'textSha256': hashlib.sha256(text.encode()).hexdigest(), 'words': words(text), 'chars': len(text),
               'status': status, 'seconds': seconds, 'scenarioStart': scenario_start, 'process': process_index,
               'start': headers.get('X-TTS-Start') or headers.get('x-tts-start'),
               'serverSeconds': headers.get('X-TTS-Seconds') or headers.get('x-tts-seconds'),
               'serverTiming': headers.get('Server-Timing') or headers.get('server-timing'),
               'speakerHeader': headers.get('X-TTS-Speaker-Profile') or headers.get('x-tts-speaker-profile')}
        if status != 200:
            row['error'] = data[:200].decode(errors='replace')
        else:
            (out / (label + '.wav')).write_bytes(data)
            row['audioSeconds'], rate, channels, width = wav_seconds(data)
            row.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), sampleRate=rate, channels=channels, sampleWidth=width)
        result['tts'].append(row)
        save()
        return row

    index = 0
    try:
        for language in args.languages.split(','):
            for first in (('short',) if args.short_only else ('short', 'long')):
                index += 1
                api = TestApi(args.source, base_env, args.port, log)
                record = {'index': index, 'language': language, 'firstRequest': first, 'loadAtStart': os.getloadavg()}
                try:
                    record['readySeconds'] = api.wait_ready()
                    record['warm'] = api.wait_warm()
                    convs = []
                    if first == 'short':
                        for n, turns in enumerate(CONVERSATIONS[language], 1):
                            messages = [{'role': role, 'content': text} for role, text in turns]
                            status, _, data, seconds = api.post('/api/mental/analyze-session', {'messages': messages,
                                                                'cloudConsent': True, 'spokenSummary': True}, language)
                            row = {'conversation': f'{language}-c{n}', 'label': f'{language}-c{n}-analysis', 'language': language,
                                   'status': status, 'seconds': seconds}
                            body = json.loads(data) if data[:1] == b'{' else {}
                            if status == 200:
                                row.update(summaryText=body.get('summaryText'), spokenSummary=body.get('spokenSummary'),
                                           spokenSummaryStatus=body.get('spokenSummaryStatus'), providerType=body.get('providerType'),
                                           moodTrend=body.get('moodTrend'))
                                row['summaryWords'] = words(row['summaryText'] or '')
                                row['spokenWords'] = words(row['spokenSummary'] or '') if row['spokenSummary'] else None
                                row['longParts'] = speech_parts(row['summaryText'] or '')
                            else:
                                row['error'] = str(body.get('detail'))[:200]
                            result['analyses'].append(row)
                            convs.append(row)
                            save()
                        c1 = convs[0]
                        if c1.get('spokenSummary'):
                            speak(api, f'{language}-c1-short-cold', c1['spokenSummary'], language, 'cold', index)
                        for i, text in enumerate([] if args.short_only else (c1.get('longParts') or [])):
                            speak(api, f'{language}-c1-long{i}-warm', text, language, 'warm', index)
                        if c1.get('spokenSummary'):
                            speak(api, f'{language}-c1-short-warm', c1['spokenSummary'], language, 'warm', index)
                        for c in convs[1:]:
                            if c.get('spokenSummary'):
                                speak(api, f"{c['conversation']}-short-warm", c['spokenSummary'], language, 'warm', index)
                            for i, text in enumerate([] if args.short_only else (c.get('longParts') or [])):
                                speak(api, f"{c['conversation']}-long{i}-warm", text, language, 'warm', index)
                    else:
                        c1 = next(a for a in result['analyses'] if a['conversation'] == f'{language}-c1')
                        for i, text in enumerate(c1.get('longParts') or []):
                            speak(api, f'{language}-c1-long{i}-cold', text, language, 'cold', index)
                finally:
                    record['leftoverAfterStop'] = api.stop()
                    record['loadAtStop'] = os.getloadavg()
                    result['processes'].append(record)
                    save()
    finally:
        result['finishedAt'] = time.time()
        save()
        log.close()


if __name__ == '__main__':
    main()
