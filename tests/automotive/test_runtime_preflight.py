"""Offline infrastructure regressions. Fixtures are never Android acceptance evidence."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).parent))
import runtime_preflight as runtime
import run_emulator as runner


class RuntimePreflightChecks(unittest.TestCase):
    def test_emulator_loader_preserves_actions_python_shared_library_path(self):
        with patch.dict(os.environ, {'LD_LIBRARY_PATH': '/fixture/actions-python/lib'}):
            env = runtime.loader_env(Path('/sdk/emulator'), Path('/sdk/emulator/lib64/gles_swiftshader/libEGL.so'))
        self.assertTrue(env['LD_LIBRARY_PATH'].endswith(':/fixture/actions-python/lib'))

    def test_missing_library_parser_collects_all_libraries(self):
        raw = ' libpulse.so.0 => not found\n libX11.so.6 => not found\n libpulse.so.0 => not found\n libc.so.6 => /lib/libc.so.6 (0x123)\n'
        self.assertEqual(runtime.missing_libraries(raw), ['libX11.so.6', 'libpulse.so.0'])

    def test_guest_bionic_is_never_passed_to_host_ldd(self):
        calls = []
        def execute(args, env):
            calls.append(args)
            return 0, ' (NEEDED) Shared library: [libc.so]\n (NEEDED) Shared library: [liblog.so]\n'
        with patch.object(runtime, 'command', side_effect=execute):
            result = runtime.inspect_elf(Path('/sdk/build-tools/35.0.0/renderscript/lib/packaged/x86_64/guest.so'), {})
        self.assertTrue(result['guest_bionic'])
        self.assertEqual([args[0] for args in calls], ['readelf'])

    def test_complete_dependency_errors_are_collected_before_emulator_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            for relative in ('emulator', 'cmdline-tools/22.0', 'platform-tools', 'build-tools/35.0.0'):
                (sdk / relative).mkdir(parents=True)
            commands = []
            def execute(args, *a, **kw):
                commands.append(args)
                return 0, ''
            def inspect(path, env):
                return {'path': str(path), 'missing': ['libpulse.so.0', 'libX11.so.6'], 'incompatible': [], 'inspection_error': None}
            def metadata(path):
                return {'Pkg.Revision': '37.2.12' if path.parent.name == 'emulator' else '37.0.1' if path.parent.name == 'platform-tools' else '22.0'}
            with patch.dict(os.environ, {'ANDROID_HOME': str(sdk), 'ANDROID_SDK_ROOT': str(sdk)}), \
                 patch.object(runtime.platform, 'freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}), \
                 patch.object(runtime.platform, 'machine', return_value='x86_64'), \
                 patch.object(runtime.shutil, 'which', return_value='/usr/bin/tool'), \
                 patch.object(runtime, 'elf_objects', side_effect=lambda root: [root / 'fixture']), \
                 patch.object(runtime, 'inspect_elf', side_effect=inspect), \
                 patch.object(runtime, 'properties', side_effect=metadata), \
                 patch.object(runtime, 'command', side_effect=execute):
                report = runtime.audit(sdk, 'sdk')
            self.assertEqual(len(report['objects']), 4)
            self.assertEqual(len(report['errors']), 4)
            self.assertTrue(all('libpulse.so.0' in error and 'libX11.so.6' in error for error in report['errors']))
            self.assertFalse(any('emulator' in str(arg) for args in commands for arg in args))

    def test_wrong_image_revision_is_rejected_before_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            image = sdk / runtime.POLICY['system_image'].replace(';', '/')
            image.mkdir(parents=True)
            (image / 'source.properties').write_text('Pkg.Revision=5\nAndroidVersion.ApiLevel=35\nAndroidVersion.ExtensionLevel=15\nSystemImage.Abi=x86_64\nSystemImage.TagId=android-automotive,google_apis\n')
            for name in ('kernel-ranchu', 'system.img', 'vendor.img', 'ramdisk.img', 'kernel_cmdline.txt'):
                (image / name).touch()
            (image / 'data').mkdir()
            errors, _ = runtime.image_errors(sdk)
            self.assertEqual(len(errors), 1)
            self.assertIn('expected 4, observed 5', errors[0])

    def test_command_spawn_and_timeout_are_reported_not_hidden(self):
        for error in [FileNotFoundError('fixture'), subprocess.TimeoutExpired('fixture', 1)]:
            with self.subTest(error=type(error).__name__), patch.object(runtime.subprocess, 'run', side_effect=error):
                code, detail = runtime.command(['fixture'])
                self.assertEqual(code, -1)
                self.assertTrue(detail)


class SingleLaunchChecks(unittest.TestCase):
    def test_readiness_requires_online_device_and_boot_completed(self):
        for replies, expected in [([(1, 'offline')], False), ([(0, 'device'), (0, '0')], False),
                                  ([(0, 'device'), (1, 'transient error')], False), ([(0, 'device'), (0, '1')], True)]:
            with self.subTest(replies=replies), patch.object(runner, 'command', side_effect=replies):
                self.assertIs(runner.boot_observed(Path('/sdk/adb')), expected)

    def test_premature_exit_does_not_retry_launch_or_run_harness(self):
        process = Mock()
        process.poll.return_value = 127
        process.returncode = 127
        with patch.object(runner, 'boot_observed') as observed:
            with self.assertRaisesRegex(RuntimeError, 'exited before boot'):
                runner.wait_boot(Path('/sdk/adb'), process)
            observed.assert_not_called()

    def test_boot_deadline_is_bounded(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(runner.time, 'monotonic', side_effect=[0, 0, 601]), \
             patch.object(runner.time, 'sleep'), patch.object(runner, 'boot_observed', return_value=False):
            with self.assertRaises(TimeoutError):
                runner.wait_boot(Path('/sdk/adb'), process)

    def test_sdk_failure_never_launches_emulator(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'ANDROID_HOME': '/sdk', 'ATTUNE_AAOS_EVIDENCE': directory}), \
                 patch.object(runner, 'audit', return_value={'errors': ['multiple missing libraries']}), \
                 patch.object(runner.subprocess, 'Popen') as launch:
                self.assertEqual(runner.run(), 69)
                launch.assert_not_called()

    def test_kvm_failure_blocks_before_avd_creation_or_emulator_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'ANDROID_HOME': '/sdk', 'ATTUNE_AAOS_EVIDENCE': directory}), \
                 patch.object(runner, 'audit', return_value={'errors': []}), \
                 patch.object(Path, 'is_char_device', return_value=False), \
                 patch.object(runner, 'free_port'), \
                 patch.object(runner, 'command', return_value=(1, 'KVM absent')), \
                 patch('shutil.disk_usage', return_value=Mock(free=10 * 1024**3)), \
                 patch.object(runner.subprocess, 'Popen') as launch, \
                 patch.object(runner.subprocess, 'run') as avd:
                self.assertEqual(runner.run(), 69)
                launch.assert_not_called()
                avd.assert_not_called()
                self.assertEqual(len(json.loads((Path(directory) / 'boot-blockers.json').read_text())), 2)

    def test_avd_configuration_preserves_image_but_removes_duplicate_resource_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.ini'
            path.write_text('image.sysdir.1=system-images/android-35-ext15/android-automotive/x86_64/\nhw.cpu.ncore=8\nhw.cpu.ncore=4\n')
            runner.configure_avd(path)
            text = path.read_text()
            self.assertEqual(text.count('hw.cpu.ncore='), 1)
            self.assertIn('hw.cpu.ncore=2', text)
            self.assertIn('image.sysdir.1=', text)


if __name__ == '__main__':
    unittest.main()
