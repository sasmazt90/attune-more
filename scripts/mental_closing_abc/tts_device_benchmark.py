#!/usr/bin/env python3
"""Compare the same pinned TTS model on CPU and on a CUDA GPU with a fixed text list.

The product worker (``mental_neural_worker.synthesize``) does the synthesis in every mode; the device comes from the
configuration file (``"device": "cpu" | "cuda"``), everything else (model files, source revision, reference voice,
generation settings, watermark) is what that file and the voice profile pin. This tool only measures.

Modes
  bench     One process. Verification cost, then a cold first request (imports, model load, first inference), then
            warm requests: every text ``--warm-repeats`` times, texts interleaved per repeat, seed = first 32 bits of
            SHA-256("<text id>#<repeat>") so CPU and GPU get the same seeds (the devices' random streams differ, so
            the same seed does not give the same audio). Stage timers wrap the model's own steps:
            conditioning (reference voice), speech-token generation (T3), waveform decoding (S3Gen), watermark.
            On CUDA every timer synchronizes the device before it starts and before it stops.
            ``--plain-repeats N`` then repeats the first N seeds without stage timers (total only); the same seed on
            the same device should give the same bytes, which shows what the timers cost and that they change nothing.
  cold      One process, one request: imports, model load and first inference of a fresh process. Run it several
            times for several cold samples.
  service   The service path without the HTTP layer: per request the product's own ``verify_speaker`` (bundle
            re-hash) and then the product's resident worker as a subprocess over its stdin/stdout protocol, started
            with the product's worker environment. The official-default model is warmed first, as at service start.
            No seed, as in the live endpoint. ``--lines`` takes the lines to speak.
  profile   Diagnostic only, never mixed with timing rows: torch.profiler on one request.

Outputs in --out: results.json, results.csv, one WAV per synthesized row. Texts are synthetic and non-personal.
No environment value is written; the tool needs no network and no credential.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import wave


def sha(data):
    return hashlib.sha256(data).hexdigest()


def seed_for(text_id, repeat):
    return int.from_bytes(hashlib.sha256(f'{text_id}#{repeat}'.encode()).digest()[:4], 'big')


def rss_kib():
    with open('/proc/self/statm') as stream:
        return int(stream.read().split()[1]) * (os.sysconf('SC_PAGE_SIZE') // 1024)


def shell(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def wav_facts(raw):
    import numpy as np
    with wave.open(io.BytesIO(raw)) as w:
        params = (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype())
        frames = w.readframes(w.getnframes())
        count = w.getnframes()
    pcm = np.frombuffer(frames, dtype='<i2')
    loud = np.flatnonzero(np.abs(pcm) > 327)  # above 1 % of full scale
    return {'bytes': len(raw), 'sha256': sha(raw), 'pcmSha256': sha(frames), 'audioSeconds': round(count / params[2], 4),
            'format': {'channels': params[0], 'sampleWidth': params[1], 'rate': params[2], 'compression': params[3]},
            'formatOk': params == (1, 2, 24000, 'NONE') and len(frames) == count * 2,
            'peak': int(np.abs(pcm).max()) if count else 0, 'rms': round(float(np.sqrt(np.mean(pcm.astype('float64') ** 2))), 1) if count else 0.0,
            'clippedSamples': int((np.abs(pcm) >= 32767).sum()),
            'leadingSilenceSeconds': round(float(loud[0]) / params[2], 3) if len(loud) else None,
            'trailingSilenceSeconds': round(float(count - 1 - loud[-1]) / params[2], 3) if len(loud) else None}


def environment_facts(config, threads):
    facts = {'python': platform.python_version(), 'platform': platform.platform(), 'cpus': os.cpu_count(), 'threads': threads,
             'cpuModel': shell(['bash', '-c', "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2"]).strip(),
             'memTotalKiB': int(shell(['bash', '-c', "grep MemTotal /proc/meminfo | tr -s ' ' | cut -d' ' -f2"]) or 0),
             'device': config.get('device', 'cpu'), 'conditioning': config.get('conditioning'),
             'modelRevision': config['model'].get('revision'), 'sourceRevision': config['model'].get('sourceRevision'),
             'modelFileSha256': {k: v['sha256'] for k, v in config['model']['files'].items()},
             'referenceSha256': (config.get('referenceAudio') or {}).get('sha256')}
    from importlib.metadata import version
    facts['packages'] = {name: version(name) for name in ('torch', 'torchaudio', 'transformers', 'safetensors', 'chatterbox-tts', 'numpy')}
    try:
        facts['packages']['resemble-perth'] = version('resemble-perth')
    except Exception:  # noqa: BLE001 - optional fact
        pass
    return facts


def torch_facts(device):
    import torch
    facts = {'torch': torch.__version__, 'cudaBuild': torch.version.cuda, 'numThreads': torch.get_num_threads(),
             'float32MatmulPrecision': torch.get_float32_matmul_precision(),
             'tf32': {'matmul': torch.backends.cuda.matmul.allow_tf32, 'cudnn': torch.backends.cudnn.allow_tf32},
             'cudnnBenchmark': torch.backends.cudnn.benchmark, 'defaultDtype': str(torch.get_default_dtype())}
    if device == 'cuda':
        facts.update({'cudaAvailable': torch.cuda.is_available(), 'gpu': torch.cuda.get_device_name(0),
                      'cudnn': torch.backends.cudnn.version(),
                      'gpuMemoryTotalMiB': round(torch.cuda.get_device_properties(0).total_memory / 2 ** 20),
                      'nvidiaSmi': shell(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used', '--format=csv,noheader'])})
    return facts


class Stages:
    """Wall-clock per model step. On CUDA the device is synchronized at both ends of every step."""

    def __init__(self, model, device):
        import torch
        self.torch, self.device, self.row = torch, device, None
        self.install(model, 'prepare_conditionals', 'conditioningSeconds')
        self.install(model.t3, 'inference', 'speechTokenSeconds', tokens=True)
        self.install(model.s3gen, 'inference', 'waveformSeconds')
        self.install(model.watermarker, 'apply_watermark', 'watermarkSeconds')

    def sync(self):
        if self.device == 'cuda':
            self.torch.cuda.synchronize()

    def install(self, owner, name, key, tokens=False):
        original = getattr(owner, name)

        def timed(*args, **kwargs):
            if self.row is None:
                return original(*args, **kwargs)
            self.sync()
            started = time.perf_counter()
            result = original(*args, **kwargs)
            self.sync()
            self.row[key] = round(self.row.get(key, 0.0) + time.perf_counter() - started, 4)
            if tokens:
                self.row['speechTokens'] = int(result.shape[-1])
            return result

        setattr(owner, name, timed)


def load_product(source, config_path):
    sys.path.insert(0, str(Path(source) / 'services/core-api'))
    os.environ['ATTUNE_MENTAL_TTS_FEMALE_CONFIG'] = str(config_path)
    import mental_neural_worker
    from mental_audio_identity import verify_speaker
    from mental_neural_tts import load_configuration, validate_wave, verify_runtime_source
    return mental_neural_worker, verify_speaker, load_configuration, validate_wave, verify_runtime_source


def verification_rows(verify_speaker, load_configuration, verify_runtime_source, config_path, tag):
    rows = []
    for language in ('tr', 'en', 'de'):
        started = time.perf_counter()
        verify_speaker(language, 'female-calm-v1')
        rows.append({'what': 'verify_speaker (per request in the service: bundle re-hash + manifest + approval)', 'language': language,
                     'when': tag, 'seconds': round(time.perf_counter() - started, 3)})
    started = time.perf_counter()
    load_configuration(str(config_path), 'en', verify_models=False)
    rows.append({'what': 'load_configuration without model hashes (resident request)', 'when': tag, 'seconds': round(time.perf_counter() - started, 3)})
    started = time.perf_counter()
    facts = verify_runtime_source()
    rows.append({'what': 'verify_runtime_source (pinned upstream source files)', 'when': tag, 'seconds': round(time.perf_counter() - started, 3),
                 'filesVerified': facts['filesVerified']})
    return rows


def synthesize_row(worker, runtime, stages, item, repeat, config_path, out, kind, device, progress, seed=True, save=True):
    # torch is imported by the worker itself on the cold request, so that request pays for the import.
    torch = sys.modules.get('torch')
    row = {'id': item['id'], 'language': item['language'], 'textKind': item['kind'], 'run': kind, 'repeat': repeat, 'device': device,
           'textSha256': sha(item['text'].encode()), 'words': len(item['text'].split()), 'characters': len(item['text'])}
    payload = {'config': str(config_path), 'language': item['language'], 'text': item['text'], 'speakerProfile': 'female-calm-v1'}
    if seed:
        row['seed'] = payload['seed'] = seed_for(item['id'], repeat)
    if device == 'cuda' and torch is not None and torch.cuda.is_initialized():
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    row['loadAverageBefore'] = round(os.getloadavg()[0], 2)
    if stages is not None:
        stages.row = row
    started = time.perf_counter()
    try:
        raw = worker.synthesize(payload, runtime)
        import torch
        if device == 'cuda':
            torch.cuda.synchronize()
        row['totalSeconds'] = round(time.perf_counter() - started, 4)
    except Exception as error:  # noqa: BLE001 - the failure is the datum; no text or path is recorded
        row.update({'totalSeconds': round(time.perf_counter() - started, 4), 'error': type(error).__name__ + ':' + str(error)[:60]})
        return row
    finally:
        if stages is not None:
            stages.row = None
    row.update(wav_facts(raw))
    row['rtf'] = round(row['totalSeconds'] / row['audioSeconds'], 4) if row['audioSeconds'] else None
    staged = sum(row.get(k, 0.0) for k in ('conditioningSeconds', 'speechTokenSeconds', 'waveformSeconds', 'watermarkSeconds'))
    if stages is not None:
        row['otherSeconds'] = round(row['totalSeconds'] - staged, 4)
        if row.get('speechTokens'):
            row['secondsPerSpeechToken'] = round(row['speechTokenSeconds'] / row['speechTokens'], 5)
    try:
        row['workerPhases'] = json.loads(Path(progress).read_text('utf-8'))
    except (OSError, ValueError):
        row['workerPhases'] = []
    row['rssKiB'] = rss_kib()
    row['peakRssKiB'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if device == 'cuda':
        row['cudaAllocatedMiB'] = round(torch.cuda.memory_allocated() / 2 ** 20, 1)
        row['cudaPeakAllocatedMiB'] = round(torch.cuda.max_memory_allocated() / 2 ** 20, 1)
        row['cudaPeakReservedMiB'] = round(torch.cuda.max_memory_reserved() / 2 ** 20, 1)
    if save:
        name = f"{item['id']}-{kind}-r{repeat}.wav"
        (out / name).write_bytes(raw)
        row['wav'] = name
    return row


def summarize(rows):
    """Median/min/max per text kind and language for warm staged rows; n is always stated."""
    table = []
    warm = [r for r in rows if r['run'] == 'warm' and not r.get('error')]
    for kind in ('short', 'long'):
        for language in ('tr', 'en', 'de', 'all'):
            group = [r for r in warm if r['textKind'] == kind and language in (r['language'], 'all')]
            if not group:
                continue
            entry = {'textKind': kind, 'language': language, 'n': len(group), 'texts': len({r['id'] for r in group})}
            for key in ('totalSeconds', 'speechTokenSeconds', 'waveformSeconds', 'conditioningSeconds', 'watermarkSeconds', 'otherSeconds',
                        'audioSeconds', 'rtf', 'speechTokens', 'secondsPerSpeechToken'):
                values = [r[key] for r in group if r.get(key) is not None]
                if values:
                    entry[key] = {'median': round(statistics.median(values), 4), 'min': round(min(values), 4), 'max': round(max(values), 4)}
            table.append(entry)
    return table


def write(out, document):
    (out / 'results.json').write_text(json.dumps(document, ensure_ascii=False, indent=1) + '\n', 'utf-8')
    keys = ['id', 'language', 'textKind', 'run', 'repeat', 'device', 'seed', 'words', 'characters', 'totalSeconds', 'conditioningSeconds',
            'speechTokenSeconds', 'waveformSeconds', 'watermarkSeconds', 'otherSeconds', 'verifySeconds', 'workerSeconds', 'speechTokens',
            'secondsPerSpeechToken', 'audioSeconds', 'rtf', 'bytes', 'sha256', 'formatOk', 'peak', 'rms', 'clippedSamples', 'rssKiB',
            'peakRssKiB', 'cudaPeakAllocatedMiB', 'cudaPeakReservedMiB', 'loadAverageBefore', 'error', 'wav']
    with (out / 'results.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(document['rows'])


def run_bench(args, config, config_path, texts, out, document):
    worker, verify_speaker, load_configuration, _validate, verify_runtime_source = load_product(args.source, config_path)
    device = config.get('device', 'cpu')
    progress = Path(tempfile.mkdtemp(prefix='attune-bench-')) / 'progress.json'
    os.environ['ATTUNE_MENTAL_TTS_PROGRESS'] = str(progress)
    document['verification'] = verification_rows(verify_speaker, load_configuration, verify_runtime_source, config_path, 'process start')
    write(out, document)
    runtime, rows = {}, document['rows']
    first = texts[0]
    started = time.perf_counter()
    cold = synthesize_row(worker, runtime, None, first, 0, config_path, out, 'cold', device, progress)
    cold['processSecondsBeforeRequest'] = round(started - args.process_started, 3)
    rows.append(cold)
    document['torch'] = torch_facts(device)
    document['memoryAfterLoad'] = {'rssKiB': rss_kib(), **({'cudaAllocatedMiB': cold.get('cudaAllocatedMiB')} if device == 'cuda' else {})}
    write(out, document)
    print(json.dumps({k: cold.get(k) for k in ('id', 'run', 'totalSeconds', 'audioSeconds', 'error')}), flush=True)
    if args.mode == 'cold' or cold.get('error'):
        return
    stages = Stages(runtime['model'], device)
    deadline = time.time() + args.max_minutes * 60
    for repeat in range(args.warm_repeats):
        for item in texts:
            if item['kind'] == 'long' and repeat >= args.long_repeats:
                continue
            if time.time() > deadline:
                document['stoppedAtDeadline'] = {'repeat': repeat, 'id': item['id']}
                break
            row = synthesize_row(worker, runtime, stages, item, repeat, config_path, out, 'warm', device, progress,
                                 save=item['kind'] == 'short' or repeat < args.save_long_repeats)
            rows.append(row)
            document['summary'] = summarize(rows)
            write(out, document)
            print(json.dumps({k: row.get(k) for k in ('id', 'run', 'repeat', 'totalSeconds', 'speechTokenSeconds', 'waveformSeconds', 'audioSeconds', 'error')}), flush=True)
    stages.row = None
    for repeat in range(args.plain_repeats):
        for item in texts:
            if time.time() > deadline or (item['kind'] == 'long' and repeat >= args.long_repeats):
                continue
            row = synthesize_row(worker, runtime, None, item, repeat, config_path, out, 'warm-plain', device, progress, save=False)
            twin = next((r for r in rows if r['run'] == 'warm' and r['id'] == item['id'] and r['repeat'] == repeat), None)
            if twin and not row.get('error'):
                row['sameBytesAsStagedRow'] = twin.get('sha256') == row['sha256']
                row['stagedMinusPlainSeconds'] = round(twin['totalSeconds'] - row['totalSeconds'], 4)
            rows.append(row)
            write(out, document)
    document['verification'] += verification_rows(verify_speaker, load_configuration, verify_runtime_source, config_path, 'after the runs')
    document['summary'] = summarize(rows)
    write(out, document)


def run_profile(args, config, config_path, texts, out, document):
    import torch
    worker = load_product(args.source, config_path)[0]
    device = config.get('device', 'cpu')
    progress = Path(tempfile.mkdtemp(prefix='attune-bench-')) / 'progress.json'
    runtime = {}
    synthesize_row(worker, runtime, None, texts[0], 0, config_path, out, 'profile-warmup', device, progress, save=False)
    activities = [torch.profiler.ProfilerActivity.CPU] + ([torch.profiler.ProfilerActivity.CUDA] if device == 'cuda' else [])
    with torch.profiler.profile(activities=activities) as profiler:
        row = synthesize_row(worker, runtime, None, texts[0], 1, config_path, out, 'profile', device, progress, save=False)
    document['diagnosticOnly'] = 'torch.profiler adds overhead; these numbers are never used as timing samples'
    document['rows'].append(row)
    order = 'cuda_time_total' if device == 'cuda' else 'cpu_time_total'
    (out / 'profile.txt').write_text(profiler.key_averages().table(sort_by=order, row_limit=40), 'utf-8')
    write(out, document)


def run_service(args, config, config_path, lines, out, document):
    """verify_speaker + the product resident worker subprocess, in the order the service uses them."""
    _worker, verify_speaker, _load, validate_wave, _source = load_product(args.source, config_path)
    import mental_neural_tts
    os.environ['ATTUNE_MENTAL_TTS_THREADS'] = str(args.threads)
    environment = mental_neural_tts.worker_environment()
    document['workerEnvironment'] = {'variableCount': len(environment), 'secretLikeNames': sum(
        any(word in key.upper() for word in ('TOKEN', 'SECRET', 'API_KEY', 'PASSWORD')) for key in environment)}
    rows = document['rows']
    for process_index in range(args.processes):
        process = subprocess.Popen([sys.executable, str(mental_neural_tts.RESIDENT_WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=environment)

        def ask(job):
            started = time.perf_counter()
            process.stdin.write(json.dumps(job, ensure_ascii=False).encode() + b'\n')
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            return reply, round(time.perf_counter() - started, 4)

        reply, seconds = ask({'config': args.official_config, 'language': 'en', 'warm': True})
        rows.append({'id': 'official-default-warm-up', 'run': 'service-start', 'process': process_index, 'workerSeconds': seconds,
                     'error': 'worker' if reply.get('error') else None, 'workerPhases': reply.get('phases')})
        write(out, document)
        order = lines[process_index % len(lines):] + lines[:process_index % len(lines)]
        for repeat in range(args.warm_repeats + 1):
            for item in order:
                if repeat and item['language'] != order[0]['language'] and args.first_language_only_warm:
                    continue
                row = {'id': item['id'], 'language': item['language'], 'textKind': item['kind'], 'process': process_index, 'repeat': repeat,
                       'device': config.get('device', 'cpu'), 'textSha256': sha(item['text'].encode()), 'words': len(item['text'].split())}
                started = time.perf_counter()
                try:
                    verify_speaker(item['language'], 'female-calm-v1')
                    row['verifySeconds'] = round(time.perf_counter() - started, 4)
                    reply, row['workerSeconds'] = ask({'config': str(config_path), 'language': item['language'], 'text': item['text'],
                                                       'speakerProfile': 'female-calm-v1'})
                    if reply.get('error'):
                        raise RuntimeError('worker')
                    raw = validate_wave(base64.b64decode(reply['wav']))
                    row['totalSeconds'] = round(time.perf_counter() - started, 4)
                    row['run'] = 'service-' + reply['start']
                    row['workerPhases'] = reply.get('phases')
                    row.update(wav_facts(raw))
                    row['rtf'] = round(row['totalSeconds'] / row['audioSeconds'], 4)
                    name = f"{item['id']}-service-p{process_index}-r{repeat}.wav"
                    (out / name).write_bytes(raw)
                    row['wav'] = name
                except Exception as error:  # noqa: BLE001
                    row.update({'run': 'service-error', 'totalSeconds': round(time.perf_counter() - started, 4), 'error': type(error).__name__})
                rows.append(row)
                write(out, document)
                print(json.dumps({k: row.get(k) for k in ('id', 'run', 'process', 'repeat', 'verifySeconds', 'workerSeconds', 'totalSeconds', 'audioSeconds', 'error')}), flush=True)
        process.stdin.close()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
    if config.get('device') == 'cuda':
        document['nvidiaSmiAfter'] = shell(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader'])
    write(out, document)


def main():
    process_started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('bench', 'cold', 'service', 'profile'))
    parser.add_argument('--source', required=True, help='repository checkout')
    parser.add_argument('--config', required=True, help='female-calm-v1 configuration (its "device" selects cpu or cuda)')
    parser.add_argument('--official-config', help='official-default configuration (service mode warm-up)')
    parser.add_argument('--texts', help='fixed text list (JSON, see docs/mental-structured/closing-abc-v1/gpu-benchmark-texts.json)')
    parser.add_argument('--lines', help='service mode: JSON list of {id, language, kind, text}')
    parser.add_argument('--out', required=True)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--warm-repeats', type=int, default=5)
    parser.add_argument('--long-repeats', type=int, default=5)
    parser.add_argument('--save-long-repeats', type=int, default=2, help='keep WAVs of the first N repeats of long texts (hashes are kept for all)')
    parser.add_argument('--plain-repeats', type=int, default=0)
    parser.add_argument('--processes', type=int, default=1)
    parser.add_argument('--first-language-only-warm', action='store_true')
    parser.add_argument('--max-minutes', type=float, default=60)
    parser.add_argument('--first', help='id of the text used for the cold request (default: first in the list)')
    args = parser.parse_args()
    args.process_started = process_started
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    config_path = Path(args.config).resolve(strict=True)
    config = json.loads(config_path.read_text('utf-8'))
    os.environ['ATTUNE_MENTAL_TTS_THREADS'] = str(args.threads)
    os.environ.setdefault('OMP_NUM_THREADS', str(args.threads))
    os.environ.setdefault('MKL_NUM_THREADS', str(args.threads))
    os.environ.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1'})
    listing = json.loads(Path(args.lines or args.texts).read_text('utf-8'))
    texts = listing['texts'] if isinstance(listing, dict) else listing
    if args.first:
        texts = [t for t in texts if t['id'] == args.first] + [t for t in texts if t['id'] != args.first]
    document = {'schema': 'attune-mental-tts-device-benchmark-v1', 'mode': args.mode, 'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'textListSha256': sha(Path(args.lines or args.texts).read_bytes()),
                'settings': {'warmRepeats': args.warm_repeats, 'longRepeats': args.long_repeats, 'plainRepeats': args.plain_repeats,
                             'seedRule': 'first 32 bits of SHA-256("<text id>#<repeat>") in bench/cold; no seed in service mode',
                             'generation': json.loads((Path(args.source) / 'shared/mental/voices/female-calm-v1.json').read_text('utf-8'))['generation']},
                'environment': environment_facts(config, args.threads), 'rows': []}
    if args.mode in ('bench', 'cold'):
        run_bench(args, config, config_path, texts, out, document)
    elif args.mode == 'profile':
        run_profile(args, config, config_path, texts, out, document)
    else:
        run_service(args, config, config_path, texts, out, document)
    document['finishedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    write(out, document)


if __name__ == '__main__':
    main()
