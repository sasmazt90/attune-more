#!/usr/bin/env bash
# Foreground supervisor. Run as an unprivileged user under systemd; no public ADB/VNC.
set -euo pipefail
: "${ANDROID_HOME:?Android SDK required}"
: "${ATTUNE_APK:?absolute cloudDemo APK path required}"
: "${ATTUNE_AVD:=AttuneAws15}"
: "${ATTUNE_AAOS_EVIDENCE:?private evidence directory required}"
# Task 13 Vision acceptance uses a 3 GiB guest. Keep an explicit 8 GiB
# diagnostic option; never silently turn a failed 3 GiB run into a larger guest.
: "${ATTUNE_AAOS_MEMORY_MB:=3072}"
[[ "$ATTUNE_AAOS_MEMORY_MB" == 3072 || "$ATTUNE_AAOS_MEMORY_MB" == 8192 ]] || {
  echo 'ATTUNE_AAOS_MEMORY_MB must be 3072 or 8192' >&2; exit 1;
}
mkdir -p "$ATTUNE_AAOS_EVIDENCE"
printf '%s\n' "$ATTUNE_AAOS_MEMORY_MB" > "$ATTUNE_AAOS_EVIDENCE/requested-memory-mb.txt"
test -r /dev/kvm && test -w /dev/kvm
"$ANDROID_HOME/emulator/emulator" -accel-check > "$ATTUNE_AAOS_EVIDENCE/kvm.txt" 2>&1
export DISPLAY=:99
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; wait || true; }
trap cleanup EXIT INT TERM
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp & pids+=("$!")
for ((n=0;n<50;n++)); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep .1; done
xdpyinfo -display :99 >/dev/null
# Isolated PulseAudio devices for optional browser PCM transport.
# Runtime guest support and calibration still require real AAOS acceptance.
if [[ "${ATTUNE_AUDIO_ENABLED:-0}" == 1 ]]; then
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export PULSE_SINK=attune_out PULSE_SOURCE=attune_mic.monitor QEMU_AUDIO_DRV=pa
pactl info >/dev/null
pactl list short sinks | rg -q "attune_out" || pactl load-module module-null-sink sink_name=attune_out rate=48000 channels=2
pactl list short sinks | rg -q "attune_mic" || pactl load-module module-null-sink sink_name=attune_mic rate=48000 channels=1
fi
"$ANDROID_HOME/emulator/emulator" -avd "$ATTUNE_AVD" -port 5554 -no-snapshot -no-boot-anim -gpu swiftshader_indirect -memory "$ATTUNE_AAOS_MEMORY_MB" -cores 4 > "$ATTUNE_AAOS_EVIDENCE/emulator.log" 2>&1 & pids+=("$!")
adb="$ANDROID_HOME/platform-tools/adb"
timeout 360 "$adb" -s emulator-5554 wait-for-device
ready=0
for ((n=0;n<180;n++)); do
  if [[ "$("$adb" -s emulator-5554 shell getprop sys.boot_completed | tr -d '\r')" == 1 ]]; then ready=1; break; fi
  sleep 2
done
[[ "$ready" == 1 ]]
"$adb" -s emulator-5554 shell getprop > "$ATTUNE_AAOS_EVIDENCE/guest-properties.txt"
"$adb" -s emulator-5554 shell cat /proc/meminfo > "$ATTUNE_AAOS_EVIDENCE/guest-meminfo.txt"
[[ "$("$adb" -s emulator-5554 shell getprop ro.build.version.sdk | tr -d '\r')" == 35 ]]
"$adb" -s emulator-5554 shell pm list features > "$ATTUNE_AAOS_EVIDENCE/features.txt"
rg -q 'android.hardware.type.automotive' "$ATTUNE_AAOS_EVIDENCE/features.txt"
"$adb" -s emulator-5554 reverse tcp:3000 tcp:3000
"$adb" -s emulator-5554 install -r "$ATTUNE_APK"
"$adb" -s emulator-5554 shell dumpsys package more.attune.automotive.prototype.clouddemo > "$ATTUNE_AAOS_EVIDENCE/apk.txt"
"$adb" -s emulator-5554 shell dumpsys media.camera > "$ATTUNE_AAOS_EVIDENCE/camera-hal.txt"
"$adb" -s emulator-5554 shell am start -n more.attune.automotive.prototype.clouddemo/more.attune.automotive.MainActivity
x11vnc -display :99 -localhost -rfbport 5900 -forever -shared -nopw > "$ATTUNE_AAOS_EVIDENCE/x11vnc.log" 2>&1 & pids+=("$!")
websockify --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900 > "$ATTUNE_AAOS_EVIDENCE/websockify.log" 2>&1 & pids+=("$!")
sha256sum "$ATTUNE_APK" > "$ATTUNE_AAOS_EVIDENCE/apk.sha256"
wait -n "${pids[@]}"
