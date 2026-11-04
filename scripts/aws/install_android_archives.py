#!/usr/bin/env python3
"""Install only the exact, previously verified official Android archives."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import urllib.request
from xml.dom import minidom
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install(manifest, sdk, cache):
    sdk.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    catalogs = {}
    for name, url in [('sdk', 'https://dl.google.com/android/repository/repository2-1.xml'),
                      ('aaos', 'https://dl.google.com/android/repository/sys-img/android-automotive/sys-img2-1.xml')]:
        with urllib.request.urlopen(url, timeout=60) as response:
            catalogs[name] = minidom.parseString(response.read())

    def download(row):
        path = cache / row['name']
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            temporary = path.with_suffix('.partial')
            with urllib.request.urlopen(row['url'], timeout=120) as response, temporary.open('wb') as sink:
                shutil.copyfileobj(response, sink, 1024 * 1024)
            if temporary.stat().st_size != row['bytes'] or digest(temporary) != row['sha256']:
                raise ValueError('ANDROID_ARCHIVE_INTEGRITY_MISMATCH')
            temporary.replace(path)
        return path

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(download, manifest))
    for row, archive in zip(manifest, archives):
        package = row['package']
        destination = sdk.joinpath(*package.split(';'))
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                relative = PurePosixPath(entry.filename)
                if relative.is_absolute() or '..' in relative.parts or '\\' in entry.filename:
                    raise ValueError('UNSAFE_ANDROID_ARCHIVE_PATH')
                # Official archives have one package root (e.g. emulator/ or x86_64/).
                target = destination.joinpath(*relative.parts[1:])
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError('ANDROID_ARCHIVE_SYMLINK_REQUIRES_REVIEW')
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as stream, target.open('wb') as sink:
                    shutil.copyfileobj(stream, sink, 1024 * 1024)
                target.chmod(0o755 if mode & 0o111 else 0o644)
        catalog = catalogs['aaos' if package.startswith('system-images;') else 'sdk']
        remote = next(p for p in catalog.getElementsByTagName('remotePackage')
                      if p.getAttribute('path') == package
                      and row['name'] in [n.firstChild.nodeValue for n in p.getElementsByTagName('url')])
        document = minidom.Document()
        root = document.createElement('attuneSdk:repository')
        # Match the catalog's common/01 schema. common/02 makes avdmanager
        # reject package.xml and misidentify the image from source.properties.
        root.setAttribute('xmlns:attuneSdk', 'http://schemas.android.com/repository/android/common/01')
        for name, value in catalog.documentElement.attributes.items():
            if name.startswith('xmlns'):
                root.setAttribute(name, value)
        document.appendChild(root)
        for license_node in catalog.getElementsByTagName('license'):
            root.appendChild(document.importNode(license_node, True))
        local = document.createElement('localPackage')
        local.setAttribute('path', package)
        local.setAttribute('obsolete', 'false')
        for child in remote.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName not in ('archives', 'channelRef'):
                local.appendChild(document.importNode(child, True))
        root.appendChild(local)
        (destination / 'package.xml').write_text(document.toxml(), encoding='utf-8')
    receipt = {'archives': manifest, 'sdkRoot': str(sdk), 'status': 'INSTALLED_HASH_VERIFIED',
               'licensesAccepted': False, 'emulatorBoot': 'NOT_RUN'}
    (cache / 'installation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'packagesInstalled': len(manifest), 'status': receipt['status']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    install(json.loads(args.manifest.read_text()), args.sdk, args.cache)
