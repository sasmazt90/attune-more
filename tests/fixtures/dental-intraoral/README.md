# Real photographic upload regressions

These are unmodified, attributed public-domain/CC0 photographs, not synthetic
mouths or clinical ground truth. `manifest.json` pins the exact file bytes.
No private user photograph or health history is included.

- `cdc-19464.jpg`, `cdc-19465.jpg`, `cdc-19466.jpg`: CDC Public Health Image
  Library low-resolution originals; real teeth and gingiva without a full face.
  19466 was added as a held-out photo after the initial gate development.
- `cdc-19463.jpg`: CDC PHIL; independently visible anatomy with glare that must
  still fail the pre-existing upload quality limit.
- `astronaut.png`: NASA public-domain Eileen Collins photograph, obtained from
  the unmodified scikit-image sample. Tests use explicitly recorded pixel
  rectangles for hair, forehead and background; no recolouring or compositing.
- `coffee.png`: Rachel Michetti / Pikolo Espresso Bar, CC0, via scikit-image.
- `chelsea.png`: Stefan van der Walt, CC0, via scikit-image.
- `brick.png`: CC0Textures, CC0, distributed scikit-image derivative.

The original CDC pages and scikit-image attribution references are linked in
the manifest. CDC provides its public-domain images free of charge at
https://wwwn.cdc.gov/phil/ ; redistribution credits CDC. These inputs verify
software admission and source-coordinate behavior, not diagnosis, medical
accuracy or population-level sensitivity/specificity.

The no-face path is deliberately conservative: multiple separately bounded
crowns, coherent row geometry, real photographic boundaries, adjacent
gingival tissue and opposed oral-space evidence must coexist. A single tight
tooth crop or ambiguous/occluded/low-detail input is not automatically admitted.
The existing facial-landmark path remains unchanged.
