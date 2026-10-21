# Attune.more AAOS prototype

This separate Android application hosts the existing web modules in a native,
parked-only Activity. It is an OEM-independent development prototype, not an
Android Auto projection app, approved Play category, or OEM integration.

Start with the [audit](../../docs/automotive/AUDIT.md),
[architecture/build/emulator guide](../../docs/automotive/README.md), and
[validation record](../../docs/automotive/VALIDATION.md).

Host policy checks: `python3 tests/automotive/run_checks.py` from repository root.
Android build: `bash scripts/automotive/build.sh` after installing the documented
SDK and JDK. The standard Gradle wrapper pins and verifies Gradle 8.11.1; its
distribution and normal build dependencies download on first use. No SDK is
bundled or installed implicitly.
