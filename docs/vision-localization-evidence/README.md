# Vision localization evidence — TR / EN / DE

[Audit and exact 28-entry translation table](../vision-localization-audit.md).
[Validation and scope proof](validation.json).

Each locale has a separate `*-browser.json` log with **43 passed stages**, visible
text and accessible labels. All three complete 24 answers across both eyes, reopen
history, and independently exercise camera/condition, recognition, permission,
model, playback, history-read and interruption errors. Each locale has **31
screenshots**, including preparation, dynamic instructions, clarifications, error
states, results/history and a full-page mobile view.

Screenshots are actual production UI. Camera pixels/model states and ASR events
are simulated. The camera fixture banner is localized and identifies the
simulation. Native approved recordings run at 4× for this display-text audit; no
recording, mapping, recognition, camera, assessment or scoring implementation is
changed. No physical camera/microphone test is claimed or required.

`corrected-strings.json` lists every corrected source/template, all three
translations, affected screen and previous translation when present.
`before-after.json` uses the actual translation engine and unchanged production
text producers against the immutable pre-audit catalog, then the corrected catalog.
It records 416 corrected derived outputs among 468 cases. Raw user transcripts
remain unchanged.

Reproduce with the normal local API/assets available and the production frontend
running on port 3306:

```sh
node tests/unit/vision_localization_runtime.cjs
node scripts/localization/check.cjs
VISION_LOCALIZATION_LANGUAGE=tr CHROME_PATH=/path/to/chrome python tests/e2e/vision_localization.py
VISION_LOCALIZATION_LANGUAGE=en CHROME_PATH=/path/to/chrome python tests/e2e/vision_localization.py
VISION_LOCALIZATION_LANGUAGE=de CHROME_PATH=/path/to/chrome python tests/e2e/vision_localization.py
```

The browser audit checks loaded fonts, document language, visible text and
accessibility text, plus mobile overflow. Screenshot review confirms readable
localized instructions, partial answers and errors. German result-table headings
wrap within the existing layout; layout and styling are preserved.
