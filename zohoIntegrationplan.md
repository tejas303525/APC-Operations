# Zoho Books Job Order Integration Plan

## Summary

- Source documents:
  - Outward Job Order: Zoho Books Estimate / Proforma Invoice.
  - Inward Job Order: Zoho Books Purchase Order.
- Integration method: Zoho webhook pushes confirmed source documents into APC.
- Accounting sync: create Zoho records and also email Accounts as audit/fallback.
- Current code already has partial Zoho stubs, but no real Zoho Books client. Existing outward dispatch and import GRN sync services are stub-capable only.

Files inspected:

- `apps/apc_operations/apc_operations/zoho/api.py`
- `apps/apc_operations/apc_operations/zoho/integration.py`
- `apps/apc_operations/apc_operations/zoho/README.md`
- `apps/apc_operations/apc_operations/zoho/doctype/apc_zoho_settings/apc_zoho_settings.json`
- `apps/apc_operations/apc_operations/zoho/doctype/zoho_sync_log/zoho_sync_log.json`
- `apps/apc_operations/apc_operations/shipping/doctype/job_order/job_order.py`
- `apps/apc_operations/apc_operations/shipping/doctype/job_order/job_order.js`
- `apps/apc_operations/apc_operations/shipping/doctype/job_order/job_order.json`
- `apps/apc_operations/apc_operations/shipping/doctype/delivery_order/delivery_order.json`
- `apps/apc_operations/apc_operations/shipping/doctype/import_grn/import_grn.json`
- `apps/apc_operations/apc_operations/shipping/doctype/loading_delivery_note/loading_delivery_note.py`
- `apps/apc_operations/apc_operations/shipping/doctype/loading_delivery_note/loading_delivery_note.json`
- `apps/apc_operations/apc_operations/shipping/doctype/transport_po_request/transport_po_request.py`
- `apps/apc_operations/apc_operations/shipping/doctype/transport_po_request/transport_po_request.json`
- `apps/apc_operations/apc_operations/transportation/doctype/transport_schedule/transport_schedule.py`
- `apps/apc_operations/apc_operations/shipping/services/zoho_dispatch_sync_service.py`
- `apps/apc_operations/apc_operations/shipping/services/zoho_import_receipt_sync_service.py`
- `apps/apc_operations/apc_operations/shipping/services/import_grn_service.py`
- `apps/apc_operations/apc_operations/tests/test_zoho_dispatch_sync.py`
- `apps/apc_operations/apc_operations/tests/test_zoho_import_receipt_sync.py`

## Current State

### Existing Zoho Integration

- `zoho/api.py` exposes API-key-protected endpoints using `X-APC-API-Key`.
- `import_pfi()` currently imports Zoho PFI/Sales Order data into `APC Sales Demand`, not directly into `Job Order`.
- `create_job_order_from_pfi()` can create a `Job Order` from `APC Sales Demand`, but it currently:
  - sets `commercial_movement = "Export"`;
  - sets `status = "Draft"`;
  - links the Sales Demand;
  - copies basic items.
- `zoho/integration.py` is mostly placeholder/mock logic.
- `APC Zoho Settings` stores API key, API secret, organization ID, endpoint fields, webhook secret, and basic sync flags, but it does not currently support full Zoho Books OAuth token refresh.

### Existing Dispatch / Receivables Flow

- `zoho_dispatch_sync_service.py` already defines a two-phase outward sync design:
  - push Loading Delivery Note to Zoho delivery notes after dispatch confirmation;
  - create Zoho invoice after gate release.
- This service is currently stubbed:
  - if stub mode is enabled, it writes fake Zoho IDs;
  - if stub mode is disabled, it returns that the real Zoho client is not implemented.
- `Loading Delivery Note` already has useful fields:
  - `zoho_dn_id`
  - `zoho_invoice_id`
  - `zoho_invoice_url`
  - `zoho_invoice_sent_to_customer`
  - `receivables_status`
  - `reported_to_receivables_on`
  - `reported_to_receivables_by`
- `LoadingDeliveryNote.report_to_receivables()` already emails Accounts users after required QC/security checks.

### Existing Import GRN / Payables Flow

- `import_grn_service.py` creates Import GRNs for import Delivery Orders.
- `approve_import_grn()` approves the GRN, then calls the Zoho import receipt sync service.
- `zoho_import_receipt_sync_service.py` pushes import receipt data in stub mode only.
- It writes back `zoho_import_receipt_id` to `Job Order`.
- It does not yet create a real Zoho payable/bill.

### Existing Transport PO / Payables Flow

- `Transport Schedule.create_transport_po_request()` creates or refreshes `Transport PO Request`.
- It sets `payables_status = "Pending Payables"`.
- It syncs transport charges into the PO request.
- It emails Accounts users through `notify_payables_team()`.
- `Transport PO Request` already has:
  - `payables_status`
  - `zoho_books_reference`
  - cost fields
  - transporter, vehicle, driver, pickup, delivery, schedule references
- There is no real Zoho Books payables push for `Transport PO Request`.

## Key Changes

### 1. Zoho Webhook Entry Points

Add authenticated webhook endpoints under `apc_operations.zoho.api`.

#### `import_zoho_estimate_as_job_order`

Purpose: create or update an outward Job Order from a Zoho Books Estimate / Proforma Invoice.

Behavior:

- Validate the webhook/API key or webhook secret.
- Read Zoho document ID and document number.
- Create or update one `Job Order` idempotently.
- Set `commercial_movement = "Export"`.
- Set `status = "Confirmed"` after required validation passes.
- Map:
  - customer
  - PFI/proforma number
  - document date
  - required dispatch date
  - payment terms
  - incoterms
  - mode of transport
  - port of loading
  - port of discharge
  - currency
  - item rows
  - item quantity and UOM
  - grade/specification
  - packing fields where present
  - commercial line values where present

If the webhook payload is missing required data, do not create a broken confirmed Job Order. Log a failed `Zoho Sync Log` entry with the reason.

#### `import_zoho_purchase_order_as_job_order`

Purpose: create or update an inward Job Order from a Zoho Books Purchase Order.

Behavior:

- Validate the webhook/API key or webhook secret.
- Read Zoho purchase order ID and number.
- Create or update one `Job Order` idempotently.
- Set `commercial_movement = "Import"`.
- Set `status = "Confirmed"` after required validation passes.
- Map:
  - supplier
  - PO number
  - purchase order date
  - expected receipt/arrival date
  - payment terms
  - incoterms
  - mode of transport
  - origin/destination route fields
  - currency
  - item rows
  - item quantity and UOM
  - grade/specification
  - packing fields where present
  - commercial line values where present

If the webhook payload is missing supplier or item data, log a failed sync and do not create a confirmed incomplete Job Order.

### 2. Real Zoho Books Client

Create a shared Zoho Books client service, for example:

`apps/apc_operations/apc_operations/zoho/books_client.py`

Responsibilities:

- Store and refresh Zoho OAuth access tokens.
- Use `organization_id` on all Zoho Books API calls.
- Provide authenticated `GET`, `POST`, and `PUT` helpers.
- Normalize Zoho errors into APC-friendly exceptions.
- Log request/response data into `Zoho Sync Log`.
- Avoid duplicate outbound records when the APC document already has a Zoho ID/reference.

Extend `APC Zoho Settings` with:

- `client_id`
- `client_secret`
- `refresh_token`
- `access_token`
- `access_token_expires_on`
- `base_api_url`
- `source_import_enabled`
- `payables_export_enabled`
- `receivables_export_enabled`
- `email_fallback_enabled`

Keep existing API key and webhook secret fields for inbound authentication.

### 3. Tabular Structure / Field Model

Use the existing operational doctypes wherever possible. Add only the fields required to track Zoho source and accounting references.

| Doctype | New / Existing Fields | Purpose |
|---|---|---|
| `Job Order` | `zoho_source_type` | `Estimate`, `Proforma Invoice`, or `Purchase Order` |
| `Job Order` | `zoho_source_id` | Zoho document ID for idempotency |
| `Job Order` | `zoho_source_number` | Zoho document number visible to users |
| `Job Order` | `zoho_sync_status` | Import status from Zoho |
| `Job Order` | `zoho_last_synced_on` | Last successful source sync timestamp |
| `Job Order` | existing `commercial_movement` | Use `Export` for outward and `Import` for inward |
| `Job Order` | existing `status` | Set to `Confirmed` after valid import |
| `Job Order Item` | `zoho_line_item_id` | Zoho line-level idempotency/reference |
| `Job Order Item` | `rate` | Zoho line rate |
| `Job Order Item` | `amount` | Zoho line amount |
| `Job Order Item` | `tax_name` | Zoho tax label/name |
| `Job Order Item` | `tax_amount` | Zoho tax amount |
| `Import GRN` | existing `zoho_import_receipt_id` | Zoho receipt reference |
| `Import GRN` | `zoho_bill_id` | Zoho payable/bill reference |
| `Import GRN` | `payables_status` | Payables sync status |
| `Loading Delivery Note` | existing `zoho_dn_id` | Zoho delivery note reference |
| `Loading Delivery Note` | existing `zoho_invoice_id` | Zoho receivable invoice reference |
| `Loading Delivery Note` | existing `zoho_invoice_url` | Link to Zoho invoice |
| `Loading Delivery Note` | existing `receivables_status` | Receivables workflow status |
| `Transport PO Request` | existing `payables_status` | Transport payable workflow status |
| `Transport PO Request` | existing `zoho_books_reference` | Human-readable Zoho reference |
| `Transport PO Request` | `zoho_bill_id` | Zoho payable/bill ID |
| `Zoho Sync Log` | new sync type options | Audit source import, payables export, receivables export |

Add these `Zoho Sync Log.sync_type` options:

- `Estimate Import`
- `Proforma Invoice Import`
- `Purchase Order Import`
- `GRN Payables Export`
- `Transport Payables Export`
- `Receivables Export`
- `Zoho Bill Export`

### 4. Outward Job Order Flow

Trigger:

- Zoho sends webhook when an Estimate / Proforma Invoice is confirmed or approved.

APC behavior:

1. Receive webhook.
2. Validate authentication.
3. Parse source document.
4. Find existing `Job Order` by `zoho_source_id`.
5. If not found, create a new `Job Order`.
6. Set `commercial_movement = "Export"`.
7. Map customer and item details.
8. Set `status = "Confirmed"` only if all required Job Order validations pass.
9. Let existing Job Order confirmation logic create or link operational booking records.
10. Write `Zoho Sync Log`.

Business impact:

- Sales/commercial data starts in Zoho Books and becomes an APC operational Job Order without duplicate manual entry.
- APC keeps its existing operational workflow after confirmation.

### 5. Inward Job Order Flow

Trigger:

- Zoho sends webhook when a Purchase Order is confirmed or approved.

APC behavior:

1. Receive webhook.
2. Validate authentication.
3. Parse purchase order data.
4. Find existing `Job Order` by `zoho_source_id`.
5. If not found, create a new `Job Order`.
6. Set `commercial_movement = "Import"`.
7. Map supplier and item details.
8. Set `status = "Confirmed"` only if validations pass.
9. Let existing import Job Order logic create or link inward transport/shipping records.
10. Write `Zoho Sync Log`.

Business impact:

- Purchase operations start from Zoho Books Purchase Orders and become APC import Job Orders.
- Supplier and item details are controlled from Zoho source data.

### 6. GRN to Payables

Reuse the existing `approve_import_grn()` flow.

Current state:

- GRN approval already calls `push_import_receipt_to_zoho()`.
- That service currently supports stub mode only.

Change:

- Extend the GRN approval sync to create the correct Zoho payable record.
- Use the real Zoho Books client.
- Write back:
  - `Import GRN.zoho_import_receipt_id`
  - `Import GRN.zoho_bill_id`
  - `Import GRN.payables_status`
  - `Job Order.zoho_import_receipt_id`
- Send an Accounts email when:
  - sync succeeds, as an audit notice; or
  - sync fails, as fallback action required.

Business impact:

- Import receipt and payable creation no longer depends only on manual email follow-up.

### 7. Outward Delivery Note to Receivables

Reuse `zoho_dispatch_sync_service.py`.

Current state:

- It can push a delivery note in stub mode.
- It can create a stub invoice after gate release.
- Loading DN already tracks Zoho delivery note and invoice IDs.

Change:

- Replace the stub-only `_post_zoho()` implementation with the shared Zoho Books client.
- Push delivery note data when the Loading Delivery Note is dispatch-confirmed/issued.
- Create receivable invoice after the existing gate-release validation passes.
- Keep COA push behavior.
- Keep existing receivables email as fallback/audit.

Business impact:

- Outward dispatch data reaches Zoho receivables without Accounts manually recreating the invoice data.

### 8. Transport PO to Payables

Reuse the existing `Transport Schedule.create_transport_po_request()` flow.

Current state:

- Transport PO Request is created automatically after transport booking.
- It is marked `Pending Payables`.
- Accounts users are emailed.

Change:

- After `Transport PO Request` creation or refresh, call a new transport payables sync service.
- Create the Zoho payable/bill/vendor charge record using:
  - transporter
  - vehicle/driver
  - pickup/delivery
  - transport charges
  - fuel cost
  - additional charges
  - total cost
  - linked Job Order
  - linked Shipping Booking
  - linked Transport Schedule
- Write back:
  - `Transport PO Request.payables_status`
  - `Transport PO Request.zoho_books_reference`
  - `Transport PO Request.zoho_bill_id`
- Keep existing email notification as fallback/audit.

Business impact:

- Transport cost payables are shared with Zoho Books automatically when transport is booked.

## Testing Plan

Add or extend tests for the following scenarios:

- Zoho Estimate webhook creates one confirmed Export Job Order.
- Duplicate Estimate webhook updates the same Job Order and does not create a duplicate.
- Zoho Purchase Order webhook creates one confirmed Import Job Order.
- Duplicate Purchase Order webhook updates the same Job Order and does not create a duplicate.
- Missing customer on outward source logs failed sync and does not create a confirmed Job Order.
- Missing supplier on inward source logs failed sync and does not create a confirmed Job Order.
- Missing item rows logs failed sync.
- Source line items map to `Job Order Item` rows, including Zoho line ID, quantity, UOM, rate, amount, and tax fields.
- GRN approval creates a payables sync request and updates GRN/Job Order Zoho references.
- GRN payables sync failure sends fallback email and logs failure.
- Loading Delivery Note dispatch creates receivables sync request and writes Zoho delivery note ID.
- Gate release creates receivable invoice and writes Zoho invoice ID/URL.
- Transport PO Request creation pushes payable data and updates payables status.
- Transport PO sync failure leaves the request pending and sends fallback email.
- Disabled Zoho flags skip outbound calls but log the skipped status.
- Stub mode tests continue to pass without network calls.

## Migration / Compatibility

- Add DocType fields through JSON changes and a migration patch.
- Backfill existing Job Orders where possible:
  - existing `pi_number` becomes `zoho_source_number`;
  - linked `sales_demand.zoho_sales_order_id` becomes `zoho_source_id`;
  - linked `sales_demand.zoho_sales_order_number` becomes `zoho_source_number`.
- Keep existing `Export` / `Import` values because the codebase uses those values, even though users describe them as outward/inward.
- No existing records need commercial movement conversion.
- Existing Sales Demand flow can remain for backward compatibility, but new Zoho source imports should create/update Job Orders directly.

## Acceptance Criteria

- A confirmed Zoho Estimate / Proforma webhook creates a confirmed outward Job Order in APC.
- A confirmed Zoho Purchase Order webhook creates a confirmed inward Job Order in APC.
- Re-sending the same Zoho webhook updates the existing Job Order, not a duplicate.
- GRN approval sends import payable data to Zoho and records the Zoho reference.
- Outward Loading Delivery Note / invoice flow sends receivables data to Zoho and records the Zoho reference.
- Transport PO Request sends payable data to Zoho and records the Zoho reference.
- Every inbound and outbound sync creates a `Zoho Sync Log`.
- If Zoho API fails, Accounts receives an email fallback and the APC document remains visibly pending/failed.
