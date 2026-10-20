# Voice and audio provenance

## Actual voice selection

The browser's real `speechSynthesis.getVoices()`/`voiceschanged` metadata is filtered to the exact selected locale. Web Speech does not standardize gender, so browser/system voices are labelled gender unknown; names are not used to guess. Missing requested voices and absent exact locales stop playback and produce an availability state. No other-language voice is silently selected. Installed Windows voices and AAOS voices are not presumed interchangeable. Online system speech containing response text needs an explicit additional voice-provider permission; existing health consent and safety checks still apply.

The existing free Microsoft Edge path can query actual locale/gender metadata on explicit user request. Provider failures remain failures, without another-language or invented-voice substitution. Existing approved TR recordings and exact TR Ahmet/Emel provider contracts remain intact. Availability of live Microsoft voices depends on the device/network/provider and was not claimed from an offline fixture.

## New, free local synthesis

New EN/DE fixed recordings use eSpeak NG 1.51 plus FFmpeg 6.1.1. Actual tool metadata and successful synthesis were verified for English (America) `en-us` and German `de` male base voices and the `female3` / `+f3` female variant. Optional MBROLA voices appearing in a list were not treated as installed. eSpeak is a synthetic voice/variant; this is not a human speaker or a Microsoft neural voice. These free tools introduce no paid API or service.

`apps/vehicle-app/public/audio/localized/manifest.json` identifies every profile, text, source-text hash, URL, size, asset SHA-256 and provenance. There are 244 MP3s: 33 guidance and 28 fixed vision prompts for each of four locale/gender profiles. Each is mono MP3 at 24 kHz; measured longest fixed prompt is 17.616 seconds, within the unchanged 25-second vision speech timeout. Runtime playback verifies content size/hash. All are explicitly `new-local-synthesis`, with auditory acceptance **pending**. They are not original approved recordings. Review pronunciation, naturalness and medical wording before release.

Optional free-text synthesis in `local_speech.py` uses installed eSpeak NG and FFmpeg, probes the actual profiles, accepts only the selected locale/profile, and uses cancellable subprocesses with bounded output/timeouts. Text flows through stdin, without a shell/network service or persisted health-text files. Moving/restricted requests fail closed, including checks before/after synthesis and while yielding output. If the tools are absent (for example on an unverified Windows installation), the UI states that fixed guidance remains available while local free-text speech is unavailable. It does not claim the tools exist on Windows or AAOS. Cloud synthesis and codec validation do not prove physical audible acceptance.

## Hearing stimuli

The original approved Turkish digit/noise assets are unchanged. EN/DE use **separate**, versioned newly synthesized 10-digit banks; a male voice is fixed for each bank, independently of narrator preference. Each WAV is mono 48 kHz, SHA-256 checked, RMS-normalized to the existing engineering target and checked for silence/clipping. The existing noise, pure tones, SNR mixing, scoring, calibration warnings and assessment algorithms are preserved. Result provenance records the bank version/hash and pending acceptance. These banks are **not** acoustically/clinically validated equivalents; this limitation is visible in the application. Cross-language thresholds must not be asserted clinically comparable.

`shared/localization/preserved-audio.json` records size/SHA-256 for all 83 pre-existing audio files captured before implementation. Tests rehash each file. The regeneration command refuses an existing output directory, generates EN/DE only, and cannot overwrite the approved TR bank:

```sh
python scripts/localization/synthesize_assets.py --stage /path/to/new/empty/staging-directory
```

Use a new version/output design for future synthesis; do not delete existing approved assets to rerun it. eSpeak NG and FFmpeg are external free tools; retain their upstream license notices when distributing the tools. New generated-speech provenance is separate from approved recording consent and from any broader commercial/clinical certification.

## Bounded CDC Local checks still required

On the actual Windows installation: list real matching TR/EN/DE voices and available metadata; check actual recognition and audible playback in each language; verify male/female choices only where metadata supports them; test mute, interruption, backgrounding and unavailable-provider errors. Do not install paid voices or assume names/gender.

On an authorized AAOS runtime: verify selected-locale recognition, actual WebView/system voice metadata, new local recordings/streamed speech, permission denial and lifecycle interruption while independently applying Car UX/backend gates. No new emulator workflow was dispatched for this change. The archived successful run #122 validates its historical source, not this localized build. Physical camera/microphone/vehicle acceptance and listening/linguistic/clinical validation remain separate.
