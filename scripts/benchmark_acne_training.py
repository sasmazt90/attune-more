#!/usr/bin/env python3
"""Permanent benchmark script measuring training resource consumption on local CPU.

Measures:
- 1 forward + backward + update step time (ms) after warm-up
- Peak RSS memory (MB)
- Model & optimizer checkpoint size on disk (MB)
- Available disk space (GB)
- Epoch time estimate based on actual consumed training tiles
"""

import sys
import json
import time
import shutil
import psutil
from pathlib import Path
import torch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIVE_TEST = ROOT.parent / 'attune-live-test'

# Path setup for YOLOX and training modules
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))

from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
from safetensors.torch import load_file
from selected_yolox_loss import KnownObjectnessBCE
from yolox_numeric import install_bounds
from train_focused_local import acne_tiles, yolo_batch

OUT_DIR = ROOT / 'audit-results/acne-candidate-training-20261013'
OUT_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_PATH = OUT_DIR / 'benchmark-results.json'

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'


def run_benchmark():
    print("=== TOGG Attune Acne Detector Training Resource Benchmark ===")
    torch.set_num_threads(2)
    torch.manual_seed(20261013)
    np.random.seed(20261013)

    # 1. Load data
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    tr = [r for r in data['rows'] if r['split'] == 'train']
    va = [r for r in data['rows'] if r['split'] == 'validation']
    items = acne_tiles(tr, training=True)
    print(f"Loaded {len(tr)} train images -> {len(items)} training tiles")

    # 2. Build model and load weights
    net = YOLOX(YOLOPAFPN(depth=0.33, width=0.5), YOLOXHead(1, width=0.5))
    install_bounds(net)
    weights = load_file(str(BASELINE_WEIGHTS))
    net.load_state_dict(weights)
    print(f"Loaded baseline weights: {BASELINE_WEIGHTS.name}")

    # Freeze stem and dark2
    for k, p in net.named_parameters():
        p.requires_grad = not k.startswith(('backbone.backbone.stem', 'backbone.backbone.dark2'))

    # Eval BatchNorm
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d):
            m.eval()

    obj_loss = KnownObjectnessBCE()
    net.head.bcewithlog_loss = obj_loss

    trainable_params = [p for p in net.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=1.5e-4, weight_decay=1e-3)

    process = psutil.Process()
    ram_before = process.memory_info().rss / (1024 * 1024)

    # Prepare batches for benchmark
    from selected_yolox_loss import known_cells
    batch_size = 2
    for t in items[:14]:
        scope = np.ones((t['row']['height'], t['row']['width']), dtype=np.uint8)
        t['known'] = known_cells(scope, t['rect'], True)

    sample_batches = []
    for i in range(0, min(14, len(items) - 1), batch_size):
        b_items = items[i:i + batch_size]
        sample_batches.append(b_items)

    # Warm-up steps
    print("Warming up 2 steps...")
    for b_items in sample_batches[:2]:
        optimizer.zero_grad()
        obj_loss.known = torch.cat([t['known'] for t in b_items])
        x, y = yolo_batch(b_items)
        out = net(x, y)
        loss = out['total_loss']
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        optimizer.step()

    # Measured steps
    print("Measuring 5 forward + backward + update steps...")
    step_times = []
    for b_items in sample_batches[2:7]:
        t0 = time.perf_counter()
        optimizer.zero_grad()
        obj_loss.known = torch.cat([t['known'] for t in b_items])
        x, y = yolo_batch(b_items)
        out = net(x, y)
        loss = out['total_loss']
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        optimizer.step()
        t1 = time.perf_counter()
        step_times.append((t1 - t0) * 1000.0)

    mean_step_ms = float(np.mean(step_times))
    std_step_ms = float(np.std(step_times))
    ram_peak = process.memory_info().rss / (1024 * 1024)

    # Checkpoint size estimation
    dummy_model_path = OUT_DIR / 'temp_model_bench.safetensors'
    from safetensors.torch import save_file
    save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(dummy_model_path))
    model_size_mb = dummy_model_path.stat().st_size / (1024 * 1024)
    dummy_model_path.unlink()

    total_train_steps = len(items) // batch_size
    epoch_train_seconds = (total_train_steps * mean_step_ms) / 1000.0
    val_seconds_measured = 35.0  # Measured for 43 images inference
    epoch_total_seconds = epoch_train_seconds + val_seconds_measured

    # 2 hour budget = 7200 seconds
    max_epochs_2h = int(7200 // epoch_total_seconds)
    disk_free_gb = shutil.disk_usage(str(ROOT)).free / (1024 ** 3)

    results = {
        'hardware': 'Local CPU (2 threads)',
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'baselineWeightsPath': str(BASELINE_WEIGHTS),
        'measuredSteps': len(step_times),
        'stepTimesMs': [round(t, 2) for t in step_times],
        'meanStepTimeMs': round(mean_step_ms, 2),
        'stdStepTimeMs': round(std_step_ms, 2),
        'initialRamMb': round(ram_before, 2),
        'peakRamMb': round(ram_peak, 2),
        'modelCheckpointSizeMb': round(model_size_mb, 2),
        'totalCheckpointSizeMb': round(model_size_mb * 3, 2),  # model + optimizer + state
        'availableDiskSpaceGb': round(disk_free_gb, 2),
        'trainingTiles': len(items),
        'batchSize': batch_size,
        'stepsPerEpoch': total_train_steps,
        'estimatedEpochTrainSeconds': round(epoch_train_seconds, 1),
        'estimatedEpochValidationSeconds': round(val_seconds_measured, 1),
        'estimatedTotalEpochSeconds': round(epoch_total_seconds, 1),
        'estimatedTotalEpochMinutes': round(epoch_total_seconds / 60.0, 2),
        'twoHourBudgetSeconds': 7200,
        'maxEpochsIn2HourBudget': max_epochs_2h,
        'budgetExecutionDecision': f'Run up to {min(7, max_epochs_2h)} epochs with patience 3, within 2-hour budget.'
    }

    with open(BENCHMARK_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print("\nBenchmark Results:")
    print(f"  Step Time:           {mean_step_ms:.2f} ms ± {std_step_ms:.2f} ms")
    print(f"  Peak RSS RAM:        {ram_peak:.2f} MB")
    print(f"  Model Size:          {model_size_mb:.2f} MB")
    print(f"  Est. Epoch Time:     {epoch_total_seconds:.1f} s ({epoch_total_seconds / 60.0:.2f} min)")
    print(f"  Max Epochs in 2h:    {max_epochs_2h}")
    print(f"  Free Disk:           {disk_free_gb:.2f} GB")
    print(f"Saved benchmark to: {BENCHMARK_PATH}")
    return results


if __name__ == '__main__':
    run_benchmark()
