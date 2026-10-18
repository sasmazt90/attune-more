# PHOTO-HISTORY-01: finite QA vehicle-read candidate

Candidate only. The running backend, launcher, frontend build, browser profile,
records and permissions have not been restarted or changed by this preparation.
The two actual human choices on QA3447 are confirmed true/true. The A–D browser
matrix remains NOT_RUN (2/6); these policy tests are not browser acceptance.

## Problem and boundary

The existing build calls `http://127.0.0.1:8311/api/vehicle/state`. Two bounded
GETs showed QA Origin3447 rejected403 (`Untrusted browser origin`, no ACAO),
while normal Origin3000 received200 with matching ACAO and actual PARK/speed0.
Changing QA3447's own `/api` guard would not fix this absolute backend call.

`qa_vehicle_read.py` snapshots these two **process-only, public** startup fields:

| Field | Accepted value |
| --- | --- |
| `ATTUNE_QA_VEHICLE_READ_ORIGIN` | exactly `http://127.0.0.1:3447` |
| `ATTUNE_QA_VEHICLE_READ_EXPIRES_UTC` | absolute UTC, future, at most45 minutes from startup |

Absent/partial/invalid/expired configuration disables access. Every request and
late response checks expiry; a startup monotonic deadline prevents wall-clock
rollback extending the lease. Changing environment values after startup does
not refresh the snapshot.

Only GET, exact decoded **and raw** `/api/vehicle/state`, empty query and empty
body qualify. Cookie/Authorization (including empty values), transfer encoding,
duplicate Origin/Content-Length, other methods/paths/origins and QA preflight
are denied. The global `ATTUNE_TRUSTED_ORIGINS` list is unchanged.

The original real handler runs. Moving state and handler errors are preserved;
no static PARK, proxy, spoofed Origin or disabled safety gate is introduced.
Only the authorized response receives exact ACAO3447, `Vary: Origin` and
`Cache-Control: no-store`; no credential or wildcard permission is added.

## Focused evidence

[Machine evidence](qa-vehicle-read-candidate-evidence-20261018.json) records
48 computed policy observations and45 pytest cases (including three existing
origin-regression cases), with no errors/failures/skips. Tests import the actual
main app and use in-process TestClient with an isolated temporary data directory;
they do not probe or mutate the normal API.

| Case | Result |
| --- | --- |
| Exact read, actual in-process speed handler set37 |200, moving=true/parked=false, exact scoped headers |
| Other path, mutation, OPTIONS, query, body, credentials, duplicate headers |403; vehicle state unchanged |
| Missing/invalid/non-UTC/over45min/expired configuration |403 |
| UTC expiry; monotonic expiry after wall-clock rollback; expiry inside handler |403 without QA ACAO |
| Test-only actual-handler503 fault |503 preserved, not replaced with success |
| Normal3000 read and preflight, including after QA expiry | Existing200/ACAO3000 behavior preserved |

Three changed Python sources parse; actual main imports during this focused run.
No model, build, inference or broad test campaign ran.

## Activation constraint: the current launcher cannot restart only8311

The current resident owner is launcher118096; backend101208, frontend117272 and
browser113452 belong to its kill-on-close job. `start_togg.pyw:246–260` detects
backend exit and closes that entire job. Its backend stdin shutdown pipe belongs
only to the resident parent. There is no authenticated backend-slot replacement
channel. Do not stop the leaf backend, inject a pipe/handle, suspend the owner,
disable its checks or claim that an on-disk launcher edit updates the live owner.

The actual wrapper is existing `.launcher/backend_host.py`, with the exact
`attune-cdc-health-final-technical-20261017/services/core-api` argument and CWD.
It loads `main:app` once, without reload. Current in-memory code predates this
candidate; no in-memory source hash was read. The public delivery descriptor
pins source8e8a517 and BUILD_ID `A-e1UWQmCW1DpJXm9fY46`.

The candidate changes on-disk main's hash. Existing launcher delivery verification
must continue to fail closed on an unreviewed mismatch. Do not relabel it as the
old source or invoke that launcher until a reviewed activation manifest is ready.

## Smallest legitimate alternative, for separate review only

One explicitly approved **whole TOGG session** maintenance restart is required
under this resident supervisor; frontend/browser PIDs would change. This exceeds
a backend-only restart approval. No restart or launcher/descriptor edit occurred.

1. Revalidate exact owned PID/start/executable/argv/CWD, both TOGG-profile windows,
   no active task and current real vehicle state. Preserve profile, data directory,
   permissions, model/config hashes and existing key-source references.
2. Archive the public deployment descriptor and exact original main bytes/hash.
   Review a descriptor amendment selecting the candidate main/helper hashes and
   backend candidate commit. Keep all other hashes, unchanged launcher files and
   frontend BUILD_ID/build provenance8e8a517. Never disable hash verification.
3. Close only the verified TOGG-profile app/QA windows via their normal lifecycle;
   let the existing owner gracefully drain backend stdin and close its owned job.
   Stop if ownership/windows differ. No global kill, unrelated Chrome action or
   mutation of the launcher's private pipe/job is permitted.
4. Start the **same** existing Pythonw/`start_togg.pyw` target, original CWD,
   profile and data paths. A bounded activation helper supplies only the two public
   QA fields in that new launcher's child environment; expiry is freshly computed
   at launch and at most45 minutes. No global env, `.env`, key copy, persistent
   launcher edit, new profile or frontend build. Existing wrapper key loading stays
   in memory from the same source reference.
5. On one failed candidate startup, let only its verified owner clean its job,
   restore archived exact original main and public descriptor bytes (candidate
   commit remains preserved), then make at most one approved baseline fallback
   launch. No reset/stash/clean, repeated launch loop or data/permission rollback.
6. Verify new backend source/config/owner identity, unchanged frontend asset/build
   hashes, actual browser vehicle read and normal behavior. Resume QA3447 once with
   its existing origin/store/true permissions. Whole-session closure may require a
   new tab ID in the same preserved profile; do not pretend the old ID survived.
   Then run the original A–D matrix, without another human consent round.

The QA grant expires automatically without another restart. Omit both fields on
later normal launches; an approved maintenance rollback can restore source pins.
An API-only replacement remains non-executable with the current resident owner.
