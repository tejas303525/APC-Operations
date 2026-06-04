# Transport Delivery Order → Security → QC → Loading → Delivery Note

**Gap analysis and implementation plan**  
**Codebase:** `apps/apc_operations` on Frappe v15 / ERPNext 15  
**Analysis date:** May 2026  
**Scope:** Outward export / local dispatch (APC as seller)

---

## 1. Executive summary

APC Operations already has **most of the building blocks** for the flow you described, but they are **split across overlapping documents and two parallel QC paths**. There is **no separate DocType named “Transport Delivery Order”** — that role is filled by **`Delivery Order`** (`DO-.YYYY.-`) with optional `transport_delivery_order_number`, linked to **`Transport Schedule`**, **`Security Draft Delivery Note` (SDDN)**, **`Security Inspection`**, **`Pre-Check Clearance`**, **`Loading Delivery Note` (LDN)**, **`Gate Pass`**, and **`Weighment Slip`**.

**What works today (partially):**

- TC can create a **Delivery Order** from Transportation Console (`generate_delivery_order_for_export`).
- Security Console queues DOs/SDDNs, verifies truck/container/driver, creates **LDN**, can queue/send to QC.
- **Pre-Check Clearance** on DO submit (QC + Security sign-off before loading bay).
- **QC Console** works off **LDN + QC Report Request** (post-SDDN flow).
- **Loading Bay Console** loads only when `do_status = Pre-Check Cleared`.
- **Dispatch confirmation** deducts stock, pulls weights, creates **ERPNext Delivery Note** side-effect.
- **Gate Pass** release is **server-enforced**: requires DO → LDN → `dispatch_confirmed` → `qc_manager_approved`.
- **Zoho push** exists as **stub/partial** pipeline on gate release.

**Critical gaps vs your target flow:**

| Area | Gap severity |
|------|----------------|
| Single coherent status model across TC → Security → QC → Loading → DN | **Critical** |
| “Delivery Note” generated **only after loading** with actual weights | **Critical** (DO/LDN often created earlier; ERPNext DN only at dispatch confirm) |
| Truck arrival → notify QC as first-class event | **High** |
| QC pre-check fields (cleanliness, odour, seal before load, etc.) | **High** |
| Net weight auto-calc on LDN + mandatory tare/gross before DN | **High** |
| Weight variance → supervisor approval (not just tolerance msgprint) | **High** |
| Gate In / Gate Out times and gate entry no. on Security | **Medium** |
| TC dashboard queues you listed | **Medium** |
| Zoho invoice only after valid DN + COA (live API) | **Medium** (stub exists) |
| Status change audit on every transition | **Medium** (partial `track_changes`) |

**Recommendation:** Treat **`Delivery Order` as the Transport Delivery Order header**, **`Loading Delivery Note` as the operational dispatch / customer DN source**, and **`Pre-Check Clearance` + `QC Report Request` as two explicit QC gates** — then unify consoles and validations around one **operational status** field (or computed status service) instead of four unrelated status fields.

---

## 2. Existing flow found in codebase

### 2.1 Document chain (as implemented)

```text
Zoho Sales Order / PFI
  → APC Sales Demand (+ APC Batch Allocation FIFO)
  → Job Order (incoterm routing)
       ├→ Transport Schedule (TRN) ──auto──→ Security Draft Delivery Note (SDDN)
       └→ Shipping Booking (export sea)

Transportation Console: "Generate DO"
  → Delivery Order (Draft, do_status=Draft)     ← TC "Transport Delivery Order"

Delivery Order.submit (optional early)
  → do_status: Issued → Pre-Check Pending
  → Pre-Check Clearance (PCC) created
  → Loading Delivery Note stub (Batch Allocation Pending) may be created

Security Console (SDDN / DO queues)
  → Verify SDDN (truck/driver/container checklist)
  → Create Loading Delivery Note (often Pending QC)
  → Queue for QC / Send to QC

QC Console (LDN-based)
  → New DO: LDN Pending QC, no QC Report Request
  → Pending: QC Report Request open
  → QC Cleared → APC COA via create_apc_coa_from_qc

QC Pre-Check Console (PCC-based)     ← separate from QC Console
  → Pass/Fail on Pre-Check Clearance.qc_status
  → Both QC+Security Passed → do_status Pre-Check Cleared

Loading Bay Console
  → Only DO with do_status in (Pre-Check Cleared, Loading, DN Issued)
  → "Issue DN" → confirm_dispatch_and_deduct_stock(LDN)
       → weights from Weighment Slips on DO
       → reconcile Security Inspection.loading_entries
       → ERPNext Delivery Note created (erpnext_delivery_note)
       → dispatch_confirmed = 1

Gate Control Console
  → Gate Pass (Out) linked to Delivery Order
  → Release only if LDN dispatch_confirmed + qc_manager_approved

Gate Pass Released
  → Zoho stub: push_dn_to_zoho → push_coa → trigger_zoho_invoice
```

### 2.2 Naming map (avoid confusion)

| Business term | Actual DocType / artifact |
|---------------|---------------------------|
| Transport Delivery Order | **`Delivery Order`** + `transport_delivery_order_number` |
| Transport coordination | **`Transport Schedule`** |
| Transport payables PO | **`Transport PO Request`** (Zoho Books ref only; not the dispatch DO) |
| Draft Delivery Note (security) | **`Security Draft Delivery Note`** (SDDN) |
| Loading / dispatch note (operations) | **`Loading Delivery Note`** (LDN) |
| Printable standard DO | Print Format **`Standard Delivery Order`** on **Delivery Order** |
| Printable loading DN | Print Format **`Standard Loading Delivery Note`** on **LDN** |
| Tax/compliance DN | **`erpnext_delivery_note`** on LDN (created at dispatch confirm) |
| Customer DN in Zoho | **`zoho_dn_id`** on LDN (push on gate release, stub) |
| Final invoice | **`zoho_invoice_id`** on LDN (stub) |

There is **duplicate “delivery note” logic** across SDDN (draft), LDN (operational), DO (TC order), ERPNext DN (side-effect), and Zoho DN (integration). Your target design should **designate LDN + confirm_dispatch as the single “final DN” moment**, with DO as the transport header only.

### 2.3 Modules, pages, APIs (inventory)

#### DocTypes (relevant)

| Module | DocTypes |
|--------|----------|
| Shipping | `Job Order`, `Job Order Item`, `Delivery Order`, `Delivery Order Item`, `Loading Delivery Note`, `Loading DN Batch`, `Loading Entry` (child of Security Inspection), `Security Draft Delivery Note`, `QC Report Request`, `Gate Pass`, `Weighment Slip`, `Transport PO Request`, `Shipping Booking`, `APC Operations Settings` |
| Transportation | `Transport Schedule`, `Vehicle`, `Driver`, `Transporter` |
| Security | `Security Inspection`, `Security Dispatch` (legacy naming) |
| Quality | `Pre-Check Clearance` |
| Inventory | `APC Batch`, `APC COA`, `COA Template`, … |
| Sales | `APC Sales Demand`, `APC Sales Demand Item`, `APC Batch Allocation`, … |
| Dispatch | `APC Dispatch Order` (separate outward dispatch path; not the same as DO/LDN truck flow) |
| Zoho | `Zoho Sync Log` |

#### Frappe Pages (consoles / dashboards)

| Page | Route | Purpose |
|------|-------|---------|
| Transportation Console | `transportation-console` | TC: inward/outward, book transport, **Generate DO** |
| Shipping Console | `shipping-console` | Vessel/CRO/booking |
| Security Console | `security-console` | DO queues, SDDN verify, create LDN, send to QC |
| QC Console | `qc-console` | LDN/QC Report Request queues |
| QC Pre-Check Console | `qc-precheck-console` | **Pre-Check Clearance** pass/fail |
| Loading Bay Console | `loading-bay-console` | Pre-Check Cleared → **Issue DN** (confirm dispatch) |
| Gate Control Console | `gate-control-console` | Gate pass release |
| Legacy | `shipping-dashboard-legacy`, `security-dashboard-legacy`, … | Deprecated |

**Missing:** dedicated **Transport Coordinator dashboard** with the queue names you listed (partially covered by Transportation Console + DO list).

#### Key backend APIs

| API module | Functions |
|------------|-----------|
| `transportation/api.py` | Lists, book transport, pending counts |
| `shipping/api.py` | `generate_delivery_order_for_export`, dashboard stats |
| `security/api.py` | SDDN verify, `create_loading_delivery_note`, `queue_loading_delivery_note_for_qc`, `send_loading_delivery_note_to_qc`, gate pass, DO detail |
| `quality/api.py` | QC console LDN queues, `submit_qc_for_loading_delivery_note`, COA helpers |
| `services/consoles.py` | Loading bay queue, gate control, PCC queue, `issue_loading_dn`, `release_gate` |
| `services/delivery_order_service.py` | Operational status for Security DO cards |
| `services/batch_allocation.py` | FIFO, **`confirm_dispatch_and_deduct_stock`** |
| `shipping/services/zoho_dispatch_sync_service.py` | Zoho DN/COA/invoice stub pipeline |

#### Hooks (`hooks.py`)

- `Transport Schedule` / `Shipping Booking` → Job Order sync  
- `Security Draft Delivery Note` / `Security Inspection` / `QC Report Request` / `Loading Delivery Note` → status sync hooks  
- `Gate Pass` → Zoho pipeline on release  
- **No hook** on `Delivery Order` for truck arrival or unified operational status  

---

## 3. Required final flow

Target flow aligned to your business description and mapped to recommended owners:

```text
1. TC creates Delivery Order (Transport DO) from Job Order / Transport Schedule
      Status: Draft → Issued → Sent to Security

2. Security: Gate In / truck arrival
      Record vehicle, driver, transporter, gate-in time, tare weight (if applicable)
      Status: Truck Arrived

3. Security notifies QC (explicit event)
      Status: QC Pre-check Pending

4. QC Pre-Check (Pre-Check Clearance + batch/COA check)
      Pass → Loading Allowed | Fail → On Hold / Cancelled

5. Security: loading allowed only if pre-check Passed
      Loading Start → enter Loading Entry lines (batch, bags, actual weight, seal)
      Loading End

6. Security: Gross weight (+ weighbridge slip), seal final
      Net = Gross - Tare (auto)
      Variance vs planned → supervisor if over tolerance

7. QC: final clearance on LDN (QC Report Request Cleared, COA approved, QC Manager approve DN↔COA)

8. Generate Delivery Note (operational)
      = confirm_dispatch on LDN + ERPNext DN + print LDN/DO
      Status: Delivery Note Generated

9. Gate Out
      Only if Gate Pass can release (dispatch_confirmed + qc_manager_approved + DO linked)
      Status: Gate Out Completed

10. Zoho (optional)
      push_dn → COA → invoice after gate release (or after step 8 — decision needed)
```

**Decision needed:** Should **step 8** be the only moment that creates/submits **Delivery Order** print + ERPNext DN, or keep early DO for TC planning? **Recommendation:** keep early **Draft DO** for TC, but block **submitted/issued DN print** and **gate out** until step 8 completes.

---

## 4. Current gaps

### 4.1 Structural gaps

1. **Two QC systems** without a single “loading allowed” gate:
   - **Pre-Check Clearance** (on DO) — used by Loading Bay Console.
   - **QC Report Request** (on LDN) — used by QC Console and `report_to_qc`.
   - They are **not synchronized** (passing PCC does not auto-create QCR; LDN can exist before PCC passes).

2. **“Delivery Note” timing:** User requires DN **after loading**. Code creates:
   - DO early (Transport Generate DO),
   - LDN at security (before loading),
   - ERPNext DN only at **`confirm_dispatch`** (closest to correct timing).

3. **No `Truck Arrived` / `Sent to QC` on Delivery Order** — statuses live on SDDN, LDN, PCC, SI separately.

4. **Transport PO Request ≠ Transport DO** — payables document; do not use for dispatch control.

### 4.2 Field gaps (summary)

See Section 5 for full matrix. Highlights:

- **Missing on DO/LDN:** expected dispatch date as TC field, packaging type on DO line, weighbridge slip no., tare/gross time, loading start/end, loader name, seal applied by, weight variance status, gate entry no., driver license.
- **Present but weak:** net weight on LDN (no `validate` auto-calc), seal on LDN/SI, batch on `Loading DN Batch` / `Loading Entry`.
- **Pre-check checklist fields** (odour, cleanliness, seal before load): **not modeled** on PCC or QCR.

### 4.3 Validation gaps (vs your 15 rules)

| # | Rule | Current state |
|---|------|----------------|
| 1 | DN only if QC pre-check passed | **Partial** — Loading Bay checks `do_status = Pre-Check Cleared`; LDN dispatch does not re-check PCC |
| 2 | Loading cannot start before pre-check | **Partial** — loading bay queue only; Security can still fill `loading_entries` on SI anytime |
| 3 | DN requires vehicle + driver | **Partial** — SDDN/SI/Gate Pass have fields; not enforced on `confirm_dispatch` |
| 4 | DN requires loaded quantity | **Partial** — `loading_entries` reconciled with tolerance msgprint only |
| 5 | DN requires batch | **Enforced** at dispatch confirm (batch_allocations required) |
| 6 | Tare + gross required (weight-based) | **Weak** — pulled from weighment slips if linked on DO; not mandatory |
| 7 | Net auto-calculated | **Yes** on `Weighment Slip` and `Security Inspection`; **not on LDN validate** |
| 8 | Net vs planned comparison | **Partial** — tolerance check on `loading_entries` vs allocation; no planned qty on LDN header |
| 9 | Variance needs supervisor approval | **No** — only `msgprint` warning; dispatch still proceeds |
| 10 | Gate out only with DN | **Partial** — requires LDN `dispatch_confirmed`, not “print DN exists” |
| 11 | Gate out blocked if DN cancelled/draft | **Partial** — gate checks dispatch flags, not DO `do_status`/`docstatus` |
| 12 | COA required if product requires | **Partial** — enforced at dispatch confirm per row; no product-level flag |
| 13 | Invoice not before valid DN | **Stub** — `push_dn_to_zoho` checks `dispatch_confirmed` |
| 14 | QC Manager before COA final | **Yes** — `qc_manager_approve` on LDN; gate release requires it |
| 15 | Every status change logged | **Partial** — PCC/SI/LDN have some audit fields; no unified transition log |

---

## 5. Recommended DocType changes

### 5.1 `Delivery Order` — treat as Transport Delivery Order

**Existing useful fields:** `job_order`, `customer`, `transport_delivery_order_number`, `destination`, `port_of_loading`, `port_of_discharge`, `do_status`, `pre_check_clearance`, `loading_delivery_note`, `weighment_slip_tare/gross`, `gate_pass`, items child table.

**Add / extend:**

| Field | Type | Notes |
|-------|------|-------|
| `operational_status` | Select | Single TC-facing status (see Section 9) |
| `expected_dispatch_date` | Date | TC planning |
| `packaging_type` | Link/Data | From demand line |
| `planned_quantity` | Float | From JO/demand |
| `vehicle_type` | Data/Link | |
| `transporter` | Link | From TRN |
| `sent_to_security_on` | Datetime | |
| `truck_arrived_on` | Datetime | |
| `gate_entry_no` | Data | |

**Avoid:** duplicating weights on DO once LDN is authoritative — link only.

### 5.2 `Security Inspection` — gate-in and loading capture

**Existing:** `gate_in_time`, `gate_out_time`, vehicle/driver, gross/tare/net, `loading_entries`, checklist, `loading_delivery_note`.

**Add:**

| Field | Notes |
|-------|-------|
| `driver_license_no` | |
| `trailer_no` | |
| `gate_entry_no` | |
| `security_remarks` | Gate-in |
| `loading_start_time` / `loading_end_time` | |
| `loading_bay` | |
| `loader_name` / `loading_supervisor` | |
| `seal_applied_by` | |
| `truck_arrived_notified_qc` | Check + datetime |
| `tare_weight_time` / `gross_weight_time` | |
| `weighbridge_slip_no` | |

### 5.3 `Pre-Check Clearance` — expand QC pre-check

**Add child table or JSON checklist:**

- product_confirmed, batch_no, coa_status  
- tanker_cleanliness, odour_check, seal_condition_before  
- qc_pre_check_status (Pending/Passed/Failed/Hold)  

Keep dual sign-off (QC + Security) or collapse Security sign-off into SI gate-in — **decision needed**.

### 5.4 `Loading Delivery Note`

**Add:**

| Field | Notes |
|-------|-------|
| `loading_start_time` / `loading_end_time` | |
| `loading_bay` | |
| `planned_quantity` | For variance |
| `weight_variance_pct` | Read-only computed |
| `weight_variance_status` | OK / Warning / Approval Required / Approved |
| `weight_variance_approved_by` | |
| `weighbridge_slip_no` | |
| `tare_weight_time` / `gross_weight_time` | |
| `seal_applied_by` | |
| `final_qc_clearance` | Check + user/time |
| `security_final_check` | Check + user/time |

**Controller:** `validate()` → `net_weight = gross_weight - tare_weight` when both set.

### 5.5 `Gate Pass`

**Add:** `gate_in_time`, `gate_out_time`, `gate_out_approved_by`, link to `loading_delivery_note` (optional direct link).

**Enforce:** on release, also check `Delivery Order.do_status` not in (`Draft`, `Cancelled`) and LDN `delivery_note_status` ≥ Dispatch Confirmed.

### 5.6 New optional: `Dispatch Status Log` (child or separate DocType)

For rule #15: `document`, `from_status`, `to_status`, `user`, `timestamp`, `remarks`.

---

## 6. Recommended API changes

| API | Change |
|-----|--------|
| `security.api.mark_truck_arrived` | **New** — set DO/SI/SDDN timestamps, optional notify QC (email + queue PCC) |
| `security.api.notify_qc_truck_arrived` | **New** — idempotent flag + PCC prompt |
| `quality.api.run_precheck` | Extend PCC with checklist fields |
| `services.consoles.get_tc_dashboard_queues` | **New** — TC dashboard counts |
| `services.consoles.start_loading` | **New** — validate PCC Passed, set loading times |
| `services.consoles.complete_loading` | **New** — validate entries, gross weight |
| `services.batch_allocation.confirm_dispatch_and_deduct_stock` | Add mandatory checks: PCC Passed, vehicle/driver, tare/gross, variance approval |
| `services.consoles.release_gate` | Also validate DO/LDN docstatus and printed DN flag |
| `delivery_order_service.compute_operational_status` | Extend to include Truck Arrived, QC Pre-check, Loading, etc. |

---

## 7. Recommended frontend / dashboard changes

### Transport Coordinator (`transportation-console` + new queues)

- Open / Issued DOs  
- Pending truck arrival (DO issued, no `truck_arrived_on`)  
- Awaiting QC pre-check  
- Loading in progress  
- DN generated / Ready for gate out / Completed  

### Security (`security-console` + `gate-control-console`)

Align queues to:

- Expected Trucks (DO issued, TRN scheduled)  
- Trucks Arrived (gate in done)  
- Waiting for QC Pre-check  
- Loading Allowed  
- Loading in Progress  
- Pending Gross Weight  
- Pending DN (dispatch not confirmed)  
- Ready for Gate Out (traffic light green)  

Actions already partially present; add: **Mark Gate In**, **Notify QC**, **Start/Complete Loading**, **Enter Gross**, on **DO modal** (recent patch added Create LDN / Send to QC).

### QC (`qc-precheck-console` + `qc-console`)

- **Pre-check queue** → expand checklist UI  
- **Truck arrived** queue (new filter on PCC or DO status)  
- **Final clearance** → `qc_manager_approve` + COA approval (already on LDN)  

### Loading / Warehouse

- Use **Loading Bay Console** + SI `loading_entries` grid on form  
- Block until PCC Passed (server-side on `start_loading`)

---

## 8. Recommended validation rules

Implement primarily in:

1. `services/dispatch_validation_service.py` (**new** — recommended in CLAUDE.md but not present; create)  
2. `confirm_dispatch_and_deduct_stock`  
3. `GatePass.validate`  
4. `PreCheckClearance.validate`  
5. `LoadingDeliveryNote.validate`  

Pseudo-guards:

```python
# Before loading_start (new API)
assert do.do_status == "Pre-Check Cleared"
assert pcc.overall_status == "Authorized"

# Before confirm_dispatch
assert vehicle and driver on SI or SDDN
assert ldn.gross_weight and ldn.tare_weight
assert ldn.net_weight == flt(gross) - flt(tare)
assert all batch rows have COA approved
if variance > tolerance: assert ldn.weight_variance_status == "Approved"

# Before gate release (extend GatePass)
assert ldn.dispatch_confirmed and ldn.qc_manager_approved
assert do.do_status in ("DN Issued", "Ready for Gate Out")
```

---

## 9. Recommended status model

### Problem today

| Document | Status field(s) |
|----------|-----------------|
| Delivery Order | `status`, `do_status` |
| SDDN | `security_status`, `gate_out_status` |
| Security Inspection | `security_status`, `qc_status` |
| LDN | `delivery_note_status`, `qc_status` |
| PCC | `overall_status`, `qc_status`, `security_status` |
| Gate Pass | `gate_status` |

`delivery_order_service.compute_operational_status` derives a **console-only** label (Pending Security, Ready for Loading, Sent to QC, …) but it is **not stored** on DO.

### Recommended: stored `Delivery Order.operational_status`

| Status | Meaning |
|--------|---------|
| Draft | TC editing |
| Issued | Sent to operations |
| Sent to Security | SDDN exists / with security |
| Truck Arrived | Gate in recorded |
| QC Pre-check Pending | Awaiting PCC/QC |
| QC Pre-check Passed | Authorized to load |
| QC Pre-check Failed | Blocked |
| Loading Allowed | Passed pre-check, not started |
| Loading Started | |
| Loading Completed | Entries + gross captured |
| Weighment Completed | Tare/gross/net validated |
| QC Final Pending | Awaiting QC manager / COA |
| Delivery Note Generated | `dispatch_confirmed` |
| Ready for Gate Out | Gate pass green |
| Gate Out Completed | Gate released |
| On Hold | |
| Cancelled | |

**Migration:** map from existing `do_status` + LDN + PCC via patch; keep `do_status` for backward compatibility during transition.

---

## 10. Delivery Note generation design

### Current behavior

| Step | What happens |
|------|----------------|
| TC Generate DO | Inserts **Delivery Order** (Draft), links JO |
| DO submit | PCC created; may create **LDN** stub (`Batch Allocation Pending`) |
| Security Create LDN | **LDN** with `Pending QC` |
| Loading Bay “Issue DN” | Calls **`confirm_dispatch_and_deduct_stock`** |
| confirm_dispatch | Deducts stock; sets `dispatch_confirmed`; creates **ERPNext Delivery Note**; sets LDN `Dispatch Confirmed` |
| Print | Standard print formats on DO and LDN (manual) |
| Gate release | Zoho stub push |

### Recommended final design

1. **Transport DO (Delivery Order)** — planning document only until loading completes.  
2. **Operational DN** = **Loading Delivery Note** after `confirm_dispatch` (includes batches, weights, seal, COA refs).  
3. **ERPNext DN** — side-effect at confirm_dispatch (keep).  
4. **Customer/Zoho DN** — on gate release or after confirm_dispatch (**decide**); must require `qc_manager_approved`.  
5. **Block gate out** unless `dispatch_confirmed` (already) + add check for **ERPNext DN or print issued flag**.

**Do not** use SDDN as final DN — it is a security draft only.

**Unclear / decide:** Is printable “Delivery Note” the **LDN** print or **DO** print for the customer? Inspect print formats:  
`shipping/print_format/standard_loading_delivery_note/`, `standard_delivery_order/`.

---

## 11. COA integration design

### Current flow

```text
Job Order → APC Batch Allocation (FIFO) → Loading DN Batch rows (batch + coa)
QC Report Request → create_apc_coa_from_qc (when QC Cleared)
APC COA: approval_status, status, coa_pdf, linked_coa on batch
LDN.verify_coas / qc_manager_approve — enforces Approved COA per row
Gate release → push_coa_to_zoho (stub)
```

### Gaps

- COA can be created from QC Console without PCC pass if LDN path used alone.  
- **QC Manager approval** exists on LDN but not on APC COA alone before gate.  
- No automatic “COA required” per Item/product master flag.  
- NAS path for COA PDF exists on APC COA; Zoho attachment stub only.

### Recommended

```text
Allocated Batch (APC Batch Allocation) → APC Batch → linked_coa (APC COA)
QC Pre-check: verify COA exists + Approved (or Pending Testing with hold)
Loading: Loading DN Batch.coa must match dispatched batch
Dispatch confirm: re-validate Approved
QC Manager: approve DN↔COA binding (existing)
Gate release: push COA PDF to Zoho
Invoice: after zoho_dn + coa + optional gate out
```

---

## 12. Zoho integration design

### Current (`zoho_dispatch_sync_service.py`, `zoho/api.py`)

| Capability | State |
|------------|-------|
| Pull sales orders / create JO from PFI | Partial APIs in `zoho/api.py` |
| Push LDN as Zoho DN | Stub (`zoho_dispatch_stub_only`) |
| Attach COA | Stub |
| Trigger invoice | Stub; writes `zoho_invoice_id` on LDN |
| Pull invoice status | Scheduled cron in hooks |
| Trigger on Gate Pass release | **Yes** — `trigger_gate_release_pipeline` |

### Recommended trigger

```text
confirm_dispatch (LDN finalised)
  → optional: push_dn_to_zoho (if settings allow early)

gate_release (truck leaves)
  → push_dn_to_zoho (if not yet)
  → push_coa_to_zoho (approved + qc_manager_approved)
  → trigger_zoho_invoice (if COA + DN valid)

Never invoice when:
  - dispatch_confirmed = 0
  - qc_manager_approved = 0
  - COA missing for required batch
  - do_status Cancelled
```

**Finance rule:** Keep invoicing in Zoho Books; APC only pushes operational truth.

---

## 13. Risk areas

1. **Dual QC paths** — operators may pass LDN QC while PCC still Pending (or reverse).  
2. **Early DO/LDN creation** — stock reserved/deducted at different times; traceability confusion.  
3. **confirm_dispatch without physical loading data** — if `loading_entries` empty, tolerance check skipped.  
4. **Gate release without explicit “printed DN”** — only system flags.  
5. **Zoho stub in production** — false sense of integration.  
6. **Import vs export** — Security Inspection has import exceptions; TC flow described is export-focused.  
7. **APC Dispatch Order** — parallel module; ensure users don’t mix with truck LDN flow.  
8. **Permission gaps** — only Shipping/Transport have query filters; Security/QC rely on DocType permissions.

---

## 14. Step-by-step implementation plan

### Phase 1 — Codebase discovery ✅ (this document)

Deliverable: this MD file + decisions log.

### Phase 2 — Schema changes

- Add `operational_status` + timestamps on Delivery Order.  
- Extend PCC, Security Inspection, LDN, Gate Pass fields (Section 5).  
- Patches under `patches/v0_4/`.  
- `bench migrate`.

### Phase 3 — Backend validation

- Create `shipping/services/dispatch_validation_service.py`.  
- Wire into `confirm_dispatch`, `GatePass`, new `mark_truck_arrived`, `start_loading`.  
- LDN `validate` net weight calc.

### Phase 4 — Security workflow

- APIs: gate in, truck arrived, notify QC, loading start/complete, gross weight.  
- Security Console queues aligned to Section 7.  
- Enforce loading_entries only after pre-check.

### Phase 5 — QC workflow

- Unify PCC pass with LDN queue (block `send_to_qc` until PCC Passed **or** merge flows).  
- Expand qc-precheck-console checklist.  
- Truck-arrived queue for QC.

### Phase 6 — Delivery Note generation

- Rename UI “Issue DN” → “Confirm Loading & Generate DN”.  
- Block ERPNext DN until validations pass.  
- Set `operational_status = Delivery Note Generated`.  
- Optional: lock LDN after gate out.

### Phase 7 — Zoho integration

- Replace stub with real Books API when credentials ready.  
- Gate invoice on validation service.  
- Extend `Zoho Sync Log` for failures.

### Phase 8 — UI dashboards

- TC dashboard page or extend `transportation-console`.  
- Security/QC queue filters by `operational_status`.  
- Exception dashboard for variance / hold.

### Phase 9 — Testing

Execute checklist in Section 16.

---

## 15. Exact files to modify

| Area | Files |
|------|-------|
| Schema DO | `shipping/doctype/delivery_order/delivery_order.json`, `.py` |
| Schema LDN | `shipping/doctype/loading_delivery_note/loading_delivery_note.json`, `.py` |
| Schema PCC | `quality/doctype/pre_check_clearance/pre_check_clearance.json`, `.py` |
| Schema SI | `security/doctype/security_inspection/security_inspection.json`, `.py` |
| Schema Gate Pass | `shipping/doctype/gate_pass/gate_pass.py`, `.json` |
| Validation | **NEW** `shipping/services/dispatch_validation_service.py` |
| Dispatch | `services/batch_allocation.py` (`confirm_dispatch_and_deduct_stock`) |
| Security API | `security/api.py` |
| QC API | `quality/api.py` |
| Consoles | `services/consoles.py` |
| Operational status | `services/delivery_order_service.py` |
| Zoho | `shipping/services/zoho_dispatch_sync_service.py` |
| Hooks | `hooks.py`, `shipping/delivery_order_events.py`, `shipping/gate_pass_events.py` |
| UI Security | `security/page/security_console/security_console.js` |
| UI QC | `quality/page/qc_precheck_console/qc_precheck_console.js`, `quality/page/qc_console/qc_console.js` |
| UI Loading | `security/page/loading_bay_console/loading_bay_console.js` |
| UI Gate | `security/page/gate_control_console/gate_control_console.js` |
| UI TC | `transportation/page/transportation_console/transportation_console.js` |
| Tests | `tests/test_dispatch_validation.py`, extend `test_gate_enforcement.py`, `test_pre_check_clearance.py` |
| Patches | `patches/v0_4/*.py`, `patches.txt` |
| Docs | `APC_OPERATIONS_STATUS.md`, `CLAUDE.md` |

---

## 16. Testing checklist

- [ ] Normal export: TC DO → Security gate in → PCC pass → load → weigh → confirm dispatch → QC manager approve → gate out → Zoho stub  
- [ ] QC pre-check fail blocks loading bay queue  
- [ ] QC hold on PCC blocks `confirm_dispatch`  
- [ ] Generate DO without vehicle/driver → confirm_dispatch blocked  
- [ ] Missing tare/gross → blocked  
- [ ] Net weight auto on LDN  
- [ ] Weight over tolerance without approval → blocked  
- [ ] Weight over tolerance with manager approval → allowed  
- [ ] Missing batch on allocation → blocked at confirm  
- [ ] Missing / unapproved COA → blocked  
- [ ] Gate out without dispatch_confirmed → blocked  
- [ ] Gate out without qc_manager_approved → blocked  
- [ ] Gate out with DO cancelled → blocked  
- [ ] LDN QC path without PCC → blocked (after fix)  
- [ ] `queue_loading_delivery_note_for_qc` → appears in QC New DO  
- [ ] `send_loading_delivery_note_to_qc` → moves to QC Pending  
- [ ] Zoho invoice not triggered when sync disabled  
- [ ] Status log entries on each transition  

---

## Gap report (structured)

| # | Feature | Current behavior | Required behavior | Gap | Risk | Primary files | Priority |
|---|---------|------------------|-------------------|-----|------|---------------|----------|
| 1 | Transport DO entity | `Delivery Order` created Draft from TC | TC-issued Transport DO with planned qty/status | No separate TDO DocType; early creation | Medium | `shipping/api.py`, `delivery_order.json` | Medium |
| 2 | Send to Security/QC | Manual SDDN/TRN; queue LDN for QC | Explicit send + notify | Partial | Medium | `security/api.py` | High |
| 3 | Truck arrival | `gate_in_time` on SI only | First-class status + QC notify | No DO status / notify API | High | `security_inspection.json`, **new API** | High |
| 4 | QC pre-check checklist | PCC pass/fail only | Product/batch/COA/cleanliness/odour/seal | Fields missing | High | `pre_check_clearance.json` | High |
| 5 | Loading before pre-check | Loading bay gated; SI entries open | Block loading until PCC Passed | Partial enforcement | **Critical** | `consoles.py`, `security_inspection.py` | Critical |
| 6 | Notify QC on arrival | `send_loading_delivery_note_to_qc` | Security informs QC on truck arrive | Wrong trigger point | Medium | `security/api.py` | High |
| 7 | Loading times / bay | `loading_date/time` on LDN | Start/end, bay, supervisor | Incomplete | Medium | `loading_delivery_note.json` | Medium |
| 8 | Loading Entry grid | Child of SI | Warehouse confirms batch/qty/seal | Exists; weak validation | Medium | `loading_entry.json`, `batch_allocation.py` | Medium |
| 9 | Tare/gross/net | WS + LDN fields; pull on confirm | Mandatory; auto net on LDN | Not mandatory; no LDN validate calc | High | `loading_delivery_note.py`, `weighment_slip.py` | High |
| 10 | Weighbridge slip no. | `slip_number` on WS | On LDN/DO operational | Not linked end-to-end | Low | `weighment_slip.json` | Medium |
| 11 | Variance approval | Tolerance msgprint only | Supervisor approval required | No approval workflow | High | `batch_allocation.py`, settings | High |
| 12 | DN after loading | ERPNext DN at confirm_dispatch | DN only after load complete | DO/LDN early | **Critical** | `batch_allocation.py`, `delivery_order.py` | Critical |
| 13 | Gate out without DN | Needs dispatch_confirmed | Block without generated DN | Close but not print-aware | Medium | `gate_pass.py` | High |
| 14 | COA on dispatch | Enforced at confirm | Required when product needs COA | No product flag | Medium | `batch_allocation.py`, Item master | High |
| 15 | QC Manager COA | `qc_manager_approve` on LDN | Before gate/Zoho | Implemented | Low | `loading_delivery_note.py` | Low |
| 16 | Zoho invoice timing | On gate release stub | After valid DN+COA | Stub only | Medium | `zoho_dispatch_sync_service.py` | Medium |
| 17 | Unified status | Computed console label | Single operational status | Fragmented | **Critical** | `delivery_order_service.py` | Critical |
| 18 | TC dashboard | Transportation console | Full TC queues | Partial | Medium | `transportation_console.js` | Medium |
| 19 | Security DO actions | Create LDN on DO modal (recent) | Full gate/weight/DN actions | Partial | Medium | `security_console.js` | Medium |
| 20 | Audit trail | Partial timestamps | Every status change logged | No central log | Medium | **new** status log | Medium |
| 21 | Dual QC | PCC + QCR separate | One “loading allowed” gate | Not unified | **Critical** | PCC + `quality/api.py` | Critical |
| 22 | Driver license / gate entry | Partial on Gate Pass/SI | Full gate-in capture | Missing fields | Medium | SI, Gate Pass JSON | Medium |
| 23 | Seal tracking | `seal_number` on LDN/SI | Seal applied by + before/after | Partial | Low | LDN, loading_entry | Low |
| 24 | Batch FIFO | Implemented | Confirm at dispatch | OK | Low | `batch_allocation.py` | Low |
| 25 | Permissions TC vs Security | DocType roles | Role matrix in Section 6 | Not fully audited | Medium | DocType permissions, `permissions.py` | Medium |

---

## Decisions needed (before build)

1. **Single QC gate:** Merge PCC + LDN QC into one “loading allowed” or keep sequential (PCC first, then LDN QC)?  
2. **When to submit Delivery Order:** At TC issue, at truck arrival, or only at dispatch confirm?  
3. **Customer-facing “Delivery Note”:** Print LDN, DO, or ERPNext DN?  
4. **Zoho push timing:** At dispatch confirm vs gate out only?  
5. **Weight-based dispatch:** Always mandatory tare/gross or only for tanker/bulk?  
6. **Transport Coordinator role:** Map to `Transportation Manager` / `Transportation User` or new role?

---

## References in repo

- Workflow target: `CLAUDE.md`, `APC_OPERATIONS_STATUS.md`, `DESIGN_CONCEPT.md`  
- Phase 3–6 consoles: `services/consoles.py`, `patches/v0_3/`  
- Gate enforcement tests: `tests/test_gate_enforcement.py`  
- Pre-check tests: `tests/test_pre_check_clearance.py`  

---

*End of analysis.*
