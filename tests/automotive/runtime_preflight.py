"""Ubuntu host ABI/SDK checks; never boots a guest or reports Android acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads(Path(__file__).with_name('runtime_policy.json').read_text())


def command(args, env=None, timeout=30):
    try:
        result = subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout)
        return result.returncode, result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return -1, str(error)


def properties(path):
    if not path.is_file():
        return {}
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))


def missing_libraries(output):
    return sorted(set(re.findall(r'^\s*(\S+)\s+=>\s+not found', output, re.M)))


def elf_objects(root):
    for path in sorted(root.rglob('*')) if root.is_dir() else []:
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            header = stream.read(20)
        # Host ELF64 little-endian x86_64 only; never ldd Android/Bionic images.
        if header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == 62:
            yield path


def loader_env(emulator, path):
    # Same order observed in the official launcher's LD_DEBUG trace, plus the
    # selected backend's private directory for standalone plugin inspection.
    directories = [emulator / 'lib64/qt/lib', emulator / 'lib64/vulkan',
                   emulator / 'lib64/gles_swiftshader', emulator / 'lib64']
    if 'gles_llvmpipe' in path.parts:
        directories.insert(0, emulator / 'lib64/gles_llvmpipe')
    inherited = os.environ.get('LD_LIBRARY_PATH', '')
    return {**os.environ, 'LD_LIBRARY_PATH': ':'.join(map(str, directories)) + (':' + inherited if inherited else '')}


def inspect_elf(path, env):
    _, dynamic = command(['readelf', '-d', str(path)], env)
    needed = re.findall(r'Shared library: \[(.*?)\]', dynamic)
    # Android SDK includes x86_64 Bionic RenderScript payloads. They are guest
    # libraries, not Ubuntu dependencies, despite sharing the ELF machine ID.
    if 'renderscript' in path.parts and ('libc.so' in needed or 'libdl.so' in needed) and 'libc.so.6' not in needed:
        return {'path': str(path), 'guest_bionic': True, 'needed': needed,
                'missing': [], 'incompatible': [], 'inspection_error': None}
    code, linkage = command(['ldd', str(path)], env)
    missing = missing_libraries(linkage)
    incompatible = [line.strip() for line in linkage.splitlines() if 'version `' in line and 'not found' in line]
    # Static host tools are valid; arbitrary ldd errors must not look like PASS.
    error = code != 0 and not any(text in linkage for text in ('not a dynamic executable', 'statically linked'))
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'needed': needed,
            'missing': missing, 'incompatible': incompatible,
            'inspection_error': linkage[-2000:] if error else None}


def image_errors(sdk):
    image = sdk / POLICY['system_image'].replace(';', '/')
    meta = properties(image / 'source.properties')
    errors = []
    for key, expected in {'Pkg.Revision': POLICY['system_image_revision'], 'AndroidVersion.ApiLevel': '35',
                          'AndroidVersion.ExtensionLevel': '15', 'SystemImage.Abi': 'x86_64',
                          'SystemImage.TagId': 'android-automotive,google_apis'}.items():
        if meta.get(key) != expected:
            errors.append(f'System image {key}: expected {expected}, observed {meta.get(key)}')
    # This exact r4 archive seeds generated userdata from data/, not userdata.img.
    for name in ('kernel-ranchu', 'system.img', 'vendor.img', 'ramdisk.img', 'kernel_cmdline.txt'):
        if not (image / name).is_file():
            errors.append('Missing system image file: ' + name)
    if not (image / 'data').is_dir():
        errors.append('Missing system image userdata seed directory: data/')
    return errors, meta


def audit(sdk, stage, require_ubuntu=True):
    errors, objects, warnings, versions = [], [], [], {}
    report = {'scope': 'Linux host only; NOT Android acceptance', 'stage': stage,
              'errors': errors, 'objects': objects, 'warnings': warnings, 'versions': versions}
    os_release = platform.freedesktop_os_release()
    report['os'] = {k: os_release.get(k) for k in ('ID', 'VERSION_ID', 'PRETTY_NAME')}
    report['kernel'] = platform.release()
    report['glibc'] = platform.libc_ver()
    if require_ubuntu and (os_release.get('ID'), os_release.get('VERSION_ID'), platform.machine()) != ('ubuntu', '24.04', 'x86_64'):
        errors.append('Expected Ubuntu 24.04 x86_64; other hosts do not establish runner compatibility')
    for name in ('ldd', 'readelf'):
        if not shutil.which(name):
            errors.append('Missing inspection tool: ' + name)
    if os.environ.get('ANDROID_SDK_ROOT', str(sdk)) != str(sdk):
        errors.append('ANDROID_HOME and ANDROID_SDK_ROOT disagree')
    emulator = sdk / 'emulator'
    roots = [sdk / 'cmdline-tools/22.0', sdk / 'platform-tools', sdk / ('build-tools/' + POLICY['build_tools'])]
    if stage != 'build-only':
        roots.insert(0, emulator)
    for root in roots:
        if not root.is_dir():
            errors.append('Missing installed SDK directory: ' + str(root))
        for path in elf_objects(root):
            env = loader_env(emulator, path) if root == emulator else os.environ.copy()
            row = inspect_elf(path, env)
            objects.append(row)
            relative = str(path.relative_to(emulator)) if root == emulator else None
            optional = POLICY['optional_emulator_objects'].get(relative)
            if root == roots[-1]:
                optional = POLICY['optional_build_tool_objects'].get(str(path.relative_to(root)))
            problems = row['missing'] or row['incompatible'] or row['inspection_error']
            if optional:
                row['optional'] = optional
                if problems:
                    warnings.append({'path': str(path), 'reason': row['optional'], 'missing': row['missing']})
            elif problems:
                errors.append(f"{path}: missing={row['missing']}, incompatible={row['incompatible']}, inspection={row['inspection_error']}")
    if list((ROOT / 'apps/automotive').rglob('*.rs')):
        errors.append('RenderScript sources require a separate audited toolchain; legacy SDK compiler cannot be ignored')
    # Explicitly test system dlopen targets without using emulator bundled libs
    # to accidentally satisfy host package requirements.
    if stage != 'build-only':
        for package, libraries in POLICY['packages'].items():
            for library in libraries:
                code, detail = command([sys.executable, '-c', 'import ctypes,os,sys;ctypes.CDLL(sys.argv[1],mode=os.RTLD_NOW)', library])
                if code:
                    errors.append(f'{library} ({package}): {detail[-700:]}')
        for key, path, expected in [('emulator', emulator / 'source.properties', POLICY['emulator']),
                                    ('adb', sdk / 'platform-tools/source.properties', POLICY['adb'])]:
            actual = properties(path).get('Pkg.Revision')
            versions[key] = actual
            if actual != expected:
                errors.append(f'Unaudited {key} version: expected {expected}, observed {actual}; re-audit before boot')
    versions['cmdline_tools'] = properties(sdk / 'cmdline-tools/22.0/source.properties').get('Pkg.Revision')
    if versions['cmdline_tools'] != POLICY['cmdline_tools']:
        errors.append('Audited command-line tools 22.0 are required')
    # Do not execute emulator until the COMPLETE dependency list is available.
    if not errors:
        probes = [('adb', [str(sdk / 'platform-tools/adb'), 'version']),
                  ('sdkmanager', [str(sdk / 'cmdline-tools/22.0/bin/sdkmanager'), '--version']),
                  ('java', ['java', '-version'])]
        if stage != 'build-only':
            probes += [('emulator_normal', [str(emulator / 'emulator'), '-version']),
                       ('emulator_headless', [str(emulator / 'emulator'), '-no-window', '-version'])]
        for name, args in probes:
            code, text = command(args)
            versions[name + '_output'] = text[:2500]
            if code:
                errors.append(f'{name} startup exit={code}: {text[-1000:]}')
        if stage != 'build-only' and f"build_id {POLICY['emulator_build']}" not in versions.get('emulator_headless_output', ''):
            errors.append('Emulator build ID differs from the audited build')
        if stage != 'build-only':
            report['renderer_loads'] = []
            for relative in ('lib64/gles_swiftshader/libEGL.so', 'lib64/gles_swiftshader/libGLESv2.so',
                             'lib64/vulkan/libvulkan.so', 'lib64/vulkan/libvk_swiftshader.so'):
                path = emulator / relative
                code, text = command([sys.executable, '-c', 'import ctypes,os,sys;ctypes.CDLL(sys.argv[1],mode=os.RTLD_NOW)', str(path)],
                                     env=loader_env(emulator, path))
                report['renderer_loads'].append({'path': relative, 'exit': code, 'detail': text[-1000:]})
                if code:
                    errors.append(f'Renderer dynamic load failed: {relative}: {text[-1000:]}')
    if stage == 'image':
        bad, report['image'] = image_errors(sdk)
        errors.extend(bad)
    if stage == 'tools':
        for name, args, expected in [('python', [sys.executable, '--version'], 'Python ' + POLICY['python']),
                                     ('node', ['node', '--version'], 'v' + POLICY['node'])]:
            code, text = command(args)
            versions[name] = text.strip()
            if code or text.strip() != expected:
                errors.append(f'{name}: expected {expected}, observed {text.strip()}')
        code, text = command(['java', '-version'])
        if code or not re.search(r'version "' + POLICY['java_major'] + r'\.', text):
            errors.append('Java 21 JDK is required: ' + text[:500])
        try:
            import importlib.metadata
            actual = importlib.metadata.version('playwright')
            versions['playwright'] = actual
            if actual != POLICY['playwright']:
                errors.append('Unaudited Playwright version: ' + actual)
        except importlib.metadata.PackageNotFoundError:
            errors.append('Playwright is not installed')
        extra = [Path(sys.executable).resolve(), Path(shutil.which('node') or '/missing-node')]
        if os.getenv('JAVA_HOME'):
            java = Path(os.environ['JAVA_HOME'])
            extra += [java / 'bin/java', java / 'lib/server/libjvm.so', java / 'lib/libjli.so',
                      java / 'lib/libjava.so', java / 'lib/libnet.so', java / 'lib/libnio.so', java / 'lib/libzip.so']
        for path in extra:
            if not path.is_file():
                errors.append('Tool binary absent: ' + str(path))
                continue
            env = os.environ.copy()
            if os.getenv('JAVA_HOME') and path.is_relative_to(Path(os.environ['JAVA_HOME'])):
                java = Path(os.environ['JAVA_HOME'])
                env['LD_LIBRARY_PATH'] = ':'.join(str(java / name) for name in ('lib/server', 'lib', 'lib/jli')) + ':' + env.get('LD_LIBRARY_PATH', '')
            row = inspect_elf(path, env)
            objects.append(row)
            if row['missing'] or row['incompatible'] or row['inspection_error']:
                errors.append(f'Tool dependency: {path}: {row}')
        native_roots = [Path(sysconfig.get_path('platlib')),
                        Path(sys.base_prefix) / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/lib-dynload']
        for root in native_roots:
            for path in elf_objects(root):
                env = os.environ.copy()
                # Wheel private dependencies are resolved within that wheel;
                # never combine every package's .libs into a global search path.
                if path.parent.name.endswith('.libs'):
                    env['LD_LIBRARY_PATH'] = str(path.parent) + ':' + env.get('LD_LIBRARY_PATH', '')
                row = inspect_elf(path, env)
                objects.append(row)
                problems = row['missing'] or row['incompatible'] or row['inspection_error']
                if path.name.startswith('_tkinter.'):
                    row['optional'] = 'Tk desktop GUI is not used by the backend or Android observer'
                    if problems:
                        warnings.append({'path': str(path), 'reason': row['optional'], 'missing': row['missing']})
                elif problems:
                    errors.append(f'Python native dependency: {path}: {row}')
        code, text = command([sys.executable, '-c',
            'import ssl,ctypes,sqlite3,lzma,bz2,zlib,fastapi,uvicorn,numpy,cv2,scipy,skimage,onnxruntime,PIL;print("PASS real native Python imports; no capture, model inference or API calls")'])
        versions['native_imports'] = text[-1500:]
        if code:
            errors.append('Native Python imports failed: ' + text[-1500:])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['sdk', 'build-only', 'tools', 'image'], default='sdk')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sdk = Path(os.environ.get('ANDROID_HOME', '/missing-android-sdk'))
    report = audit(sdk, args.stage)
    output = args.output or Path(os.environ.get('ATTUNE_AAOS_EVIDENCE', '/tmp/attune-aaos-evidence')) / ('runtime-' + args.stage + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    for error in report['errors']:
        print('BLOCKED:', error)
    for warning in report['warnings']:
        print('OPTIONAL:', warning['path'], warning['missing'], warning['reason'])
    guest = sum(bool(row.get('guest_bionic')) for row in report['objects'])
    print(f"{'BLOCKED' if report['errors'] else 'PASS'}: {len(report['objects']) - guest} host ELF objects, {guest} guest payloads excluded from host ldd; {len(report['errors'])} errors; evidence={output}")
    return 69 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
