---
goal: Prove stale-plan edit conflicts across the authenticated HTTP, inline-job, and PostgreSQL revision pipeline
version: 1.0
date_created: 2026-10-02
last_updated: 2026-10-02
owner: A-AI
status: 'In progress'
tags: [feature, testing, integration, postgres, 2d]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

Add a deterministic integration test that starts an authenticated 2D edit through the HTTP API, pauses the fake AI response, commits a newer editor revision to PostgreSQL, then verifies that the stale edit job fails with `revision_conflict` and cannot replace the current plan. No external model/provider is called.

## 1. Requirements & Constraints

- **REQ-001**: Exercise `POST /api/v1/projects/{id}/edit`, asynchronous inline edit processing, `jobs` persistence, and `project.SaveRevision` against real PostgreSQL.
- **REQ-002**: Use a fake local AI HTTP server with a deterministic response and synchronization barrier; do not incur model or network-provider cost.
- **REQ-003**: Establish a newer plan revision while the fake AI call is blocked, then release it and prove compare-and-swap rejects the stale base revision.
- **REQ-004**: Verify job terminal state/error, current revision, revision count, and the exact current plan document after the conflict.
- **REQ-005**: In the dedicated PostgreSQL CI job, database-backed test helpers must fail instead of skip when the required database is missing, unreachable, or unmigrated; ordinary local `go test` runs may continue to skip without a database.
- **SEC-001**: Use a unique test org/project and cleanup via existing test helpers; never point the test at an implicit database or mutate shared fixture rows.
- **CON-001**: Integration test may skip when `DATABASE_URL` is absent/unreachable/schema is not migrated, following existing `testDB`/`idorTestServer` conventions.
- **CON-002**: Tests must not invoke Gemini, Together, or other external model services.
- **GUD-001**: Keep test orchestration bounded with request contexts/timeouts and explicit channel synchronization rather than sleeps.
- **PAT-001**: Reuse existing test service constructors and HTTP auth helpers; test observable API/job/database contracts without changing production behavior unless the test proves a defect.

## 2. Implementation Steps

### Implementation Phase 1 — deterministic end-to-end conflict test

- GOAL-001: Reproduce a stale AI edit racing with a newer editor save and assert persisted conflict behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Inspect `internal/httpapi/handlers_api.go:handleEditPlan/processEditPlan`, `internal/jobs/service.go:RunInlineEdit`, `internal/project/service.go:SaveRevision`, and existing PostgreSQL test fixtures; document exact request and job response fields. | Oui — flux et contrat CAS tracés avant implémentation | 2026-10-02 |
| TASK-002 | Add a focused test helper or test-local server wiring in `internal/httpapi/handlers_api_test.go` with a fake AI endpoint that blocks `/v1/edit` until released and returns a deterministic valid `plan_document`; preserve the existing skip behavior for unavailable PostgreSQL. | Oui — serveur local avec token interne et barrière channel | 2026-10-02 |
| TASK-003 | Add an integration test that registers a fresh user/project, persists a baseline revision, starts authenticated `POST /api/v1/projects/{id}/edit`, saves a second editor revision while AI is blocked, releases AI, polls the job endpoint, and asserts `failed` + `revision_conflict`, current revision unchanged from the editor save, exact document preserved, and exactly two revisions. | Oui — assertions HTTP/job/DB et teardown borné; exécution DB non disponible localement | 2026-10-02 |

### Implementation Phase 2 — verification and closure

- GOAL-002: Prove the new test passes against PostgreSQL and close TASK-007 only with that evidence.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Validate plan identifiers/front matter and run formatting plus targeted Go tests; attempt local PostgreSQL execution and retain the exact environment result without treating a skip as proof. | Partiel — packages passent; test d'intégration sauté (`DATABASE_URL` absente, Docker Engine indisponible) | 2026-10-02 |
| TASK-005 | Run `go test ./internal/httpapi ./internal/jobs ./internal/project`, inspect `git diff --check`, and perform Standards and Spec reviews of the change. | Oui — suites ciblées, `go vet`, YAML et whitespace validés; revues sans finding résiduel | 2026-10-02 |
| TASK-006 | Add `.github/workflows/test.yml:postgres-integration` with a PostgreSQL 16 health-checked service, run `go run ./cmd/api -migrate-only`, then execute the HTTP/jobs/project suites with `DATABASE_URL` set so the regression test is not skipped in CI. | Oui — service PostgreSQL séparé et migration avant les tests | 2026-10-02 |
| TASK-007 | Update `docs/sprints/4-command-contracts.md` with outcome, environment, exact command and whether PostgreSQL execution occurred; keep the command-contracts TASK-007 open until a real DB-backed API/job test run succeeds. | En cours — vérifications locales et garde-fou CI consignés; preuve PostgreSQL réelle encore requise | 2026-10-02 |
| TASK-008 | Set `REQUIRE_DATABASE_TESTS=1` only in `.github/workflows/test.yml:postgres-integration`; make PostgreSQL test helpers in `internal/httpapi/handlers_api_test.go` and `internal/project/service_test.go` fail on missing/unreachable/unmigrated DB in required mode, and verify optional local mode still skips. | Oui — tests en sous-processus confirment l'issue réelle skip local / échec strict dans les deux packages | 2026-10-02 |

## 3. Alternatives

- **ALT-001**: Extend only `project.SaveRevision` unit tests; rejected because it does not prove HTTP authentication, job transitions, error mapping, or end-to-end current-revision preservation.
- **ALT-002**: Call the external Gemini/Together provider; rejected because it is non-deterministic, costly, and unnecessary for validating the persistence contract.
- **ALT-003**: Use sleep-based race timing; rejected because barriers provide deterministic ordering and avoid flaky tests.

## 4. Dependencies

- **DEP-001**: A migrated PostgreSQL test database supplied through `DATABASE_URL`.
- **DEP-002**: Existing Go `pgx` driver and local `httptest` package; no new library required.
- **DEP-003**: Auth, billing, jobs, project services and the `/api/v1/jobs/{id}` endpoint.

## 5. Files

- **FILE-001**: `internal/httpapi/handlers_api_test.go` — database-backed authenticated API/job integration scenario and fake AI server.
- **FILE-002**: `docs/sprints/4-command-contracts.md` — sprint checklist and evidence.
- **FILE-003**: `plan/feature-postgres-cas-http-job-1.md` — executable sprint plan and status.
- **FILE-004**: `.github/workflows/test.yml` — reproducible PostgreSQL-backed integration execution in CI.

## 6. Testing

- **TEST-001**: With PostgreSQL, API edit is accepted while fake AI is blocked; a newer editor revision is saved; releasing stale AI causes job failure `revision_conflict`.
- **TEST-002**: After conflict, project current revision/document remain the intervening editor revision and revision count is unchanged by the stale AI result.
- **TEST-003**: Without PostgreSQL, integration suite skips using the repository convention; this is not reported as a passing integration proof.
- **TEST-004**: Run focused and package-level Go tests plus `gofmt` and `git diff --check`.
- **TEST-005**: Exercise `databaseUnavailable` in an isolated Go test subprocess for both flag states; assert that optional mode exits successfully with a skip and required mode exits nonzero with the required-database diagnostic. Run real database-backed tests in CI to prove PostgreSQL connectivity and migrated schema.

## 7. Risks & Assumptions

- **RISK-001**: The test DB may be unavailable in this host, in which case implementation can be written and compile-checked but the key acceptance criterion remains unverified.
- **RISK-002**: HTTP handler starts background work; test must synchronize fake AI entry, release, and job completion with bounded deadlines and avoid leaking goroutines.
- **ASSUMPTION-001**: Current inline edit path sets `SkipQueue` and runs `processEditPlan` asynchronously, while PostgreSQL persists the job separately from revisions.
- **ASSUMPTION-002**: The existing registration helper seeds quota/subscription state sufficiently for edit API admission; verify while implementing.

## 8. Related Specifications / Further Reading

- `docs/sprints/4-command-contracts.md` — TASK-007 contract and previous verification status.
- `internal/project/service.go` — revision compare-and-swap implementation.
- `internal/httpapi/handlers_api.go` — edit API, background pipeline and job-status endpoints.
- `internal/jobs/service.go` — inline AI call and job persistence.
