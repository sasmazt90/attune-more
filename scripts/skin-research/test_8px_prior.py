#!/usr/bin/env python3
"""Test initial IoU with reg_bias = log(2.0) (8px initial box at stride 4)."""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

import math
import torch
from yolox.models.yolo_head import bboxes_iou

def main():
    print("Testing initial IoU with 8px prior box at stride 4...")
    # Prior box at (192, 192) with w=8, h=8
    prior_box = torch.tensor([[192.0, 192.0, 8.0, 8.0]])

    test_sizes = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
    for s in test_sizes:
        gt_box = torch.tensor([[192.0, 192.0, s, s]])
        iou = bboxes_iou(gt_box, prior_box, False)
        print(f"  GT {s:4.1f} px vs 8px prior box -> IoU: {iou.item():.4f}")

if __name__ == '__main__':
    main()
