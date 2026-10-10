---
goal: Preserve stable plan identity and layout choices across compatible 2D rebuild edits
version: 1.0
date_created: 2026-10-02
last_updated: 2026-10-04
owner: A-AI
status: 'Completed'
tags: [feature, refactor, benchmark, 2d, reliability]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Close the remaining 2D edit-contract gap for full program rebuilds. Before changing code,
archive and run a local paired benchmark; then carry forward source room IDs and the source
layout descriptor only when valid, let the existing optimizer determine whether its recorded
arrangement is still compatible, preserve room IDs only for unambiguous same-type polygon
correspondences, and report any identifiers/layout metadata that changed.
No remote image model is called and no claim of improved architectural quality is in scope.

## 1. Requirements & Constraints

- **REQ-001**: Trace the edit flow `interpret → EditCommand → edit_service → rebuild/pipeline → vectorize → plan_adapt → validate → render`; keep transport/persistence outside the domain edit service.
- **REQ-002**: Local non-rebuild commands continue to deep-copy the source and preserve its unaffected IDs and `layout` metadata.
- **REQ-003**: For `replace_program` and `remove_room`, preserve an existing room ID only when an unconsumed source room has the same room type and a mutual, geometrically dominant polygon IoU match (IoU ≥ 0.25 and ≥ 0.10 above the next candidate); never trust model-provided IDs or list order as identity evidence.
- **REQ-004**: New rooms receive deterministic globally unused IDs; final IDs remain unique across PlanDocument collections.
- **REQ-005**: Pass the source `layout` descriptor through the existing build/vectorize/adaptation pipeline. Let `normalize_variant` and the current optimizer decide whether the old parti/seed/arrangement remains usable; do not bypass feasibility checks.
- **REQ-006**: If a rebuild changes or drops a previously stored layout descriptor, or drops source object IDs, append an explicit French warning; never promise preservation for an incompatible result.
- **REQ-007**: Compare a frozen six-case, five-seed edit benchmark before/after using the exact same source PlanDocuments and one deterministic room-area edit per pair; save source/result documents, local PNGs, metrics, manifests, contact sheets and a concise report.
- **CON-001**: Keep this sprint in 2D and use the local renderer only; do not call Gemini, Together, or other external providers.
- **CON-002**: Do not modify the held-out evaluation split or overwrite existing benchmark evidence; use a new run directory and archived working-tree sources.
- **CON-003**: Do not claim scientific improvement from coverage, ID-retention, a small synthetic corpus, or aesthetic impressions alone; report paired plan-level deltas and limitations.
- **GUD-001**: Freeze source code/inputs and capture the reference run before production-code edits; implement in isolated blocks, review immediately, rerun targeted/full suites and then run the candidate benchmark.
- **PAT-001**: Keep ID reconciliation pure/deterministic, reuse the existing immutable `EditCommand`, injectable rebuild callback, and `normalize_variant`; avoid a second generator or persistence path.

## 2. Implementation Steps

### Implementation Phase 1 — architecture trace and frozen reference

- **GOAL-001**: Establish reproducible baseline evidence for structural edit rebuilds before changing runtime behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Trace `services/ai/app/diffusion.py:edit_plan/_adapted_from_spec`, `edit_service.edit_plan`, `pipeline.build_document`, `vectorize.vectorize`, `plan_adapt.adapt`, and `layout_select.select`; record where source `layout` and room IDs are currently lost and which downstream validation/warning steps already exist. | ✅ | 2026-10-02 |
| TASK-002 | Add `benchmark/edit_rebuild.py` using only local providers and six frozen development source cases `dev01`–`dev05` plus `dev07` from `benchmark/runs/3a-baseline`, seeds 0–4; make one deterministic +1 m² living-area program edit per source, forbid socket connections, archive source hashes, and save source/result JSON, local PNG and independent geometry metrics. | ✅ | 2026-10-02 |
| TASK-003 | Execute the reference run into a new `benchmark/runs/edit-rebuild-reference-20261002/`; verify 30 paired inputs and preserve every failure as data before modifying production modules. | ✅ | 2026-10-02 |

### Implementation Phase 2 — identity and layout carry-forward

- **GOAL-002**: Preserve compatible source identity/layout through the current rebuild pipeline without changing local edit semantics.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Update `services/ai/app/edit_service.py` to remove room IDs from generator inputs, match old/new same-type rooms by mutual dominant polygon IoU (≥ 0.25 and ≥ 0.10 margin), reject duplicate generated room IDs, allocate collision-free IDs for unmatched rooms, remap dependent references, and attach source layout only to rebuild context. | ✅ | 2026-10-04 |
| TASK-005 | Thread the optional preferred layout through `services/ai/app/diffusion.py:_adapted_from_spec`, `services/ai/app/pipeline.py:build_document`, and `services/ai/app/vectorize.py:vectorize`; preserve existing generation behavior when no source descriptor is provided and let `plan_adapt` reject/fallback if the old arrangement is infeasible. | ✅ | 2026-10-02 |
| TASK-006 | Extend `_with_rebuild_warning` and `services/ai/tests/test_edit_service.py` for geometric ID correspondence, same-type reordering, ambiguous/unmatched rooms, duplicate generated-ID rejection, reference remapping, new ID uniqueness, layout reuse/fallback warnings, dropped-object warnings, unchanged source and exact render/validation target. | ✅ | 2026-10-04 |

### Implementation Phase 3 — candidate comparison and closure

- **GOAL-003**: Validate the rebuilt-plan behavior and publish evidence without overclaiming architectural quality.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add `benchmark/compare_edit_rebuild.py` to enforce identical case/seed/source hashes, compute paired ID retention, source-denominator same-ID polygon IoU and independent geometry metric deltas, and create per-case source/reference/candidate PNG contact sheets plus a report. | ✅ | 2026-10-04 |
| TASK-008 | Run candidate `edit-rebuild-id-candidate-final-v2-20261004`; compare with explicitly rebased legacy run `edit-rebuild-id-legacy-reference-final-20261004` into `benchmark/comparisons/edit-rebuild-id-final-v5-20261004/`; inspect all six contact sheets and classify preservation, layout-compatible differences and regressions. | ✅ | 2026-10-04 |
| TASK-009 | Run focused edit/pipeline/vectorize tests, full AI suite, Ruff and `git diff --check`; obtain final Standards/Spec reviews; update `docs/sprints/4-command-contracts.md` and this plan. | ✅ | 2026-10-04 |

## 3. Alternatives

- **ALT-001**: Copy source IDs by list index; rejected because ordering/count changes can silently assign an old identity to a different room type.
- **ALT-002**: Preserve every prior wall/opening/furniture ID unconditionally; rejected because regenerated geometry can represent a different object and IDs must not claim semantic continuity without a valid match.
- **ALT-003**: Bypass adaptation and directly reuse old polygons; rejected because changed programs require repacking and full document validation.
- **ALT-004**: Use Gemini output as the comparison; rejected because this sprint studies vector rebuild semantics and paid/stochastic raster output cannot establish ID or topology correctness.

## 4. Dependencies

- **DEP-001**: Frozen development documents/specs in `benchmark/runs/3a-baseline/` and corpus cases in `benchmark/cases/corpus.json`.
- **DEP-002**: Existing local `pipeline.build_document`, `layout_select`, `plan_adapt`, document validator, local renderer and independent `research.metrics.geometry.evaluate`.
- **DEP-003**: Pillow, pytest, pytest-cov and installed AI-service dependencies; no external service credential is required.

## 5. Files

- **FILE-001**: `services/ai/app/edit_service.py` — deterministic source-ID matching, private rebuild context and warnings.
- **FILE-002**: `services/ai/app/diffusion.py`, `pipeline.py`, `vectorize.py` — optional preferred-layout plumbing.
- **FILE-003**: `services/ai/tests/test_edit_service.py`, `test_pipeline.py`, `test_layout_select.py` — behavior contracts.
- **FILE-004**: `benchmark/edit_rebuild.py`, `benchmark/compare_edit_rebuild.py` — frozen paired edit benchmark.
- **FILE-005**: New `benchmark/runs/edit-rebuild-*` and `benchmark/comparisons/edit-rebuild-20261002/` evidence.
- **FILE-006**: `docs/sprints/4-command-contracts.md` and this plan — sprint status and method/results.

## 6. Testing

- **TEST-001**: ID reconciliation tests cover same-type reordering, mutually dominant polygon matching, unmatched geometry, decreasing/increasing counts, untrusted IDs, duplicate generated IDs, dependent-reference remapping, and cross-collection collisions.
- **TEST-002**: Pipeline/vectorize tests prove preferred layout is propagated, seed/arr is retained when feasible, and no-descriptor generation remains unchanged.
- **TEST-003**: Full candidate documents pass existing document validation; warnings list every dropped source ID and changed source layout descriptor.
- **TEST-004**: Reference/candidate benchmark pairs have identical case, seed, source document/spec hashes and complete local PNG + metrics artifacts for all 30 rows or explicit failures.
- **TEST-005**: Full AI suite, Ruff, `git diff --check`, Standards/Spec review and visual contact-sheet inspection pass before closing.

## 7. Risks & Assumptions

- **RISK-001**: Polygon IoU is only a geometric continuity proxy, not occupant-perceived semantic identity; the 0.25 IoU/0.10 margin thresholds are uncalibrated heuristics, so ambiguous, weak-overlap, or invalid-polygon matches receive new IDs. Same-ID IoU is a diagnostic, not an architectural quality score.
- **RISK-002**: A remembered arrangement may be infeasible or outside the optimizer's preference tolerance after a program edit; retaining seed alone is not equivalent to retaining geometry.
- **RISK-003**: Existing source fixtures are synthetic and represent only six development programs; benchmark results are regression evidence, not an external architecture evaluation.
- **ASSUMPTION-001**: `layout.parti/seed/arr` is internal metadata accepted by `normalize_variant`; `plan_adapt.adapt` remains the authority on feasibility.
- **ASSUMPTION-002**: The archived `3a-baseline` source documents are valid inputs to the current `edit_service` and contain a living room required by the fixed area edit.
- **ASSUMPTION-003**: Stable room IDs are meaningful to the editor and downstream room/furniture references, so unchanged rooms should retain them through a compatible rebuild.

## 8. Related Specifications / Further Reading

- `docs/sprints/4-command-contracts.md` — edit command and rebuild-warning contract.
- `services/ai/app/layout_select.py` — persisted `parti/seed/arr` selection semantics.
- `services/ai/app/plan_adapt.py` — existing arrangement compatibility/fallback.
- `benchmark/README.md` — immutable source archives, paired runs and image comparison protocol.
