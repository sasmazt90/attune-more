# Regional skin-map SVG layer integration

The accepted regional colour contract is now implemented in the existing skin
result portrait rather than in a separate demo flow. A strict presentation
planner consumes only a source-bound `regional-skin-evidence-v1` summary:

- dry regions use a blue anatomical-region fill;
- oily regions use a green anatomical-region fill;
- evaluated normal regions remain uncoloured;
- unknown/conflicting/incomplete regions use light grey and never become normal;
- positive redness uses a separate red hatch and contour, so it can overlap any
  dry/oily/unknown state and is never presented as sensitivity.

The layer is rejected when capture ID, FRONT pose, source dimensions or
coordinate space differ from the displayed snapshot. Unsupported criteria and
the periorbital view produce no regional type layer. When a validated pixel-local
map exists for the selected criterion, it takes priority over the coarser
anatomical summary.

Four actual Python server-builder fixtures exercise unknown, complete
combination, partial and conflicting cases through the TypeScript parser and
presentation planner. The expanded suite passes 58 assertions, including source
binding, exact colour decisions, independent redness, no sensitivity inference,
unknown handling and strict removal/rejection of unrelated fields.

This is an implementation/contract milestone, not model or camera acceptance.
The shapes are existing MediaPipe anatomical meshes, not predicted pixel masks.
The accepted-method registry remains authoritative; synthetic test policies do
not enable a production method. Full application typecheck was unavailable in
the scratch runtime because frontend dependencies are absent. Browser screenshot,
retained-photo replay, real-camera slices and final end-to-end acceptance remain
open.
