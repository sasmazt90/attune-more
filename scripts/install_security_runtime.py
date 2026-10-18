"""Install pinned TOGG runtime wheels without changing shared Python packages."""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '.runtime/security-20261008'
subprocess.run([sys.executable, '-m', 'pip', 'install', '--only-binary=:all:',
 '--no-deps', '--upgrade', '--target', str(TARGET), '-r',
 str(ROOT / 'services/core-api/security-runtime.txt')], check=True)
env = {**os.environ, 'PYTHONPATH': str(TARGET) + os.pathsep + os.environ.get('PYTHONPATH', '')}
subprocess.run([sys.executable, '-c',
 "import fastapi,starlette,aiohttp,PIL,edge_tts,skimage; from importlib.metadata import requires,version; from packaging.requirements import Requirement; packages=('fastapi','starlette','aiohttp','pillow'); [print(p,version(p)) for p in packages]; [None if r.marker and not r.marker.evaluate() else (None if version(r.name) in r.specifier else (_ for _ in ()).throw(RuntimeError(str(r)))) for p in packages for r in map(Requirement,requires(p) or [])]"], env=env, check=True)
