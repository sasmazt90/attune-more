# Storage protection for resumed skin training — 2026-10-11

Physical C: free space was **1.51 GiB before** and **7.57 GiB after** the operation and verified training resume. These are measured volume values, not uploaded payload sizes. No other physical local/external disk was connected. Google Drive desktop was connected in streaming mode with no mirror roots; its content cache remained on C: at 45,112 bytes. Connector cloud reads avoided filling that cache.

## Archive and preservation evidence

The closed dental downloader's `Dataset.zip` and `Benchmarking Dataset.zip` were independently matched to the public publisher checksums at https://zenodo.org/records/14827784. Current skin preparation/training, normal launcher, model API and evaluation readers do not open these ZIPs. The old downloader must restore them before a future rerun. Extracted data/models and the separate YOLOX source tree remain local.

Both originals were copied as exact 96 MiB or smaller byte ranges, without creating another compressed ZIP. All 32 ranges were fetched back from Google Drive, completely read and SHA-256 matched. Only then did a native PowerShell scope/hash check remove the two unused original ZIPs and fourteen exact duplicate download chunks. The full path/size/SHA/Drive manifest and restoration helper were uploaded and their complete cloud bytes were independently SHA-256 verified. Private Drive identifiers are retained only in ignored local receipts.

One cold, unreferenced negative YOLOX generation (`checkpoint-0005808-01791724355149389000`) was likewise copied as model, optimizer and state files; every cloud file was fully hashed before removing its two obsolete local tensor files. Its complete state/history and cloud restore receipt remain at the original directory. No live training directory was moved or renamed. `CURRENT`, the last two complete generations, actual selected-weight hash matches, per-target best references and frozen parents stay local. Candidate planning fails closed on scope/reparse/hash errors and never uploads user photos, health records, databases, audio or secrets.

An old photographic fixture's cloud upload was rejected by automatic review and was retained locally. Transparent NTFS LZX compression on that fixture, seven raw audit videos and five large generated JSON files preserved their paths and every SHA-256. It did not change scientific inputs or user records.

## Remaining capacity and exact continuation

Retaining every future checkpoint locally needs a conservative 10.98–16.65 GiB. The installed rolling policy instead archives only verified, cold unreferenced generations. Its incremental local peak is 5.64 GiB, including local current/fallback/best/in-flight slots, simultaneous transactional saves, export/evaluation space, connector scratch, 1 GiB extra Windows paging and 2 GiB safety. Prepared tensors and original source archives already needed by active recipes remain C:.

Resume requires measured free space of at least 6 GiB. A local supervisor samples disk space every 60 seconds; the thread heartbeat checks/archive eligibility every 15 minutes. Below 3 GiB, both phases receive a pause marker and save complete model/optimizer/scheduler/RNG checkpoints before stopping naturally. Trainers also enforce a 2 GiB per-batch reserve. No trainer is killed, no data split/acceptance gate/model selection is changed, and no candidate is promoted by storage handling.

The exact network tensors, optimizer tensors/param groups, scheduler and Torch/NumPy/Python RNG were load-verified from the following CURRENT checkpoints:

| Phase | Resume checkpoint | First proven gradient update |
|---|---|---|
| Negative YOLOX | `checkpoint-0007229-01791728926528656500` | step 7229 → 7230; cursor 906 → 908; epoch 2 |
| Negative mask continuation | `checkpoint-0010181-01791728927584744300` | step 10181 → 10182; cursor 271 → 272; epoch 0 |

An initial supervisor attempt stopped at the ownership guard because Windows PID 0 is a system process. No training/checkpoint mutation occurred. Using a verified nonexistent prior-PID sentinel corrected dispatch; both owned trainers subsequently made the real gradient updates above.

Production model hashes and BUILD_ID `sUqjoY1oyQXF6lvSRvtff` were unchanged; the normal shortcut remains present. The product had naturally closed at 18:14 and was not relaunched solely for storage checks. UI, voices, user records and other approved health modules were not edited.

Focused verification: exact checkpoint restoration, all active data paths present on C:, cloud full-byte hashes, native removal scope guards, current/last-two/selected/best/in-flight archive protections, storage reserve/pause-marker boundary checks, Python compilation and Git whitespace checks. No unrelated product test campaign was run. Detailed private operational receipts are under `.runtime/storage-20261011/`, including `archive-manifest.json`, `archive-manifest-cloud-proof.json`, `storage-status.json` and `monitor-procedure.md`. Training/evaluation/export/product acceptance remain separate ongoing work.


## Resumed mask validation correction

The negative mask ledger also contains 51 complete development validation tiles for `dry`, while the frozen model has seven output channels and no dry channel. The validation loop previously indexed this unsupported channel and failed at the first resumed epoch boundary. It now selects only rows belonging to the existing model targets. All 241 supported validation rows, their labels, source groups, tensor contents and splits remain unchanged; the original continuation validation pool is unchanged as well. Dry coverage remains pending and cannot be reported as passing. Model architecture, training sampling, protocol hashes, acceptance thresholds and final-test gates are unchanged.

The failed process retained its previous complete checkpoint. The other trainer was paused through its native transactional checkpoint path so the existing two-phase supervisor could restart without duplicate ownership. Exact model, optimizer, scheduler and RNG loading is checked before continuation. Development validation and acceptance still need to finish; no candidate is promoted by this repair.
