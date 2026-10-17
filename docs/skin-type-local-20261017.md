# TYPE-01: local pretrained skin type

The normal skin API now uses a pinned, local three-class ViT ONNX model. Hosted
skin type remains disabled; no cloud credentials, training, new model downloads,
or user-photo transfers were used in this task. Other analysis methods, V5,
voices, approved images, privacy UI and numeric historical records are preserved.

## Selection and identity

Exactly two already downloaded models were compared once, using the frozen
existing development list. Fifteen dry/normal/oily photos were scored; five
combination photos were excluded from three-class accuracy. The sources were
already seen development data, not an independent test, and publisher labels
are not expert diagnosis or evidence of subject independence.

| Model | Accuracy | Macro-F1 |
|---|---:|---:|
| AishaBaliyan/glamour-ai-skin-model | 9/15 | 0.555556 |
| dima806/skin_types_image_detection | 10/15 | 0.670707 |

The pre-registered macro-F1 selection rule chose dima806 revision
`5aace4f4df0ba3265a07fbddab12a4ad38e0f6a6`. Upstream weights SHA-256:
`572185743c6be523efcc72b71f12c089cb81baf54525a1831b333544ba47224a`.
Converted ONNX SHA-256:
`99b4c2fa1e9ac013d539f635eb948c5a29f4c5f86f34fe26c380ad308c26c65a`.
The unmodified upstream model card and attribution notice accompany the config.
Its declared Apache-2.0 model license does not establish dataset rights or
general camera accuracy. Binary remains local and ignored by Git.

Input is the current product face crop: RGB PIL bilinear 224x224, rescale 1/255,
mean/std 0.5/0.5, class order dry/normal/oily. Standard local safetensors were
loaded without executing remote repository code. ONNX CPU parity across the
same 15 inputs preserved every argmax; maximum absolute logit error was
2.086163e-6. Repeated inference was deterministic; an external-connect sentinel
observed no network attempt. Missing/invalid config, weights or output returns
unavailable, with no hosted fallback or substitute class.

## Regional combination contract and limits

`combination-regional-user-v2-final-product-visible-support-v1` implements the fixed user rule:
T-zone oily and remaining measured regions normal OR dry means combination.
The global three-class argmax cannot overrule that pattern. Unknown/invalid
regions never count as normal/dry. A usable base model is still required.
No whole-face classifier is applied to arbitrary cheek crops.

The observations are the product's existing native oil/flake support proxies,
including their original quality and pixel gates. They are NOT sebum/hydration
measurements or validated regional skin-type labels. Any accepted area versus
measured zero is the explicit rule; no new cutoff was fitted, and UI rounding
is never used. In particular very small visible supports can trigger this rule;
regional categorical accuracy remains unestablished. Nose oil already includes
the forehead union, so it is not added a second time. Both anatomical parts
must be observed, and cheek/chin oil AND dry measurements must be valid.
Derived combination has no fabricated model confidence; the base confidence
and full decision trace remain separate. Confidence is never severity.

Finalization occurs once at the normal endpoint boundary, after native dryness
and optional V5 replacements. The shared/research analyzer returns only the
raw base model output. A separate `basePrediction` snapshot preserves the
three-class value/confidence/version/hash; repeated finalization is idempotent
and never treats an earlier Karma decision as a base model. Final receipts and
activeCriterionMethods are refreshed after the decision. Rule v2 separates
this final-product scope from earlier v1 results; historical records are not
rewritten. Model weights, base model version and all thresholds are unchanged.

## Evidence and acceptance boundary

The actual API/analyzer replay used an existing recorded browser MediaPipe
payload from a public-domain NASA fixture (1280x960, FRONT), not a fabricated
result, new user capture or physical camera test. It completed in 26.391 s:
base oily, final combination, with 0 hosted calls and 0 external connections.
Existing native support was T-zone oil 0.049834%, left cheek dry 0.102407%,
right cheek dry 0.042385%, and measured-zero chin oil/dry. These small support
values illustrate the rule's visible-proxy limitation, not clinical validation.

The original replay above exposed a sequencing defect: the early right-cheek
dry trace was 0.042384854 / appearance-cv-6 while the final native measurement
was 0 / appearance-native-dry-2. The lightweight correction replay reconstructs
only the explicitly recorded base model identity and consumes those already
recorded final API measurements; it does not run inference or modify records.
Its six cheek/chin oil/dry observations match final value/quality/method/area,
including native zero. The label stays Karma because both normal and dry rest
regions satisfy the user rule; this is an input-consistency correction, not a
demonstrated label-accuracy improvement. Invalid/missing final rows retract
an earlier matched combination to the preserved base class. The new actual
normal API verification is recorded separately, subject to the unchanged RAM
gate. `replay-result.json` remains original evidence, not rewritten as v2.

Focused Python checks: 32 passed including launcher preservation. The real
numeric response passed the current TypeScript overview/record validator,
JSON round-trip and Turkish Karma label check. An old hosted record remains
valid and unmodified. No test record was written to user storage. Method and
decision versions distinguish the new result from old records; no migration
or historical recomputation occurs. Typecheck passed.

Full receipts, frozen input SHA/group list, predictions, parity, resource lease,
replay, schema and normal-launcher delivery evidence are stored outside Git in
`cdc-progress/skin-type-local-20261017` under the workspace parent. Final build
and live shortcut identity are recorded there. UI/visual/physical acceptance
remains OPEN under the existing computer-use URL-policy boundary; API and
filesystem evidence do not close that layer.
