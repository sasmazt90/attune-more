# Attune braces local patch 1

Owner: TOGG Attune maintainers. Upstream: braces 3.0.3, MIT (LICENSE retained).
Identity: 3.0.3-attune.1, not an official upstream fixed release.
Upstream byte hashes are in UPSTREAM-HASHES.json. LOCAL-HASHES.json binds the
packaged source; the root lockfile pins the generated tarball integrity.

GHSA-vfj7-8cjw-p6xm: reject actual traversal depth beyond 256, cyclic nodes,
cyclic/deep value arrays and cyclic/deep parent lookup before recursive use.
Parser stack checks precede node construction, including parentheses and its
internal stringify path. Compile, expand and stringify validate direct AST and
direct lib subpath calls. Flatten/append validate arrays from range transforms.
Numeric options/AST metadata and transform results are checked before recursive
array coercion, including inside fill-range. Transform wrapping preserves option
descriptors/prototype. Terminal values do not traverse dormant nodes metadata.
Error: RangeError, code ERR_BRACES_STRUCTURE. There is no silent truncation.

256 edges retain ordinary globs and leave headroom beneath Node 22.20.0's
measured 4,000-level baseline stack failure. This intentionally rejects
previously accepted extreme structures; maxLength/rangeLimit cannot disable it.
Normal character/range limits, ordering, escaping and duplicate behavior stay
unchanged. AST parent/prev backreferences and shared children remain valid.
Custom JavaScript callbacks/getters are executable trusted code, not a sandbox.
This does not impose a total Cartesian expansion memory budget.

The root npm override pins every resolved braces package to the local tarball.
Next's bundled NFT also contains braces code, not resolved as a package; its
observed ignore path calls picomatch, and reachability of its recursive braces
walkers has not been established. This patch makes no whole-bundle closure or
upstream advisory-clear claim. Upstream warnings must remain separately tracked.

Rebuild tarball with pinned Node 22.20.0/npm 10.9.3 using npm pack ./vendor/braces
--pack-destination ./vendor, then update lock using npm install --package-lock-only
--ignore-scripts --no-audit. Clean install uses npm ci --no-audit. Regenerate
LOCAL-HASHES.json whenever vendored package bytes change; review changes before
repacking. Do not modify normal delivery node_modules or the installed site.
