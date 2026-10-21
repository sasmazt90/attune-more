#!/usr/bin/env python3
"""Compile and run the actual platform-independent Android policy classes on a host JDK."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / 'apps/automotive/app/src/main/java/more/attune/automotive'


def run_checks():
    if not shutil.which('java'):
        raise RuntimeError('JDK 17+ is required for the automotive host checks')
    # Some managed images ship the compiler module without a javac launcher.
    compiler = ['javac'] if shutil.which('javac') else ['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main']
    names = ['VehicleSnapshot', 'GatePolicy', 'OriginPolicy', 'MediaPermissionPolicy',
             'VehicleDataProvider', 'UnavailableVehicleProvider']
    with tempfile.TemporaryDirectory(prefix='attune-aaos-checks-') as directory:
        subprocess.run([*compiler, '-source', '17', '-target', '17', '-Xlint:-options', '-d', directory,
                        *(str(JAVA / (name + '.java')) for name in names),
                        str(ROOT / 'tests/automotive/ContractChecks.java'),
                        str(ROOT / 'tests/automotive/JavaSyntaxChecks.java')], check=True)
        policy = subprocess.run(['java', '-cp', directory, 'more.attune.automotive.ContractChecks'],
                                check=True, text=True, capture_output=True).stdout.strip()
        syntax = subprocess.run(['java', '-cp', directory, 'more.attune.automotive.JavaSyntaxChecks',
                                 *(str(path) for path in sorted(JAVA.glob('*.java')))],
                                check=True, text=True, capture_output=True).stdout.strip()
        return policy + '\n' + syntax


if __name__ == '__main__':
    print(run_checks())
