#!/usr/bin/env python3
"""Prompt on the approved WEB host; never echo or log a provider credential."""
import getpass
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import stat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace', action='store_true',
                        help='Atomically replace an existing root-owned provider file.')
    args = parser.parse_args()
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise SystemExit('Run as root in an interactive SSM terminal on the WEB host.')
    subprocess.run([sys.executable, str(Path(__file__).with_name('host_identity.py')),
                    '--role', 'web'], check=True)
    root = Path('/etc/attune')
    root.mkdir(mode=0o750, exist_ok=True)
    target = root / 'provider.env'
    if target.is_symlink():
        raise SystemExit('Refusing a symbolic link at provider.env.')
    if target.exists():
        info = target.stat()
        if not args.replace:
            raise SystemExit('provider.env already exists; use --replace for intentional replacement.')
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0:
            raise SystemExit('Refusing to replace a nonregular or non-root-owned provider file.')
    key = getpass.getpass('OpenAI API key (hidden input): ').strip()
    if not key or any(c.isspace() or ord(c) < 32 for c in key):
        raise SystemExit('A nonempty single-line credential is required.')
    if key.count('sk-') > 1:
        raise SystemExit('Repeated key prefix detected. Nothing was saved; paste the key once.')
    fd, name = tempfile.mkstemp(prefix='.provider-', dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write('OPENAI_API_KEY=' + json.dumps(key) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        # Refuse an unexpected concurrently created file, including a symlink.
        if args.replace:
            os.replace(name, target)
        else:
            os.link(name, target)
    finally:
        Path(name).unlink(missing_ok=True)
    print('Provider credential saved in root-owned mode 0600. No value was logged.')


if __name__ == '__main__':
    main()
