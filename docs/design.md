# HarborView Property Operations Portal - Design Document

## 1. Architecture Overview

```
+--------------------------------------------------+
|              Vue.js SPA (TypeScript)              |
|  +------------+  +----------+  +---------------+ |
|  | IndexedDB  |  | Service  |  | Web Crypto    | |
|  | Cache      |  | Worker   |  | (AES-GCM)     | |
|  +------------+  +----------+  +---------------+ |
+--------------------------------------------------+
              |  HTTPS / JSON  |
+--------------------------------------------------+
|              FastAPI (Python)                     |
|  +----------+  +----------+  +-----------------+ |
|  | Auth     |  | Business |  | Background      | |
|  | Layer    |  | Logic    |  | Tasks           | |
|  +----------+  +----------+  +-----------------+ |
+--------------------------------------------------+
              |  asyncpg / SQLAlchemy  |
+--------------------------------------------------+
|              PostgreSQL                           |
|  +----------+  +----------+  +-----------------+ |
|  | Core     |  | Billing  |  | Audit           | |
|  | Tables   |  | Tables   |  | Tables          | |
|  +----------+  +----------+  +-----------------+ |
+--------------------------------------------------+
              |
+--------------------------------------------------+
|  Local Filesystem                                |
|  +-------------------+  +---------------------+  |
|  | Media Uploads     |  | Encrypted Backups   |  |
|  | /data/uploads/    |  | /data/backups/       | |
|  +-------------------+  +---------------------+  |
+--------------------------------------------------+
```

### Technology Stack

| Layer | Technology | Version Target |
|-------|-----------|---------------|
| Frontend | Vue.js 3 + TypeScript | 3.4+ |
| State Management | Pinia | 2.x |
| UI Framework | Vuetify or PrimeVue | Latest stable |
| Build Tool | Vite | 5.x |
| Backend | FastAPI | 0.110+ |
| ORM | SQLAlchemy 2.0 (async) | 2.0+ |
| Database | PostgreSQL | 15+ |
| PDF Generation | WeasyPrint | Latest stable |
| Containerization | Docker + Docker Compose | Latest stable |
| PWA/Offline | Workbox (Service Worker) | Latest stable |

### Deployment Model

- Single on-prem server (or local network)
- Docker Compose orchestration: frontend (Nginx), backend (Uvicorn), database (PostgreSQL)
- No cloud dependencies, no external APIs, no internet requirement
- Media and backups stored on local filesystem volumes

---

## 2. Frontend Modules

### 2.1 Module Map

| Module | Route Prefix | Roles |
|--------|-------------|-------|
| Auth | `/login` | All |
| Dashboard | `/` | All (role-filtered) |
| Resident Profile | `/resident/profile` | Resident |
| Billing & Statements | `/billing` | Resident, Accounting Clerk, Property Manager, Administrator |
| Payment Evidence | `/billing/payments` | Resident, Accounting Clerk |
| Service Orders | `/orders` | All |
| Listings | `/listings` | All (CRUD for staff, read for Resident) |
| Content Management | `/admin/content` | Administrator |
| User Management | `/admin/users` | Administrator |
| System Settings | `/admin/settings` | Administrator |
| Backup Management | `/admin/backup` | Administrator |

### 2.2 Core Frontend Services

| Service | Responsibility |
|---------|---------------|
| AuthService | Login, token storage, role extraction |
| OfflineCacheService | IndexedDB read/write with AES-GCM encryption |
| RetryQueueService | Queue failed writes, replay on reconnect |
| ConflictResolver | Side-by-side diff UI, merge field selection |
| MediaUploader | Client-side validation, chunked upload, progress |
| PDFDownloader | Request and download server-generated PDFs |
| SyncManager | Connectivity detection, sync orchestration |

### 2.3 PWA / Offline Support

- Service Worker registered via `public/sw.js` with stale-while-revalidate caching for static assets
- PWA manifest at `public/manifest.json` for installable mode
- Runtime cache: API GET responses cached in encrypted IndexedDB via response interceptor
- IndexedDB stores: `cached_records` (AES-GCM encrypted), `retry_queue` (encrypted), `sync_metadata`
- Encryption key derived from user password via PBKDF2 (100k iterations, SHA-256), initialized at login
- Connectivity detection via `navigator.onLine` + periodic `/health` ping (15s interval)
- Schema initialization: `Base.metadata.create_all()` on startup (not Alembic migrations)

---

## 3. Backend Modules

### 3.1 Module Map

| Module | Path Prefix | Responsibility |
|--------|------------|----------------|
| auth | `/api/v1/auth` | Login, token issue, password management |
| users | `/api/v1/users` | User CRUD, role assignment |
| residents | `/api/v1/residents` | Resident profile, addresses |
| properties | `/api/v1/properties` | Property and unit management |
| billing | `/api/v1/billing` | Fee rules, bill generation, reconciliation |
| payments | `/api/v1/payments` | Payment evidence, verification |
| credits | `/api/v1/credits` | Credit memos, refund requests |
| orders | `/api/v1/orders` | Service order state machine |
| listings | `/api/v1/listings` | Marketplace CRUD, publish controls |
| media | `/api/v1/media` | File upload, validation, serving |
| content | `/api/v1/content` | Homepage modules, preview, rollout |
| reports | `/api/v1/reports` | PDF receipts, CSV export |
| backup | `/api/v1/backup` | Backup trigger, restore, status |
| health | `/api/v1/health` | Liveness and readiness checks |
| audit | internal | Audit log writes (not directly exposed) |

### 3.2 Middleware Stack

| Middleware | Order | Registration | Purpose |
|-----------|-------|-------------|---------|
| CORS | 1 | `app.add_middleware(CORSMiddleware)` | Restrict to known localhost origins |
| Idempotency | 2 | `app.add_middleware(IdempotencyMiddleware)` | Store idempotency key on request.state |
| Request ID | 3 | `@app.middleware("http")` | UUID per request for tracing |
| Auth/JWT | per-route | `Depends(get_current_user)` | Token validation, role extraction |
| Version Check | per-route | `If-Match` header in PUT handlers | Optimistic locking, 409 on conflict |
| Audit Logger | per-route | `log_audit()` calls in handlers | Log mutations to audit table |

### 3.3 Background Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| Bill Generation | Configurable per property (e.g., 1st of month) | Generate bills for all active residents |
| Late Fee Application | Daily at midnight | Apply late fees to overdue bills past grace period |
| Backup | Nightly (configurable) | pg_dump + encrypt + rotate |
| Backup Retention | Nightly after backup | Delete backups older than 30 days |

---

## 4. PostgreSQL Data Model

### 4.1 Core Tables

```
properties
  id              UUID PK
  name            VARCHAR(255) NOT NULL
  address         TEXT
  billing_day     INTEGER DEFAULT 1
  late_fee_days   INTEGER DEFAULT 10
  late_fee_amount DECIMAL(10,2) DEFAULT 25.00
  tax_rate        DECIMAL(5,4) DEFAULT 0.0600
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

units
  id              UUID PK
  property_id     UUID FK -> properties
  unit_number     VARCHAR(50) NOT NULL
  status          VARCHAR(20) DEFAULT 'active'
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

users
  id              UUID PK
  username        VARCHAR(100) UNIQUE NOT NULL
  password_hash   VARCHAR(255) NOT NULL
  role            VARCHAR(30) NOT NULL
  is_active       BOOLEAN DEFAULT true
  canary_enabled  BOOLEAN DEFAULT false
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

residents
  id              UUID PK
  user_id         UUID FK -> users UNIQUE
  unit_id         UUID FK -> units
  first_name      VARCHAR(100) NOT NULL
  last_name       VARCHAR(100) NOT NULL
  email_encrypted BYTEA
  phone_encrypted BYTEA
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

addresses
  id              UUID PK
  resident_id     UUID FK -> residents
  address_type    VARCHAR(20) NOT NULL  -- 'shipping' | 'mailing'
  line1           VARCHAR(255) NOT NULL
  line2           VARCHAR(255)
  city            VARCHAR(100) NOT NULL
  state           VARCHAR(50) NOT NULL
  zip_code        VARCHAR(20) NOT NULL
  is_primary      BOOLEAN DEFAULT false
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1
```

### 4.2 Billing Tables

```
fee_items
  id              UUID PK
  property_id     UUID FK -> properties
  name            VARCHAR(255) NOT NULL
  amount          DECIMAL(10,2) NOT NULL
  is_taxable      BOOLEAN DEFAULT false
  is_active       BOOLEAN DEFAULT true
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

bills
  id              UUID PK
  resident_id     UUID FK -> residents
  property_id     UUID FK -> properties
  billing_period  VARCHAR(7) NOT NULL   -- 'YYYY-MM'
  due_date        DATE NOT NULL
  subtotal        DECIMAL(10,2) NOT NULL
  tax_total       DECIMAL(10,2) NOT NULL
  late_fee        DECIMAL(10,2) DEFAULT 0.00
  total           DECIMAL(10,2) NOT NULL
  balance_due     DECIMAL(10,2) NOT NULL
  status          VARCHAR(20) DEFAULT 'generated'  -- generated | partially_paid | paid | overdue
  generated_at    TIMESTAMPTZ
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

bill_line_items
  id              UUID PK
  bill_id         UUID FK -> bills
  fee_item_id     UUID FK -> fee_items
  description     VARCHAR(255) NOT NULL
  amount          DECIMAL(10,2) NOT NULL
  tax_amount      DECIMAL(10,2) DEFAULT 0.00
  created_at      TIMESTAMPTZ

payments
  id              UUID PK
  bill_id         UUID FK -> bills
  resident_id     UUID FK -> residents
  amount          DECIMAL(10,2) NOT NULL
  payment_method  VARCHAR(30) NOT NULL  -- 'check' | 'money_order'
  evidence_media_id UUID FK -> media NULL
  status          VARCHAR(20) DEFAULT 'pending'  -- pending | verified | rejected
  reviewed_by     UUID FK -> users NULL
  reviewed_at     TIMESTAMPTZ NULL
  rejection_reason TEXT NULL
  idempotency_key UUID UNIQUE NOT NULL
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

credit_memos
  id              UUID PK
  resident_id     UUID FK -> residents
  bill_id         UUID FK -> bills NULL
  order_id        UUID FK -> orders NULL
  amount          DECIMAL(10,2) NOT NULL
  reason          TEXT NOT NULL
  status          VARCHAR(20) DEFAULT 'pending'  -- pending | approved | applied
  applied_to_bill_id UUID FK -> bills NULL
  created_by      UUID FK -> users
  approved_by     UUID FK -> users NULL
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1
```

### 4.3 Service Order Tables

```
orders
  id              UUID PK
  resident_id     UUID FK -> residents
  property_id     UUID FK -> properties
  title           VARCHAR(255) NOT NULL
  description     TEXT
  category        VARCHAR(50)
  priority        VARCHAR(20) DEFAULT 'normal'
  status          VARCHAR(30) NOT NULL DEFAULT 'created'
  assigned_to     UUID FK -> users NULL
  idempotency_key UUID UNIQUE NOT NULL
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

order_milestones
  id              UUID PK
  order_id        UUID FK -> orders
  from_status     VARCHAR(30)
  to_status       VARCHAR(30) NOT NULL
  changed_by      UUID FK -> users
  notes           TEXT
  created_at      TIMESTAMPTZ

  -- Immutable: no updated_at, no version. Insert-only.
```

### 4.4 Listings Tables

```
listings
  id              UUID PK
  property_id     UUID FK -> properties
  created_by      UUID FK -> users
  title           VARCHAR(255) NOT NULL
  description     TEXT
  category        VARCHAR(50) NOT NULL  -- 'garage_sale' | 'parking_sublet' | 'amenity_addon'
  price           DECIMAL(10,2) NULL
  status          VARCHAR(20) DEFAULT 'draft'  -- draft | published | unpublished | archived
  published_at    TIMESTAMPTZ NULL
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

listing_media
  id              UUID PK
  listing_id      UUID FK -> listings
  media_id        UUID FK -> media
  sort_order      INTEGER DEFAULT 0
  created_at      TIMESTAMPTZ

media
  id              UUID PK
  uploaded_by     UUID FK -> users
  filename        VARCHAR(255) NOT NULL
  original_name   VARCHAR(255) NOT NULL
  mime_type       VARCHAR(50) NOT NULL
  file_size       BIGINT NOT NULL
  storage_path    VARCHAR(500) NOT NULL
  created_at      TIMESTAMPTZ
```

### 4.5 Content Management Tables

```
content_configs
  id              UUID PK
  name            VARCHAR(255) NOT NULL
  status          VARCHAR(20) DEFAULT 'draft'  -- draft | canary | published | archived
  created_by      UUID FK -> users
  published_at    TIMESTAMPTZ NULL
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1

content_sections
  id              UUID PK
  config_id       UUID FK -> content_configs
  section_type    VARCHAR(30) NOT NULL  -- 'carousel' | 'recommended_tiles' | 'announcement_banner'
  title           VARCHAR(255)
  content_json    JSONB NOT NULL
  sort_order      INTEGER DEFAULT 0
  is_active       BOOLEAN DEFAULT true
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  version         INTEGER DEFAULT 1
```

### 4.6 Audit and System Tables

```
audit_logs
  id              UUID PK
  user_id         UUID FK -> users NULL
  action          VARCHAR(50) NOT NULL
  resource_type   VARCHAR(50) NOT NULL
  resource_id     UUID NOT NULL
  old_value       JSONB NULL
  new_value       JSONB NULL
  ip_address      VARCHAR(45)
  idempotency_key UUID NULL
  created_at      TIMESTAMPTZ

  -- Immutable: insert-only, no updates, no deletes.

idempotency_keys
  key             UUID PK
  user_id         UUID FK -> users
  endpoint        VARCHAR(255) NOT NULL
  response_code   INTEGER
  response_body   JSONB
  created_at      TIMESTAMPTZ
  expires_at      TIMESTAMPTZ

backup_records
  id              UUID PK
  filename        VARCHAR(255) NOT NULL
  file_size       BIGINT
  encryption_method VARCHAR(20) NOT NULL
  status          VARCHAR(20) DEFAULT 'completed'  -- in_progress | completed | failed
  started_at      TIMESTAMPTZ
  completed_at    TIMESTAMPTZ
  expires_at      DATE NOT NULL
  created_at      TIMESTAMPTZ
```

### 4.7 Key Indexes

```sql
CREATE INDEX idx_residents_user_id ON residents(user_id);
CREATE INDEX idx_residents_unit_id ON residents(unit_id);
CREATE INDEX idx_units_property_id ON units(property_id);
CREATE INDEX idx_bills_resident_id ON bills(resident_id);
CREATE INDEX idx_bills_property_period ON bills(property_id, billing_period);
CREATE INDEX idx_bills_status ON bills(status);
CREATE INDEX idx_payments_bill_id ON payments(bill_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_orders_resident_id ON orders(resident_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_assigned ON orders(assigned_to);
CREATE INDEX idx_listings_property_id ON listings(property_id);
CREATE INDEX idx_listings_status ON listings(status);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);
```

---

## 5. Auth and Role Model

### 5.1 Authentication

- Local username/password only. No OAuth, SSO, or external identity provider.
- Passwords: minimum 12 characters, must include uppercase, lowercase, digit, and special character.
- Password hashing: bcrypt with work factor 12 (or argon2id if preferred).
- Session: JWT access token (short-lived, 30 minutes) + refresh token (longer-lived, 24 hours).
- Tokens stored in httpOnly cookie (preferred) or secure localStorage.
- No SMTP email. No email-based password reset. Admin resets passwords directly.

### 5.2 Role Definitions

| Role | Code | Description |
|------|------|-------------|
| Administrator | `admin` | Full system access, user management, content config, backups |
| Property Manager | `property_manager` | Operations: orders, listings, resident management, billing oversight |
| Accounting Clerk | `accounting_clerk` | Billing, payment verification, reconciliation, CSV export |
| Maintenance/Dispatcher | `maintenance_dispatcher` | Service order processing, state transitions |
| Resident | `resident` | Self-service: profile, statements, payments, orders, view listings |

### 5.3 Permission Matrix

| Resource | Admin | Prop. Manager | Acct. Clerk | Maint/Dispatch | Resident |
|----------|-------|--------------|-------------|----------------|----------|
| Users | CRUD | R | - | - | - |
| Properties | CRUD | R | R | R | - |
| Units | CRUD | CRUD | R | R | - |
| Residents | CRUD | CRUD | R | R | Own only |
| Addresses | CRUD | R | R | - | Own only |
| Fee Items | CRUD | R | CRUD | - | - |
| Bills | CRUD | R | CRUD | - | Own R |
| Payments | CRUD | R+verify | R+verify | - | Own C+R |
| Credit Memos | CRUD | C+R+approve | C+R | - | Own R |
| Orders | CRUD | CRUD | R | CRUD (assigned) | Own C+R |
| Listings | CRUD | CRUD | R | R | R |
| Media | CRUD | CRUD | R | R | Own C+R |
| Content Config | CRUD | R | - | - | - |
| Audit Logs | R | R | R (billing) | - | - |
| Backups | CRUD | - | - | - | - |

### 5.4 Data Masking by Role

| Field | Admin | Prop. Manager | Acct. Clerk | Maint/Dispatch | Resident |
|-------|-------|--------------|-------------|----------------|----------|
| Email | Full | Last 4 + domain | Last 4 + domain | Masked | Own full |
| Phone | Full | Last 4 digits | Last 4 digits | Masked | Own full |
| SSN | Blocked | Blocked | Blocked | Blocked | Blocked |

---

## 6. Offline Cache Design

### 6.1 Architecture

```
+-------------------+       +------------------+
| Vue Component     | <---> | Pinia Store      |
+-------------------+       +------------------+
                                    |
                            +------------------+
                            | OfflineCache     |
                            | Service          |
                            +------------------+
                              |             |
                    +-----------+     +------------+
                    | IndexedDB |     | Web Crypto |
                    | (Dexie.js)|     | (AES-GCM)  |
                    +-----------+     +------------+
```

### 6.2 IndexedDB Stores

| Store | Contents | Encryption |
|-------|----------|-----------|
| `cached_records` | GET response data keyed by endpoint | AES-GCM encrypted |
| `retry_queue` | Pending POST/PUT/PATCH/DELETE requests | AES-GCM encrypted |
| `user_session` | JWT tokens, role, user ID | AES-GCM encrypted |
| `sync_metadata` | Last sync timestamps per resource type | Plaintext |

### 6.3 Encryption

- Algorithm: AES-256-GCM via Web Crypto API (SubtleCrypto)
- Key derivation: PBKDF2 from user password + device salt
- Key stored in memory only during active session; cleared on logout
- Each record encrypted individually to allow granular access

### 6.4 Cache Invalidation

- Stale-while-revalidate: serve from cache immediately, fetch fresh in background
- Version-based: compare record version numbers with server response
- Full resync on login: pull all user-relevant records fresh

---

## 7. Retry Queue Design

### 7.1 Queue Entry Structure

```json
{
  "id": "uuid",
  "method": "POST",
  "url": "/api/v1/orders",
  "headers": { "Idempotency-Key": "uuid", "If-Match": "3" },
  "body": { ... },
  "created_at": "2026-01-15T10:30:00Z",
  "retry_count": 0,
  "max_retries": 5,
  "status": "pending"
}
```

### 7.2 Replay Rules

1. Queue is FIFO - strict ordering preserved
2. Replay starts automatically when `navigator.onLine` transitions to `true` and server ping succeeds
3. Each request includes its original idempotency key
4. On success (2xx): remove from queue, update local cache
5. On conflict (409): pause queue, show conflict resolution UI to user
6. On client error (4xx except 409): mark as failed, notify user, continue queue
7. On server error (5xx): exponential backoff retry (1s, 2s, 4s, 8s, 16s), pause after max retries
8. User can view, retry, or discard any queued entry manually

---

## 8. Optimistic Locking and Conflict Handling

### 8.1 Version Protocol

- Every writable table has a `version INTEGER DEFAULT 1` column
- Client sends `If-Match: <version>` header on PUT/PATCH requests
- Server compares: if `record.version != header_version`, return 409
- On successful update: `version = version + 1`

### 8.2 Conflict Response (409)

```json
{
  "error": "conflict",
  "message": "Record has been modified by another user",
  "your_version": 3,
  "server_version": 4,
  "your_data": { ... },
  "server_data": { ... },
  "changed_fields": ["status", "assigned_to"]
}
```

### 8.3 Resolution UI

- Side-by-side diff showing each changed field
- Three options per field:
  - **Keep mine**: use the client's value
  - **Keep theirs**: use the server's value
  - **Merge**: for text fields, manual edit combining both
- Global shortcuts: "Keep all mine" / "Keep all theirs"
- Resolved payload submitted with current server version
- Resolution action logged in audit trail

---

## 9. Order State Machine

### 9.1 State Diagram

```
created --> payment_recorded --> accepted --> dispatched
                                                  |
                                                  v
            after_sales_credit <-- completed <-- in_service <-- arrived
```

### 9.2 State Transitions

| From | To | Allowed Roles | Validation |
|------|----|--------------|------------|
| created | payment_recorded | Resident, Accounting Clerk | Payment evidence must be attached |
| payment_recorded | accepted | Property Manager, Accounting Clerk | Payment must be verified |
| accepted | dispatched | Property Manager, Maintenance/Dispatcher | Assignee must be set |
| dispatched | arrived | Maintenance/Dispatcher | - |
| arrived | in_service | Maintenance/Dispatcher | - |
| in_service | completed | Maintenance/Dispatcher | Completion notes required |
| completed | after_sales_credit | Property Manager, Accounting Clerk | Credit memo must be created |

### 9.3 Invariants

- No state can be skipped (key-node validation)
- Every transition creates an immutable `order_milestones` record
- Each state change carries an idempotency key to prevent double-transitions during retries
- Backward transitions are not allowed (except to after_sales_credit from completed)
- Only the assigned Maintenance/Dispatcher can advance dispatched -> arrived -> in_service -> completed

---

## 10. Billing Engine Design

### 10.1 Bill Generation Flow

```
1. Scheduler triggers on property's billing_day
2. For each active resident in property:
   a. Create bill record for current billing_period
   b. For each active fee_item in property:
      - Create bill_line_item
      - If fee_item.is_taxable: calculate tax = amount * property.tax_rate
   c. Calculate subtotal, tax_total, total
   d. Set due_date = billing_day + late_fee_days
   e. Set balance_due = total - any applied credits
3. Log bill generation in audit trail
```

### 10.2 Late Fee Processing

```
1. Daily job scans bills where:
   - status IN ('generated', 'partially_paid')
   - due_date + late_fee_days < current_date
   - late_fee = 0 (not already applied)
2. Apply flat late fee from property config
3. Update bill total and balance_due
4. Log in audit trail
```

### 10.3 Reconciliation

- Match verified payments against bills
- Update bill balance_due and status (partially_paid or paid)
- Apply credit memos to outstanding balances
- Generate reconciliation report showing: expected, received, outstanding, credits

### 10.4 Financial Reports

- **PDF Statements**: per-resident, per-period, all line items with tax breakdown
- **PDF Payment Receipts**: per-payment confirmation
- **PDF Credit Memos**: per-credit document
- **CSV Export**: configurable date range, filterable by property/status, includes all billing data

---

## 11. Listings and Media Upload Design

### 11.1 Listing Lifecycle

```
draft --> published --> unpublished --> published (re-publish)
  |           |              |
  v           v              v
archived   archived       archived
```

### 11.2 Bulk Operations

- Select multiple listings via checkbox
- Available bulk actions: publish, unpublish, archive
- Server processes as a batch with individual success/failure per listing
- Audit log entry per listing affected

### 11.3 Media Upload Pipeline

```
Client Side:
1. File selected by user
2. Validate type (JPG/PNG for image, MP4 for video)
3. Validate size (<=10MB image, <=200MB video)
4. Show immediate error if validation fails
5. If offline: queue upload in retry queue
6. If online: upload via multipart/form-data with progress

Server Side:
1. Validate MIME type (magic bytes, not just extension)
2. Validate file size
3. Generate unique filename (UUID + extension)
4. Write to /data/uploads/{property_id}/{year}/{month}/
5. Create media record in database
6. Return media_id for linking to listing
```

### 11.4 Supported Formats

| Type | Formats | Max Size |
|------|---------|----------|
| Image | JPG (image/jpeg), PNG (image/png) | 10 MB |
| Video | MP4 (video/mp4) | 200 MB |

---

## 12. Homepage Content Module Design

### 12.1 Content Structure

A content configuration consists of ordered sections. Each section is one of:

| Section Type | Fields |
|-------------|--------|
| carousel | panels: [{image_url, title, subtitle, link_url}] |
| recommended_tiles | tiles: [{image_url, title, description, link_url}] |
| announcement_banner | text, severity (info/warning/urgent), dismissible |

### 12.2 Configuration Lifecycle

```
draft --> canary --> published
  |         |           |
  v         v           v
archived  archived   archived
```

- **Draft**: visible only to creator in edit mode
- **Canary**: visible to staff with `canary_enabled = true` (approximately 10%)
- **Published**: visible to all users
- **Archived**: no longer served

### 12.3 Preview Mode

- Admin can preview any draft/canary config in a modal overlay
- Preview renders exact same components as production homepage
- No data side effects during preview

---

## 13. Rollout Design for 10% of Staff

### 13.1 Mechanism

- `users.canary_enabled` boolean flag on staff accounts
- Administrator selects which staff accounts are canary testers
- Target: approximately 10% of total staff accounts

### 13.2 Content Resolution Logic

```python
def resolve_content_config(user):
    if user.canary_enabled:
        config = get_config_by_status('canary')
        if config:
            return config
    return get_config_by_status('published')
```

### 13.3 Rollout Workflow

1. Admin creates content configuration (draft)
2. Admin previews and edits until satisfied
3. Admin promotes to "canary" status
4. Canary staff see new config; others see current published
5. Admin monitors feedback
6. Admin promotes canary to "published" (old published becomes archived)

---

## 14. Audit Log Design

### 14.1 Principles

- **Immutable**: insert-only table, no updates or deletes
- **Comprehensive**: all mutations logged with before/after state
- **Traceable**: user ID, IP address, timestamp, idempotency key
- **Queryable**: indexed by resource type, resource ID, user, and time

### 14.2 Log Entry Fields

| Field | Description |
|-------|-------------|
| user_id | Who performed the action |
| action | CREATE, UPDATE, DELETE, STATE_CHANGE, LOGIN, LOGOUT |
| resource_type | Table/entity name (e.g., 'order', 'bill', 'listing') |
| resource_id | Primary key of affected record |
| old_value | JSONB snapshot before change (null for CREATE) |
| new_value | JSONB snapshot after change (null for DELETE) |
| ip_address | Client IP |
| idempotency_key | Links to the retry/idempotency key if applicable |
| created_at | Immutable timestamp |

### 14.3 Retention

- Audit logs are never deleted by the application
- Included in nightly backups
- Queryable by admin through the API (paginated, filterable)

---

## 15. Backup and Restore Design

### 15.1 Backup Process

```
1. Scheduled task triggers (nightly, configurable time)
2. Run pg_dump with custom format
3. Include media uploads directory (tar)
4. Encrypt combined archive with AES-256 (age or GPG symmetric)
5. Write to configured backup directory: /data/backups/
6. Filename: harborview_backup_YYYYMMDD_HHMMSS.enc
7. Record in backup_records table
8. Delete backups older than 30 days
```

### 15.2 Restore Process

```
1. Admin selects backup from backup_records list or provides file path
2. System prompts for encryption passphrase
3. Decrypt archive
4. Restore PostgreSQL from pg_dump
5. Restore media files to uploads directory
6. Verify integrity (record counts, checksums)
7. Log restore action in audit trail
```

### 15.3 Constraints

- No internet dependency for backup or restore
- Encryption passphrase is not stored in the database
- Backup directory is configurable via environment variable
- Backup can be triggered manually via admin API endpoint

---

## 16. Encryption and Masking Design

### 16.1 Encryption at Rest (Server)

| Data | Method | Key Management |
|------|--------|---------------|
| Passwords | bcrypt (work factor 12) | One-way hash, no key |
| Resident email | Fernet (AES-128-CBC + HMAC) | App-level key from env var |
| Resident phone | Fernet (AES-128-CBC + HMAC) | App-level key from env var |
| SSN | Not collected, rejected by validation | N/A |
| Backup files | AES-256 (age/GPG) | Admin-configured passphrase |

### 16.2 Encryption at Rest (Client)

| Data | Method | Key Management |
|------|--------|---------------|
| Cached records | AES-256-GCM | PBKDF2 derived from user password |
| Retry queue | AES-256-GCM | Same derived key |
| Session tokens | AES-256-GCM | Same derived key |

### 16.3 Data Masking API

- Masking applied at the serializer/response layer, not the database
- Role determines masking level (see Section 5.4)
- Masked format examples:
  - Email: `****@domain.com`
  - Phone: `****5678`
  - SSN: always returns `***-**-****` (field does not exist, but input is rejected if pattern matches)

---

## 17. Docker Deployment Assumptions

### 17.1 Docker Compose Services

| Service | Image | Ports | Volumes |
|---------|-------|-------|---------|
| `frontend` | Nginx + Vue build | 80:80 | - |
| `backend` | Python + Uvicorn | 8000:8000 | uploads, backups |
| `db` | PostgreSQL 15 | 5432:5432 | pgdata |

### 17.2 Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `DATABASE_URL` | backend | PostgreSQL connection string |
| `SECRET_KEY` | backend | JWT signing key |
| `ENCRYPTION_KEY` | backend | Fernet key for field encryption |
| `BACKUP_PASSPHRASE` | backend | Backup encryption passphrase |
| `BACKUP_DIR` | backend | Path to backup directory |
| `UPLOAD_DIR` | backend | Path to media uploads directory |

### 17.3 Startup Sequence

```
1. docker compose up -d db
2. Wait for PostgreSQL ready (health check)
3. docker compose up -d backend
4. Backend creates tables via `Base.metadata.create_all()` on startup
5. Backend seeds default admin user if no users exist
6. docker compose up -d frontend
7. Nginx proxies /api/* to backend:8000
```

### 17.4 Assumptions

- Host machine has Docker and Docker Compose installed
- Ports 80, 8000, 5432 are available
- Sufficient disk space for PostgreSQL, media uploads, and 30 days of backups
- No internet required after initial `docker pull` of base images
- `.env` file at repo root provides all environment variables
