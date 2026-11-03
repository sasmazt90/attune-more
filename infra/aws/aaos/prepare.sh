#!/usr/bin/env bash
# Host prerequisites: JDK21, official Android SDK cmdline tools, Xvfb, x11vnc,
# websockify, noVNC, ripgrep. Accept Android licenses as the operator, not silently here.
set -euo pipefail
: "${ANDROID_HOME:?}"
: "${ATTUNE_AVD:=AttuneAws15}"
: "${ATTUNE_ANDROID_LICENSES_ACCEPTED:?Set only after reviewing Android SDK/image licenses}"
[[ "$ATTUNE_ANDROID_LICENSES_ACCEPTED" == 1 ]]
image='system-images;android-35-ext15;android-automotive;x86_64'
sdkmanager 'platform-tools' 'emulator' 'platforms;android-35' 'build-tools;35.0.0' "$image"
if ! avdmanager list avd -c | rg -x "$ATTUNE_AVD" >/dev/null; then
  printf 'no\n' | avdmanager create avd -n "$ATTUNE_AVD" -k "$image"
fi
# The package may have Camera HAL disabled. Never claim -camera-back repairs it.
"$ANDROID_HOME/emulator/emulator" -accel-check
