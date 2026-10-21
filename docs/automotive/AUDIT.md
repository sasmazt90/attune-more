# Repository audit before automotive implementation

Date: 19 October 2026. Base: `1ee2386efd3dc30fe8d5b0d2bbf336ac7f03c98e`,
tree `d4377f28db95e73cc345f74448cd9e45ec6ef95c`. The Cloud checkout was clean
before creating `feature/aaos-oem-agnostic-prototype-20261019`. No applicable
`AGENTS.md` was found at repository root, in descendants, or its workspace parents.

## Scope and method

The complete tracked-path inventory contained 1,244 files. Repository-wide text
inventory covered 1,124 source/configuration/documentation files (306,509 lines);
651 Python files parsed without syntax errors. These inventory/parser results
are not a claim that every line received an exhaustive security or clinical audit.
Focused code review traced the current routes, shared packages, API handlers,
safety/consent/storage/media flows, launch/build configuration and both CI workflows.
Binary model/media assets were inventoried rather than executed or replaced.

| Scope | Existing implementation and constraints |
| --- | --- |
| `apps/vehicle-app` (235 tracked files) | Next.js 15.5.27, React 19.0.8, strict TypeScript, Tailwind. Nine routes: dashboard, five health modules, care, profile, privacy. Root layout provides consent and vehicle context. Preserve routes and design. |
| `services` (68 files) | Python 3.11 FastAPI core, Starlette, Pydantic, Uvicorn; local appearance/dental ONNX pipelines; mental provider/context/speech streaming; care search/handoff; session storage. Preserve all health/business implementations. |
| `packages` (10 files) | `IVehicleProvider`, `VehicleState`, `MockVehicleProvider`; shared profile types, clinical language/crisis and driving guards. Existing mutable simulator is a demo, not authenticated vehicle telemetry. |
| `shared` (2 files) | Five health module labels/routes/specialties and dental upload limits. Existing module names and compatibility IDs remain authoritative. |
| `tests` (282 files) | Python unit/integration regressions plus Node/CJS and browser scripts. Some E2E scripts require Windows, native audio, physical devices, historical fixtures or external services; not all are runnable CI tests. |
| `scripts` (420 files) | Protected Windows launch/build/process control, finite resource/identity guards, research/training/export utilities, browser diagnostics. Do not execute research/training scripts or change local worktrees as part of AAOS. |
| `docs` (147 files) | Product and dated research/delivery evidence. Root `ARCHITECTURE.md` explicitly describes an older snapshot (including outdated module/version/storage descriptions); use current source/README for actual behavior. |
| `.github` (2 existing workflows) | Main/PR deterministic Python suite and production frontend build; separate manually/branch-triggered browser audit. CI pins Node 22.20.0 and YOLOX source. No Android job/project existed. |
| `third-party` / `vendor` | Model/library notices and manifests, reviewed local braces package. No model/license changes required for the prototype. |
| Root/deployment | npm workspaces, pinned npm 10.9.3, Python requirements, normal Windows hash-verified launcher, explicit local environment opt-in. No Android, Docker, Render or Vercel deployment configuration was found. Existing Windows delivery and production infrastructure remain separate. |

## Vehicle and safety findings

- `packages/vehicle-context/types.ts` already defines `IVehicleProvider`; the mock
  supports speed, park/move transitions and subscriptions. It also contains demo
  driver/location/hardware fields; those are not evidence of device capabilities
  or authentication.
- `VehicleContext.tsx` polls `GET /api/vehicle/state` once per second, validates
  consistency, ignores stale request generations, applies a five-second request
  deadline, and locks visual eligibility until synchronization. Mutation immediately
  sets an updating state. UI simulation calls `POST /api/vehicle/speed`.
- FastAPI stores the same simulation in memory. Speed mutation rejects negative
  and nonfinite values and updates speed/park/move/gear together. No real CAN,
  VHAL, OEM SDK, driver identity provider or authorized vehicle API is connected.
- `local_health.payload()` checks PARK before reading media, bounds request bodies,
  requires explicit processing consent, and rechecks parking/disconnection.
  Main wires this gate directly to backend simulation state. Existing driving
  and privacy regressions cover these boundaries.
- Current UI stops/cancels active health work when PARK eligibility is lost;
  media and asynchronous results are tied to cancellation/epoch lifecycles.
  The mental backend also has a driving-aware crisis response. The automotive
  shell must apply stricter parked-only availability across the whole activity.
- Android display UX restrictions are a second gate, not equivalent to the
  repository's simulated speed. Backend Park cannot override Android restrictions.

## Existing APIs, authentication and data handling

Read routes include `/api/health`, `/api/vehicle/state`, `/api/profile`, mental
provider status and session history. Mutating routes include vehicle speed/toggle,
mental conversation/context/summary/speech/session operations, vision speech,
care matching, privacy wipe and bounded local-health skin/dental operations.

The backend is designed for a local trusted host: explicit CORS/browser-origin
allowlists, no wildcard trust, bounded validation, consent and per-record deletion
tokens. It does **not** implement a remote multiuser authentication/session system.
Demo `driverAuthenticated` is not an authentication mechanism. Do not expose this
API publicly or reinterpret CORS as authorization. The existing leased QA read-only
exception remains untouched and is not an automotive authentication strategy.

Web processing consents are service-specific. Native Android permission does not
replace those consents. Numeric records/preferences live in localStorage;
photo persistence is opt-in and uses browser storage; mental backend records use
`ATTUNE_DATA_DIR`. Existing deletion/recovery logic and storage IDs must remain.
No records, permissions or credentials migrate into the Android app automatically.
`ATTUNE_LOAD_LOCAL_ENV=0` keeps this prototype/test environment keyless.

Skin/dental use real image/landmark/model inputs, vision uses camera/calibration
and browser speech recognition, hearing uses audio/response protocols, and mental
uses browser recognition plus explicitly consented backend provider/TTS paths.
Network/provider failure must remain failure, not fabricated clinical success.
Appointments require explicit confirmation; this task makes no bookings/contact.

## Reuse and architecture decision

No native Android implementation or AAOS UX-restriction integration existed.
Use a separate native Activity and narrowly configured WebView to reuse the web
product and API. Rewriting five modules in Compose or forcing them into an
unrelated Car App Library category would duplicate tested logic and misrepresent
distribution eligibility. The new native provider reads the **existing backend
simulation**, not a second model; release uses an unavailable provider until a
properly authorized vehicle adapter is supplied. See the architecture guide for
independent platform gating and production boundaries.
