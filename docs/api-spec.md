# HarborView Property Operations Portal - API Specification

Base URL: `/api/v1`

All endpoints return JSON. All timestamps are ISO 8601 UTC. All IDs are UUIDv4.

## Common Headers

| Header | Description | Required |
|--------|-------------|----------|
| `Authorization` | `Bearer <jwt_token>` | All except login and health |
| `Content-Type` | `application/json` (or `multipart/form-data` for uploads) | Write operations |
| `Idempotency-Key` | UUID to prevent duplicate writes | All POST/PUT/PATCH on writable resources |
| `If-Match` | Version number for optimistic locking | All PUT/PATCH operations |

## Common Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Not Found |
| 409 | Conflict (version mismatch) |
| 413 | Payload Too Large |
| 422 | Unprocessable Entity |
| 429 | Rate Limited |
| 500 | Internal Server Error |

## Pagination

List endpoints support:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Items per page (max 100) |
| `sort_by` | string | `created_at` | Sort field |
| `sort_order` | string | `desc` | `asc` or `desc` |

Response includes:
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

---

## 1. Auth

### POST /auth/login

Login with username and password. Returns JWT access and refresh tokens.

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response 200:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "username": "string",
    "role": "string",
    "canary_enabled": false
  }
}
```

### POST /auth/refresh

Refresh an expired access token.

**Request:**
```json
{
  "refresh_token": "string"
}
```

**Response 200:**
```json
{
  "access_token": "string",
  "expires_in": 1800
}
```

### POST /auth/logout

Invalidate the current refresh token.

**Response 204:** No content.

### PUT /auth/password

Change the current user's password.

**Request:**
```json
{
  "current_password": "string",
  "new_password": "string"
}
```

**Response 200:**
```json
{
  "message": "Password updated successfully"
}
```

**Validation:** New password must be at least 12 characters with uppercase, lowercase, digit, and special character.

---

## 2. Users

**Roles required:** Administrator for CRUD. Others: read own profile only.

### GET /users

List all users. Paginated.

**Query params:** `role` (filter), `is_active` (filter), `search` (username search)

### POST /users

Create a new user.

**Request:**
```json
{
  "username": "string",
  "password": "string",
  "role": "admin | property_manager | accounting_clerk | maintenance_dispatcher | resident",
  "is_active": true,
  "canary_enabled": false
}
```

**Response 201:** Full user object.

### GET /users/{id}

Get a single user.

### PUT /users/{id}

Update a user. Requires `If-Match` header.

### DELETE /users/{id}

Deactivate a user (soft delete: sets `is_active = false`).

### PUT /users/{id}/reset-password

Admin resets a user's password.

**Request:**
```json
{
  "new_password": "string"
}
```

---

## 3. Residents

### GET /residents

List residents. Paginated. Filterable by `property_id`, `unit_id`.

**Roles:** Administrator, Property Manager, Accounting Clerk, Maintenance/Dispatcher.

### GET /residents/{id}

Get a resident profile. Sensitive fields masked by caller's role.

### POST /residents

Create a resident. Requires a linked user account.

**Request:**
```json
{
  "user_id": "uuid",
  "unit_id": "uuid",
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone": "string"
}
```

### PUT /residents/{id}

Update a resident profile. Requires `If-Match` header.

### GET /residents/me

Get the current user's resident profile (for Resident role).

### PUT /residents/me

Update the current user's own profile. Requires `If-Match` header.

---

## 4. Addresses

### GET /residents/{resident_id}/addresses

List all addresses for a resident.

### POST /residents/{resident_id}/addresses

Add a new address.

**Request:**
```json
{
  "address_type": "shipping | mailing",
  "line1": "string",
  "line2": "string | null",
  "city": "string",
  "state": "string",
  "zip_code": "string",
  "is_primary": false
}
```

### PUT /residents/{resident_id}/addresses/{id}

Update an address. Requires `If-Match` header.

### DELETE /residents/{resident_id}/addresses/{id}

Remove an address.

---

## 5. Properties

### GET /properties

List all properties. Paginated.

### POST /properties

Create a property. Admin only.

**Request:**
```json
{
  "name": "string",
  "address": "string",
  "billing_day": 1,
  "late_fee_days": 10,
  "late_fee_amount": 25.00,
  "tax_rate": 0.0600
}
```

### GET /properties/{id}

Get a single property.

### PUT /properties/{id}

Update a property. Requires `If-Match` header.

### GET /properties/{id}/units

List all units in a property.

### POST /properties/{id}/units

Create a unit in a property.

**Request:**
```json
{
  "unit_number": "string",
  "status": "active | inactive"
}
```

---

## 6. Billing

### GET /billing/fee-items

List fee items. Filterable by `property_id`, `is_active`.

### POST /billing/fee-items

Create a fee item.

**Request:**
```json
{
  "property_id": "uuid",
  "name": "string",
  "amount": 100.00,
  "is_taxable": false
}
```

### PUT /billing/fee-items/{id}

Update a fee item. Requires `If-Match` header.

### GET /billing/bills

List bills. Filterable by `property_id`, `resident_id`, `billing_period`, `status`. Paginated.

### GET /billing/bills/{id}

Get a bill with line items.

**Response 200:**
```json
{
  "id": "uuid",
  "resident_id": "uuid",
  "property_id": "uuid",
  "billing_period": "2026-04",
  "due_date": "2026-04-11",
  "subtotal": 1500.00,
  "tax_total": 30.00,
  "late_fee": 0.00,
  "total": 1530.00,
  "balance_due": 1530.00,
  "status": "generated",
  "line_items": [
    {
      "id": "uuid",
      "description": "Monthly Rent",
      "amount": 1400.00,
      "tax_amount": 0.00
    },
    {
      "id": "uuid",
      "description": "Parking Fee",
      "amount": 100.00,
      "tax_amount": 6.00
    }
  ],
  "version": 1
}
```

### POST /billing/generate

Trigger bill generation for a property.

**Request:**
```json
{
  "property_id": "uuid",
  "billing_period": "2026-04"
}
```

**Response 201:**
```json
{
  "bills_generated": 45,
  "property_id": "uuid",
  "billing_period": "2026-04"
}
```

**Roles:** Administrator, Accounting Clerk.

---

## 7. Statements

### GET /billing/statements

List statements for the current Resident (or filtered by `resident_id` for staff).

**Query params:** `resident_id`, `billing_period`, `year`

### GET /billing/statements/{bill_id}/pdf

Download a PDF statement for a specific bill.

**Response:** `application/pdf` binary stream.

---

## 8. Payment Evidence Uploads

### GET /payments

List payments. Filterable by `bill_id`, `resident_id`, `status`. Paginated.

### POST /payments

Submit payment evidence.

**Request (multipart/form-data):**

| Field | Type | Required |
|-------|------|----------|
| `bill_id` | UUID | Yes |
| `amount` | decimal | Yes |
| `payment_method` | string (check, money_order) | Yes |
| `evidence_file` | file (JPG/PNG, max 10 MB) | Yes |
| `idempotency_key` | UUID | Yes |

**Response 201:**
```json
{
  "id": "uuid",
  "bill_id": "uuid",
  "amount": 1530.00,
  "payment_method": "check",
  "evidence_media_id": "uuid",
  "status": "pending",
  "created_at": "2026-04-06T10:30:00Z"
}
```

### GET /payments/{id}

Get a payment with evidence link.

### PUT /payments/{id}/verify

Staff verifies or rejects payment evidence.

**Request:**
```json
{
  "action": "verify | reject",
  "rejection_reason": "string | null"
}
```

**Response 200:** Updated payment object.

**Roles:** Property Manager, Accounting Clerk.

---

## 9. Refunds as Credits

### GET /credits

List credit memos. Filterable by `resident_id`, `status`. Paginated.

### POST /credits

Create a credit memo (refund request).

**Request:**
```json
{
  "resident_id": "uuid",
  "bill_id": "uuid | null",
  "order_id": "uuid | null",
  "amount": 50.00,
  "reason": "string"
}
```

**Roles:** Resident (own), Property Manager, Accounting Clerk.

### GET /credits/{id}

Get a single credit memo.

### PUT /credits/{id}/approve

Approve a pending credit memo.

**Request:**
```json
{
  "applied_to_bill_id": "uuid | null"
}
```

**Roles:** Property Manager, Administrator.

### GET /credits/{id}/pdf

Download a PDF credit memo document.

**Response:** `application/pdf` binary stream.

---

## 10. Service Orders

### GET /orders

List orders. Filterable by `resident_id`, `property_id`, `status`, `assigned_to`. Paginated.

### POST /orders

Create a new service order.

**Request:**
```json
{
  "property_id": "uuid",
  "title": "string",
  "description": "string",
  "category": "string",
  "priority": "low | normal | high | urgent",
  "idempotency_key": "uuid"
}
```

**Roles:** Resident (own property), Property Manager, Administrator.

**Response 201:** Full order object with status `created`.

### GET /orders/{id}

Get an order with milestones.

**Response 200:**
```json
{
  "id": "uuid",
  "resident_id": "uuid",
  "title": "string",
  "status": "dispatched",
  "assigned_to": "uuid",
  "milestones": [
    {
      "from_status": null,
      "to_status": "created",
      "changed_by": "uuid",
      "notes": null,
      "created_at": "2026-04-01T09:00:00Z"
    },
    {
      "from_status": "created",
      "to_status": "payment_recorded",
      "changed_by": "uuid",
      "notes": "Check #4521",
      "created_at": "2026-04-02T14:00:00Z"
    }
  ],
  "version": 3
}
```

### PUT /orders/{id}

Update order details (title, description, category, priority, assigned_to). Requires `If-Match` header.

### POST /orders/{id}/transition

Advance the order to the next state.

**Request:**
```json
{
  "to_status": "string",
  "notes": "string | null",
  "idempotency_key": "uuid"
}
```

**Response 200:** Updated order with new milestone appended.

**Validation:** Enforces valid transitions per state machine. Returns 422 if transition is invalid.

---

## 11. Listings

### GET /listings

List marketplace listings. Filterable by `property_id`, `category`, `status`. Paginated.

**Roles:** All (Residents see only `published` listings for their property).

### POST /listings

Create a new listing (starts as draft).

**Request:**
```json
{
  "property_id": "uuid",
  "title": "string",
  "description": "string",
  "category": "garage_sale | parking_sublet | amenity_addon",
  "price": 50.00
}
```

**Roles:** Administrator, Property Manager.

**Response 201:** Full listing object with status `draft`.

### GET /listings/{id}

Get a single listing with media.

### PUT /listings/{id}

Update listing details. Requires `If-Match` header.

### PUT /listings/{id}/status

Change listing status.

**Request:**
```json
{
  "status": "published | unpublished | archived"
}
```

### POST /listings/bulk-status

Bulk status change for multiple listings.

**Request:**
```json
{
  "listing_ids": ["uuid", "uuid"],
  "status": "published | unpublished | archived"
}
```

**Response 200:**
```json
{
  "updated": 5,
  "failed": 0,
  "results": [
    { "id": "uuid", "status": "published", "success": true },
    { "id": "uuid", "status": "published", "success": true }
  ]
}
```

---

## 12. Media Uploads

### POST /media/upload

Upload a file.

**Request (multipart/form-data):**

| Field | Type | Required |
|-------|------|----------|
| `file` | binary | Yes |
| `listing_id` | UUID | No (links media to listing) |

**Validation:**
- Images: JPG/PNG only, max 10 MB
- Videos: MP4 only, max 200 MB
- MIME type verified by magic bytes

**Response 201:**
```json
{
  "id": "uuid",
  "filename": "string",
  "original_name": "string",
  "mime_type": "image/jpeg",
  "file_size": 2048576,
  "url": "/api/v1/media/uuid/file"
}
```

### GET /media/{id}

Get media metadata.

### GET /media/{id}/file

Download/serve the media file. Returns binary with appropriate Content-Type.

### DELETE /media/{id}

Delete a media file. Removes from filesystem and database.

### POST /listings/{listing_id}/media

Attach existing media to a listing.

**Request:**
```json
{
  "media_id": "uuid",
  "sort_order": 0
}
```

### DELETE /listings/{listing_id}/media/{media_id}

Detach media from a listing.

---

## 13. Admin Content Modules

### GET /content/configs

List all content configurations. Paginated.

**Roles:** Administrator.

### POST /content/configs

Create a new content configuration.

**Request:**
```json
{
  "name": "Spring 2026 Homepage"
}
```

### GET /content/configs/{id}

Get a config with all sections.

### PUT /content/configs/{id}

Update config metadata. Requires `If-Match` header.

### PUT /content/configs/{id}/status

Change config status (draft, canary, published, archived).

**Request:**
```json
{
  "status": "canary | published | archived"
}
```

**Business rules:**
- Only one config can be `published` at a time (previous is auto-archived)
- Only one config can be `canary` at a time
- Publishing a canary config archives the current published config

### GET /content/configs/active

Get the active config for the current user (considers canary flag).

### GET /content/configs/{id}/preview

Get a config for preview rendering. Does not change any state.

### POST /content/configs/{id}/sections

Add a section to a config.

**Request:**
```json
{
  "section_type": "carousel | recommended_tiles | announcement_banner",
  "title": "string | null",
  "content_json": { ... },
  "sort_order": 0,
  "is_active": true
}
```

**Content JSON examples:**

Carousel:
```json
{
  "panels": [
    {
      "image_url": "/api/v1/media/uuid/file",
      "title": "Welcome to HarborView",
      "subtitle": "Your community portal",
      "link_url": "/listings"
    }
  ]
}
```

Recommended tiles:
```json
{
  "tiles": [
    {
      "image_url": "/api/v1/media/uuid/file",
      "title": "Pool Hours",
      "description": "Updated summer schedule",
      "link_url": "/announcements/pool"
    }
  ]
}
```

Announcement banner:
```json
{
  "text": "Maintenance scheduled for Saturday 8am-12pm",
  "severity": "info | warning | urgent",
  "dismissible": true
}
```

### PUT /content/configs/{config_id}/sections/{id}

Update a section. Requires `If-Match` header.

### DELETE /content/configs/{config_id}/sections/{id}

Remove a section.

---

## 14. Rollout Controls

### GET /rollout/canary-users

List all staff users with their canary status.

**Response 200:**
```json
{
  "total_staff": 50,
  "canary_count": 5,
  "canary_percentage": 10.0,
  "users": [
    { "id": "uuid", "username": "string", "role": "string", "canary_enabled": true }
  ]
}
```

### PUT /rollout/canary-users

Batch update canary status for multiple users.

**Request:**
```json
{
  "updates": [
    { "user_id": "uuid", "canary_enabled": true },
    { "user_id": "uuid", "canary_enabled": false }
  ]
}
```

**Roles:** Administrator only.

---

## 15. Reconciliation

### GET /billing/reconciliation

Generate a reconciliation report for a property and period.

**Query params:** `property_id` (required), `billing_period` (required)

**Response 200:**
```json
{
  "property_id": "uuid",
  "billing_period": "2026-04",
  "summary": {
    "total_billed": 67500.00,
    "total_received": 52000.00,
    "total_outstanding": 14000.00,
    "total_credits": 1500.00,
    "total_late_fees": 750.00
  },
  "residents": [
    {
      "resident_id": "uuid",
      "name": "string",
      "billed": 1530.00,
      "paid": 1530.00,
      "credits": 0.00,
      "balance": 0.00,
      "status": "paid"
    }
  ]
}
```

### GET /billing/reconciliation/csv

Download reconciliation data as CSV.

**Query params:** Same as above.

**Response:** `text/csv` with Content-Disposition header.

---

## 16. PDF Receipts and Statements

### GET /billing/statements/{bill_id}/pdf

Download a PDF billing statement. (Also listed under Statements section.)

### GET /payments/{id}/receipt/pdf

Download a PDF payment receipt.

**Response:** `application/pdf` binary stream.

### GET /credits/{id}/pdf

Download a PDF credit memo. (Also listed under Credits section.)

---

## 17. CSV Export

### GET /reports/billing/csv

Export billing data as CSV.

**Query params:** `property_id`, `from_date`, `to_date`, `status`

**Response:** `text/csv`

### GET /reports/payments/csv

Export payment data as CSV.

**Query params:** `property_id`, `from_date`, `to_date`, `status`

**Response:** `text/csv`

### GET /reports/orders/csv

Export service order data as CSV.

**Query params:** `property_id`, `from_date`, `to_date`, `status`

**Response:** `text/csv`

---

## 18. Backup and Restore

### GET /backup/records

List backup records. Paginated.

**Roles:** Administrator only.

### POST /backup/trigger

Trigger an immediate backup.

**Response 202:**
```json
{
  "backup_id": "uuid",
  "status": "in_progress",
  "started_at": "2026-04-06T02:00:00Z"
}
```

### GET /backup/records/{id}

Get status of a specific backup.

### POST /backup/restore

Initiate a restore from a backup.

**Request:**
```json
{
  "backup_id": "uuid",
  "passphrase": "string"
}
```

**Response 202:**
```json
{
  "message": "Restore initiated",
  "backup_id": "uuid",
  "status": "restoring"
}
```

### GET /backup/restore/status

Get the current restore operation status.

---

## 19. Health Endpoints

### GET /health

Basic liveness check. No auth required.

**Response 200:**
```json
{
  "status": "ok",
  "timestamp": "2026-04-06T10:00:00Z"
}
```

### GET /health/ready

Readiness check including database connectivity. No auth required.

**Response 200:**
```json
{
  "status": "ready",
  "database": "connected",
  "timestamp": "2026-04-06T10:00:00Z"
}
```

**Response 503:**
```json
{
  "status": "not_ready",
  "database": "disconnected",
  "timestamp": "2026-04-06T10:00:00Z"
}
```

---

## 20. Audit Logs

### GET /audit/logs

Query audit logs. Paginated.

**Query params:** `resource_type`, `resource_id`, `user_id`, `action`, `from_date`, `to_date`

**Roles:** Administrator (all), Property Manager (all), Accounting Clerk (billing-related only).

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "action": "UPDATE",
      "resource_type": "order",
      "resource_id": "uuid",
      "old_value": { "status": "created" },
      "new_value": { "status": "payment_recorded" },
      "ip_address": "192.168.1.50",
      "created_at": "2026-04-06T10:30:00Z"
    }
  ],
  "total": 1250,
  "page": 1,
  "page_size": 20,
  "pages": 63
}
```
