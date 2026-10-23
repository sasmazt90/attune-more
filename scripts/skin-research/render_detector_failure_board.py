"""Reproducible validation-only failure triage; publisher truth is not expert review."""
import argparse
import io
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw
import supervision as sv

from evaluate_detector_snapshot import CLASSES, match_events, point, read_snapshot


def render(archive, snapshots, validation, output):
    data, truth, predictions, receipts, identity, _ = read_snapshot(archive, snapshots, 'valid')
    if identity != validation['modelIdentity']: raise ValueError('MODEL_IDENTITY_MISMATCH')
    images = {row['id']: row for row in data['images']}
    board = Image.new('RGB', (1440, 1500), '#101827'); draw = ImageDraw.Draw(board)
    selections = []; used = set()
    with zipfile.ZipFile(archive) as z:
        for row_index, label in enumerate(CLASSES):
            threshold = validation['lockedThresholds'][label]
            candidates = []
            for image_id in images:
                if image_id in used: continue
                events, total = match_events({image_id: truth[image_id]}, {image_id: predictions[image_id]}, label)
                if total < 5: continue
                metrics = point(events, total, threshold)
                candidates.append((metrics['f1'], -total, image_id, metrics))
            _, _, image_id, metrics = min(candidates)
            used.add(image_id); im = images[image_id]
            photo = Image.open(io.BytesIO(z.read('valid/' + im['file_name']))).convert('RGB')
            gt = [r['bbox'] for r in truth[image_id] if r['class'] == label]
            ps = [r['bbox'] for r in predictions[image_id] if r['class'] == label and r['confidence'] >= threshold]
            panels = [('Source', photo), ('Publisher labels', photo), ('Predictions at validation threshold', photo)]
            for col, (title, panel) in enumerate(panels):
                panel = panel.copy()
                boxes = gt if col == 1 else ps if col == 2 else []
                if boxes:
                    xyxy = np.array([[x, y, x + w, y + h] for x, y, w, h in boxes], dtype=float)
                    detections = sv.Detections(xyxy=xyxy, class_id=np.zeros(len(boxes), dtype=int))
                    colour = '#38bdf8' if col == 1 else '#f97316'
                    panel = sv.BoxAnnotator(color=sv.Color.from_hex(colour), thickness=2).annotate(scene=panel, detections=detections)
                panel.thumbnail((472, 430))
                x = col * 480; y = row_index * 500
                board.paste(panel, (x, y + 55)); draw.text((x + 8, y + 8), title, fill='white')
            draw.text((8, row_index * 500 + 28), f"{label}: TP {metrics['tp']} / FP {metrics['fp']} / FN {metrics['fn']} at {threshold:.2f}", fill='white')
            selections.append(dict(label=label, imageId=image_id, filename=im['file_name'], metrics=metrics,
                                   selection='lowest per-image F1 among validation images with >=5 publisher instances; no repeated image'))
    output.parent.mkdir(parents=True, exist_ok=True)
    board.save(output)
    with Image.open(output) as check: check.load()
    return dict(modelIdentity=identity, split='valid', selections=selections,
                labelSemanticsExpertVerified=False, requiresVisualReview=True,
                drawingLibrary='supervision ' + sv.__version__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--snapshots', required=True, type=Path)
    parser.add_argument('--validation', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    result = render(args.archive, args.snapshots, json.loads(args.validation.read_text()), args.output)
    with args.receipt.open('x') as stream: json.dump(result, stream, indent=2)
    print(json.dumps(result))
