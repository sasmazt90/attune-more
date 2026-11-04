import hashlib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('restore_onnx', Path(__file__).parents[2] / 'scripts/aws/restore_onnx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def backup(tmp_path):
    parts = tmp_path / 'parts'
    parts.mkdir()
    rows = []
    for i, data in enumerate([b'first', b'second', b'third', b'fourth', b'step0']):
        name = f'skin-type-local-v1-model.onnx.part-{i:03d}' if i < 4 else 'step0-with-features-stable-silu.onnx'
        (parts / name).write_bytes(data)
        rows.append({'name': name, 'fileSizeBytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    combined = b'firstsecondthirdfourth'
    return parts, {'parts': list(reversed(rows)), 'combinedSkinType': {
        'bytes': len(combined), 'sha256': hashlib.sha256(combined).hexdigest(),
        'destination': 'skin/model.onnx'}, 'step0Destination': 'acne/step0.onnx'}


def test_numeric_order_and_idempotent_restore(tmp_path):
    parts, manifest = backup(tmp_path)
    out = tmp_path / 'out'
    module.restore(parts, out, manifest)
    module.restore(parts, out, manifest)
    assert (out / 'skin/model.onnx').read_bytes() == b'firstsecondthirdfourth'
    assert (out / 'acne/step0.onnx').read_bytes() == b'step0'


@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'combined', 'escape', 'existing'])
def test_fail_closed_without_publishing(tmp_path, failure):
    parts, manifest = backup(tmp_path)
    out = tmp_path / 'out'
    part = parts / 'skin-type-local-v1-model.onnx.part-001'
    if failure == 'missing':
        part.unlink()
    elif failure == 'corrupt':
        part.write_bytes(b'bad')
    elif failure == 'combined':
        manifest['combinedSkinType']['sha256'] = '0' * 64
    elif failure == 'escape':
        manifest['combinedSkinType']['destination'] = '../outside.onnx'
    else:
        (out / 'skin').mkdir(parents=True)
        (out / 'skin/model.onnx').write_bytes(b'existing')
    with pytest.raises(ValueError):
        module.restore(parts, out, manifest)
    assert not (out / 'acne/step0.onnx').exists()
    if failure == 'existing':
        assert (out / 'skin/model.onnx').read_bytes() == b'existing'
    else:
        assert not (out / 'skin/model.onnx').exists()
