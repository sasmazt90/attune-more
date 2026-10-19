"""Automotive policy behavior and parked-only distribution/security boundaries."""
from pathlib import Path
import importlib.util
import shutil
import xml.etree.ElementTree as ET
import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'apps/automotive/app'
ANDROID = '{http://schemas.android.com/apk/res/android}'


def test_actual_automotive_policy_classes_on_host_jvm():
    if not shutil.which('java'):
        pytest.skip('JDK unavailable; Android host checks need JDK 17+')
    spec = importlib.util.spec_from_file_location('automotive_checks', ROOT / 'tests/automotive/run_checks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.run_checks().startswith('PASS ')


def test_manifest_requires_aaos_but_does_not_require_camera_or_microphone():
    manifest = ET.parse(APP / 'src/main/AndroidManifest.xml').getroot()
    features = {element.get(ANDROID + 'name'): element.get(ANDROID + 'required')
                for element in manifest.findall('uses-feature')}
    assert features['android.hardware.type.automotive'] == 'true'
    assert features['android.hardware.camera.any'] == 'false'
    assert features['android.hardware.microphone'] == 'false'
    assert not any(e.get(ANDROID + 'name') == 'distractionOptimized'
                   for e in manifest.iter('meta-data'))
    assert not any('CAR_SPEED' in e.get(ANDROID + 'name', '') or 'CAR_POWERTRAIN' in e.get(ANDROID + 'name', '')
                   for e in manifest.findall('uses-permission'))
    assert manifest.find('application').get(ANDROID + 'allowBackup') == 'false'
    # android.car is a boot-classpath API, not a PM-registered shared library
    # on the pinned AAOS 35-ext15 image. Compilation still uses the SDK stubs.
    for path in (APP / 'src/main/AndroidManifest.xml',
                 ROOT / 'tests/automotive/emulator-probe/src/main/AndroidManifest.xml'):
        assert not any(e.get(ANDROID + 'name') == 'android.car'
                       for e in ET.parse(path).getroot().iter('uses-library'))
    rules = ET.parse(APP / 'src/main/res/xml/data_extraction_rules.xml').getroot()
    for mode in ('cloud-backup', 'device-transfer'):
        assert {e.get('domain') for e in rules.find(mode).findall('exclude')} == {
            'root', 'file', 'database', 'sharedpref', 'external'}
        assert all(e.get('path') == '.' for e in rules.find(mode).findall('exclude'))


def test_cleartext_is_limited_to_debug_loopback():
    production = ET.parse(APP / 'src/main/res/xml/network_security_config.xml').getroot()
    debug = ET.parse(APP / 'src/debug/res/xml/network_security_config.xml').getroot()
    assert production.find('base-config').get('cleartextTrafficPermitted') == 'false'
    assert not production.findall('domain-config')
    assert debug.find('base-config').get('cleartextTrafficPermitted') == 'false'
    assert {e.text for e in debug.iter('domain')} == {'localhost', '127.0.0.1'}
    assert all(e.get('includeSubdomains') == 'false' for e in debug.iter('domain'))
