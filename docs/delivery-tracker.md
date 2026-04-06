# HarborView Property Operations Portal - Delivery Tracker

## Current Stage

**Phase: Backend Foundation Implementation**
Status: GO - Backend verified and running

## Current Focus

- Backend foundation fully implemented and verified
- All 82 API endpoints registered and loading
- JWT auth with bcrypt hashing operational
- All 5 roles seeded with test accounts
- Property, units, resident seed data in place
- Field encryption (Fernet) and data masking operational
- Audit logging on auth events operational
- 28 unit tests passing, 16 API tests passing (44 total)
- Docker Compose (db + backend) running and verified

## Hard-Fail Risks

| # | Risk | Severity | Status |
|---|------|----------|--------|
| 1 | Offline sync with optimistic locking and conflict resolution UI (side-by-side diff + merge fields) | HIGH | Open |
| 2 | Strict order state machine with idempotency keys and immutable audit logs | HIGH | Open |
| 3 | Controlled rollout toggle (10% canary for site content) | MEDIUM | Open |
| 4 | Encrypted local cache on client (IndexedDB + Web Crypto) | MEDIUM | Open |
| 5 | Nightly encrypted backup with offline restore workflow | MEDIUM | Open |
| 6 | Docker startup must be truly runnable and verified end-to-end | HIGH | Open |
| 7 | Local PDF generation for receipts and statements | LOW | Open |
| 8 | Video upload validation and storage (MP4 up to 200 MB) | MEDIUM | Open |

## Required Package Structure

```
w1t13/
  docs/
    design.md
    api-spec.md
    questions.md
    delivery-tracker.md
  repo/
    README.md
    docker-compose.yml
    run_tests.sh
    backend/          (FastAPI + PostgreSQL)
    frontend/         (Vue.js)
  sessions/
    develop-1.json
  metadata.json
```

## Required Docs

| Document | Location | Status |
|----------|----------|--------|
| design.md | docs/design.md | Not started |
| api-spec.md | docs/api-spec.md | Not started |
| questions.md | docs/questions.md | Not started |
| delivery-tracker.md | docs/delivery-tracker.md | Created |
| README.md | repo/README.md | Not started |

## Auth Decision

- **Local username/password only** - confirmed by prompt ("local username and password", "security is local-first")
- No OAuth, SSO, or external identity provider
- No SMTP email verification (not mentioned in prompt; overdue reminders are in-app only)
- Password requirements: minimum 12 characters with complexity checks, strong hashing (bcrypt/argon2)

## Open Business Ambiguities

| # | Question | My Understanding | Solution |
|---|----------|-----------------|----------|
| 1 | What happens when a Resident uploads payment evidence (scanned check)? | Staff manually reviews and records the payment. No automated payment processing. | Manual review workflow: upload -> staff review -> payment recorded. |
| 2 | Are refunds actual money returns or credit-only? | Credits applied to future billing cycles. Prompt says "request refunds as credits." | Credit memo records that reduce next billing cycle balance. |
| 3 | Can Residents create marketplace listings or only staff? | Staff only. Prompt says "property staff can create and manage." | Only Property Manager and Administrator can create/edit listings. |
| 4 | What does "after-sales credit" mean as a terminal order state? | Post-completion credit/refund adjustment. | State reachable only from "completed," generating a credit memo. |
| 5 | How is 10% canary rollout calculated? | Fixed cohort of flagged staff accounts, not random per-request. | Boolean canary_tester flag on staff user records. |
| 6 | Encrypted at rest - application-level or database-level? | Application-level field encryption (Fernet/AES). | Encrypt sensitive fields before DB write; decrypt on read by role. |
| 7 | What backup encryption method? | No specific method required. | AES-256 via age or GPG on pg_dump output. |
| 8 | Are SSNs ever collected? | No. Prompt says "disallowed by default." | No SSN field in schema; reject SSN-pattern input. |
| 9 | PDF receipts for payments only or also statements? | Both. Residents can "view and download statements." | Generate PDFs for statements and payment confirmations. |
| 10 | Does amenity booking listing require a calendar system? | No. Simple listing with optional date, not a booking engine. | Listing type with optional date field; no calendar UI. |

## Packaging Exclusions

The following must NOT be included in the final package:

- node_modules/
- .venv/
- .next/
- dist/
- .pytest_cache/
- __pycache__/
- .codex/
- .opencode/
- .vscode/
- Runtime or editor cache folders
- AI session conversion scripts
- Database dumps or environment-dependent content

## Delivery Checklist

- [x] Feasibility screening
- [x] Hard-fail risk identification
- [x] Business ambiguity identification (questions.md)
- [x] Auth scope confirmation
- [x] SMTP/email scope confirmation
- [x] Delivery tracker created
- [x] Architecture design (design.md)
- [x] API specification (api-spec.md)
- [x] Questions documented (questions.md)
- [x] Backend foundation - models, schemas, routers, services
- [x] Backend auth - JWT + bcrypt + role-based access
- [x] Backend persistence - auto-migrate + seed data
- [x] Backend security - field encryption + masking + SSN rejection
- [x] Backend audit logging
- [x] Backend health checks
- [x] Docker Compose (db + backend) verified
- [x] Unit tests (28 passing)
- [x] API tests (54 passing)
- [x] Resident self-service (addresses, statements, payments, credits, orders)
- [x] Billing engine (fee items, generation, tax calc, late fees, reconciliation)
- [x] PDF generation (statements, receipts, credit memos via ReportLab)
- [x] CSV export (billing, payments, orders)
- [x] Payment evidence upload with file validation
- [x] Overdue bill detection and late fee application
- [x] Listings lifecycle (draft, publish, unpublish, archive, bulk status)
- [x] Media uploads with magic-byte validation (JPG, PNG, MP4)
- [x] Media size enforcement (10MB image, 200MB video)
- [x] Listing-media attachment and removal
- [x] Service order state machine (8 states, key-node validation)
- [x] Order idempotency (create + transition)
- [x] Immutable milestones with timestamps
- [x] Role-based transition permissions
- [x] Resident order tracking (auto-filter, milestones)
- [x] Offline: encrypted IndexedDB cache (AES-256-GCM via Web Crypto)
- [x] Offline: FIFO retry queue with idempotency keys
- [x] Offline: auto-replay on reconnect with backoff
- [x] Offline: 409 Conflict responses on all PUT endpoints (8 routers, 12 endpoints)
- [x] Offline: side-by-side diff ConflictResolver component
- [x] Offline: keep-mine / keep-theirs / merge-fields resolution
- [x] Admin: content modules (carousel, tiles, banners) with sections CRUD
- [x] Admin: preview mode (real, no side effects)
- [x] Admin: controlled rollout (canary flag, stats endpoint, 10% deterministic)
- [x] Admin: publish auto-archives old, canary auto-archives old
- [x] Admin: backup with real pg_dump + Fernet encryption
- [x] Admin: 30-day retention cleanup
- [x] Admin: restore with passphrase validation + pg_restore
- [x] README.md
- [x] metadata.json
- [ ] Frontend implementation (views)
- [ ] Session export
- [ ] Final verification (full stack Docker + test execution)
- [ ] Package cleanup (exclusions removed)
