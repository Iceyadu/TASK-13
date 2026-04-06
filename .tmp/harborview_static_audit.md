# HarborView Property Operations Portal Static Audit

## 1. Verdict
- Overall conclusion: **Fail**

## 2. Scope and Static Verification Boundary
- Reviewed: repository documentation, FastAPI entry points, routers, models, schemas, services, Vue routes/views/stores/services, Docker/config files, unit tests, and API tests under `repo/`.
- Not reviewed: runtime behavior, browser rendering, network calls, container orchestration, database state after execution, backup/restore execution, or generated artifacts.
- Intentionally not executed: project startup, Docker, tests, migrations, service worker behavior, backup/restore commands.
- Manual verification required for: actual browser/PWA install behavior, real offline replay behavior, real backup/restore execution, and runtime rendering fidelity.

## 3. Repository / Requirement Mapping Summary
- Prompt core goal: an offline-capable property-operations portal covering local auth, role-based navigation, resident billing/self-service, listings with media validation, service-order state machine, configurable homepage content with 10% canary rollout, optimistic locking/conflict resolution, auditability, CSV/PDF reporting, and offline-local backups.
- Main implementation areas mapped: FastAPI routers for auth/users/residents/properties/billing/payments/credits/orders/listings/media/content/rollout/backup/reports; Vue views for dashboard, billing, orders, listings, payments, credits, addresses, admin content/users/backup; unit and API tests.

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- Conclusion: **Partial Pass**
- Rationale: The repo has a usable `README`, `.env.example`, Docker definitions, and API spec, so a reviewer can statically map entry points and config. However, several docs-to-code details are inconsistent, and the README overstates frontend/test structure.
- Evidence: `repo/README.md:44`, `repo/README.md:100`, `repo/.env.example:1`, `repo/backend/app/main.py:61`, `repo/README.md:165`, `repo/README.md:172`, `repo/unit_tests/frontend/setup.ts:1`
- Manual verification note: Runtime startup/testing still requires manual execution.

#### 1.2 Material deviation from the Prompt
- Conclusion: **Fail**
- Rationale: The backend covers many prompt domains, but the delivered portal materially misses key user-facing flows: staff billing operations UI, staff order-fulfillment UI, fully wired optimistic-locking UX, and working media-backed listings in the client.
- Evidence: `repo/frontend/src/views/BillingView.vue:46`, `repo/frontend/src/views/OrdersView.vue:4`, `repo/frontend/src/views/OrdersView.vue:70`, `repo/frontend/src/views/ListingsView.vue:38`, `repo/frontend/src/views/AddressesView.vue:122`, `docs/api-spec.md:13`

### 2. Delivery Completeness

#### 2.1 Coverage of explicit core requirements
- Conclusion: **Fail**
- Rationale: Core backend pieces exist, but important explicit prompt requirements are only partial or missing in delivery: backup/restore does not include media files, client-side role navigation is incomplete, listings media cannot render correctly, and staff billing/order workflows are not fully delivered in the UI.
- Evidence: `repo/backend/app/routers/backup.py:66`, `repo/backend/app/routers/backup.py:273`, `docs/design.md:842`, `repo/frontend/src/router/index.ts:6`, `repo/frontend/src/components/layout/AppNavbar.vue:23`, `repo/frontend/src/views/ListingsView.vue:42`, `repo/backend/app/schemas/listing.py:68`
- Manual verification note: None needed to confirm these static gaps.

#### 2.2 Basic end-to-end deliverable vs partial/demo
- Conclusion: **Partial Pass**
- Rationale: This is a multi-module application rather than a fragment, but several flows remain effectively partial because backend capability is not exposed or is mismatched in the shipped frontend.
- Evidence: `repo/backend/app/main.py:97`, `repo/frontend/src/router/index.ts:4`, `repo/frontend/src/views/CreditsView.vue:102`, `repo/frontend/src/views/BillingView.vue:46`, `repo/frontend/src/views/OrdersView.vue:63`

### 3. Engineering and Architecture Quality

#### 3.1 Structure and module decomposition
- Conclusion: **Pass**
- Rationale: The project uses clear separation across models, schemas, routers, services, frontend views/stores/services, and tests. Core domains are not piled into a single file.
- Evidence: `repo/backend/app/main.py:13`, `repo/backend/app/models/`, `repo/backend/app/routers/`, `repo/backend/app/services/`, `repo/frontend/src/router/index.ts:4`, `repo/README.md:134`

#### 3.2 Maintainability and extensibility
- Conclusion: **Partial Pass**
- Rationale: The backend is reasonably decomposed, but maintainability is weakened by duplicated per-endpoint idempotency/conflict logic, frontend/backend contract mismatches, and UI routes that do not share a consistent authorization model.
- Evidence: `repo/backend/app/routers/listings.py:145`, `repo/backend/app/routers/residents.py:116`, `repo/backend/app/middleware/idempotency.py:12`, `repo/frontend/src/router/index.ts:23`, `repo/frontend/src/components/layout/AppNavbar.vue:23`

### 4. Engineering Details and Professionalism

#### 4.1 Error handling, logging, validation, API design
- Conclusion: **Partial Pass**
- Rationale: There is meaningful validation for passwords, media types, and optimistic locking, plus audit logging hooks. However, some paths are incomplete or unsafe: payment evidence uses a broken media storage contract, backup readiness/status semantics are weak, and several write flows are not safely wired in the client.
- Evidence: `repo/backend/app/schemas/user.py:23`, `repo/backend/app/routers/media.py:42`, `repo/backend/app/services/audit_service.py:11`, `repo/backend/app/routers/payments.py:143`, `repo/backend/app/routers/media.py:148`, `repo/backend/app/routers/health.py:17`

#### 4.2 Product/service realism vs demo
- Conclusion: **Partial Pass**
- Rationale: The codebase resembles a real product more than a toy, but important flows still stop at “API exists” rather than complete product delivery, especially for staff operations and media-backed listings.
- Evidence: `repo/backend/app/routers/billing.py:235`, `repo/backend/app/routers/orders.py:225`, `repo/frontend/src/views/BillingView.vue:46`, `repo/frontend/src/views/OrdersView.vue:70`

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business-goal and constraint fit
- Conclusion: **Fail**
- Rationale: The implementation understands the major business domains, but it does not fully meet the prompt’s operational constraints for kiosk/offline security, full conflict-resolution delivery, media-rich listings, staff workflows, and backup completeness.
- Evidence: `repo/frontend/src/stores/auth.ts:14`, `repo/frontend/src/stores/auth.ts:24`, `repo/frontend/src/services/offlineCache.ts:199`, `repo/frontend/src/views/ListingsView.vue:42`, `repo/backend/app/routers/backup.py:149`

### 6. Aesthetics (frontend/full-stack)

#### 6.1 Visual and interaction quality
- Conclusion: **Partial Pass**
- Rationale: The UI is coherent and responsive at the file level, with consistent spacing/cards/badges. Still, role-specific navigation is inconsistent, some interactions silently fail, and media rendering for listings is statically broken.
- Evidence: `repo/frontend/src/views/DashboardView.vue:30`, `repo/frontend/src/components/layout/AppSidebar.vue:13`, `repo/frontend/src/components/layout/AppNavbar.vue:23`, `repo/frontend/src/views/ListingsView.vue:134`
- Manual verification note: Final visual quality and responsive behavior require browser verification.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

1. **Backups exclude uploaded media and restore only the database**
- Severity: **Blocker**
- Conclusion: Backup/restore is incomplete for a portal whose resident payment evidence and listing media are stored on disk.
- Evidence: `repo/backend/app/routers/backup.py:66`, `repo/backend/app/routers/backup.py:149`, `repo/backend/app/routers/backup.py:273`, `docs/design.md:842`, `docs/design.md:843`
- Impact: A restore can bring back database rows while losing the actual uploaded files they reference, breaking statements, payment evidence review, and listings media after recovery.
- Minimum actionable fix: Include uploads/media in the backup artifact and restore workflow, then add integrity verification for both DB and file payloads.

### High

2. **Listings media is not consumable by the delivered frontend**
- Severity: **High**
- Conclusion: Uploaded listing media cannot reliably display in the shipped UI because the frontend expects fields and endpoints the backend does not provide.
- Evidence: `repo/frontend/src/views/ListingsView.vue:40`, `repo/frontend/src/views/ListingsView.vue:42`, `repo/frontend/src/views/ListingsView.vue:48`, `repo/backend/app/routers/media.py:140`, `repo/backend/app/schemas/listing.py:68`, `repo/backend/app/schemas/listing.py:96`
- Impact: A core marketplace requirement, embedded media uploads with immediate feedback and visible published media, is broken at delivery level.
- Minimum actionable fix: Align the contract by returning media metadata needed for rendering and use the actual backend file endpoint consistently.

3. **Payment-evidence media records use a storage path format incompatible with the media download endpoint**
- Severity: **High**
- Conclusion: Payment uploads store relative paths, but media file retrieval reads them as direct filesystem paths.
- Evidence: `repo/backend/app/routers/payments.py:143`, `repo/backend/app/routers/payments.py:153`, `repo/backend/app/routers/media.py:148`
- Impact: Payment evidence may be persisted in the database but still be undisplayable/unrecoverable through the media API, undermining accounting review and audit traceability.
- Minimum actionable fix: Normalize all media storage paths to a single convention and resolve them relative to `UPLOAD_DIR` in download/delete code.

4. **Role-based navigation and route guarding are incomplete**
- Severity: **High**
- Conclusion: Non-admin routes lack role metadata, while the navbar exposes links broadly to roles that cannot use them.
- Evidence: `repo/frontend/src/router/index.ts:6`, `repo/frontend/src/router/index.ts:13`, `repo/frontend/src/components/layout/AppNavbar.vue:23`, `repo/frontend/src/components/layout/AppSidebar.vue:15`, `repo/backend/app/routers/billing.py:177`
- Impact: The prompt explicitly requires role-based navigation; maintenance/accounting users can reach pages that immediately fail with authorization errors.
- Minimum actionable fix: Add route-level role metadata for all protected pages and align navbar/sidebar visibility with backend authorization.

5. **Staff order-fulfillment workflow is not delivered in the frontend**
- Severity: **High**
- Conclusion: The backend supports transitions and assignment, but the shipped orders view only creates resident orders and lists milestones.
- Evidence: `repo/backend/app/routers/orders.py:178`, `repo/backend/app/routers/orders.py:225`, `repo/frontend/src/views/OrdersView.vue:4`, `repo/frontend/src/views/OrdersView.vue:70`
- Impact: Maintenance/Dispatcher and managers cannot fulfill orders through the portal as required.
- Minimum actionable fix: Add staff UI for assignment, transition actions, validation feedback, and milestone progression.

6. **Staff billing/reconciliation operations are not delivered in the frontend**
- Severity: **High**
- Conclusion: BillingView only lists bills and local PDF generation; it does not expose fee-rule management, generation, reconciliation, late-fee operations, or staff reconciliation flows.
- Evidence: `repo/frontend/src/views/BillingView.vue:46`, `repo/backend/app/routers/billing.py:36`, `repo/backend/app/routers/billing.py:235`, `repo/backend/app/routers/billing.py:269`
- Impact: A core business objective for accounting/property staff is only partially delivered.
- Minimum actionable fix: Add staff-facing billing screens for fee items, bill generation, reconciliation, overdue management, and financial exports.

7. **Client optimistic-locking support is inconsistent and breaks required write flows**
- Severity: **High**
- Conclusion: The API requires `If-Match` for updates, but key frontend update flows do not send it, and bulk listing status silently uses the wrong pattern.
- Evidence: `docs/api-spec.md:13`, `repo/backend/app/routers/residents.py:206`, `repo/frontend/src/views/AddressesView.vue:122`, `repo/frontend/src/views/ListingsView.vue:134`, `repo/backend/app/routers/listings.py:180`
- Impact: Offline conflict handling and even ordinary updates are not fully usable through the delivered client.
- Minimum actionable fix: Carry record versions in the UI, send `If-Match` on every update path, and use the actual bulk endpoint for bulk status changes.

8. **Credit approval can apply one resident’s credit to another resident’s bill**
- Severity: **High**
- Conclusion: Approval logic validates only that the target bill exists, not that it belongs to the same resident or original charge context.
- Evidence: `repo/backend/app/routers/credits.py:173`, `repo/backend/app/routers/credits.py:177`, `repo/backend/app/models/billing.py:85`
- Impact: Cross-resident financial corruption is possible through admin actions, breaking data isolation and reconciliation integrity.
- Minimum actionable fix: Verify resident/bill/order ownership alignment before approval and reject mismatched applications.

9. **Access and refresh tokens are stored in plain localStorage despite shared-device usage**
- Severity: **High**
- Conclusion: The client stores bearer tokens unencrypted in browser storage.
- Evidence: `repo/frontend/src/stores/auth.ts:14`, `repo/frontend/src/stores/auth.ts:15`, `repo/frontend/src/stores/auth.ts:24`, `repo/frontend/src/stores/auth.ts:25`
- Impact: On shared kiosks/tablets, tokens are trivially recoverable from browser storage, weakening local-first security for a role-sensitive portal.
- Minimum actionable fix: Move tokens to a more defensible storage strategy and ensure kiosk/session logout invalidates server-side refresh state.

### Medium

10. **Offline retry counter does not reliably increment**
- Severity: **Medium**
- Conclusion: The retry-count update expression uses nullish-coalescing in a way that leaves existing counts unchanged.
- Evidence: `repo/frontend/src/services/offlineCache.ts:198`
- Impact: Retry limits and queue aging can fail, making offline replay behavior less predictable.
- Minimum actionable fix: Update the expression so existing `retryCount` values increment deterministically.

11. **Frontend logout does not call the backend logout endpoint**
- Severity: **Medium**
- Conclusion: Logout clears client storage but does not revoke the refresh token server-side.
- Evidence: `repo/frontend/src/components/layout/AppNavbar.vue:10`, `repo/frontend/src/stores/auth.ts:38`, `repo/backend/app/routers/auth.py:64`
- Impact: Tokens remain valid longer than the UI suggests, which is especially risky on shared devices.
- Minimum actionable fix: Call `/auth/logout` with the refresh token before clearing client state.

12. **Readiness endpoint returns a success response body even on DB failure**
- Severity: **Medium**
- Conclusion: `/health/ready` returns a JSON `not_ready` payload instead of an error status.
- Evidence: `repo/backend/app/routers/health.py:17`
- Impact: External health checks can misclassify an unhealthy backend as ready.
- Minimum actionable fix: Return a non-2xx status when database connectivity fails.

13. **Frontend test suite is effectively absent**
- Severity: **Medium**
- Conclusion: `package.json` advertises frontend tests, but the repo only contains a setup file and no actual frontend test cases or vitest config in the tracked files.
- Evidence: `repo/frontend/package.json:10`, `repo/unit_tests/frontend/setup.ts:1`
- Impact: Major UI, offline, and route-guard regressions can ship undetected.
- Minimum actionable fix: Add frontend tests for auth guards, offline queueing, conflict resolution UI, and critical role-based screens.

14. **Documentation overstates delivered frontend/test structure**
- Severity: **Medium**
- Conclusion: README claims a frontend test area and compressed counts that do not match the tracked files.
- Evidence: `repo/README.md:165`, `repo/README.md:170`, `repo/unit_tests/frontend/setup.ts:1`, `repo/API_tests/test_admin_features.py:1`
- Impact: Reviewers get an overly optimistic picture of delivered verification surface.
- Minimum actionable fix: Update README counts/scope to match the repository exactly.

## 6. Security Review Summary
- Authentication entry points: **Partial Pass**. JWT login/refresh/logout/password-change routes exist and password complexity is validated. Evidence: `repo/backend/app/routers/auth.py:25`, `repo/backend/app/schemas/auth.py:33`, `repo/backend/app/services/auth_service.py:23`.
- Route-level authorization: **Partial Pass**. Backend role dependencies are broadly used, but frontend route guarding is incomplete for non-admin pages. Evidence: `repo/backend/app/dependencies.py:41`, `repo/backend/app/routers/users.py:25`, `repo/frontend/src/router/index.ts:6`.
- Object-level authorization: **Partial Pass**. Bills/payments/credits/orders have ownership helpers, but credit approval lacks same-resident validation and some tests skip cross-user cases. Evidence: `repo/backend/app/utils/ownership.py:32`, `repo/backend/app/routers/credits.py:173`, `repo/API_tests/test_object_auth.py:55`.
- Function-level authorization: **Partial Pass**. Sensitive admin functions are mostly protected, but logout revocation is bypassed by the client and transition UI is missing for authorized staff. Evidence: `repo/backend/app/routers/backup.py:131`, `repo/frontend/src/components/layout/AppNavbar.vue:10`.
- Tenant / user data isolation: **Partial Pass**. Resident scoping exists for bills/payments/credits/orders, but cross-resident credit application is a concrete integrity flaw. Evidence: `repo/backend/app/routers/billing.py:181`, `repo/backend/app/routers/payments.py:119`, `repo/backend/app/routers/credits.py:173`.
- Admin / internal / debug protection: **Pass**. Admin-only user, backup, audit, and rollout routes are statically protected. Evidence: `repo/backend/app/routers/users.py:30`, `repo/backend/app/routers/backup.py:106`, `repo/backend/app/routers/audit.py:27`, `repo/backend/app/routers/rollout.py:20`.

## 7. Tests and Logging Review
- Unit tests: **Partial Pass**. Backend unit tests cover password validation, auth hashing/token creation, encryption helpers, and state-machine basics, but not many core services/endpoints. Evidence: `repo/unit_tests/backend/test_auth_service.py:12`, `repo/unit_tests/backend/test_order_state_machine.py:22`.
- API / integration tests: **Partial Pass**. There is meaningful API coverage for auth, billing, orders, conflicts, content/rollout, media, and object authorization, but frontend delivery issues and some high-risk integrity paths are untested. Evidence: `repo/API_tests/test_service_orders.py:96`, `repo/API_tests/test_offline_conflicts.py:47`, `repo/API_tests/test_admin_features.py:288`.
- Logging categories / observability: **Partial Pass**. Backend sets structured logger names and audit logging exists, but frontend uses `console.log`, and there is no clear category strategy beyond basic app logging. Evidence: `repo/backend/app/main.py:5`, `repo/backend/app/services/audit_service.py:11`, `repo/frontend/src/services/syncManager.ts:42`.
- Sensitive-data leakage risk in logs / responses: **Partial Pass**. API responses mask resident contact data by role, but plaintext bearer tokens and many verbose test/client prints exist; no static evidence shows secret fields logged server-side. Evidence: `repo/backend/app/routers/residents.py:46`, `repo/frontend/src/stores/auth.ts:24`, `repo/API_tests/conftest.py:38`.

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests exist: backend pytest files under `repo/unit_tests/backend/`. Evidence: `repo/run_tests.sh:36`, `repo/unit_tests/backend/test_password_validation.py:1`.
- API/integration tests exist: HTTP-based pytest files under `repo/API_tests/`. Evidence: `repo/run_tests.sh:54`, `repo/API_tests/conftest.py:14`.
- Frontend tests do not meaningfully exist beyond setup scaffolding. Evidence: `repo/frontend/package.json:10`, `repo/unit_tests/frontend/setup.ts:1`.
- Test commands are documented. Evidence: `repo/README.md:100`, `repo/run_tests.sh:74`.

### 8.2 Coverage Mapping Table
| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Login / token issuance | `repo/API_tests/test_auth.py`, `repo/unit_tests/backend/test_auth_service.py:28` | Valid login returns token; token helpers create JWTs | basically covered | No frontend auth-flow tests; logout path not covered | Add UI auth/refresh/logout tests |
| Password policy | `repo/unit_tests/backend/test_password_validation.py:17` | Rejects short/no-uppercase/no-digit/no-special | sufficient | No end-to-end password-change/reset tests | Add API tests for `/auth/password` and `/users/{id}/reset-password` |
| Order state machine and milestones | `repo/API_tests/test_service_orders.py:96`, `repo/unit_tests/backend/test_order_state_machine.py:22` | Full transition chain, invalid transitions, milestones count | sufficient | No frontend staff workflow tests | Add frontend staff transition tests |
| Offline conflict response shape | `repo/API_tests/test_offline_conflicts.py:47` | 409 body contains versions, your/server data, changed fields | basically covered | No frontend replay/conflict UI tests | Add Vitest/component tests for resolver and queue replay |
| Listing bulk status API | `repo/API_tests/test_listings_media.py:171` | POST `/listings/bulk-status` updates 3 listings | basically covered | Delivered frontend does not call this endpoint correctly | Add frontend integration test for bulk publish/unpublish |
| Media validation | `repo/API_tests/test_listings_media.py:218` | JPG/PNG/MP4 accepted, GIF/oversize rejected | basically covered | No test covers listing-page rendering contract | Add contract test for listing media response fields and file URLs |
| Payment evidence submission | `repo/API_tests/test_payment_evidence.py:79` | JPEG upload accepted, missing file rejected, verify path covered | basically covered | No test covers retrieval of stored evidence file | Add API test for `/media/{id}/file` after payment upload |
| Object-level authorization | `repo/API_tests/test_object_auth.py:31` | Resident blocked from other bills/PDFs/admin endpoints | insufficient | Several cases skip when seed data is not favorable; no credit-application integrity test | Add deterministic fixtures for cross-user access and cross-resident credit approval |
| Backup / restore | `repo/API_tests/test_admin_features.py:484` | Record creation and wrong-passphrase/not-found checks | insufficient | No test verifies files/media are included or restore rebuilds complete system state | Add backup artifact-content test and restore completeness test |
| Frontend role-based navigation | none | none | missing | No frontend coverage for role nav/route guards | Add component/router tests for each role |

### 8.3 Security Coverage Audit
- Authentication: **Basically covered** by API and unit tests for login/refresh/token helpers, but logout invalidation from the frontend is not covered.
- Route authorization: **Partially covered** by object/admin API tests, but not by frontend route/nav tests.
- Object-level authorization: **Insufficient** because tests skip some cross-user cases and do not cover cross-resident credit application.
- Tenant / data isolation: **Insufficient**; resident bill/payment/credit/order scoping is tested, but financial cross-link integrity is not.
- Admin / internal protection: **Basically covered** for users/backup via API tests.

### 8.4 Final Coverage Judgment
- **Partial Pass**
- Major backend happy paths and some security checks are covered, but uncovered UI, backup-completeness, media-contract, and cross-resident financial-integrity risks mean tests could still pass while severe delivery defects remain.

## 9. Final Notes
- The repository shows serious implementation effort and meaningful backend coverage.
- The decisive failures are not stylistic; they are concrete delivery gaps and contract flaws that materially affect recovery, security, listings media, role navigation, and staff operations.
