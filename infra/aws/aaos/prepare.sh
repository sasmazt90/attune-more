#!/usr/bin/env bash
# Host prerequisites: JDK21, official Android SDK cmdline tools, Xvfb, x11vnc,
# websockify, noVNC, ripgrep. Accept Android licenses as the operator, not silently here.
set -euo pipefail
: "${ANDROID_HOME:?}"
: "${ATTUNE_AVD:=AttuneAws15}"
: "${ATTUNE_ANDROID_LICENSES_ACCEPTED:?Set only after reviewing Android SDK/image licenses}"
[[ "$ATTUNE_ANDROID_LICENSES_ACCEPTED" == 1 ]]
image='system-images;android-35-ext15;android-automotive;x86_64'
# Preserve the exact official archives already verified/staged for this task.
# An unconditional sdkmanager invocation may upgrade a successfully installed package.
missing=()
for package in platform-tools emulator 'platforms;android-35' 'build-tools;35.0.0' "$image"; do
  package_dir="${package//;/\/}"
  [[ -f "$ANDROID_HOME/$package_dir/package.xml" ]] || missing+=("$package")
done
if (( ${#missing[@]} )); then sdkmanager "${missing[@]}"; fi
if ! avdmanager list avd -c | rg -x "$ATTUNE_AVD" >/dev/null; then
  printf 'no\n' | avdmanager create avd -n "$ATTUNE_AVD" -k "$image"
fi
# avdmanager's generic default is a 320x640 phone-shaped display. Configure
# the actual automotive surface; guest memory remains controlled by run.sh.
avd_root="${ANDROID_AVD_HOME:-$HOME/.android/avd}"
python3 - "$avd_root/$ATTUNE_AVD.avd/config.ini" <<'PY_CONFIG'
from pathlib import Path
import sys
path = Path(sys.argv[1])
values = {'hw.lcd.width': '1280', 'hw.lcd.height': '800',
          'hw.lcd.density': '160', 'hw.keyboard': 'yes', 'showDeviceFrame': 'no'}
lines = [line for line in path.read_text().splitlines()
         if line.split('=', 1)[0].strip() not in values]
path.write_text('\n'.join(lines + [f'{key}={value}' for key, value in values.items()]) + '\n')
PY_CONFIG
# The package may have Camera HAL disabled. Never claim -camera-back repairs it.
"$ANDROID_HOME/emulator/emulator" -accel-check
