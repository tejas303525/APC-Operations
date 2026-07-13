# APC Operations — System Development Overview

> **As of:** May 2026  
> **Purpose:** High-level map of what is built, what system owns each area, and where the gaps are.

---

## 1. System Ownership Map

| Business Area | Owned By | Status |
|---|---|---|
| Sales Orders / PFIs | **Zoho Books** | Live |
| Invoicing & AR | **Zoho Books** | Live |
| Accounting & Payments | **Zoho Books** | Live |

| Quality Inspection (raw) | **ERPNext** | Live (native) |
| Batch / Lot Master | **ERPNext + APC Batch** | Live |
| FIFO Batch Allocation | **APC Operations** | Built |
| Sales Demand (PFI mirror) | **APC Operations** | Built |
| Job Order (operational) | **APC Operations** | Built |
| Shipping Booking | **APC Operations** | Built |
| Transport Schedule | **APC Operations** | Built |
| Security Inspection & Gate | **APC Operations** | Built |
| QC / Certificate of Analysis | **APC Operations** | Built |
| Loading & Delivery Notes | **APC Operations** | Built |
| Gate Pass | **APC Operations** | Built |
| Production Orders | **APC Operations** | Built |
| Dispatch Orders | **APC Operations** | Built |
| Document / PDF Storage | **NAS** | Built (service layer) |
| Zoho Dispatch Push (DN sync) | **APC Operations → Zoho** | Stub / partial |
| Zoho Invoice Pull | **APC Operations ← Zoho** | Stub / partial |
| Customer / Item Master | **ERPNext** | Live (native) |

| Procurement / Supplier POs |ZOHO | **Gap** |
| Import Logistics | **APC Operations** | Partial |

---

## 2. Platform Breakdown

### Zoho Books
> Finance, sales administration, and customer-facing documents.

- **Sales Orders & PFIs** — source of truth for all demand
- **Invoicing** — commercial invoices raised and sent from Zoho
- **Accounts Receivable** — payment tracking and reconciliation
- **Accounting / GL** — all journal entries, bank reconciliation
- **Delivery Note (final)** — Zoho DN is pushed to from our system when Gate Pass is released

**Integration touch-points with APC Operations:**
- Inbound: APC pulls PFI / Sales Order → creates `APC Sales Demand`
- Outbound: APC pushes `Loading Delivery Note` data → Zoho DN → triggers invoice
- Outbound: COA attachments pushed alongside DN
- Scheduled: Invoice status pulled every 15 minutes

---

### ERPNext (Standard — no customisation)
> Core ERP primitives used as a backbone.

- **Item & Customer Masters** — referenced by all modules
- **Batch / Lot records** — linked to `APC Batch` for FIFO tracking
- **Quality Inspection** — raw QI results sync into `APC COA`
- **Manufacturing** — basic production orders (APC Production Order extends this)

---

### APC Operations (Custom Frappe App)
> Operational execution layer. Everything between receiving a demand and handing off to Zoho for invoicing.

#### Sales Module
- `APC Sales Demand` — mirror of Zoho PFI/sales order
- `APC Batch Allocation` — FIFO assignment of batches to a demand

#### Job Order (Core Routing Hub)
- `Job Order` — central operational document; drives all downstream creation
- Incoterm rules determine: who arranges transport, who books vessel, whether insurance is required
- Auto-creates Transport Schedule and/or Shipping Booking on confirmation
- Handles both **Export** (APC = seller) and **Import** (APC = buyer) flows

#### Shipping Module
- `Shipping Booking` — sea freight / CRO / vessel coordination
- `Bill of Lading`, `Container Detail` — export documentation
- `Delivery Order` — operational delivery instruction
- `Loading Delivery Note` + `Loading Entry` — final loaded quantities with batch traceability
- `Gate Pass` — site exit control; release triggers Zoho dispatch sync
- `Weighment Slip` — weighbridge capture

#### Transportation Module
- `Transport Schedule` — full inland transport coordination
- Vehicle, Driver, Transporter masters
- `Transport PO Request` — transport purchase coordination
- Transportation console (live operational view)

#### Security Module
- `Security Draft Delivery Note` — pre-loading security review
- `Security Inspection` — inspection → triggers QC Request + Loading DN creation
- `Gate Control Console` — live gate management UI
- `Loading Bay Console` — bay status view

#### Quality (QC) Module
- `QC Report Request` — triggered by Security Inspection
- `Pre Check Clearance` — pre-loading QC clearance gate
- `APC COA` — Certificate of Analysis (synced from ERPNext Quality Inspection)
- COA Templates, Test Parameters, Test Results
- QC Console + QC Pre-check Console

#### Production Module
- `Production Order` — manufacturing execution
- `APC Production Requirement` — shortage-driven production planning trigger
- `Production Capacity Configuration` — capacity defaults
- Production Calendar + Production Dashboard

#### Inventory Module
- `APC Batch` — extended batch record with FIFO position, ERPNext batch link
- FIFO stock reports: Batch Stock Ledger, FIFO Allocation Report, Stock Availability
- Inventory FIFO console

#### Dispatch Module
- `APC Dispatch Order` — dispatch with full batch and COA traceability
- Batch-level and COA-level dispatch detail lines

#### Zoho Integration Module
- `APC Zoho Settings` — API credentials, endpoint config, sync toggles
- `Zoho Sync Log` — full audit trail for every sync operation
- REST API layer for all inbound/outbound Zoho communication

#### NAS Storage
- `APC NAS Settings` — mount path configuration
- Automatic PDF filing: COAs → `NAS/QC/COA/{Year}/{Customer}/{JobOrder}/`
- Security checklists → `NAS/QC/Checklists/`
- Daily retry job for failed saves

---

## 3. Operational Flow (End-to-End)

```
Zoho Books (Sales Order / PFI)
        │
        ▼  [API pull → APC Sales Demand]
APC Sales Demand
        │
        ▼  [FIFO allocation]
APC Batch Allocation ──────────── APC Batch (stock)
        │
        ▼  [create_job_order_from_pfi]
Job Order  (incoterm routing determines what is auto-created below)
        ├──────────────────────────────────────────────────────────────┐
        ▼                                                              ▼
Transport Schedule                                         Shipping Booking
        │                                                  (sea / CRO / vessel)
        ▼
Security Draft Delivery Note
        │
        ▼
Security Inspection
        │
        ▼
QC Report Request ──→ Pre Check Clearance ──→ APC COA
        │
        ▼
Loading Delivery Note  (batches + COA lines)
        │
        ▼
Loading Entry
        │
        ▼
Gate Pass  ──────────── [Zoho Dispatch Sync triggered]
        │
        ▼
Zoho Books  (Delivery Note → Invoice → AR)
```

Parallel shortage track:
```
APC Sales Demand → shortage detected → APC Production Requirement → Production Order
```

---

## 4. Potential Gaps & Risks

### Integration Gaps

| Gap | Detail | Priority |
|---|---|---|
| **Zoho dispatch sync is stub-only** | `zoho_dispatch_stub_only` flag means DN/COA/invoice push is logged but no real HTTP call is made until fully enabled. Invoice loop is incomplete. | High |
| **Zoho webhooks not implemented** | `webhook_pfi_created`, `webhook_pfi_updated`, `webhook_delivery_confirmed` are placeholder stubs. Real-time Zoho → APC push doesn't exist; relies on scheduled polling. | High |
| **Invoice status feedback loop** | 15-minute poll pulls invoice status, but there is no automated action taken in APC when an invoice is paid / overdue. | Medium |
| **Zoho customer & item master sync** | No automated sync; customer/item must be manually aligned between Zoho Books and ERPNext masters. | Medium |

### Functional Gaps

| Gap | Detail | Priority |
|---|---|---|
| **Import flow partially built** | Job Order incoterm rules cover Import (APC = buyer), but the downstream Security / QC / Loading workflow is designed around Export outward movement. Import inward receiving flow is unclear. | High |
| **Procurement / Supplier POs** | Transport PO Request exists, but there is no full procurement module. Supplier invoices, freight cost capture, and purchase reconciliation are unassigned — neither fully in Zoho nor in the custom app. | High |
| **HR & Payroll** | No system currently owns HR, driver/staff records (beyond master data), attendance, or payroll. | Medium |
| **Customer communication** | No email/portal notifications to customers at key milestones (shipment booked, vessel loaded, etc.). | Medium |
| **Demurrage / Laytime tracking** | No module for calculating demurrage on vessels or containers. Common in petrochemical export. | Medium |
| **Freight cost allocation** | Freight, insurance, port charges not captured against Job Orders for landed cost analysis. | Medium |
| **Multi-site / multi-warehouse** | Single site configuration. No evidence of multi-warehouse inbound receiving flows. | Low |
| **Reporting & BI** | Only 3 inventory reports exist. No cross-module operational KPI reports, no export volumes, no customer-level P&L contribution. | Low |

### Technical Gaps

| Gap | Detail | Priority |
|---|---|---|
| **No CI/CD pipeline** | `developer_mode: 1` and `allow_tests: 1` in site config; tests exist but no automated pipeline to run them. | Medium |
| **Zoho API key in database** | Credentials stored in `APC Zoho Settings` DocType — acceptable for now, but no secrets rotation or vault integration. | Low |
| **Version still `0.0.1`** | `pyproject.toml` has not been incremented despite 24 migration patches; versioning is misleading. | Low |
| **NAS failure handling** | NAS saves that fail go to a daily retry job — no alerting if retry consistently fails. | Low |

---

## 5. Module Maturity Summary

| Module | Built | Integrated | Production-Ready |
|---|---|---|---|
| Sales Demand + FIFO Allocation | ✅ | Partial (Zoho pull) | Mostly |
| Job Order + Incoterm Routing | ✅ | ✅ | Yes |
| Shipping Booking | ✅ | Partial | Mostly |
| Transport Schedule | ✅ | ✅ | Yes |
| Security + Gate Control | ✅ | ✅ | Yes |
| QC + COA | ✅ | ✅ (ERPNext QI sync) | Yes |
| Loading + Gate Pass | ✅ | Partial (Zoho stub) | Mostly |
| Production | ✅ | Partial | Mostly |
| Dispatch Orders | ✅ | Partial | Mostly |
| Zoho Dispatch Push | ⚠️ Stub | ❌ Not live | No |
| Zoho Webhooks | ❌ Placeholder | ❌ | No |
| Import Receiving Flow | ⚠️ Partial | ❌ | No |

---

## 6. Quick Reference — Who Owns What

| If you need to… | Go to… |
|---|---|
| Raise or view an invoice | Zoho Books |
| Check payment status / AR | Zoho Books |
| Create a sales order / PFI | Zoho Books |
| View stock levels / warehouse | ERPNext |
| Manage items and customers | ERPNext |
| Allocate batches to an order | APC Operations → Sales → Batch Allocation |
| Create / track a Job Order | APC Operations → Shipping → Job Order |
| Book a vessel or CRO | APC Operations → Shipping → Shipping Booking |
| Schedule inland transport | APC Operations → Transportation → Transport Schedule |
| Run security inspection | APC Operations → Security → Security Inspection |
| Issue / view a Gate Pass | APC Operations → Shipping → Gate Pass |
| Generate or view a COA | APC Operations → Inventory → APC COA |
| Run a QC pre-check | APC Operations → Quality → Pre Check Clearance |
| Raise a production order | APC Operations → Production → Production Order |
| View FIFO batch stock | APC Operations → Inventory → Batch Stock Ledger |
| Check Zoho sync logs | APC Operations → Zoho → Zoho Sync Log |
| Store/retrieve COA PDFs | NAS → `QC/COA/{Year}/{Customer}/{JobOrder}/` |

---

## Dispatch Flow Implementation — Progress Tracker

> **Implementation started:** 21 May 2026
> **Plan reference:** `dispatch-flow-implementation-plan.canvas.tsx`
> **Target flow:** Delivery Order → Gate In → QC Pre-Check → Loading → Weight Capture → DN Generation → QC Final → Gate Out → Zoho Invoice

### Phase 1: Schema Fields ✅ COMPLETE — 21 May 2026

All 5 DocType JSON files updated and `bench migrate` run successfully. All columns verified in MariaDB.

| DocType | New Fields Added |
|---|---|
| Delivery Order | `operational_status` (18-value status), `expected_dispatch_date`, `planned_quantity`, `packaging_type`, `vehicle_type`, `transporter`, `sent_to_security_on`, `truck_arrived_on`, `gate_entry_no` |
| Security Inspection | `driver_license_no`, `trailer_no`, `gate_entry_no`, `truck_arrived_notified_qc`, `truck_arrived_notified_qc_on`, `tare_weight_time`, `gross_weight_time`, `weighbridge_slip_no`, `loading_bay_section`, `loading_bay`, `loading_start_time`, `loading_end_time`, `loader_name`, `loading_supervisor`, `seal_applied_by`, `security_remarks` |
| Pre-Check Clearance | `product_confirmed`, `batch_no`, `coa_status`, `tanker_cleanliness`, `odour_check`, `seal_condition_before_loading`, `qc_pre_check_status`, `failure_reason` |
| Loading Delivery Note | `planned_quantity`, `loading_start_time`, `loading_end_time`, `loading_bay`, `tare_weight_time`, `gross_weight_time`, `weighbridge_slip_no`, `seal_applied_by`, `weight_variance_qty`, `weight_variance_pct`, `weight_variance_status`, `weight_variance_approved_by`, `weight_variance_approved_on`, `final_qc_clearance`, `final_qc_clearance_by`, `final_qc_clearance_on`, `security_final_check`, `security_final_check_by`, `security_final_check_on` |
| Gate Pass | `loading_delivery_note`, `transport_schedule` (bug fix), `gate_in_time`, `gate_out_time`, `gate_out_approved_by` |

**Bug fixed:** `transport_schedule` field added to Gate Pass DocType JSON — resolves `gate_pass_events.py` broken TRN completion logic.

### Phase 2: dispatch_validation_service.py ✅ COMPLETE — 21 May 2026

Created `shipping/services/dispatch_validation_service.py` with 13 validation functions plus document resolution helpers.

| Function | Purpose |
|---|---|
| `validate_truck_arrival_allowed` | DO issued to Security, not cancelled/on hold |
| `validate_qc_precheck_before_loading` | PCC must be Authorized |
| `validate_loading_start_allowed` | QC passed + DO in loading-allowed status |
| `validate_loading_completion` | Start time, loaded qty, vehicle/driver present |
| `validate_weight_capture` | Tare/gross captured; gross ≥ tare |
| `calculate_net_weight` | Net = gross − tare |
| `validate_weight_variance` / `compute_weight_variance` | Compare net vs planned qty using APC Operations Settings tolerance |
| `validate_supervisor_approval` | Variance within tolerance or approved |
| `validate_coa_required` / `validate_coa_approved` | Batch COA requirement and approval checks |
| `validate_delivery_note_generation` | Full DN preconditions (loading, batches, weights, COA, variance) |
| `validate_gate_out_allowed` | DN confirmed, QC final, security final, weights, COA verified |
| `validate_zoho_invoice_allowed` | Dispatch + QC + COA + gate released (Option C guard) |

Helpers: `resolve_ldn_for_do`, `resolve_pcc_for_do`, `resolve_security_inspection_for_do`.

Tests: `tests/test_dispatch_validation_service.py` — 14 tests, all passing.

**Note:** Service is created but not yet wired into Gate Pass controllers or APIs (Phases 4–8).

### Phase 3: operational_status transitions ✅ COMPLETE — 21 May 2026

Created `shipping/services/dispatch_lifecycle_service.py` to compute, persist, and sync the 18-value `Delivery Order.operational_status` field.

| Component | Change |
|---|---|
| `dispatch_lifecycle_service.py` | `compute_dispatch_lifecycle_status`, `sync_dispatch_lifecycle_status`, `set_delivery_order_operational_status`, transition graph, `do_status` mapping |
| `delivery_order.py` | On submit: sets `sent_to_security_on`, syncs lifecycle |
| `delivery_order_events.py` | Hooks sync lifecycle on DO, LDN, PCC updates |
| `hooks.py` | Added `Delivery Order.on_update` and `Pre-Check Clearance.on_update` hooks |
| `gate_pass_events.py` | Syncs lifecycle when gate pass updates |
| `delivery_order_service.py` | `resolve_do_for_ldn` prefers `transport_delivery_order`; LDN sync calls lifecycle |

Tests: `tests/test_dispatch_lifecycle_service.py` — 9 tests, all passing.

**Note:** Console cards still use legacy pipeline labels (`Pending Security`, `QC Cleared`, etc.) via `compute_operational_status`. Dashboard migration to lifecycle statuses is Phase 9.

### Phase 4: Security workflow APIs ✅ COMPLETE — 21 May 2026

Created `security/dispatch_workflow.py` with DO-centric workflow actions and whitelisted wrappers in `security/api.py`.

| API | Purpose |
|---|---|
| `mark_truck_arrived` | Gate in + vehicle/driver capture |
| `record_gate_in_details` / `record_tare_weight` | Driver/trailer/tare weight capture |
| `notify_qc_truck_arrived` | Notify QC; move to pre-check pending |
| `start_loading` / `complete_loading` | Loading bay workflow with QC gate |
| `record_gross_weight` | Gross weight, net calc, variance fields |
| `record_seal_details` | Seal capture on SI/LDN |
| `security_final_check` | Security exit check before gate out |
| `request_delivery_note_generation` | Validated DN generation via `confirm_dispatch` |
| `mark_delivery_order_gate_out` | DO-centric gate release |

Also updated `services/consoles.py` (`issue_loading_dn`, `release_gate`) to use validation service.

Tests: `tests/test_security_dispatch_workflow.py` — 4 tests, all passing.

### Phase 5: QC workflow APIs ✅ COMPLETE — 21 May 2026

Created `quality/dispatch_workflow.py` with DO-centric QC actions and whitelisted wrappers in `quality/api.py`.

| API | Purpose |
|---|---|
| `get_qc_precheck_queue` | DOs awaiting QC pre-check with lifecycle status |
| `submit_qc_precheck` | Pass/fail/hold pre-check with tanker/product fields |
| `put_qc_on_hold` / `fail_qc_precheck` | Hold and fail shortcuts |
| `link_batch_to_precheck` | Link APC Batch + derive COA status on PCC |
| `verify_coa_for_batch` | Validate approved COA and mark LDN verified |
| `submit_final_qc_clearance` | Post-loading final QC sign-off on LDN |
| `qc_manager_approve_dispatch` | QC Manager DN↔COA approval after final clearance |

Also updated `pre_check_clearance.py` for `On Hold` handling and lifecycle sync on DO.

Tests: `tests/test_qc_dispatch_workflow.py` — 6 tests.

### Phase 6: Weight variance logic ✅ COMPLETE — 21 May 2026

| Component | Change |
|---|---|
| `dispatch_validation_service.py` | Added `apply_weight_variance_to_ldn()` — auto net weight + variance qty/pct/status |
| `loading_delivery_note.py` | `before_save` calls variance compute; `approve_weight_variance()` whitelisted method |
| `security/dispatch_workflow.py` | Refactored to use shared helper; added `approve_weight_variance` API |
| `security/api.py` | Whitelisted `approve_weight_variance` wrapper |
| `dispatch_lifecycle_service.py` | Fixed bug: lifecycle now uses `validate_weight_variance(ldn_name)` |

Tests: `tests/test_loading_delivery_note_weight_variance.py` — 4 tests.

### Phase 7: DN generation validation ✅ COMPLETE — 21 May 2026

| Component | Change |
|---|---|
| `batch_allocation.py` | `confirm_dispatch_and_deduct_stock` now calls `validate_delivery_note_generation` after weight pull/reconcile; removed duplicate COA checks; syncs DO lifecycle on success |
| `security/dispatch_workflow.py` | `request_delivery_note_generation` already validated — now benefits from service-layer gate |
| `tests/test_batch_qc_fifo_dispatch.py` | Updated dispatch tests with `_prepare_ldn_for_dispatch_confirmation` helper |

Tests: `tests/test_confirm_dispatch_validation.py` — 5 tests.

### Phase 8: Gate out enforcement ✅ COMPLETE — 21 May 2026

| Component | Change |
|---|---|
| `gate_pass.py` | `_enforce_release_preconditions()` delegates to `validate_gate_out_allowed(for_release=True)` |
| `gate_pass.py` | Auto-backfills `loading_delivery_note` from DO before validation |

Full gate-out checks: dispatch confirmed, final QC clearance, QC manager approval, security final check, weights captured, variance approved, COA verified (when required).

Tests: `tests/test_gate_enforcement.py` — 8 release tests + 2 QC approval tests.

### Phase 9: Dashboard/console updates ✅ COMPLETE — 21 May 2026

| Component | Change |
|---|---|
| `delivery_order_service.py` | `resolve_console_operational_status()` prefers persisted lifecycle; security queues use lifecycle groupings; tones for all 18 statuses |
| `delivery_order_service.py` | `sync_delivery_order_operational_status()` now delegates to `sync_dispatch_lifecycle_status` |
| `consoles.py` | Loading bay / gate control queues filter by lifecycle; gate traffic-light uses full readiness; QC precheck delegates to Phase 5 workflow |
| `security/api.py` | Read-only cards include terminal lifecycle statuses |
| `delivery_order_events.py` | Removed duplicate lifecycle sync on DO update |

Tests updated: `test_consoles.py`, `test_delivery_order_console.py`.

### Phase 10: Zoho trigger (Option C) ✅ COMPLETE — 21 May 2026

| Component | Change |
|---|---|
| `zoho_dispatch_sync_service.py` | Two-phase sync: DN after dispatch confirm; invoice after gate release |
| `zoho_dispatch_sync_service.py` | `trigger_dispatch_confirmed_pipeline()` → `_run_dn_push_pipeline` (DN + COAs if verified) |
| `zoho_dispatch_sync_service.py` | `trigger_gate_release_pipeline()` → `_run_invoice_push_pipeline` (validate → DN ensure → COAs → invoice) |
| `zoho_dispatch_sync_service.py` | `trigger_zoho_invoice()` calls `validate_zoho_invoice_allowed()` when `loading_dn_name` provided |
| `batch_allocation.py` | `confirm_dispatch_and_deduct_stock()` enqueues DN push after lifecycle sync |
| `gate_pass.py` | Existing release hook calls `trigger_gate_release_pipeline()` (invoice-only path) |

Tests: `tests/test_zoho_dispatch_sync.py` — DN on dispatch confirm, invoice blocked before gate out, invoice after gate release.

### Phase 11: Automated tests ⏳ NEXT

### Phase 12: Migration patches (v0_4) ✅ COMPLETE — 21 May 2026

| Patch | Purpose |
|---|---|
| `v0_4/extend_dispatch_flow_schema.py` | Idempotent schema columns on DO, SI, PCC, LDN, Gate Pass |
| `v0_4/backfill_do_operational_status.py` | Map legacy `do_status` → `operational_status`, then lifecycle recompute |
| `v0_4/backfill_ldn_planned_qty_and_weight_variance.py` | Planned qty from DO; weight variance for historical LDNs |
| `v0_4/backfill_gate_pass_operational_links.py` | Gate Pass LDN + transport schedule links; gate out timestamps |

Registered in `patches.txt` (4 patches). Run on staging before production.
