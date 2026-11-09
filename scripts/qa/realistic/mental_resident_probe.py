"""Equivalent synthetic speech probes; no provider calls, altered weights or saved user data.

The device comes from the verified configuration (``cpu`` or ``cuda``); the probe never edits it.
CUDA work is asynchronous, so on CUDA every timed span is bracketed by ``torch.cuda.synchronize()``.
TF32 is disabled before the model loads, keeping the comparison strictly FP32 on both devices.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import wave

p = argparse.ArgumentParser()
p.add_argument('--source', default='/opt/attune/services/core-api')
p.add_argument('--config', required=True)
p.add_argument('--out', required=True)
p.add_argument('--repetitions', type=int, default=2)
p.add_argument('--seed-start', type=int, default=42)
p.add_argument('--order', choices=('forward', 'reverse'), default='forward')
args = p.parse_args()
if args.repetitions < 1:
    p.error('--repetitions must be positive')
out = Path(args.out)
out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, args.source)
import torch
from mental_neural_worker import synthesize
from mental_neural_tts import worker_progress

# Strict FP32: Ampere and newer GPUs otherwise run cuDNN convolutions in TF32 by default.
torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False

texts = {
    'en': ['That sounds like a difficult day for you.', 'What would feel most useful to discuss right now?'],
    'de': ['Das klingt nach einem schwierigen Tag für Sie.', 'Was wäre für Sie jetzt besonders hilfreich zu besprechen?'],
    'tr': ['Bugün sizin için zor bir gün olmuş gibi görünüyor.', 'Şu anda konuşmak size hangi konuda yardımcı olur?'],
}
progress = out / 'worker-progress.json'
os.environ['ATTUNE_MENTAL_TTS_PROGRESS'] = str(progress)
runtime = {}
rows = []
subphases = {}
counts = {}
# The worker reads the same field; the loaded model's device is checked after warm-up.
device = {'type': json.loads(Path(args.config).read_text('utf-8')).get('device', 'cpu')}
if device['type'] not in ('cpu', 'cuda'):
    raise SystemExit('UNSUPPORTED_PROBE_DEVICE')


def synchronize():
    if device['type'] == 'cuda':
        torch.cuda.synchronize()


def timed(owner, name, label):
    original = getattr(owner, name)
    def call(*a, **kw):
        synchronize()
        start = time.perf_counter()
        try:
            result = original(*a, **kw)
            synchronize()
        finally:
            subphases[label] = subphases.get(label, 0) + time.perf_counter() - start
        if label == 'speechTokens' and hasattr(result, 'shape'):
            counts['speechTokensIncludingStop'] = int(result.shape[-1])
        return result
    setattr(owner, name, call)


def host_load():
    try:
        return [float(value) for value in Path('/proc/loadavg').read_text().split()[:3]]
    except (OSError, ValueError):
        return None


def gpu_memory():
    if device['type'] != 'cuda':
        return None
    return {'peakAllocatedMiB': round(torch.cuda.max_memory_allocated() / 2**20, 1),
            'peakReservedMiB': round(torch.cuda.max_memory_reserved() / 2**20, 1)}


def say(language, text, label, seed):
    subphases.clear()
    counts.clear()
    if device['type'] == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    load_before = host_load()
    cpu_before = os.times()
    synchronize()
    start = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        audio = synthesize({'config': args.config, 'language': language, 'text': text, 'seed': seed}, runtime)
    synchronize()
    elapsed = time.perf_counter() - start
    cpu_after = os.times()
    with wave.open(io.BytesIO(audio)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    (out / (label + '.wav')).write_bytes(audio)
    row = {'label': label, 'index': len(rows), 'language': language, 'seed': seed, 'device': device['type'],
           'textSha256': hashlib.sha256(text.encode()).hexdigest(),
           'seconds': elapsed, 'audioSeconds': duration, 'realTimeFactor': elapsed / duration,
           'audioSha256': hashlib.sha256(audio).hexdigest(), 'phases': worker_progress(progress),
           'subphasesSeconds': dict(subphases), **counts,
           'processCpuSeconds': round((cpu_after.user + cpu_after.system) - (cpu_before.user + cpu_before.system), 3),
           'hostLoadBefore': load_before, 'hostLoadAfter': host_load(), 'gpuMemory': gpu_memory(),
           'peakRSSKiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    rows.append(row)
    (out / 'results.json').write_text(json.dumps({
        'scope': 'Same pinned worker, synthetic text, numerical wrappers only; no subjective acceptance',
        'device': device['type'], 'order': args.order, 'seedStart': args.seed_start,
        'threads': os.environ.get('ATTUNE_MENTAL_TTS_THREADS'), 'rows': rows}, indent=2) + '\n')
    print(json.dumps({k: row[k] for k in ('label', 'seconds', 'audioSeconds', 'subphasesSeconds')}), flush=True)


def nvidia_smi():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def cpu_model():
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or None


say('en', 'Hello.', 'warmup', args.seed_start)
model = runtime['model']
if str(model.device).split(':')[0] != device['type']:
    raise SystemExit('PROBE_DEVICE_MISMATCH')
fingerprint = {
    'device': device['type'], 'python': sys.version.split()[0], 'torch': torch.__version__,
    'cudaRuntime': getattr(torch.version, 'cuda', None),
    'cudnn': torch.backends.cudnn.version() if device['type'] == 'cuda' else None,
    'gpu': torch.cuda.get_device_name(0) if device['type'] == 'cuda' else None,
    'gpuCapability': list(torch.cuda.get_device_capability(0)) if device['type'] == 'cuda' else None,
    'nvidiaSmi': nvidia_smi() if device['type'] == 'cuda' else None,
    'precision': {'matmulTF32': torch.backends.cuda.matmul.allow_tf32, 'cudnnTF32': torch.backends.cudnn.allow_tf32,
                  'float32MatmulPrecision': torch.get_float32_matmul_precision()},
    'cpuModel': cpu_model(), 'logicalCpus': os.cpu_count(),
    'threadsSetting': os.environ.get('ATTUNE_MENTAL_TTS_THREADS'),
    'reuseConditioning': os.environ.get('ATTUNE_MENTAL_TTS_REUSE_CONDITIONING') == '1',
}
(out / 'runtime.json').write_text(json.dumps(fingerprint, indent=2) + '\n')
timed(model.t3, 'inference', 'speechTokens')
timed(model.s3gen, 'inference', 'waveDecoder')
timed(model.watermarker, 'apply_watermark', 'watermark')
timed(model, 'prepare_conditionals', 'conditioning')
plan = [(language, text, language + '-' + str(repeat) + '-' + str(part), args.seed_start + repeat)
        for repeat in range(args.repetitions) for language, parts in texts.items() for part, text in enumerate(parts)]
for language, text, label, seed in (reversed(plan) if args.order == 'reverse' else plan):
    say(language, text, label, seed)
