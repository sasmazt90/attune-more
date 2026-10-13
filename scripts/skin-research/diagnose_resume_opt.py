import sys
from pathlib import Path
import torch
import random
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model, load_baseline_weights_to_p2_model
from focal_objectness_loss import SigmoidFocalObjectnessLoss
from negative_mask_builder import build_hole_preserved_negative_masks, acne_tiles_p2, known_cells_p2
from train_focused_local import yolo_batch
from train_p2_focal_trial import save_transactional_checkpoint
import tempfile
import json
from safetensors.torch import load_file

BASELINE_WEIGHTS = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
DATA_PATH = ROOT / 'audit-results/acne-candidate-training-20261013/train-data-engineering-reviewed-20261013.json'

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
tr_rows = [r for r in data['rows'] if r['split'] == 'train']
masks, weights = build_hole_preserved_negative_masks(tr_rows[:10], pseudo_manifest_path=DATA_PATH)
all_tiles = acne_tiles_p2(tr_rows[:10], masks, training=True)
for t in all_tiles:
    sha = t['row']['sha256']
    t['source_mask'] = masks[sha]
    t['source_weights'] = weights[sha]

test_tiles = all_tiles[:6]

# Run A
torch.manual_seed(42); np.random.seed(42); random.seed(42)
net_a = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
load_baseline_weights_to_p2_model(net_a, BASELINE_WEIGHTS)
fl_a = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
net_a.head.obj_focal_loss = fl_a
trainable_a = [p for p in net_a.parameters() if p.requires_grad]
opt_a = torch.optim.AdamW(trainable_a, lr=1e-5)
sched_a = torch.optim.lr_scheduler.CosineAnnealingLR(opt_a, T_max=10)

order = list(range(len(test_tiles)))
random.shuffle(order)

# Step 1 & 2
for step in range(2):
    b_idx = order[step*2 : (step+1)*2]
    batch_items = [test_tiles[i] for i in b_idx]
    x, y = yolo_batch(batch_items)
    kt = torch.cat([known_cells_p2(it['source_mask'], it['source_weights'], it['rect'])[0] for it in batch_items], 0)
    wt = torch.cat([known_cells_p2(it['source_mask'], it['source_weights'], it['rect'])[1] for it in batch_items], 0)
    fl_a.known = kt; fl_a.boundary_weights = wt
    opt_a.zero_grad()
    loss = net_a(x, y)['total_loss']
    loss.backward()
    opt_a.step()
    sched_a.step()

# Save checkpoint
tmp_dir = Path(tempfile.mkdtemp())
state = {'step': 2, 'epoch': 1, 'cursor': 4, 'shuffleOrder': order, 'bestScore': 0.0, 'bestCheckpoint': None}
ckpt_dir = save_transactional_checkpoint(tmp_dir, net_a, opt_a, sched_a, state)

# Run Step 3 in Run A
b_idx = order[4:6]
batch_items = [test_tiles[i] for i in b_idx]
x, y = yolo_batch(batch_items)
kt = torch.cat([known_cells_p2(it['source_mask'], it['source_weights'], it['rect'])[0] for it in batch_items], 0)
wt = torch.cat([known_cells_p2(it['source_mask'], it['source_weights'], it['rect'])[1] for it in batch_items], 0)
fl_a.known = kt; fl_a.boundary_weights = wt
opt_a.zero_grad()
loss_a_3 = net_a(x, y)['total_loss']
loss_a_3.backward()
opt_a.step()
sched_a.step()

# Now Run B (Resumed from checkpoint)
net_b = build_yolox_p2_model(num_classes=1, depth=0.33, width=0.5)
fl_b = SigmoidFocalObjectnessLoss(alpha=0.25, gamma=2.0)
net_b.head.obj_focal_loss = fl_b
trainable_b = [p for p in net_b.parameters() if p.requires_grad]
opt_b = torch.optim.AdamW(trainable_b, lr=1e-5)
sched_b = torch.optim.lr_scheduler.CosineAnnealingLR(opt_b, T_max=10)

net_b.load_state_dict(load_file(str(ckpt_dir / 'model.safetensors')))
with open(ckpt_dir / 'state.json', 'r') as f:
    st = json.load(f)

# What if we use torch.save / torch.load for optimizer?
torch_opt_path = ckpt_dir / 'optimizer.pt'
torch.save(opt_a.state_dict(), str(torch_opt_path)) # just test if torch.save preserves 100%
opt_b.load_state_dict(torch.load(str(torch_opt_path)))

# Check if opt_b state dict matches opt_a state dict
print("Testing optimizer state restoration...")
print("Step 3 comparison...")
b_idx = order[4:6]
batch_items = [test_tiles[i] for i in b_idx]
x, y = yolo_batch(batch_items)
kt = torch.cat([known_cells_p2(it['source_mask'], it['source_weights'], it['rect'])[0] for it in batch_items], 0)
wt = torch.cat([known_cells_p2(it['source_mask'], it['source_weights'], it['rect'])[1] for it in batch_items], 0)
fl_b.known = kt; fl_b.boundary_weights = wt
opt_b.zero_grad()
loss_b_3 = net_b(x, y)['total_loss']
loss_b_3.backward()
opt_b.step()
sched_b.step()

print(f"Loss A 3: {loss_a_3.item():.8f}")
print(f"Loss B 3: {loss_b_3.item():.8f}")
print(f"Diff 3: {abs(loss_a_3.item() - loss_b_3.item()):.2e}")

# Check model weight diff
diff = max((net_a.state_dict()[k].float() - net_b.state_dict()[k].float()).abs().max().item() for k in net_a.state_dict())
print(f"Weight diff after step 3: {diff:.2e}")
