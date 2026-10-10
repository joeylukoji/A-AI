---
goal: Close parser boundary-test gaps for deterministic 2D edit commands
version: 1.0
date_created: 2026-10-02
last_updated: 2026-10-02
owner: A-AI
status: 'Completed'
tags: [feature, testing, 2d, reliability]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

Add deterministic regression tests for unexercised validation boundaries in the typed
2D edit-command parser. This sprint is test-only: preserve the command contract and do
not alter generation, geometry, renderer output, or benchmark artifacts.

## 1. Requirements & Constraints

- **REQ-001**: Preserve the v1 command contract in `services/ai/app/edit_commands.py`; tests must target branches identified by branch coverage, not invent new semantics.
- **REQ-002**: Cover invalid optional IDs, non-finite/overflowing numeric inputs, unsupported opening types, malformed program shapes/items, missing opening type/catalog ID, and non-string replies where applicable.
- **REQ-003**: Assert stable `EditCommandError.code` and `.field` for each invalid field rather than only asserting that an exception occurs.
- **CON-001**: Keep this sprint test-only; if tests reveal a contract defect, stop and plan a behavior-changing sprint separately.
- **CON-002**: Do not call Gemini, Together, or any other model; do not modify image, benchmark, or generated-plan artifacts.
- **GUD-001**: Record baseline first, add tests in small logical groups, then run focused tests, full AI suite, Ruff, and two-axis review.
- **PAT-001**: Prefer parameterized contract cases over duplicating test bodies; preserve clear case names for diagnosis.

## 2. Implementation Steps

### Implementation Phase 1 — map and cover uncovered parser branches

- GOAL-001: Raise behavioral confidence in malformed edit command handling without changing runtime behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Record baseline with `python -m pytest tests/test_edit_commands.py --cov=app.edit_commands --cov-branch --cov-report=term-missing -q` from `services/ai/`; correlate missed lines with `_optional_id`, `_finite_number`, `_program`, and action-specific requirements. | Oui — 32 tests, 89% coverage; 10 missed statements and 8 partial branches reviewed | 2026-10-02 |
| TASK-002 | Extend `services/ai/tests/test_edit_commands.py` with named parameterized invalid cases for malformed IDs, overflow/non-finite numeric values, unsupported/missing opening type, missing furniture catalog ID, malformed room-program container/entry, non-string reply, and field/code diagnostics. | Oui — 16 cas invalides nommés, champs absents/null distingués, ID optionnel et réponse normalisés | 2026-10-02 |

### Implementation Phase 2 — verification and evidence

- GOAL-002: Confirm the test-only changes are deterministic, style-compliant, and do not alter plan outputs.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | Run focused parser tests and branch coverage, then full `services/ai/tests`; run Ruff check/format and `git diff --check`; confirm no production modules or benchmark outputs changed. | Oui — 49 tests ciblés, 915 tests IA complets; Ruff et whitespace passent; 100% statements/branches ciblés | 2026-10-02 |
| TASK-004 | Review the exact test diff against this plan and repository conventions; record Standards/Spec results and any remaining uncovered branches without treating coverage as plan quality. | Oui — revues finales Standards/Spec sans finding; code production et artefacts benchmark inchangés | 2026-10-02 |

## 3. Alternatives

- **ALT-001**: Add a global minimum coverage gate; rejected because coverage is a diagnostic, not a correctness oracle.
- **ALT-002**: Change parser semantics while adding tests; rejected because any behavioral change needs a separate reviewed contract sprint.
- **ALT-003**: Use property-based fuzzing for these bounded error cases; rejected in this sprint because explicit examples provide clearer contract diagnostics.

## 4. Dependencies

- **DEP-001**: `services/ai/app/edit_commands.py` v1 parser and `EditCommandError` contract.
- **DEP-002**: Existing pytest and pytest-cov setup in `services/ai/`.
- **DEP-003**: `docs/sprints/4-command-contracts.md` for the parent edit-command contract.

## 5. Files

- **FILE-001**: `services/ai/tests/test_edit_commands.py` — parameterized parser boundary regression tests.
- **FILE-002**: `plan/feature-edit-command-boundaries-1.md` — this implementation plan.
- **FILE-003**: `docs/sprints/4-command-contracts.md` — sprint tracking and evidence.

## 6. Testing

- **TEST-001**: Focused parser suite and branch-coverage report before/after.
- **TEST-002**: Full AI test suite from `services/ai/`.
- **TEST-003**: Ruff check/format on the changed test and `git diff --check`.
- **TEST-004**: Standards/Spec review confirms tests match v1 contract and no production/benchmark files are modified.

## 7. Risks & Assumptions

- **RISK-001**: Existing contract behavior could be surprising; tests must pin documented parser behavior only and report ambiguity rather than silently define new behavior.
- **RISK-002**: Very large Python integers raise during float normalization; tests must verify deterministic domain error translation rather than leak `OverflowError`.
- **ASSUMPTION-001**: A missing optional `rotation_deg` on furniture addition intentionally normalizes to `0.0`, as already asserted by the current suite.
- **ASSUMPTION-002**: Coverage is measured with the project's installed Python/coverage versions and is used only to locate branches.

## 8. Related Specifications / Further Reading

- `docs/sprints/4-command-contracts.md` — typed command contract and edit action behavior.
- `services/ai/app/edit_commands.py` — implementation under test.
- `services/ai/tests/test_edit_commands.py` — existing contract tests.
