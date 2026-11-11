"""Probe control flow with explicit fake torch/worker modules; NEVER neural or timing evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / 'scripts/qa/realistic/mental_resident_probe.py'

FAKE_TORCH = '''
import json, time
from pathlib import Path
from types import SimpleNamespace as NS
LOG = Path(__file__).with_name('torch-calls.jsonl')
state = {'pending': 0.0}
def record(name):
    with LOG.open('a') as stream: stream.write(json.dumps(name) + '\\n')
def synchronize():
    # Simulates queued GPU work that only a synchronisation waits for.
    time.sleep(state['pending']); state['pending'] = 0.0; record('synchronize')
__version__ = '2.6.0+fixture'
version = NS(cuda='12.4-fixture')
backends = NS(cuda=NS(matmul=NS(allow_tf32=True)), cudnn=NS(allow_tf32=True, version=lambda: 90100))
cuda = NS(synchronize=synchronize, reset_peak_memory_stats=lambda: record('reset-peak'),
          max_memory_allocated=lambda: 3 * 2**30, max_memory_reserved=lambda: 4 * 2**30,
          get_device_name=lambda index: 'Fixture GPU', get_device_capability=lambda index: (8, 6))
get_float32_matmul_precision = lambda: 'highest'
'''

FAKE_WORKER = '''
import io, json, wave
from pathlib import Path
from types import SimpleNamespace as NS
import torch
class Tokens:
    shape = (1, 51)
def synthesize(payload, runtime):
    device = json.loads(Path(payload['config']).read_text())['device']
    def decode():
        torch.state['pending'] = 0.05 if device == 'cuda' else 0.0
    model = runtime.setdefault('model', NS(device=device, t3=NS(inference=lambda: Tokens()),
        s3gen=NS(inference=decode), watermarker=NS(apply_watermark=lambda: None), prepare_conditionals=lambda: None))
    with Path(payload['config']).with_name('calls.jsonl').open('a') as stream:
        stream.write(json.dumps({k: payload[k] for k in ('language', 'text', 'seed')}) + '\\n')
    model.t3.inference(); model.s3gen.inference(); model.watermarker.apply_watermark()
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000); audio.writeframes(b'\\x00\\x00' * 240)
    return output.getvalue()
'''


class ResidentProbeTests(unittest.TestCase):
    def run_probe(self, device, *extra):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'torch.py').write_text(FAKE_TORCH)
        (root / 'mental_neural_worker.py').write_text(FAKE_WORKER)
        (root / 'mental_neural_tts.py').write_text('def worker_progress(path): return []\n')
        (root / 'config.json').write_text(json.dumps({'device': device}))
        process = subprocess.run([sys.executable, str(PROBE), '--source', str(root), '--config', str(root / 'config.json'),
                                  '--out', str(root / 'results'), '--repetitions', '2', *extra],
                                 capture_output=True, text=True, timeout=60)
        results = root / 'results/results.json'
        runtime = root / 'results/runtime.json'
        log = root / 'torch-calls.jsonl'
        return (process, json.loads(results.read_text()) if results.exists() else None,
                json.loads(runtime.read_text()) if runtime.exists() else None,
                [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else [],
                [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
                if (root / 'calls.jsonl').exists() else [])

    def test_cpu_probe_keeps_inputs_and_records_strict_fp32(self):
        process, results, runtime, torch_calls, calls = self.run_probe('cpu')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(results['rows']), 13)  # One warm-up + 12 segments.
        self.assertEqual(calls[0], {'language': 'en', 'text': 'Hello.', 'seed': 42})
        self.assertEqual([(c['language'], c['seed']) for c in calls[1:3]], [('en', 42), ('en', 42)])
        self.assertEqual(torch_calls, [])  # No CUDA calls on CPU.
        self.assertEqual(runtime['precision'], {'matmulTF32': False, 'cudnnTF32': False, 'float32MatmulPrecision': 'highest'})
        self.assertIsNone(runtime['gpu'])
        row = results['rows'][1]
        self.assertEqual((row['device'], row['speechTokensIncludingStop'], row['gpuMemory']), ('cpu', 51, None))
        self.assertEqual(set(row['subphasesSeconds']), {'speechTokens', 'waveDecoder', 'watermark'})

    def test_cuda_spans_wait_for_queued_work_and_record_gpu_memory(self):
        process, results, runtime, torch_calls, _ = self.run_probe('cuda')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual((runtime['gpu'], runtime['gpuCapability'], runtime['cudnn']), ('Fixture GPU', [8, 6], 90100))
        self.assertFalse(runtime['precision']['matmulTF32'] or runtime['precision']['cudnnTF32'])
        for row in results['rows'][1:]:
            # The decoder returned instantly; only synchronisation reveals the queued 50 ms.
            self.assertGreaterEqual(row['subphasesSeconds']['waveDecoder'], 0.045)
            self.assertEqual(row['gpuMemory'], {'peakAllocatedMiB': 3072.0, 'peakReservedMiB': 4096.0})
        self.assertEqual(torch_calls.count('reset-peak'), 13)
        # Each measured row: total start/end plus start/end of three timed spans.
        self.assertEqual(torch_calls.count('synchronize'), 2 + 12 * 8)

    def test_reverse_order_measures_the_same_inputs(self):
        _, forward, _, _, forward_calls = self.run_probe('cpu')
        process, reverse, _, _, reverse_calls = self.run_probe('cpu', '--order', 'reverse')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(reverse['order'], 'reverse')
        self.assertEqual(reverse_calls[0], forward_calls[0])
        self.assertEqual(reverse_calls[1:], list(reversed(forward_calls[1:])))
        self.assertEqual([row['label'] for row in reverse['rows'][1:]],
                         [row['label'] for row in reversed(forward['rows'][1:])])

    def test_seed_start_and_invalid_arguments(self):
        process, results, _, _, calls = self.run_probe('cpu', '--seed-start', '50')
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(sorted({c['seed'] for c in calls[1:]}), [50, 51])
        process, _, _, _, calls = self.run_probe('mps')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('UNSUPPORTED_PROBE_DEVICE', process.stderr)
        self.assertEqual(calls, [])  # Refused before any synthesis.
        process = subprocess.run([sys.executable, str(PROBE), '--config', 'unused', '--out', 'unused', '--repetitions', '0'],
                                 capture_output=True, text=True, timeout=60)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('--repetitions must be positive', process.stderr)

    def test_loaded_model_device_must_match_configuration(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'torch.py').write_text(FAKE_TORCH)
        (root / 'mental_neural_worker.py').write_text(FAKE_WORKER.replace(
            "device = json.loads(Path(payload['config']).read_text())['device']", "device = 'cpu'"))
        (root / 'mental_neural_tts.py').write_text('def worker_progress(path): return []\n')
        (root / 'config.json').write_text(json.dumps({'device': 'cuda'}))
        process = subprocess.run([sys.executable, str(PROBE), '--source', str(root), '--config', str(root / 'config.json'),
                                  '--out', str(root / 'results')], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('PROBE_DEVICE_MISMATCH', process.stderr)
        self.assertEqual(len(json.loads((root / 'results/results.json').read_text())['rows']), 1)


if __name__ == '__main__':
    unittest.main()
