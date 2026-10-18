# Bounded live harness preparation

Run `python tests/e2e/live_harness_preparation.py` with the fresh production build
and ports 3000/8000 free. It invokes the checked-in orchestrator, backend and
browser CLI entrypoints twice, using separate `prep-*` identities.

Preparation scrubs inherited OpenAI configuration, disables local environment
loading and uses a clearly nonsecret sentinel only to exercise the real SDK
code path. A test-only HTTPX MockTransport prevents provider network traffic.
No production source contains fixtures or test switches. JSON conversation and
summary fixtures and a generated binary MP3 tone are preparation evidence only.

The actual SDK default client family is identified before server startup. HTTPX
and HTTPX2 are admitted at their own `Client.send`; unknown families refuse to
start. The constructed SDK client must still use that exact gated send method.
Preparation also independently denies non-loopback socket connections. The
HTTPX2 migration in SDK 3.24.0 exposed a CI instrumentation gap; the earlier CI
fallback did not pass this preparation and its zero captured send counter was
not a verified zero network count. Its sentinel was nonsecret and local key
loading was disabled. See the official SDK migration documentation:
https://github.com/openai/openai-python/blob/main/httpx2.md

The successful case verifies both gates, exact session history 0/2/4, alternating
conversation/TTS followed by one summary, admission before UI release, three
actual media playing/ended events, and one consented record after explicit end.
The failure case returns HTTP 503, verifies SDK retries zero at construction,
blocks a second browser admission and a separate backend probe before transport,
and preserves safe error reports. Both cases verify matching CLI identities,
marker creation before transport, owned service/storage cleanup and unchanged
prior authorization/consumption ledgers. CLI unit tests reject missing approval
and mixed live/fixture modes.

Only a separately authorized, distinct, one-shot live identity may use `--live`.
Counters distinguish admission attempts, original SDK send calls, fixture calls,
network send attempts, received HTTP responses and unverified billing. A network
send attempt alone does not prove receipt or billing. No failed live run is reset
or automatically retried. Physical capture remains denied throughout text tests.

The dependency prototype is not approved for promotion: product full audit has
7 high records, prototype 5 high, production-only 0; the common braces advisory
remains open. Product ESLint 8 and prototype ESLint 9 maintenance risks remain
separate. Closure requires an official patched compatible chain, supported lint
dependencies, clean full/production audits and installs, CSS/function acceptance,
and separate user approval to promote. No exception or framework upgrade is used.
