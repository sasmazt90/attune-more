#!/usr/bin/env bash
# Non-chargeable build preparation. This does not start AWS or fetch model weights.
set -euo pipefail
: "${ATTUNE_ASSET_MANIFEST:?Reviewed model path/size/SHA-256 manifest required}"
: "${ATTUNE_ASSET_ROOT:?Verified model bundle root required}"
: "${ATTUNE_BUNDLE_OUTPUT:?Output directory outside the source tree required}"
mkdir -p "$ATTUNE_BUNDLE_OUTPUT"
python3 scripts/aws/verify_assets.py --root "$ATTUNE_ASSET_ROOT" --manifest "$ATTUNE_ASSET_MANIFEST" --output "$ATTUNE_BUNDLE_OUTPUT/assets.json"
npm ci
export NEXT_PUBLIC_ATTUNE_SAME_ORIGIN_API=1 NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE=1 NEXT_PUBLIC_ATTUNE_ACNE_V5=1 NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER=openai NEXT_PUBLIC_ATTUNE_MEDIAPIPE_DELEGATE=CPU NEXT_TELEMETRY_DISABLED=1
npm run build
apps/automotive/gradlew --no-daemon --max-workers=2 -p apps/automotive :app:assembleCloudDemo :app:lintCloudDemo
cp apps/automotive/app/build/outputs/apk/cloudDemo/app-cloudDemo.apk "$ATTUNE_BUNDLE_OUTPUT/"
git rev-parse HEAD > "$ATTUNE_BUNDLE_OUTPUT/source-commit.txt"
sha256sum "$ATTUNE_BUNDLE_OUTPUT/app-cloudDemo.apk" > "$ATTUNE_BUNDLE_OUTPUT/apk.sha256"
# Record build evidence. Do not archive secrets, browser profiles or participant frames.
