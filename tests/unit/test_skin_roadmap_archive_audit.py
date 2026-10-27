"""Real-file audit regressions; synthetic fixtures test tooling, not skin accuracy."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import sys

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/skin-research/audit_roadmap_archives.py'
spec = importlib.util.spec_from_file_location('archive_audit', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
sys.path.insert(0, str(SCRIPT.parent))
from verify_roadmap_filter import verify


def picture(fmt='PNG'):
    image = Image.new('RGB', (20, 20))
    image.putdata([(x * 9 % 256, y * 11 % 256, x * y % 256)
                   for y in range(20) for x in range(20)])
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


class ArchiveAuditTests(unittest.TestCase):
    def test_box_never_becomes_mask(self):
        result = audit.geometry({'bbox': [1, 1, 8, 8], 'segmentation': []}, 20, 20)
        self.assertTrue(result['validBox'])
        self.assertFalse(result['validMask'])
        rectangle = audit.geometry({'bbox': [1, 1, 8, 8],
                                    'segmentation': [[1, 1, 9, 1, 9, 9, 1, 9]]}, 20, 20)
        self.assertEqual(rectangle['kind'], 'rectangle-polygon')
        self.assertFalse(rectangle['validMask'])

    def test_real_polygon_and_bad_coordinates(self):
        annotation = {'bbox': [1, 1, 8, 8], 'segmentation': [[1, 1, 9, 2, 8, 9, 1, 8]]}
        self.assertTrue(audit.geometry(annotation, 20, 20)['validMask'])
        annotation['segmentation'][0][0] = -1
        self.assertFalse(audit.geometry(annotation, 20, 20)['validMask'])
        annotation['bbox'][0] = float('nan')
        self.assertFalse(audit.geometry(annotation, 20, 20)['validBox'])

    def test_self_crossing_not_repaired(self):
        # Nonzero shoelace area; testing area alone would incorrectly admit it.
        result = audit.geometry({'bbox': [0, 0, 20, 20],
                                 'segmentation': [[0, 0, 20, 20, 0, 20, 15, 0]]}, 20, 20)
        self.assertEqual(result['maskReason'], 'SELF_INTERSECTION')
        self.assertFalse(result['validMask'])

    def test_rle_is_explicitly_unsupported(self):
        result = audit.geometry({'bbox': [1, 1, 8, 8],
                                 'segmentation': {'size': [20, 20], 'counts': [1, 5, 394]}}, 20, 20)
        self.assertEqual(result['maskReason'], 'RLE_DECODER_REQUIRED')
        self.assertFalse(result['validMask'])

    def test_exact_pixel_duplicates_cross_splits_and_candidate_only(self):
        _, pixel, dhash = audit.fingerprints(picture())
        _, pixel2, _ = audit.fingerprints(picture('BMP'))
        self.assertEqual(pixel, pixel2)
        base = {'sha256': 'a', 'decodedSHA256': pixel, 'dhash': dhash}
        rows = [{**base, 'key': 'a', 'split': 'train'},
                {**base, 'sha256': 'b', 'key': 'b', 'split': 'test'},
                {**base, 'sha256': 'c', 'decodedSHA256': 'different', 'key': 'c', 'split': 'valid'}]
        exact, candidates = audit.duplicate_groups(rows)
        self.assertEqual(len(exact), 1)
        self.assertTrue(exact[0]['crossSplit'])
        self.assertEqual(set(exact[0]['members']), {'a', 'b'})
        self.assertEqual(len(candidates), 2)
        self.assertNotEqual(rows[0]['exactGroup'], rows[2]['exactGroup'])

    def test_zip_end_to_end_preserves_bytes_and_missing_labels_not_normal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.zip'
            annotation = {'images': [{'id': 1, 'file_name': 'x.png', 'width': 20, 'height': 20}],
                          'categories': [{'id': 2, 'name': 'dry'}], 'annotations': []}
            with zipfile.ZipFile(path, 'w') as archive:
                for split in ('train', 'test'):
                    archive.writestr(split + '/x.png', picture())
                    archive.writestr(split + '/_annotations.coco.json', json.dumps(annotation))
            before = path.read_bytes()
            result = audit.audit_sources({'fixture': path})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result['summary']['crossSplitExactGroups'], 1)
            self.assertFalse(result['acceptance']['lockedTestAccepted'])
            self.assertFalse(result['acceptance']['expertReviewed'])
            self.assertTrue(all(row['annotations'] == 0 for row in result['images']))
            self.assertEqual(result['archives'][0]['classes'], {})

    def test_dimension_mismatch_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.zip'
            data = {'images': [{'id': 1, 'file_name': 'x.png', 'width': 99, 'height': 20}],
                    'categories': [], 'annotations': []}
            def write(payload):
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('train/x.png', picture())
                    archive.writestr('train/_annotations.coco.json', json.dumps(payload))
            write(data)
            self.assertEqual(audit.audit_archive(path, 'fixture')['issues'][0]['reason'], 'DIMENSION_MISMATCH')
            data['images'].append(copy.deepcopy(data['images'][0]))
            write(data)
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_IMAGE_ID'):
                audit.audit_archive(path, 'fixture')

    def test_unsafe_paths(self):
        for name in ('../x.png', '/x.png', 'C:/x.png', 'train/../x.png', 'train\\x.png'):
            with self.assertRaisesRegex(ValueError, 'UNSAFE_ARCHIVE_MEMBER'):
                audit.safe_member(name)

    def test_filename_crop_hints_are_not_identity_groups(self):
        rows = [{'key': 'a', 'source': 'dc', 'split': 'train',
                 'path': 'train/a1b2c3d4-12345678_left_jpg.rf.aaa.jpg'},
                {'key': 'b', 'source': 'dc', 'split': 'test',
                 'path': 'test/f1f2f3f4-12345678_right_jpg.rf.bbb.jpg'},
                {'key': 'c', 'source': 'other', 'split': 'train',
                 'path': 'train/f1f2f3f4-12345678_right_jpg.rf.bbb.jpg'}]
        candidates = audit.filename_candidates(rows)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['members'], ['a', 'b'])
        self.assertTrue(candidates[0]['crossSplit'])
        self.assertFalse(candidates[0]['samePhotoConfirmed'])
        self.assertNotIn('exactGroup', rows[0])

    def test_filtered_import_keeps_boxes_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.zip', Path(directory) / 'target.zip'
            original = {'images': [{'id': 1, 'file_name': 'x.png', 'width': 20, 'height': 20}],
                        'categories': [{'id': 1, 'name': 'Pimple'}, {'id': 2, 'name': 'Mole'}],
                        'annotations': [{'id': 1, 'image_id': 1, 'category_id': 1, 'bbox': [1, 1, 2, 2]},
                                        {'id': 2, 'image_id': 1, 'category_id': 2, 'bbox': [4, 4, 2, 2]}]}
            filtered = copy.deepcopy(original)
            filtered['categories'] = filtered['categories'][:1]
            filtered['annotations'] = filtered['annotations'][:1]
            def write(path, data, image):
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('train/x.png', image)
                    archive.writestr('train/_annotations.coco.json', json.dumps(data))
            write(source, original, picture())
            write(target, filtered, picture())
            result = verify(source, target, {'Pimple'})
            self.assertEqual(result['removedConfounderAnnotations'], {'Mole': 1})
            filtered['annotations'][0]['bbox'][0] = 2
            write(target, filtered, picture())
            with self.assertRaisesRegex(ValueError, 'TARGET_ANNOTATIONS_CHANGED'):
                verify(source, target, {'Pimple'})
            write(target, filtered, picture('BMP'))
            with self.assertRaisesRegex(ValueError, 'IMAGE_BYTES_CHANGED'):
                verify(source, target, {'Pimple'})


if __name__ == '__main__':
    unittest.main()
