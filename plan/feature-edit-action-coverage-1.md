---
goal: Close high-risk behavioral test gaps in the deterministic 2D plan-editing service
version: 1.0
date_created: 2026-10-02
last_updated: 2026-10-02
owner: A-AI
status: 'Completed'
tags: [feature, testing, refactor, 2d]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Raise confidence in the existing local edit service through targeted tests for uncovered domain branches: room-removal rejection and aggregation, overlapping rugs, and collision-free generated IDs. This sprint is test-first and 2D-only; it does not change the edit algorithm or claim improved plan quality.

## 1. Requirements & Constraints

- **REQ-001**: Preserve the existing action contract in `docs/sprints/4-command-contracts.md`; cover only concrete untested behaviors found in `services/ai/app/edit_service.py`.
- **REQ-002**: Room removal with a missing target or fewer than two rooms left must reject before rebuild/render and leave the input document unchanged.
- **REQ-003**: Room-removal reconstruction must aggregate repeated room types, preserve an explicit `area_m2` from the building specification, and derive a missing area as the mean polygon area of remaining rooms of that type.
- **REQ-004**: Furniture addition must permit rug overlap in both directions (new rug over existing furniture, new furniture over existing rug), consistent with the existing domain contract.
- **REQ-005**: Generated `edit_f*` identifiers must avoid collisions with IDs in all PlanDocument collections while preserving existing IDs and source immutability.
- **CON-001**: Keep this sprint test-only. If a test exposes a production behavior defect, record a finding and plan a separate behavior-changing sprint before changing the algorithm.
- **CON-002**: Do not run model calls or alter any benchmark baseline/candidate artifacts; no generator or renderer implementation changes are in scope.
- **GUD-001**: Establish baseline coverage first, make small isolated test additions, run tests after each logical group, and record exact results and limitations in `docs/`.
- **PAT-001**: Prefer parameterized pytest cases and assert domain errors, document immutability, and absence of downstream rebuild/render calls.

## 2. Implementation Steps

### Implementation Phase 1 — rejected room-removal boundaries

- GOAL-001: Make invalid room-removal outcomes explicit and mutation-free.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Record baseline for `python -m pytest tests/test_edit_service.py --cov=app.edit_service --cov-branch --cov-report=term-missing -q` from `services/ai/`; baseline is 29 passing tests and 85% statement/branch coverage summary. | Oui — 29 passed; 85% couverture mesurée avant changement | 2026-10-02 |
| TASK-002 | Add `test_remove_room_rejects_missing_or_last_remaining_room_without_rebuilding` in `services/ai/tests/test_edit_service.py`; assert `target_not_found` or `constraint_violation`, unchanged source, and rebuild/render callbacks are not invoked. | Oui — deux cas paramétrés passent avec source inchangée et aucun rebuild/render | 2026-10-02 |

### Implementation Phase 2 — room program and furniture invariants

- GOAL-002: Lock down type aggregation/area semantics and two explicit placement/identity invariants.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Add `test_remove_room_aggregates_duplicate_types_and_uses_mean_area_when_unspecified`; assert duplicate counts, explicit per-type area preservation, and polygon-area mean fallback for a type absent from `spec.rooms`. | Oui — chambres contiguës; deux bureaux de 4/6 m² produisent la moyenne de 5 m²; aire demandée 10,5 m² préservée | 2026-10-02 |
| TASK-004 | Add parameterized rug-overlap cases to `test_add_furniture_allows_rug_overlap_in_either_insertion_order`; assert both objects are retained, source remains unchanged, and stable IDs are assigned. | Oui — rug→canapé et canapé→rug passent, avec document source inchangé | 2026-10-02 |
| TASK-005 | Add `test_add_furniture_skips_generated_id_collisions_across_plan_collections`; seed `edit_f1` in a non-furniture collection and assert the new item receives the next free ID without mutating the source. | Oui — collision de mur détectée; `edit_f2` assigné sans modifier l'original | 2026-10-02 |

### Implementation Phase 3 — verification and documentation

- GOAL-003: Verify focused and complete IA tests, style, coverage delta, and two-axis review without overstating coverage as plan quality.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-006 | Run focused tests after each test group, then `python -m pytest services/ai/tests -q`, Ruff check/format on the changed test, and `git diff --check`; rerun branch coverage for comparison with baseline. | Oui — 898 tests IA réussis; Ruff passe; couverture ciblée 85%→87%; diff whitespace propre | 2026-10-02 |
| TASK-007 | Review the final test diff against this plan and repository standards; update `docs/sprints/4-command-contracts.md` and this plan. Leave PostgreSQL TASK-007 separately open until its DB-backed CI run succeeds. | Oui — revues sans finding; bilan documenté; la tâche CAS PostgreSQL reste explicitement ouverte | 2026-10-02 |

## 3. Alternatives

- **ALT-001**: Raise a global coverage percentage threshold; rejected because statement coverage is not a correctness oracle and would incentivize unrelated test inflation.
- **ALT-002**: Modify production rules while expanding tests; rejected because this sprint is a focused coverage pass and any output-changing change needs a separately planned paired benchmark.
- **ALT-003**: Add stochastic/property-based generators; rejected for this bounded set of deterministic contract edges, which can be expressed as small parameterized examples.

## 4. Dependencies

- **DEP-001**: `services/ai/app/edit_service.py` action and geometry semantics.
- **DEP-002**: Existing fixtures/helpers in `services/ai/tests/test_edit_service.py` and `services/ai/app/furnish.py:CATALOG`.
- **DEP-003**: pytest, pytest-cov, Ruff already installed in the project environment.

## 5. Files

- **FILE-001**: `services/ai/tests/test_edit_service.py` — deterministic regression coverage only.
- **FILE-002**: `docs/sprints/4-command-contracts.md` — Phase 10 task status and evidence.
- **FILE-003**: `plan/feature-edit-action-coverage-1.md` — this executable sprint plan.

## 6. Testing

- **TEST-001**: Run the focused test names from Phases 1–2 and verify all pass.
- **TEST-002**: Run `python -m pytest services/ai/tests -q` and Ruff check/format for the changed test file.
- **TEST-003**: Compare branch/statement coverage report against the measured 85% baseline; interpret uncovered branches qualitatively rather than as plan-quality gains.
- **TEST-004**: Run `git diff --check` and Standards/Spec reviews; verify production modules and benchmark artifacts are unchanged by this sprint.

## 7. Risks & Assumptions

- **RISK-001**: A test may expose a mismatch between implementation and documented semantics; do not silently adjust either—the deviation must be reviewed and assigned a separate sprint.
- **RISK-002**: Coverage numbers may vary across Python/coverage versions; exact behavioral assertions remain the acceptance criterion.
- **ASSUMPTION-001**: The documented floorplan semantics intend `area_m2` to remain a per-type request when supplied; an absent request area is derived from remaining polygons.
- **ASSUMPTION-002**: Rugs are explicitly allowed to overlap ordinary furniture in either insertion order, matching the existing placement engine contract.

## 8. Related Specifications / Further Reading

- `docs/sprints/4-command-contracts.md` — TASK-015 edit-service coverage and action contract.
- `services/ai/app/edit_service.py` — room removal, furniture placement and ID allocation.
- `services/ai/app/furnish.py` — catalogue and rug-overlap behavior.
