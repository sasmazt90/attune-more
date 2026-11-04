#!/usr/bin/env bash
# Runs one recorded journey on the host. Usage: run_e2e.sh <web|aaos> <skin|dental|din|tone|mental|vision> <output name> [--record]
# Inputs are the reference files prepared on the host; the report states which ones were used.
set -u
PLATFORM=$1; MODULE=$2; NAME=$3; RECORD=${4:-}
Q=/var/lib/attune/qa
I=/opt/attune-staging/inputs
R=/opt/attune/scripts/qa/realistic
# Dry runs only: a dev folder overrides the deployed scripts. Final recordings have no dev folder.
[ -d $Q/dev ] && R=$Q/dev
OUT=/var/lib/attune/evidence/$NAME
A=/opt/android-sdk/platform-tools/adb
U=$(id -u attune)
CAPTURE=()
mkdir -p "$OUT" "$Q/realistic"; chown -R attune:attune "$OUT" "$Q/realistic"
P="runuser -u attune -- env XDG_RUNTIME_DIR=/run/user/$U HOME=/home/attune PULSE_RUNTIME_PATH=/run/user/$U/pulse"
loginctl enable-linger attune 2>/dev/null
mkdir -p /run/user/$U 2>/dev/null; chown attune:attune /run/user/$U

# Audio path: a microphone sink the speech clips play into, and an output sink that can be recorded.
if ! $P pactl info >/dev/null 2>&1; then
  $P pulseaudio --kill 2>/dev/null; sleep 1; pkill -u attune -x pulseaudio 2>/dev/null; rm -rf /run/user/$U/pulse
  $P pulseaudio --daemonize=yes --exit-idle-time=-1 >/dev/null 2>&1
  sleep 2
fi
$P pactl list short sinks 2>/dev/null | grep -q attune_mic || $P pactl load-module module-null-sink sink_name=attune_mic rate=48000 channels=1 >/dev/null
$P pactl list short sinks 2>/dev/null | grep -q attune_out || $P pactl load-module module-null-sink sink_name=attune_out rate=48000 channels=2 >/dev/null
$P pactl list short sources 2>/dev/null | grep -q attune_mic_source || $P pactl load-module module-remap-source master=attune_mic.monitor source_name=attune_mic_source source_properties=device.description=AttuneMic >/dev/null

if [ "$PLATFORM" = web ]; then
  pgrep -x Xvfb >/dev/null || { Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/dev/null 2>&1 & sleep 1; }
  chmod 1777 /tmp/.X11-unix 2>/dev/null
  # Browser notices are not part of the application. Keep them out of the recording.
  mkdir -p /etc/opt/chrome/policies/managed
  echo '{"TranslateEnabled":false,"CommandLineFlagSecurityWarningsEnabled":false,"PromotionalTabsEnabled":false,"BrowserSignin":0,"DefaultBrowserSettingEnabled":false}' > /etc/opt/chrome/policies/managed/attune-qa.json
else
  # A vehicle is in a real time zone. The emulator image defaults to UTC, which would show UTC times.
  $A -s emulator-5554 shell cmd alarm set-timezone Europe/Berlin </dev/null >/dev/null 2>&1 || $A -s emulator-5554 shell setprop persist.sys.timezone Europe/Berlin </dev/null >/dev/null 2>&1
  $A -s emulator-5554 shell pm grant more.attune.automotive.prototype.clouddemo android.permission.RECORD_AUDIO </dev/null >/dev/null 2>&1
  # Record exactly the emulator's 1280x800 display at native size.
  ORIGIN=$(DISPLAY=:99 xwininfo -root -tree 2>/dev/null | grep 'Android Emulator' | head -1 | sed -E 's/.*\+([0-9]+)\+([0-9]+)$/\1,\2/')
  CAPTURE=(--display ":99+${ORIGIN:-0,0}" --video-size 1280x800)
fi

y4m() { # source png, target y4m
  ffmpeg -loglevel error -y -i "$1" -vf crop=1446:1080 -pix_fmt yuv420p -f yuv4mpegpipe "$2" </dev/null; chown attune:attune "$2"
}
SENDER=
start_sender() { # prefix, poses
  printf FRONT > $Q/camera-pose.txt; chown attune:attune $Q/camera-pose.txt; rm -f $Q/camera-pair.json
  /opt/attune-venv/bin/python $R/reference_camera_sender.py --prefix "$1" --poses "$2" > "$OUT/sender.log" 2>&1 &
  SENDER=$!
}
# A camera has one frame size, and the bridge accepts at most 1080 rows. Supplied photos are 1446 to 1448
# wide and 1086 or 1087 high, so every frame is centre-cropped to 1446x1080. Pixels are never scaled.
CROP=crop=1446:1080
fit() { ffmpeg -loglevel error -y -i "$1" -vf "$CROP" "$2" </dev/null; }
pngs() { # prefix, FRONT file, RIGHT file, LEFT file, [BITE file]
  fit "$2" "$1FRONT.png"; fit "$3" "$1RIGHT.png"; fit "$4" "$1LEFT.png"; [ -n "${5:-}" ] && fit "$5" "$1BITE.png"; chown attune:attune "$1"*.png
}
EXTRA=()
case "$PLATFORM-$MODULE" in
  *-care) EXTRA=(--input-map '{"appointment":"Scripted example; no real booking was made"}') ;;
  web-skin)
    y4m $Q/inputs/Char11-2.png $Q/e2e-skin-FRONT.y4m; y4m $Q/inputs/Char11-1.png $Q/e2e-skin-RIGHT.y4m; y4m $Q/inputs/Char11-3.png $Q/e2e-skin-LEFT.y4m
    EXTRA=(--frames "$Q/e2e-skin-POSE.y4m" --poses FRONT,RIGHT,LEFT --input-map '{"FRONT":"Char11-2","RIGHT":"Char11-1","LEFT":"Char11-3"}') ;;
  aaos-skin)
    pngs $Q/e2e-skin- $I/Char49-2.png $I/Char49-1.png $I/Char49-3.png
    start_sender $Q/e2e-skin- FRONT,RIGHT,LEFT
    EXTRA=(--input-map '{"FRONT":"Char49-2","RIGHT":"Char49-1","LEFT":"Char49-3"}') ;;
  web-dental)
    y4m $I/Male-Dental-4.png $Q/e2e-dental-FRONT.y4m; y4m $I/Male-Dental-1.png $Q/e2e-dental-RIGHT.y4m; y4m $I/Male-Dental-3.png $Q/e2e-dental-LEFT.y4m; y4m $I/Male-Dental-2.png $Q/e2e-dental-BITE.y4m
    EXTRA=(--frames "$Q/e2e-dental-POSE.y4m" --poses FRONT,RIGHT,LEFT,BITE --input-map '{"FRONT":"Male-Dental-4","RIGHT":"Male-Dental-1","LEFT":"Male-Dental-3","BITE":"Male-Dental-2"}') ;;
  aaos-dental)
    pngs $Q/e2e-dental- $I/Female-Dental-2.png $I/Female-Dental-1.png $I/Female-Dental-3.png $I/Female-Dental-4.png
    start_sender $Q/e2e-dental- FRONT,RIGHT,LEFT,BITE
    EXTRA=(--input-map '{"FRONT":"Female-Dental-2","RIGHT":"Female-Dental-1","LEFT":"Female-Dental-3","BITE":"Female-Dental-4"}') ;;
  *-mental)
    EXTRA=(--clips $Q --input-map '{"speech":"Mental-Health-1 to 5, in order"}') ;;
  *-din) EXTRA=(--input-map '{"listener":"Scripted, follows the digits to about -6 dB SNR. Reads no audio."}') ;;
  *-tone) EXTRA=(--input-map '{"listener":"Scripted, responds to real audio on the tested channel at set digital levels."}') ;;
esac
cp -f $R/*.py $Q/realistic/; chown -R attune:attune $Q/realistic
echo "harness $R $(sha256sum $R/e2e_modules.py | cut -c1-16)"
cd $Q/realistic
ENVIRONMENT="DISPLAY=:99 XDG_RUNTIME_DIR=/run/user/$U HOME=/home/attune PULSE_RUNTIME_PATH=/run/user/$U/pulse TZ=Europe/Berlin"
if [ "$MODULE" = vision ]; then
  if [ "$PLATFORM" = aaos ]; then
    pngs $Q/e2e-vision- $I/Male-Vision-1.png $I/Male-Vision-3.png $I/Male-Vision-2.png
    start_sender $Q/e2e-vision- FRONT,RIGHT,LEFT
  else
    for pair in FRONT:Female-Vision-1 RIGHT:Female-Vision-3 LEFT:Female-Vision-2; do
      ffmpeg -loglevel error -y -i "$I/${pair#*:}.png" -vf scale=640:480 -q:v 3 "$Q/web-vision-${pair%%:*}.jpg" </dev/null
    done
    chown attune:attune $Q/web-vision-*.jpg
  fi
  runuser -u attune -- env $ENVIRONMENT PYTHONPATH=$Q/realistic /opt/attune-venv/bin/python vision_realistic.py --platform "$PLATFORM" --scenario full --clips $Q/vision-speech/en --out "$OUT" "${CAPTURE[@]}" $RECORD
else
  runuser -u attune -- env $ENVIRONMENT PYTHONPATH=$Q/realistic /opt/attune-venv/bin/python e2e_modules.py --module "$MODULE" --platform "$PLATFORM" --out "$OUT" "${EXTRA[@]}" "${CAPTURE[@]}" $RECORD
fi
STATUS=$?
[ -n "$SENDER" ] && { kill $SENDER 2>/dev/null; wait $SENDER 2>/dev/null; }
chown -R attune:attune "$OUT"
exit $STATUS
