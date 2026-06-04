# APC Operations — End-to-End Architecture & Code Audit

**Report date:** 2026-05-12
**Scope:** `apps/apc_operations` (Frappe v15 / ERPNext)
**Auditor role:** Senior software architect / code auditor

---

## 1. Executive Summary

### Top 5 Most Important Risks

1. **Duplicate `on_submit`/`on_update` execution corrupts stock and dispatch quantities.** Three core controllers (`APC Dispatch Order`, `APC Batch Allocation`, `APC Sales Demand`) both implement business logic on `on_submit`/`on_update` **and** register a `doc_events` hook in `hooks.py` that calls the same logic again. Every dispatch submission decrements stock twice, double-attaches COAs, and double-allocates batches. This is the single biggest production-breaking issue.
2. **The hourly/daily/cron reminder scheduler is silently dead.** `hooks.py` defines `scheduler_events` twice (lines 27–49 and 112–116). The second definition wins, so all cutoff/CRO/pullout/transport reminders defined in `reminders.py` never run. Operations rely on emails that aren't being sent.
3. **Insecure Zoho integration surface.** `validate_api_key` in `zoho/api.py` **bypasses authentication entirely if no key is configured**. Three public webhook endpoints (`webhook_pfi_*`, `webhook_delivery_confirmed`) have zero auth/signature check. A hardcoded fallback developer email (`tejas303525@gmail.com`) receives any unrouted operational alerts.
4. **Race conditions in FIFO batch allocation + dispatch.** `APCBatch.allocate_quantity` / `deduct_dispatch_qty` and `confirm_dispatch_and_deduct_stock` use `db_set` (raw `UPDATE`) without row locking (`SELECT ... FOR UPDATE`). Concurrent allocations can over-allocate the same batch; concurrent dispatch confirmations can drive stock negative.
5. **`Transport Schedule` is duplicated as a module folder** (`shipping/doctype/transport_schedule/` is an empty stub; `transportation/doctype/transport_schedule/` is the real one) and **JSON migrations are missing from `patches.txt`** (`add_loading_dn_qc_fields`, `add_loading_dn_batch_allocations`, `backfill_apc_batch_stock_status`, `add_production_order_item_fields` exist on disk but aren't registered). New environments will silently lack required fields.

### Overall Codebase Health Score: **4 / 10**

- The domain model and Incoterm logic are thoughtful and well-documented in code.
- The reliability foundation is fragile: status syncs leak, hooks misfire, and there are no transactions around critical writes.
- The security posture is below acceptable for a production ERP integration (auth bypass, hardcoded emails, `ignore_permissions=True` everywhere).
- Tests exist but are happy-path unit tests; nothing tests concurrent allocation, double-execution, or status sync inversion.

### Main Theme of the Problems

The codebase reads like a controller-heavy MVP that grew without an event-sourcing or service-boundary discipline. Cross-document status synchronization is done by **direct `frappe.db.set_value` calls inside `on_update`**, with ad-hoc `frappe.flags.in_*` recursion guards. This pattern is replicated in eight controllers. The result is double-executions, recursion risks, partial writes with no transactions, and an inability to reason about the system. The Zoho integration is largely placeholder code, but the auth and webhook entry points are already live and dangerous.

---

## 2. System Map

### Main Modules

| Module | Path | Purpose |
|---|---|---|
| Shipping | `apc_operations/shipping/` | Job Order, Shipping Booking, Gate Pass, Loading DN, QC Report Request, dashboards, hooks router |
| Transportation | `apc_operations/transportation/` | The real `Transport Schedule` controller, transportation dashboard |
| Security | `apc_operations/security/` | Security Inspection, Security Draft DN, Security Dispatch, checklist |
| Inventory | `apc_operations/inventory/` | APC Batch, APC COA, COA Templates, FIFO reports |
| Sales | `apc_operations/sales/` | APC Sales Demand, Batch Allocation, Allocation Detail |
| Production | `apc_operations/production/` | Production Order, Production Requirement, capacity config |
| Dispatch | `apc_operations/dispatch/` | APC Dispatch Order, Batch/COA detail tables |
| Quality | `apc_operations/quality/` | QC API + console page |
| Zoho | `apc_operations/zoho/` | Mock integration to Zoho Books, sync log, settings |
| Services | `apc_operations/services/` | `batch_allocation.py`, `nas_service.py`, `dashboard.py`, `email_recipients.py`, console status helpers |

### Key Workflows

```
Zoho Sales Order ──► import_pfi() ──► APC Sales Demand
                                              │
                                              ▼
                              allocate_batches_fifo()  (services/batch_allocation.py)
                                              │
                                ├──► APC Batch Allocation + Details
                                └──► APC Production Requirement (if shortage)

create_job_order_from_pfi() ──► Job Order ──► determine_booking_requirement() (Incoterm rules)
                                              │
                                ├──► Transport Schedule  (create_or_link_transport_schedule)
                                └──► Shipping Booking   (create_or_link_shipping_booking)

Transport Schedule (on_update) ──► creates Security Draft DN + Transport PO Request
                                              │
                                              ▼
Security Draft DN ──► create_security_inspection_from_draft_dn()
                                              │
                                              ▼
Security Inspection ──► create_loading_delivery_note() ──► Loading DN
                          │                                       │
                          └──► report_to_qc() ──► QC Report Request
                                                       │
                                                  qc_status = "QC Cleared"
                                                       │
                                                       ▼
                          Loading DN.report_to_receivables()  (final step)

APC Dispatch Order (on_submit) ──► deducts stock from APC Batch (currently runs twice — bug)
```

### Important Dependencies

- **Frappe Framework v15 + ERPNext** (required app)
- **ERPNext `Batch`, `Item`, `Customer`, `Driver`, `Vehicle`** bridge records
- **Zoho Books** — placeholder REST integration in `zoho/integration.py` / `zoho/api.py` (no real client)
- **NAS share** — file system mount configured via `APC NAS Settings` (PDF persistence for COA + checklist)
- **Scheduled jobs** — registered in `hooks.py` `scheduler_events` (currently broken; see Gap #1)
- **Notification email** — `frappe.sendmail()` with `tejas303525@gmail.com` fallback in `services/email_recipients.py`, `reminders.py`, and `transportation/.../transport_schedule.py`

### Production Assumptions the Code Makes

1. Customers exist as ERPNext `Customer` records (Zoho `get_or_create_customer` will silently create with defaults `Commercial` / `All Territories`).
2. Item batch tracking is mutable at runtime — `APCBatch.ensure_item_batch_tracking` sets `Item.has_batch_no = 1` on the fly.
3. Only one COA per batch (the entire model assumes 1:1; `APCCOA.create_apc_coa_from_qc` enforces this).
4. Default Company, Customer Group, Territory, Item Group exist (`zoho/integration.py:_get_default_*` chains rely on this).
5. `frappe.db.commit()` is safe to call mid-request (used in `log_sync` — dangerous in a transactional request).
6. No concurrent access to a batch (no `for_update` locking anywhere).

---

## 3. Gap Analysis

### CRITICAL

#### Gap 1 — Duplicate event handlers cause double-execution of stock/dispatch mutations
- **Severity:** Critical
- **Area:** Data integrity / Operations
- **Files:**
  - `apps/apc_operations/apc_operations/hooks.py` lines 100–108
  - `apps/apc_operations/apc_operations/dispatch/doctype/apc_dispatch_order/apc_dispatch_order.py` lines 20–24 + 287–298
  - `apps/apc_operations/apc_operations/sales/doctype/apc_batch_allocation/apc_batch_allocation.py` lines 70–77 + 131–140
  - `apps/apc_operations/apc_operations/sales/doctype/apc_sales_demand/apc_sales_demand.py` lines 15–17 + 179–182
- **What's wrong:** Each of these controllers implements `on_submit`/`on_update` in the `Document` subclass **and** registers an identically-scoped handler in `hooks.py`. Frappe invokes both. For `APC Dispatch Order.on_submit`, the side effects are mutative:
  - `attach_batch_coas_to_dispatch` appends rows to `attached_coas` — doubled.
  - `update_allocation_dispatched_qty` increments `dispatched_quantity` — doubled.
  - `update_batch_depletion` reduces `available_quantity` — doubled.
  - `update_sales_demand_status` increments `total_dispatched_quantity` — doubled.
- **Why it matters:** Every dispatch submission silently corrupts batch stock and sales-demand fulfillment. Production data already in the DB is suspect.
- **Recommended fix:** Pick exactly one execution path (prefer the controller's `on_submit` for testability; drop the hook entry). Delete the hook entries for these three doctypes. Add a regression test that asserts `available_quantity` decreases by exactly the dispatched qty.
- **Effort:** Quick (≤ 1 hour); plus a data-fix patch to recompute current values.

#### Gap 2 — `scheduler_events` defined twice; reminders never run
- **Severity:** Critical
- **Area:** Operations / Reliability
- **File:** `apps/apc_operations/apc_operations/hooks.py` lines 27–49 (first definition with all reminders) and lines 112–116 (second definition with only the NAS retry)
- **What's wrong:** Python module-level re-assignment. The second `scheduler_events = {...}` overwrites the first. Frappe only sees the NAS retry; everything else (`check_upcoming_cutoffs`, `check_pending_pull_outs`, `check_pending_cros`, `check_pending_transport`, daily summaries, morning/evening reminders, 48h unassigned reminder) is silently dropped.
- **Why it matters:** Vessel cutoff alerts, CRO chase emails, and unassigned-vehicle reminders are not being sent. Operations is flying blind on overdue items.
- **Recommended fix:** Merge into one `scheduler_events` dict; add a startup self-check (e.g. lint or assert in `before_tests`) that counts registered scheduler jobs.
- **Effort:** Quick (10 minutes).

#### Gap 3 — Zoho API auth bypass when no key is configured
- **Severity:** Critical
- **Area:** Security
- **File:** `apps/apc_operations/apc_operations/zoho/api.py` lines 32–55
- **What's wrong:** The `validate_api_key` decorator falls through and calls the wrapped function **with no authentication** if `APC Zoho Settings.api_key` is empty or the settings doc is missing (`except: pass`). All `@frappe.whitelist()` endpoints — including `import_pfi`, `create_job_order_from_pfi`, `update_job_order_status`, `sync_delivery_note`, `get_inventory`, `get_batch_details` — become publicly callable.
- **Why it matters:** Anyone reaching `/api/method/...` can create Job Orders, alter statuses, and read inventory.
- **Recommended fix:** Fail closed. Remove the dev-bypass; require `api_key` to be set or refuse all requests. Use `hmac.compare_digest` for constant-time compare. Validate origin IP or use Frappe's built-in API Key/Secret model.
- **Effort:** Quick (≤ 2 hours).

#### Gap 4 — Public webhook endpoints with no signature verification
- **Severity:** Critical
- **Area:** Security
- **File:** `apps/apc_operations/apc_operations/zoho/api.py` lines 803–823 (`webhook_pfi_created`, `webhook_pfi_updated`, `webhook_delivery_confirmed`)
- **What's wrong:** `@frappe.whitelist()` with `allow_guest` semantics, no signature header check, no payload validation. The functions don't yet do anything, but the routes are live.
- **Why it matters:** Once activated, anyone can drive Job Order state from outside.
- **Recommended fix:** Require an HMAC header derived from a shared secret in `APC Zoho Settings`; verify against the raw request body using `hmac.compare_digest`. Reject unsigned requests.
- **Effort:** Quick.

#### Gap 5 — FIFO allocation has race conditions; no row locking
- **Severity:** Critical
- **Area:** Data integrity / Concurrency
- **Files:**
  - `apps/apc_operations/apc_operations/inventory/doctype/apc_batch/apc_batch.py` `allocate_quantity` lines 221–240, `deduct_dispatch_qty` lines 242–261
  - `apps/apc_operations/apc_operations/services/batch_allocation.py` `allocate_batches_fifo` lines 189–315, `confirm_dispatch_and_deduct_stock` lines 626–707
- **What's wrong:** The check-then-act pattern (`if quantity > available_quantity: throw` followed by `db_set("allocated_quantity", new_allocated)`) has no `SELECT ... FOR UPDATE`. Two concurrent allocations both see the same `available_quantity`, both pass the check, both write — over-allocating.
- **Why it matters:** A petrochemical dispatch system over-allocating batches will ship physical product that doesn't exist.
- **Recommended fix:** Wrap each allocation/dispatch in a single transaction; use `frappe.db.sql("SELECT ... FOR UPDATE")` to lock the batch row; recompute available inside the lock; raise if insufficient. Or use a single atomic SQL update with a guard:
  `UPDATE tabAPC Batch SET allocated_quantity = allocated_quantity + %s, available_quantity = available_quantity - %s WHERE name = %s AND available_quantity >= %s` and assert `rowcount == 1`.
- **Effort:** Medium (1–2 days including tests).

#### Gap 6 — Patches on disk are not registered in `patches.txt`
- **Severity:** Critical
- **Area:** Data integrity / Deployment
- **Files:**
  - On disk in `apc_operations/patches/v0_2/`: `add_loading_dn_qc_fields.py`, `add_loading_dn_batch_allocations.py`, `backfill_apc_batch_stock_status.py`, `add_production_order_item_fields.py`
  - Missing from `apps/apc_operations/apc_operations/patches.txt`
- **What's wrong:** Patches exist as code but aren't part of the migration list. New site installs / `bench migrate` will skip them, leaving fields (`qc_status`, `coa_verified`, `dispatch_confirmed`, `batch_allocations`, etc.) missing or with NULL defaults. Loading DN, dispatch confirmation, and FIFO override flows will silently fail.
- **Recommended fix:** Add missing entries to `patches.txt` in the correct order; verify each patch is idempotent (rerun-safe).
- **Effort:** Quick.

#### Gap 7 — Hardcoded developer email as production fallback recipient
- **Severity:** Critical
- **Area:** Security / Data leakage
- **Files:**
  - `apps/apc_operations/apc_operations/services/email_recipients.py` line 4
  - `apps/apc_operations/apc_operations/shipping/reminders.py` line 8 + every `or FALLBACK_NOTIFICATION_EMAIL` usage (lines 262, 291, 313, 334)
  - `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` line 9
- **What's wrong:** `FALLBACK_NOTIFICATION_EMAIL = "tejas303525@gmail.com"`. If a role has no users with a valid email, or `modified_by` has no email, internal operational notifications (vessel cutoffs, CRO chases, driver assignments, dispatch alerts, payables tracking) are sent to an external personal Gmail.
- **Why it matters:** Customer names, vessel info, container counts, and dispatch details leak outside the org. PII / commercial sensitivity violation.
- **Recommended fix:** Replace with a `notification_fallback_email` field on a new `APC Operations Settings` single doctype, defaulted to empty. If empty, log a warning and drop the email rather than send to an unknown recipient.
- **Effort:** Quick (1–2 hours).

---

### HIGH

#### Gap 8 — Duplicated `Transport Schedule` doctype folder (one is a stub)
- **Severity:** High
- **Area:** Architecture / Maintainability
- **Files:**
  - `apps/apc_operations/apc_operations/shipping/doctype/transport_schedule/` (only `__init__.py`)
  - `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/` (real `.json`, `.py`, `.js`, test)
- **What's wrong:** Frappe `desk` and other code may resolve module paths from the doctype JSON's `module` field. Having two folders for the same doctype name creates ambiguity for tooling and code search (`from apc_operations.shipping.doctype.transport_schedule ...` would currently fail or import an empty stub).
- **Recommended fix:** Delete the empty `shipping/doctype/transport_schedule/` folder; ensure all imports use `apc_operations.transportation.doctype.transport_schedule.transport_schedule`. Run `bench --site apc.local clear-cache` and verify Module list.
- **Effort:** Quick.

#### Gap 9 — `validate_immutable_after_approval` on COA is never called
- **Severity:** High
- **Area:** Data integrity / Audit
- **File:** `apps/apc_operations/apc_operations/inventory/doctype/apc_coa/apc_coa.py` lines 193–211 (defined) — not called from `validate()` (lines 18–24)
- **What's wrong:** The COA is supposed to be immutable after approval, but the guard method isn't wired into `validate()`. Approved COAs can be edited at will.
- **Recommended fix:** Call `self.validate_immutable_after_approval()` from `validate()`. Add a test that asserts saving an approved COA with a changed test result throws.
- **Effort:** Quick.

#### Gap 10 — `create_apc_coa_from_qc` creates an Approved COA bypassing all test validation
- **Severity:** High
- **Area:** Data integrity / Compliance
- **File:** `apps/apc_operations/apc_operations/inventory/doctype/apc_coa/apc_coa.py` lines 463–572
- **What's wrong:** Creates a new `APC COA` with `status = "Approved"`, `approval_status = "Approved"`, `approved_by = frappe.session.user`, **with zero test_results rows**. The normal `approve_coa()` path requires mandatory test parameters to be filled and passing — that's all skipped here.
- **Why it matters:** A COA "approved" without test data has no compliance value and trivially breaks the FIFO+COA traceability promise.
- **Recommended fix:** Either (a) require an attached COA Template and execute the standard validation, or (b) create the COA in `Pending Testing` status and require a Quality Manager to explicitly approve. At minimum, populate `qc_remarks` and log the auto-approval source in a comment.
- **Effort:** Medium.

#### Gap 11 — Recursive `save()` calls in `SecurityInspection.on_update` (no recursion guard)
- **Severity:** High
- **Area:** Reliability
- **File:** `apps/apc_operations/apc_operations/security/doctype/security_inspection/security_inspection.py` lines 121–138
- **What's wrong:** `on_update` calls `sync_to_qc_report` → `qc_doc.save()` (which triggers QC Report Request's `on_update`, which writes back to Security Inspection via `frappe.db.set_value`). It also calls `sync_to_loading_dn` → `ld_doc.save()` (which calls `sync_to_security_inspection`). There is no `frappe.flags.in_sync_*` guard, unlike the Shipping Booking and Transport Schedule flows.
- **Why it matters:** Status flips made by users can cascade into multiple unnecessary saves; combined with the auto status-mapping logic, manual edits can be silently overwritten.
- **Recommended fix:** Adopt the existing `frappe.flags.in_*` pattern used in `transport_events.py` / `shipping_booking.py`; or prefer `frappe.db.set_value` over `doc.save()` when only a single field is changing.
- **Effort:** Quick.

#### Gap 12 — `ignore_permissions=True` used liberally (≈ 80 call sites)
- **Severity:** High
- **Area:** Security
- **Locations:** Counted occurrences include `security/api.py` (19), `inventory/apc_batch.py` (4), `inventory/apc_coa.py` (3), `shipping/api.py` (2), `services/batch_allocation.py` (1), `zoho/api.py` (3), `zoho/integration.py` (4), `production/production_order_events.py` (3), and many more.
- **What's wrong:** Whitelisted endpoints invoke `doc.insert(ignore_permissions=True)` / `doc.save(ignore_permissions=True)` and `frappe.db.set_value(..., update_modified=False)`. Combined with the auth bypass in `validate_api_key`, this lets any caller create batches, items, customers, job orders, and dispatch orders.
- **Recommended fix:** Audit every `ignore_permissions=True` against the calling context. For server-to-server flows (Zoho), prefer a dedicated service account with explicit role permissions; remove `ignore_permissions` for user-driven endpoints.
- **Effort:** Medium (sweeping change with risk of breaking flows; review per file).

#### Gap 13 — `frappe.db.commit()` inside Zoho log_sync mid-request
- **Severity:** High
- **Area:** Data integrity
- **Files:**
  - `apps/apc_operations/apc_operations/zoho/integration.py` line 386
  - `apps/apc_operations/apc_operations/zoho/api.py` line 794
- **What's wrong:** Calling `frappe.db.commit()` from a request handler forces a commit of the entire current transaction, even unrelated work, and breaks Frappe's automatic transaction management. If a subsequent step in the same request fails, the partial state is already persisted.
- **Recommended fix:** Remove `frappe.db.commit()` from `log_sync`. Frappe will commit at the end of the request automatically. If you want logs to survive a rollback, write them via `frappe.enqueue` to a background job instead.
- **Effort:** Quick.

#### Gap 14 — Broken date-range filters via duplicate dict keys
- **Severity:** High
- **Area:** Data accuracy (dashboards)
- **File:** `apps/apc_operations/apc_operations/shipping/api.py` lines 128–140
- **What's wrong:**

```python
"pull_out_3days": frappe.db.count("Shipping Booking", {
    "pull_out_date": ["<=", in_3_days],
    "pull_out_date": [">=", today_str],
}),
"etd_7days": frappe.db.count("Shipping Booking", {
    "vessel_date": ["<=", in_7_days],
    "vessel_date": [">=", today_str],
}),
```

Python dict literal with duplicate keys keeps only the last value. So `pull_out_3days` only checks `pull_out_date >= today_str` (not the upper bound), and `etd_7days` only checks `vessel_date >= today_str`. Dashboards over-count.
- **Recommended fix:** Use Frappe's `["between", [low, high]]` operator (`{"pull_out_date": ["between", [today_str, in_3_days]]}`).
- **Effort:** Quick.

#### Gap 15 — `populate_source_details` mutates customer to `None` mid-validation
- **Severity:** High
- **Area:** Data integrity
- **File:** `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` lines 467–501
- **What's wrong:** In `create_security_draft_delivery_note`, if `self.customer` doesn't exist as a `Customer` record, the code sets `self.customer = None` on the parent Transport Schedule doc, then proceeds to insert the draft DN. On the next save of the Transport Schedule, the customer link is silently destroyed.
- **Recommended fix:** Don't mutate the parent doc. Use a local variable: `dn_customer = self.customer if frappe.db.exists("Customer", self.customer) else None`.
- **Effort:** Quick.

#### Gap 16 — `bulk_generate_transport` swallows exceptions and rolls forward
- **Severity:** High
- **Area:** Reliability
- **File:** `apps/apc_operations/apc_operations/shipping/api.py` lines 725–740
- **What's wrong:** Catches `except Exception` per booking, returns `{"status": "error"}` to the client, but logs nothing. Failures during bulk operation are invisible to operations.
- **Recommended fix:** `frappe.log_error(frappe.get_traceback(), "Bulk Generate Transport")` per failure and include a `traceback_id` in the response so admins can audit.
- **Effort:** Quick.

#### Gap 17 — Duplicated `sync_status_to_job_order` in two places, inconsistent semantics
- **Severity:** High
- **Area:** Architecture
- **Files:**
  - `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` lines 239–264 (`TransportSchedule.sync_status_to_job_order` — uses `frappe.flags.in_sync_status_to_job_order`)
  - `apps/apc_operations/apc_operations/shipping/transport_events.py` lines 53–78 (`sync_transport_to_job_order` — uses `frappe.flags.in_sync_transport_to_job_order`)
- **What's wrong:** Two near-identical functions with different flag names. The controller `on_update` does NOT call its own `sync_status_to_job_order`; it relies on the hook in `transport_events.py`. The flag the hook checks is different from the flag the controller would set, so cross-recursion guards don't actually protect each other.
- **Recommended fix:** Consolidate into one helper in `transport_events.py`; remove the dead method from the controller; standardize on one flag name (`frappe.flags.in_transport_status_sync`).
- **Effort:** Quick.

#### Gap 18 — Whitelisted endpoints have no role scope
- **Severity:** High
- **Area:** Security
- **Files:** Most `@frappe.whitelist()` endpoints (counted ≥ 130 total)
- **What's wrong:** `@frappe.whitelist()` accepts the default authentication (any logged-in user). Many endpoints assume the caller has the right role but never check (`allocate_batches_fifo`, `release_allocation`, `create_dispatch_from_allocation`, `confirm_dispatch_and_deduct_stock`, `quick_create_vessel_booking`, `update_job_order_status`, etc.). A `Shipping User` can release allocations meant for `Quality Manager`.
- **Recommended fix:** Add explicit role checks at the top of each whitelisted method:

```python
if not set(frappe.get_roles()).intersection({"Quality Manager", "System Manager"}):
    frappe.throw(_("Insufficient permissions"), frappe.PermissionError)
```

Or implement a decorator (`@requires_role(...)`) and apply it consistently.
- **Effort:** Medium.

#### Gap 19 — `QCReportRequest.on_update` allows arbitrary user to set "QC Cleared"
- **Severity:** High
- **Area:** Security / Compliance
- **File:** `apps/apc_operations/apc_operations/shipping/doctype/qc_report_request/qc_report_request.py` lines 11–90
- **What's wrong:** The doc has no docstatus (Draft remains editable). Any user with write access to `QC Report Request` can change `qc_status` to `"QC Cleared"`. The flow then propagates "QC Cleared" to Security Inspection and Loading DN automatically.
- **Recommended fix:** Restrict `qc_status` transition to a Quality Manager role; require submission (`docstatus = 1`) before "QC Cleared" propagates; sign with `qc_checked_by = frappe.session.user` enforced server-side.
- **Effort:** Medium.

#### Gap 20 — Multi-batch dispatch has no transaction; partial writes possible
- **Severity:** High
- **Area:** Data integrity
- **File:** `apps/apc_operations/apc_operations/services/batch_allocation.py` `confirm_dispatch_and_deduct_stock` lines 678–697
- **What's wrong:** Iterates `loading_dn.batch_allocations` and calls `batch_doc.deduct_dispatch_qty(...)` per row, then `frappe.db.set_value` on the COA, then `db_set` on the loading_dn. If the 5th batch fails (e.g. raises during deduct), the first 4 are already updated and there's no rollback.
- **Recommended fix:** Wrap the whole flow in `frappe.db.savepoint(name)` / explicit transaction. Or pre-validate all batches first (`for_update` lock), then commit all writes only after validation passes.
- **Effort:** Medium.

---

### MEDIUM

#### Gap 21 — `_resolve_user_email` falls back to user-id-as-email
- **Severity:** Medium
- **Area:** Security / Email deliverability
- **File:** `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` lines 21–25, and identical pattern in `services/email_recipients.py`
- **What's wrong:** If a user has no `email` field set, the code falls back to `_first_valid_email(user_id)`. Frappe `User.name` is typically the email, so this often works — but it's a brittle assumption and silently bypasses missing-email validation. Worse: if `user_id` happens to be valid as an email (e.g. `tej@apc.com`), notifications get sent there regardless of whether the user actually owns that inbox.
- **Recommended fix:** Drop the fallback; rely on `User.email` only; log when a role member has no email.
- **Effort:** Quick.

#### Gap 22 — Empty `before_submit` in Transport Schedule disables business gate
- **Severity:** Medium
- **Area:** Workflow integrity
- **File:** `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` lines 135–138
- **What's wrong:**

```python
def before_submit(self):
    # if self.transport_status not in ["Delivered", "Completed"]:
    #     frappe.throw(_("Transport must be Delivered or Completed before submission"))
    pass
```

The check is commented out, so any draft transport can be submitted (and that triggers `create_gate_passes` and `notify_payables_team`).
- **Recommended fix:** Either remove the method entirely or restore the validation. Decide whether submission ought to require a terminal status.
- **Effort:** Quick.

#### Gap 23 — `validate_dates` in Transport Schedule throws on equal pickup/cutoff
- **Severity:** Medium
- **Area:** Data integrity / UX
- **File:** `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` lines 107–109
- **What's wrong:** `if getdate(self.scheduled_pickup_date) >= getdate(self.cutoff_date)` will throw even if both are equal — but in `Job Order.create_or_link_transport_schedule` the auto-created Transport Schedule sets both `scheduled_pickup_date = self.date` and `scheduled_delivery_date = self.date`, then later when `populate_source_details` copies `cutoff_date` from the Shipping Booking, if cutoff is the same day as pickup, save will throw.
- **Recommended fix:** Use `>`, not `>=`, OR ensure auto-population sets pickup to `cutoff_date - N days`.
- **Effort:** Quick.

#### Gap 24 — `loading_dn.save(ignore_permissions=True)` inside `create_loading_dn_batch_allocations`
- **Severity:** Medium
- **Area:** Security
- **File:** `apps/apc_operations/apc_operations/services/batch_allocation.py` line 588
- **What's wrong:** Whitelisted entry point saves a Loading DN bypassing permissions. Even though the underlying doctype check should be done by Frappe, this short-circuits role-based restrictions.
- **Recommended fix:** Require explicit role (Security/Quality Manager) before bypassing.
- **Effort:** Quick.

#### Gap 25 — `APC Batch Allocation` modifies child rows via `detail.save()` after `Released`
- **Severity:** Medium
- **Area:** Data integrity
- **File:** `apps/apc_operations/apc_operations/services/batch_allocation.py` lines 346–350
- **What's wrong:** After setting `allocation.allocation_status = "Released"` and saving, the function iterates again over `allocation.allocation_details` and calls `detail.save()` per row. Child table rows can only be saved via the parent — `detail.save()` is a no-op on child docs in Frappe and won't persist `detail.status = "Released"`.
- **Recommended fix:** Set `detail.status = "Released"` inside the same loop before `allocation.save()`, or use `frappe.db.set_value("APC Batch Allocation Detail", detail.name, "status", "Released", update_modified=False)`.
- **Effort:** Quick.

#### Gap 26 — `update_batch_depletion` in Dispatch Order ignores allocated_quantity
- **Severity:** Medium
- **Area:** Data integrity
- **File:** `apps/apc_operations/apc_operations/dispatch/doctype/apc_dispatch_order/apc_dispatch_order.py` lines 194–205
- **What's wrong:** After dispatch, the code does `new_available = batch.available_quantity - detail.quantity`. But `APCBatch.calculate_available_quantity` (validate) recomputes `available_quantity = batch_quantity - allocated_quantity`. Next time the batch is saved (e.g. via on_update hook), the manual `db_set` of available_quantity is reverted. The two layers don't agree on which formula governs stock.
- **Recommended fix:** Decouple `available_quantity` calculation. Use `available = batch_quantity - allocated - dispatched` everywhere, or maintain `available_quantity` as the materialized source of truth and never auto-compute it from `batch_quantity - allocated`.
- **Effort:** Medium.

#### Gap 27 — Validation of `validate_checklist_completion` skips if no items
- **Severity:** Medium
- **Area:** Workflow integrity
- **File:** `apps/apc_operations/apc_operations/security/doctype/security_inspection/security_inspection.py` lines 62–77
- **What's wrong:** If `self.checklist_items` is empty (race during insert, or a future inspection without `before_insert` populating defaults — e.g. created by code that doesn't trigger `before_insert`), the method returns silently and status stays `Draft`. A user can then advance it manually to `Reported to QC` without a checklist.
- **Recommended fix:** Throw if checklist items are missing on any non-Draft status, or auto-populate inside `validate()`.
- **Effort:** Quick.

#### Gap 28 — `LoadingDeliveryNote.report_to_receivables` skips COA check if `batch_allocations` empty
- **Severity:** Medium
- **Area:** Compliance / Traceability
- **File:** `apps/apc_operations/apc_operations/shipping/doctype/loading_delivery_note/loading_delivery_note.py` lines 132–159
- **What's wrong:** "No batch allocations — this is acceptable only if explicitly flagged" → shows an orange `msgprint` and proceeds. The doctype has no `explicit_no_batch_traceability` flag, so the warning is informational; receivables reporting still completes. Per `CLAUDE.md` "User cannot dispatch a batch without approved COA", this contradicts the requirement.
- **Recommended fix:** Block report_to_receivables unless either (a) batch_allocations rows exist AND each has approved COA, or (b) a dedicated `traceability_override` field + reason is set by a Quality Manager.
- **Effort:** Quick.

#### Gap 29 — `Security Inspection.create_dispatch_order` allows dispatch without batch traceability
- **Severity:** Medium
- **Area:** Compliance / Traceability
- **File:** `apps/apc_operations/apc_operations/security/doctype/security_inspection/security_inspection.py` lines 454–463
- **What's wrong:** If no allocation is found, the `else` branch appends Job Order items into `dispatch.batch_details` with **no batch**. The dispatch then submits with rows lacking `batch`, defeating FIFO + COA traceability.
- **Recommended fix:** Throw if no allocation is linked; require Sales Demand + Allocation before dispatch.
- **Effort:** Quick.

#### Gap 30 — N+1 queries in dispatch update
- **Severity:** Medium
- **Area:** Performance
- **Files:**
  - `apps/apc_operations/apc_operations/dispatch/doctype/apc_dispatch_order/apc_dispatch_order.py` `update_allocation_dispatched_qty` does a `frappe.get_all` then a `frappe.get_doc` per match — N+1 against `APC Batch Allocation Detail`.
  - `apps/apc_operations/apc_operations/inventory/doctype/apc_batch/apc_batch.py` `check_allocation_limits` runs a SQL per batch save.
- **Recommended fix:** Pre-fetch all matching alloc detail rows in one query; or use `frappe.db.sql` with grouped UPDATE.
- **Effort:** Medium.

#### Gap 31 — `frappe.get_doc("Customer", ...)` with no null check in `create_job_order_from_pfi`
- **Severity:** Medium
- **Area:** Reliability
- **File:** `apps/apc_operations/apc_operations/zoho/api.py` lines 282–301
- **What's wrong:** No null check on `sales_demand.customer` before `frappe.get_doc("Customer", ...)`. If the Sales Demand has no customer (possible during partial imports), the API returns a 500.
- **Recommended fix:** Validate before; return a structured `{"success": false, "error": "Sales Demand has no Customer"}`.
- **Effort:** Quick.

#### Gap 32 — Two `get_or_create_customer` / `get_or_create_item` implementations diverge
- **Severity:** Medium
- **Area:** Code duplication / Data consistency
- **Files:**
  - `apps/apc_operations/apc_operations/zoho/integration.py` lines 268–290
  - `apps/apc_operations/apc_operations/zoho/api.py` lines 698–773
- **What's wrong:** The api.py version hardcodes `customer_group = "Commercial"`, `territory = "All Territories"`, `item_group = "APC Products"`. The integration.py version uses cascading lookups for defaults. Whichever module is imported first wins, and behavior depends on call site.
- **Recommended fix:** Consolidate into a single `apc_operations.zoho.helpers` module with explicit `get_or_create_customer_from_zoho`. Delete the dupe.
- **Effort:** Quick.

#### Gap 33 — Whitelisted methods on doctype classes have no role enforcement
- **Severity:** Medium
- **Area:** Security
- **Examples:**
  - `SecurityInspection.report_to_qc`, `create_loading_delivery_note`, `create_dispatch_order` (all `@frappe.whitelist()` instance methods)
  - `APCBatchAllocation.release_allocation`
  - `LoadingDeliveryNote.confirm_dispatch`, `allocate_batches_fifo`, `verify_coas`, `report_to_receivables`
- **What's wrong:** Any user with write access on the parent doctype can call these methods. They perform privileged transitions (creating linked docs, releasing reservations).
- **Recommended fix:** Add per-method role checks. Define a `@requires_role(...)` helper.
- **Effort:** Medium.

#### Gap 34 — Inconsistent recursion-guard naming and coverage
- **Severity:** Medium
- **Area:** Reliability
- **Files:** `frappe.flags.in_sync_booking_to_job_order` (shipping_booking.py), `frappe.flags.in_sync_transport_to_job_order` (transport_events.py), `frappe.flags.in_sync_status_to_job_order` (transport_schedule.py, dead), `frappe.flags.in_create_operational_booking` (job_order.py), `frappe.flags.in_erpnext_batch_sync` (apc_batch.py), `frappe.flags.in_auto_coa_creation` (apc_batch.py).
- **What's wrong:** Five different naming conventions for the same idea. If a future developer adds a new sync from Job Order to Shipping Booking, they have to know to set BOTH `in_sync_booking_to_job_order` and `in_sync_transport_to_job_order`. There is no central registry.
- **Recommended fix:** Build a `_with_sync_lock(flag_name)` context manager utility; document the canonical naming. Or rebuild the sync layer as a centralised "event bus" that handles status mappings declaratively.
- **Effort:** Large (architectural refactor).

#### Gap 35 — Patches use raw `frappe.db.sql` but don't wrap in transactions
- **Severity:** Medium
- **Area:** Data integrity (migration)
- **File:** Multiple in `apps/apc_operations/apc_operations/patches/`
- **What's wrong:** Each patch runs SQL directly. If a patch fails halfway, partial column changes/backfills remain.
- **Recommended fix:** Frappe patches generally run in a transaction by default but custom SQL needs explicit handling for DDL vs DML. Add try/except + log_error.
- **Effort:** Medium.

#### Gap 36 — `webhook_*` endpoints return success unconditionally without storing payload
- **Severity:** Medium
- **Area:** Operations (lost data)
- **File:** `apps/apc_operations/apc_operations/zoho/api.py` lines 803–823
- **What's wrong:** Even when they get implemented, they don't log the raw body for debugging. Webhook failures from Zoho will be undebuggable.
- **Recommended fix:** Always persist raw payload to `Zoho Sync Log` before processing.
- **Effort:** Quick.

#### Gap 37 — `Notification Log` insert uses non-existent user fallback
- **Severity:** Medium
- **Area:** Reliability
- **File:** `apps/apc_operations/apc_operations/shipping/reminders.py` lines 268–275
- **What's wrong:** Inside `notify_users_about_cutoffs`, if `booking.modified_by` doesn't exist in `User`, fallback is `"Administrator"`. Each reminder is logged to Administrator's notification feed. Noisy and useless.
- **Recommended fix:** Skip Notification Log creation when the recipient user is invalid; or send to the role group.
- **Effort:** Quick.

#### Gap 38 — No timeouts/retries/backoff anywhere in Zoho integration
- **Severity:** Medium
- **Area:** Reliability
- **File:** `apps/apc_operations/apc_operations/zoho/integration.py` and `apc_operations/zoho/api.py`
- **What's wrong:** Once real Zoho calls are wired in (`get_zoho_sales_order`, `create_zoho_delivery_note`, `update_zoho_stock`), there are no `requests` timeouts, retry policy, circuit breaker, or rate-limit handling.
- **Recommended fix:** Use `frappe.enqueue` for outbound Zoho calls; wrap with `tenacity` retry (exponential backoff, max 3 attempts); set request timeouts (≤ 10 s); record retry_count in `Zoho Sync Log`.
- **Effort:** Medium.

#### Gap 39 — `tests/test_batch_allocation.py` deletes data with raw SQL bypassing controllers
- **Severity:** Medium
- **Area:** Testing
- **File:** `apps/apc_operations/apc_operations/tests/test_batch_allocation.py` lines 128–155
- **What's wrong:** `tearDown` runs `DELETE FROM \`tabAPC Batch\`...` directly. Stock state, COA links, and bridge ERPNext Batches remain orphaned between tests, contaminating subsequent runs.
- **Recommended fix:** Use `frappe.delete_doc` to cascade; or use `FrappeTestCase`'s built-in rollback (transactional tests).
- **Effort:** Quick.

#### Gap 40 — Tests don't validate the double-execution bug exists
- **Severity:** Medium
- **Area:** Testing
- **What's wrong:** `test_fifo_allocation` (test_batch_allocation.py line 211) creates an allocation but doesn't `submit()` it, so the on_submit double-execution path is never exercised. Same for dispatch tests.
- **Recommended fix:** Add explicit `submit()` + post-condition asserts (`assertEqual(batch.allocated_quantity, alloc_qty)` after submit, not `2 * alloc_qty`).
- **Effort:** Quick.

---

### LOW

#### Gap 41 — Inconsistent currency handling
- **Severity:** Low
- **File:** `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py` lines 391–423 (emails reference `self.currency` without validating it's set)
- **Recommended fix:** Default currency, validate before email; or pull from Company.

#### Gap 42 — HTML email templates inline in Python (XSS risk if values from user input)
- **Severity:** Low
- **Files:** `reminders.py`, `transport_schedule.py`, `loading_delivery_note.py`, `qc_report_request.py` — all build HTML emails by string interpolation of model fields.
- **Recommended fix:** Use Frappe Email Templates (`get_template`) and parameterize via Jinja with auto-escaping.

#### Gap 43 — Mixed `today()` vs `now()` semantics
- **Severity:** Low
- **Files:** Many — sometimes `today()` (date), sometimes `now()` (datetime), sometimes mixing for the same conceptual timestamp.
- **Recommended fix:** Standardize on `frappe.utils.now()` for audit timestamps.

#### Gap 44 — Dead code: `JobOrder.create_or_link_on_business_confirmation` is defined but never called
- **Severity:** Low
- **File:** `apps/apc_operations/apc_operations/shipping/doctype/job_order/job_order.py` lines 367–376
- **Recommended fix:** Remove; or wire into `on_update` and adjust `ensure_operational_booking_links`.

#### Gap 45 — `JobOrder.validate` calls 5 methods but only 4 are mirrored in the `validate_job_order` module-level hook
- **Severity:** Low
- **File:** `apps/apc_operations/apc_operations/shipping/doctype/job_order/job_order.py` line 217 vs line 548
- **What's wrong:** `JobOrder.validate()` calls `validate_job_order_number_uniqueness` + `fetch_customer_name` + `determine_booking_requirement` + `sync_booking_flags` + `validate_insurance_on_confirm`. The `hooks.py` "Job Order:validate" handler `validate_job_order` skips `validate_job_order_number_uniqueness`. If the controller logic is ever conditioned on doctype hooks, behaviour drifts.
- **Recommended fix:** Either delete the module-level hook (the class's `validate()` is enough) or keep them aligned.

#### Gap 46 — Markdown docs in repo are stale (`APC_ERPNEXT_AUDIT_REPORT.md`, `IMPLEMENTATION_SUMMARY.md`)
- **Severity:** Low
- **Recommended fix:** Move to `docs/` and date-stamp; or remove from the repo root.

#### Gap 47 — `_safe_path_segment` doesn't normalise leading dots, multiple separators
- **Severity:** Low
- **File:** `apps/apc_operations/apc_operations/services/nas_service.py` lines 226–230
- **Recommended fix:** Strip leading dots; collapse multiple underscores; cap length to 64 chars.

#### Gap 48 — Many docstrings/comments use ASCII box-drawing characters
- **Severity:** Low
- **Area:** Developer experience
- **Recommended fix:** Cosmetic; OK in Python comments but render oddly in some IDEs.

#### Gap 49 — `app_version = "0.0.1"` and `required_apps = ["erpnext"]` without pin
- **Severity:** Low
- **File:** `apps/apc_operations/apc_operations/hooks.py` lines 7–8
- **Recommended fix:** Pin to a tested ERPNext version (e.g. `>=15.0.0,<16`).

---

## 4. Gap Analysis Table (Index)

| # | Gap | Severity | Area | File / location | Recommended fix | Effort |
|---|---|---|---|---|---|---|
| 1 | Duplicate event handlers double-execute dispatch mutations | Critical | Data integrity | `hooks.py` 100–108 + apc_dispatch_order.py / apc_batch_allocation.py / apc_sales_demand.py | Drop hook entries; keep controller `on_submit` only | Quick |
| 2 | `scheduler_events` defined twice — reminders dead | Critical | Operations | `hooks.py` 27–49 and 112–116 | Merge into single dict | Quick |
| 3 | Zoho API auth bypass when no key configured | Critical | Security | `zoho/api.py` 32–55 | Fail closed; constant-time compare | Quick |
| 4 | Public webhooks have no signature verification | Critical | Security | `zoho/api.py` 803–823 | HMAC verification | Quick |
| 5 | FIFO allocation race condition; no row lock | Critical | Data integrity | `apc_batch.py` + `services/batch_allocation.py` | `SELECT ... FOR UPDATE` or atomic conditional UPDATE | Medium |
| 6 | Patches on disk not in `patches.txt` | Critical | Deployment | `apc_operations/patches/v0_2/*` | Register patches | Quick |
| 7 | Hardcoded developer email fallback | Critical | Security | `services/email_recipients.py` + reminders.py + transport_schedule.py | Settings field, empty default | Quick |
| 8 | Duplicate `Transport Schedule` doctype folder | High | Architecture | `shipping/doctype/transport_schedule/` (stub) | Delete stub | Quick |
| 9 | `validate_immutable_after_approval` never called | High | Data integrity | `apc_coa.py` 193–211 | Wire into `validate()` | Quick |
| 10 | `create_apc_coa_from_qc` auto-approves without tests | High | Compliance | `apc_coa.py` 463–572 | Require test results or use Pending Testing | Medium |
| 11 | `SecurityInspection.on_update` recursive saves | High | Reliability | `security_inspection.py` 121–138 | Add recursion guard | Quick |
| 12 | `ignore_permissions=True` widespread | High | Security | ~80 sites | Audit per call site | Medium |
| 13 | `frappe.db.commit()` mid-request in Zoho logs | High | Data integrity | `zoho/integration.py` 386, `zoho/api.py` 794 | Remove commit | Quick |
| 14 | Duplicate dict keys break date-range filters | High | Data accuracy | `shipping/api.py` 128–140 | Use `["between", [low, high]]` | Quick |
| 15 | `populate_source_details` nulls customer | High | Data integrity | `transport_schedule.py` 467–501 | Use local var | Quick |
| 16 | `bulk_generate_transport` swallows errors silently | High | Reliability | `shipping/api.py` 725–740 | Log + return traceback id | Quick |
| 17 | Duplicate sync functions, mismatched flags | High | Architecture | `transport_schedule.py` 239–264 + `transport_events.py` 53–78 | Consolidate | Quick |
| 18 | Whitelisted endpoints have no role check | High | Security | ~130 endpoints | `@requires_role` decorator | Medium |
| 19 | Anyone can flip QC Report Request to QC Cleared | High | Security/Compliance | `qc_report_request.py` 11–90 | Role gate + docstatus | Medium |
| 20 | Multi-batch dispatch is not transactional | High | Data integrity | `services/batch_allocation.py` 678–697 | Savepoint / pre-validate | Medium |
| 21 | `_resolve_user_email` falls back to user_id | Medium | Security | `transport_schedule.py` 21–25 | Drop fallback | Quick |
| 22 | Empty `before_submit` in Transport Schedule | Medium | Workflow | `transport_schedule.py` 135–138 | Restore check or remove | Quick |
| 23 | `validate_dates` `>=` rejects equal dates | Medium | UX | `transport_schedule.py` 107–109 | Use `>` | Quick |
| 24 | Loading DN save with `ignore_permissions=True` | Medium | Security | `services/batch_allocation.py` 588 | Add role check | Quick |
| 25 | `detail.save()` on child rows is no-op | Medium | Data integrity | `services/batch_allocation.py` 346–350 | Set status in main loop | Quick |
| 26 | `update_batch_depletion` conflicts with validate() | Medium | Data integrity | `apc_dispatch_order.py` 194–205 | Unify available_quantity formula | Medium |
| 27 | Checklist validation skips when items empty | Medium | Workflow | `security_inspection.py` 62–77 | Throw if missing | Quick |
| 28 | `report_to_receivables` skips COA when no allocations | Medium | Compliance | `loading_delivery_note.py` 132–159 | Require allocations or override | Quick |
| 29 | `create_dispatch_order` allows dispatch without batch | Medium | Compliance | `security_inspection.py` 454–463 | Throw if no allocation | Quick |
| 30 | N+1 query in dispatch update | Medium | Performance | `apc_dispatch_order.py` `update_allocation_dispatched_qty` | Bulk fetch + grouped UPDATE | Medium |
| 31 | Null customer crash in PFI → Job Order | Medium | Reliability | `zoho/api.py` 282–301 | Validate before get_doc | Quick |
| 32 | Duplicate `get_or_create_*` helpers | Medium | Code duplication | `zoho/integration.py` + `zoho/api.py` | Consolidate | Quick |
| 33 | Doctype-level whitelisted methods unauthorised | Medium | Security | Multiple controllers | Per-method role check | Medium |
| 34 | Inconsistent recursion-guard naming | Medium | Reliability | Several files | Central `with_sync_lock(...)` | Large |
| 35 | Patches don't try/except wrap raw SQL | Medium | Migration safety | `apc_operations/patches/**` | Add try/except + log | Medium |
| 36 | Webhook payloads not persisted | Medium | Operations | `zoho/api.py` 803–823 | Save raw body to `Zoho Sync Log` | Quick |
| 37 | Notification Log fallback to Administrator | Medium | Reliability | `reminders.py` 268–275 | Skip on invalid user | Quick |
| 38 | No timeouts/retries on Zoho calls | Medium | Reliability | `zoho/*` | tenacity + frappe.enqueue + timeouts | Medium |
| 39 | Test teardown bypasses controllers | Medium | Testing | `test_batch_allocation.py` 128–155 | Use FrappeTestCase rollback | Quick |
| 40 | Tests don't exercise double-execution | Medium | Testing | `test_batch_allocation.py` | Add `submit()` + post-asserts | Quick |
| 41 | Currency assumed in emails | Low | Reliability | `transport_schedule.py` 391–423 | Default from Company | Quick |
| 42 | HTML emails by string interpolation | Low | Security/UX | `reminders.py`, others | Use Email Templates | Medium |
| 43 | Mixed `today()` / `now()` | Low | Consistency | Many files | Standardise | Quick |
| 44 | Dead `create_or_link_on_business_confirmation` | Low | Code hygiene | `job_order.py` 367–376 | Remove or wire | Quick |
| 45 | `validate_job_order` mirrors controller imperfectly | Low | Consistency | `job_order.py` 548 vs 217 | Align or delete one | Quick |
| 46 | Stale Markdown reports at repo root | Low | DX | `*.md` at root | Move to `docs/` | Quick |
| 47 | `_safe_path_segment` not strict enough | Low | Security (defence in depth) | `nas_service.py` 226–230 | Strict normalise | Quick |
| 48 | Box-drawing characters in code | Low | DX | Many | Cosmetic | Trivial |
| 49 | `required_apps = ["erpnext"]` not pinned | Low | Deployment | `hooks.py` 7–8 | Pin version range | Quick |

---

## 5. Quick Wins (under 1 day each)

| # | Action | Effort |
|---|---|---|
| 1 | Merge the duplicate `scheduler_events` dict in `hooks.py` (Gap 2) | 10 min |
| 2 | Remove `on_submit_dispatch`, `on_submit_allocation`, `on_update_sales_demand` from `hooks.py.doc_events` (Gap 1). Keep the controllers. | 30 min |
| 3 | Add missing patches to `patches.txt` (Gap 6) | 15 min |
| 4 | Wire `validate_immutable_after_approval` into COA `validate()` (Gap 9) | 15 min |
| 5 | Replace `FALLBACK_NOTIFICATION_EMAIL` constants with a settings field; default to empty (Gap 7) | 1 hour |
| 6 | Delete the empty `shipping/doctype/transport_schedule/` folder (Gap 8) | 10 min |
| 7 | Fix duplicate dict keys in `upcoming_milestones` using `between` operator (Gap 14) | 15 min |
| 8 | Remove the `self.customer = None` mutation in Transport Schedule (Gap 15) | 10 min |
| 9 | Fail closed in `validate_api_key` if no key configured (Gap 3) | 30 min |
| 10 | Remove `frappe.db.commit()` from Zoho `log_sync` (Gap 13) | 10 min |
| 11 | Fix `validate_dates` `>=` → `>` in Transport Schedule (Gap 23) | 5 min |
| 12 | Add error logging to `bulk_generate_transport` (Gap 16) | 15 min |
| 13 | Restore or remove the empty `before_submit` in Transport Schedule (Gap 22) | 5 min |
| 14 | Move `detail.status = "Released"` inside the save loop in batch allocation release (Gap 25) | 10 min |
| 15 | Drop `_resolve_user_email` user-id-as-email fallback (Gap 21) | 30 min |

A single half-day of focused work covers the dispatch corruption bug, the dead scheduler, the auth bypass, and the email leak.

---

## 6. High-Impact Refactors

1. **Status synchronization engine.** Replace the scattered `on_update` → `db.set_value` + `frappe.flags.in_*` pattern with a declarative sync layer (a `status_map.yml` listing source doctype → destination doctype → field map → trigger condition), plus a single dispatcher. Eliminates Gaps 11, 17, 34.
2. **Atomic FIFO allocation service.** Rewrite `allocate_batches_fifo` and `confirm_dispatch_and_deduct_stock` as transactional operations that use `SELECT ... FOR UPDATE` (or atomic conditional UPDATEs) and execute the whole loop under one savepoint. Reuse the same helper for `APC Batch.allocate_quantity`, `release_allocation`, `deduct_dispatch_qty`. Addresses Gaps 5, 20, 25, 26.
3. **Zoho integration extraction.** Build a real `ZohoClient` (httpx + tenacity), separate models for Sales Order / Delivery Note, idempotency keys, signed webhooks, and a job queue (`frappe.enqueue`). Move mock helpers behind a `FakeZohoClient` injectable for tests. Addresses Gaps 3, 4, 13, 32, 36, 38.
4. **Role-based whitelist decorator.** `@apc_endpoint(roles=[...], audit=True)` that runs `frappe.session.user` role check, logs the call with parameters to a `APC Audit Log`, and returns a consistent JSON envelope. Addresses Gaps 12, 18, 19, 24, 33.
5. **Service-layer split.** Move all "create linked doc" logic out of `Document` subclasses into `apc_operations.services.*` modules per `CLAUDE.md` recommendation. Controllers should only validate; services should orchestrate. Improves testability.
6. **Centralise email recipient resolution.** One module, role-based, no fallback email, with role-mapping configured via Workspace Setting docs. Addresses Gap 7, 21, 37.

---

## 7. Missing Tests

### Critical regression tests (write these immediately)

1. **`test_dispatch_submit_does_not_double_deduct`** — submit a dispatch, assert `APC Batch.available_quantity` decreased by exactly the dispatched amount, not 2×.
2. **`test_allocation_submit_does_not_double_reserve`** — submit a batch allocation, assert `APC Batch.allocated_quantity` increased by exactly the allocated amount.
3. **`test_attach_batch_coas_is_idempotent`** — submitting a dispatch twice (via amend/re-submit) does not duplicate `attached_coas` rows.
4. **`test_concurrent_fifo_allocation`** — two threads each call `allocate_batches_fifo` for the same demand; assert total allocation does not exceed available.
5. **`test_dispatch_confirm_stops_on_failure_midway`** — make the 3rd batch deduct raise; assert batches 1 and 2 are not deducted (savepoint rollback).
6. **`test_scheduler_jobs_registered`** — boot Frappe, assert `check_upcoming_cutoffs`, `send_morning_reminders`, etc. are listed in the scheduler.

### Zoho integration tests

7. **`test_zoho_api_requires_key`** — calling `import_pfi` without `X-APC-API-Key` returns 401-equivalent JSON.
8. **`test_zoho_webhook_signature`** — webhook with no signature is rejected.
9. **`test_zoho_import_idempotent`** — same `zoho_pfi_id` twice yields the same Sales Demand.

### COA / batch lifecycle

10. **`test_coa_immutable_after_approval`** — modify test_results on approved COA raises.
11. **`test_create_apc_coa_from_qc_requires_test_results`** — assert auto-creation no longer marks Approved without test data.
12. **`test_qc_status_cleared_requires_quality_role`** — a Shipping User cannot flip qc_status to QC Cleared.

### Incoterm coverage (per `CLAUDE.md`)

13. EXW: only security gate-pass Transport Schedule; no Shipping Booking.
14. FOB: APC origin Transport + Shipping Booking; insurance_required = 0; shipping_arranged_by = Customer.
15. CFR: shipping_arranged_by = APC; insurance_required = 0.
16. CIF: insurance_required = 1; validate_insurance_on_confirm throws if no policy.
17. DAP/DDP: destination_delivery_by/destination_clearance_by checks.
18. **`test_unknown_incoterm_does_not_create_transport`** — robustness.

### Status synchronization

19. Updating Transport Schedule status → Job Order.transport_status mirrors correctly (no `Pending Booking` regression after Vehicle Assigned).
20. Updating Shipping Booking booking_status → Job Order.shipping_status flows.
21. QC Report Request → Loading DN → Security Inspection sync, both Cleared and Rejected paths.

### Edge cases

22. **`test_partial_allocation_creates_production_requirement`** — covered partially in existing tests, but tighten to assert exact required quantity.
23. **`test_release_allocation_after_partial_dispatch_blocked`**.
24. **`test_loading_dn_report_to_receivables_requires_batch_traceability_or_override`**.

---

## 8. Production Readiness Checklist

Must be done before declaring this system production-grade:

- [ ] Resolve all CRITICAL gaps (1–7).
- [ ] Add the regression tests from §7 and have them pass in CI.
- [ ] Replace mock Zoho client with a real one; pin API base URL & auth in `APC Zoho Settings`.
- [ ] Add HMAC verification for Zoho webhooks.
- [ ] Replace `tejas303525@gmail.com` fallback with org-controlled distribution list configured in a Settings doctype.
- [ ] Add database row-locking around APC Batch mutations.
- [ ] Add transaction/savepoint wrappers around multi-row dispatch confirmation.
- [ ] Add explicit role checks on all whitelisted methods that mutate state.
- [ ] Audit and reduce `ignore_permissions=True` usage; document each remaining occurrence.
- [ ] Register every patch on disk in `patches.txt`.
- [ ] Set up centralised structured logging (`frappe.log_error` → Sentry/Loki) and alerting on `Zoho Sync Log` failures.
- [ ] Add background-job retry policy for outbound integrations (`tenacity` + `frappe.enqueue`).
- [ ] Document the canonical status-sync map (table per doctype pair).
- [ ] Run `bench --site apc.local migrate` on a clean DB; verify all custom fields appear without manual fixups.
- [ ] Capture a baseline DB integrity report: for each APC Batch, assert `batch_quantity = available_quantity + allocated_quantity + dispatched_quantity`.
- [ ] Add health-check endpoint reporting scheduler last-run times, Zoho sync queue depth, NAS reachability.
- [ ] Define a backup/restore runbook; verify Zoho Sync Log retention.
- [ ] Document and freeze role matrix per the modules in `fixtures` (lines 122–141 of `hooks.py`).

---

## 9. Action Plan

### Next 7 days (priority-ordered)

| Day | Tasks |
|---|---|
| **Day 1** | Apply Quick Wins #1–#4 and #6 from §5. Audit production DB for batches where `batch_quantity ≠ available + allocated + dispatched` (likely casualties of Gap 1). Reconcile manually. |
| **Day 2** | Quick Wins #5, #7, #9, #10. Add the four most important regression tests (§7 #1, #2, #3, #6). Get CI green. |
| **Day 3** | Add HMAC verification to Zoho webhooks. Lock down `validate_api_key` (Gap 3). Remove `frappe.db.commit()` from log_sync (Gap 13). Add explicit role checks to the top 10 most sensitive whitelisted methods. |
| **Day 4** | Wrap `confirm_dispatch_and_deduct_stock` and `allocate_batches_fifo` in savepoint + `SELECT FOR UPDATE` locks (Gap 5, 20). Add the concurrency test (§7 #4, #5). |
| **Day 5** | Fix Gaps 9, 10, 11, 14, 15, 22, 23, 25 (medium-priority controllers). Verify each via a focused test. |
| **Day 6** | Consolidate duplicate Zoho `get_or_create_*` helpers (Gap 32). Standardise the recursion-flag naming (Gap 17, 34). |
| **Day 7** | Run end-to-end smoke: Zoho PFI import → Job Order → Allocation → Dispatch → Loading DN → Reported to Receivables. Document outstanding issues; capture screenshots / DB snapshots before / after. |

### Days 8–30

- **Week 2:** Build the role-based whitelist decorator and migrate all `@frappe.whitelist()` endpoints to it. Stand up `APC Audit Log` doctype. Backfill all remaining unit/integration tests from §7.
- **Week 3:** Replace mock Zoho client with a real `ZohoClient` (httpx + tenacity). Move all outbound calls to `frappe.enqueue` background jobs. Add retry tracking to `Zoho Sync Log`.
- **Week 4:** Refactor status-sync into a declarative engine (config-driven). Migrate two of the existing flows (Transport Schedule ↔ Job Order, Shipping Booking ↔ Job Order) onto the new engine as proof. Add observability: health-check endpoint, scheduler-last-run dashboard, Zoho-sync-queue-depth metric.

---

## 10. Evidence Summary

- File:line citations are inline above. The four most consequential single locations to inspect are:
  - `apps/apc_operations/apc_operations/hooks.py` (duplicate scheduler dict, redundant doc_events)
  - `apps/apc_operations/apc_operations/dispatch/doctype/apc_dispatch_order/apc_dispatch_order.py` (double-execution corruption)
  - `apps/apc_operations/apc_operations/zoho/api.py` (auth bypass, unsigned webhooks)
  - `apps/apc_operations/apc_operations/services/batch_allocation.py` (no concurrency control)
- The codebase has a solid domain model and good Incoterm coverage; the issues are concentrated in cross-document orchestration and integration boundaries.
- Many medium issues are mechanical and individually small. The combination, however, makes the operational state untrustworthy: it is not currently safe to assume that DB values for `available_quantity`, `dispatched_quantity`, or `total_dispatched_quantity` reflect reality until Gap 1 is fixed and a reconciliation patch is run.

---

*End of report.*
