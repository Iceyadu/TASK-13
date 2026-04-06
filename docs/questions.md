# HarborView Property Operations Portal - Business Ambiguities

## Business Process Ambiguities

### Q1: Payment Evidence Review Workflow

Question:
When a Resident uploads payment evidence (scanned check or money order image), what is the expected staff workflow? Is there a formal approval queue, or does any authorized staff member mark the payment as verified?

My Understanding:
Payment evidence is uploaded as proof of payment. An Accounting Clerk or Property Manager reviews the scanned image and manually records the payment against the corresponding bill. There is no automated OCR or payment gateway integration.

Solution:
Implement a payment evidence review queue visible to Accounting Clerk and Property Manager roles. The reviewer sees the uploaded image alongside the bill details, then either confirms (recording the payment) or rejects (with a reason visible to the Resident). The action is logged in the audit trail.

---

### Q2: Refund as Credit Memo Scope

Question:
Does "request refunds as credits" mean that credits are only applied against future bills, or can credits also result in an actual monetary disbursement to the Resident?

My Understanding:
The prompt says "refund handling as credit memos," which implies credits are ledger entries applied to future billing cycles. No actual money transfer or check issuance is involved.

Solution:
Implement credit memos as negative line items. When a Resident requests a refund, staff creates a credit memo tied to the original charge. The credit automatically offsets the next billing cycle balance. No external payment disbursement workflow is included.

---

### Q3: Who Creates Marketplace Listings

Question:
Can Residents create their own marketplace listings (e.g., garage sale items), or is listing creation restricted to property staff only?

My Understanding:
The prompt states "property staff can create and manage marketplace-style listings." Residents are not mentioned as listing creators. Listing examples include parking spot sublets and amenity add-ons, which are typically staff-managed.

Solution:
Only Administrator, Property Manager, and Accounting Clerk roles can create and manage listings. Residents can browse and view published listings only. If Resident-created listings are needed in the future, the role permission model supports adding it without schema changes.

---

### Q4: Service Order Origination

Question:
Who can create service orders? Can Residents submit maintenance requests that become service orders, or do only staff create orders?

My Understanding:
The prompt says Residents can "track service orders through clear status badges and timestamped milestones," implying Residents can at minimum view orders. The phrase "service orders" alongside Resident self-service suggests Residents can also initiate them (e.g., maintenance request).

Solution:
Residents can create service orders (maintenance requests) through self-service. The order enters the state machine at "created." Maintenance/Dispatcher staff then processes the order through subsequent states. Residents see status updates and milestones but cannot advance the state themselves.

---

## Business Rule Ambiguities

### Q5: Order State Machine - After-Sales Credit

Question:
What does the "after-sales credit" terminal state represent? Is it a refund for a completed order, a partial credit, or a warranty-style adjustment?

My Understanding:
After a service order reaches "completed," a credit can be issued if the Resident is unsatisfied or was overcharged. This is a post-completion financial adjustment, not a state that every order passes through.

Solution:
Implement "after-sales credit" as an optional terminal state reachable only from "completed." Transitioning to this state requires staff action and generates a credit memo linked to the original order. The order's financial record is adjusted accordingly.

---

### Q6: Late Fee Application Timing

Question:
When exactly is the late fee applied? On day 11 (the first day after the 10-day grace period), or at the end of the billing cycle? Is it a one-time charge or does it compound?

My Understanding:
The prompt says "late after 10 days, $25.00 late fee." This is a one-time flat fee applied once the payment is overdue past the grace period. It does not compound monthly.

Solution:
Apply a single $25.00 late fee on day 11 if the bill remains unpaid. The fee is added as a separate line item on the bill. No compounding. If the bill is partially paid before day 11, the late fee still applies if the remaining balance is greater than zero.

---

### Q7: Sales Tax Scope

Question:
Which line items are taxable? The prompt says "6.00% sales tax only on taxable line items" but does not define which fee types are taxable.

My Understanding:
Taxability is a configurable attribute on each fee item. Common practice: service fees and amenity charges are taxable; base rent and government-mandated fees are not.

Solution:
Each fee item in the configuration has a boolean `is_taxable` flag. When generating a bill, the 6.00% tax is applied only to line items where `is_taxable` is true. The tax rate itself is also configurable per property to accommodate local jurisdictions.

---

### Q8: Billing Cycle and Multi-Property Scope

Question:
Does "automated bill generation per property" mean each property has independent billing cycles, or is there a single global cycle? Can a Resident belong to multiple properties?

My Understanding:
Each property has its own billing configuration (cycle day, fee rules, tax rate). A Resident belongs to one property at a time through a unit/lease assignment.

Solution:
Billing cycles are configured per property. Each property defines its own cycle start day, fee items, late fee amount, and tax rate. A Resident is assigned to one unit in one property. The billing engine runs per property, generating bills for all active Residents in that property.

---

## Data Relationship Ambiguities

### Q9: Property-Unit-Resident Relationship

Question:
What is the data hierarchy? Is it Property > Building > Unit > Resident, or a simpler Property > Unit > Resident?

My Understanding:
The prompt does not mention buildings or floors as distinct entities. The operational focus is on property-level management with Residents as the billing targets.

Solution:
Use a simplified hierarchy: Property > Unit > Resident. A Property contains Units. Each Unit is assigned to one or more Residents (e.g., co-tenants). Billing is per Resident. If a building-level grouping is needed later, it can be added as an optional attribute on Unit.

---

### Q10: Listing Relationship to Property

Question:
Are listings scoped to a single property or visible across all properties in the system?

My Understanding:
Since the system is on-prem and likely serves a single property or a small group of related properties, listings are scoped per property.

Solution:
Each listing belongs to one property. The listing browse view filters by the user's assigned property. Administrators can view listings across all properties.

---

## Boundary Condition Ambiguities

### Q11: Offline Conflict Resolution - Concurrent Edits

Question:
When two staff members edit the same record offline and both sync, who wins? The prompt mentions side-by-side diff with "keep mine, keep theirs, or merge fields" - but who sees the conflict UI?

My Understanding:
The second sync attempt detects the version mismatch. The user whose sync arrives second sees the conflict resolution UI with the diff. The first sync succeeds normally.

Solution:
Optimistic locking via version number. The first write to reach the server wins and increments the version. The second write fails with a 409 Conflict response containing the current server state. The client that received the 409 displays the side-by-side diff UI, allowing the user to choose keep mine, keep theirs, or merge individual fields. The resolved version is submitted as a new write with the current server version.

---

### Q12: Retry Queue Ordering and Idempotency

Question:
When the client comes back online and replays queued writes, must they be replayed in order? What if a later write depends on an earlier one (e.g., create order then record payment)?

My Understanding:
Writes must be replayed in the order they were queued, since later operations may depend on earlier ones. Idempotency keys prevent duplicate processing if a replay is interrupted and retried.

Solution:
The retry queue is a FIFO queue. Writes are replayed sequentially in the order they were created. Each write carries an idempotency key (UUID generated at creation time). The server checks the idempotency key before processing - if already processed, it returns the original response. If a replayed write fails (e.g., 409 conflict), the queue pauses and presents the conflict to the user before continuing.

---

### Q13: Canary Rollout Percentage Calculation

Question:
Is the 10% canary rollout a random selection of staff on each page load, or a fixed cohort of staff accounts designated as canary testers?

My Understanding:
A fixed cohort is more predictable and testable. Random per-request would cause inconsistent experiences for the same user.

Solution:
Implement a `canary_enabled` boolean flag on staff user accounts. Administrators select which staff accounts participate in canary testing. The content module checks this flag to determine whether to serve the new or current configuration. When ready for full rollout, the admin publishes the new configuration to all users and the canary flag becomes irrelevant for that content version.

---

### Q14: Media Upload Size Limits - Server vs Client Enforcement

Question:
Are the file size limits (10 MB for images, 200 MB for videos) enforced only on the client, or also on the server? What happens if a file is uploaded while offline and exceeds the limit?

My Understanding:
Limits must be enforced on both client and server. The client validates before queuing (including offline), and the server rejects oversized uploads as a safety net.

Solution:
Client-side validation runs before the file enters the retry queue, even offline. Files exceeding limits are rejected immediately with a user-facing error. Server-side validation also enforces limits and returns 413 Payload Too Large if exceeded. Accepted formats: JPG, PNG for images; MP4 for videos. All other formats are rejected with a descriptive error before any storage write.

---

### Q15: Backup Encryption Key Management

Question:
How is the encryption key for nightly backups managed? Is it a static passphrase configured by the admin, or an auto-generated key stored securely on the server?

My Understanding:
Since the system is fully local with no internet dependency, a simple approach is an admin-configured passphrase stored in a server-side configuration file with restricted file permissions.

Solution:
The backup encryption key is a passphrase configured by the Administrator through a server-side environment variable or configuration file (not stored in the database). The backup script uses this passphrase with AES-256 encryption via the `age` tool or GPG symmetric mode. The restore workflow prompts for the passphrase. The passphrase is not logged or included in audit trails.

---

### Q16: PDF Receipt Generation Scope

Question:
Does "locally generated PDF receipts" cover only payment receipts, or also billing statements and credit memos?

My Understanding:
Residents can "view and download statements," which implies PDF statements. Payment receipts are generated when a payment is recorded. Credit memos should also be downloadable for Resident records.

Solution:
Generate PDFs for three document types: (1) monthly billing statements with all line items, taxes, and balance due; (2) payment receipts confirming recorded payments; (3) credit memo documents showing the credit amount and reason. All PDFs are generated server-side using a Python PDF library (WeasyPrint or ReportLab) with no external service dependency.
