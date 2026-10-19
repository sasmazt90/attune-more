#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../.." && pwd)"
task_gradle="$(command -v gradle || true)"
if [[ -z "$task_gradle" ]]; then task_gradle="$task_root/apps/automotive/gradlew"; fi
task_gradle_version="$("$task_gradle" --version)"
if [[ "$task_gradle_version" != *$'\nGradle 8.11.1\n'* ]]; then
  echo 'This prototype pins Gradle 8.11.1.' >&2
  exit 69
fi
exec "$task_gradle" --no-daemon --max-workers=2 -p "$task_root/apps/automotive" :app:assembleDebug :app:lintDebug
