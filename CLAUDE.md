# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## System Context

APC Operations System for Asia Petrochemicals LLC — a petrochemical manufacturing and trading company operations platform built on Frappe Framework v15.

This repository is focused on **outward movement operations**.

Finance operations such as invoicing, payables, receivables, accounting, collections, and financial reporting are handled in **Zoho Books** or designed as integration points. Do not implement full finance/accounting modules inside APC Operations unless explicitly requested.

The APC Operations system should focus on:

- Sales demand handling from Zoho Books Sales Orders
- Production requirement identification
- Batch allocation
- FIFO stock allocation
- COA handling
- Transport scheduling
- Shipping coordination
- Security review
- Quality clearance
- Loading and dispatch
- Outward movement traceability
- Zoho Books integration points

## Business Direction

This system is for **APC as the seller/exporter** unless explicitly stated otherwise.

When analyzing or changing Job Orders, Incoterms, transport, shipping, dispatch, and outward movement logic, assume the Job Order represents a sale from APC to a customer.

Do not confuse this with purchase/import logic where APC is the buyer.

Avoid supplier-side terminology such as `Supplier Arranged` unless the flow is explicitly a purchase/import flow.

For APC sales Job Orders, prefer:

- APC Arranged
- Customer Arranged
- Not Applicable
- Pending
- Scheduled
- Completed

## Development Commands

All commands assume you are in the bench directory:

```bash
/home/it/Project/APC_Operations/frappe-bench
```

and the virtual environment is activated.

```bash
# Activate environment
source env/bin/activate

# Start development server
bench start

# Run all tests for the app
bench --site apc.local run-tests --app apc_operations

# Run specific DocType tests
bench --site apc.local run-tests --doctype "Transport Schedule"

# Run specific test method
bench --site apc.local run-tests --doctype "Job Order" --test test_job_order_creation

# Database migration after DocType JSON changes
bench --site apc.local migrate

# Clear caches after Python changes or metadata changes
bench --site apc.local clear-cache
bench --site apc.local clear-website-cache

# Rebuild assets after JS/CSS changes
bench --site apc.local build

# Access Python console
bench --site apc.local console

# Check logs
tail -f logs/frappe.log
```

## Architecture Overview

### App Structure

```text
apps/apc_operations/apc_operations/
├── hooks.py                    # Doc events, scheduled jobs, permissions
├── shipping/                   # Main outward movement module
│   ├── doctype/                # Core business documents
│   ├── api.py                  # Dashboard and utility APIs
│   ├── shipping_booking_events.py
│   ├── transport_events.py
│   ├── gate_pass_events.py
│   ├── security_events.py
│   ├── reminders.py            # Scheduled notifications
│   ├── notifications.py
│   ├── permissions.py          # Role-based access
│   └── page/                   # Dashboard pages
├── security/                   # Security module
│   └── doctype/
├── transportation/             # Transportation module
│   └── doctype/
└── patches/                    # Database migrations
```

## Target Operational Workflow

The outward movement workflow should eventually follow this operational chain:

```text
Zoho Books Sales Order
    ↓
APC Sales Demand / Job Order
    ↓
Stock Availability Check
    ↓
Batch Allocation / Production Requirement
    ↓
Transport Schedule, if APC transport is required
    ↓
Shipping Booking / Shipping Coordination, if sea freight or vessel coordination is required
    ↓
Security Draft Delivery Note
    ↓
Security Inspection
    ↓
QC Report Request
    ↓
Loading Delivery Note
    ↓
Dispatch Completion
    ↓
Zoho Books integration point for invoice / delivery / receivables
```

## Current Implementation Workflow

The current implementation may follow this document chain:

```text
Job Order (JO)
    ↓
    ├──→ Transport Schedule (TRN)
    └──→ Shipping Booking (SB)
            ↓
        Transport Schedule
            ↓
        Security Draft Delivery Note
            ↓
        Security Inspection
            ↓
        QC Report Request
            ↓
        Loading Delivery Note
            ↓
        Receivables / Zoho integration point
```

When changing the workflow, clearly distinguish between:

1. Existing implementation behavior
2. Correct business behavior
3. Migration or compatibility requirements

## Sales Demand and Production Logic

Sales demand should originate from **Zoho Books Sales Orders**, not invoices.

Invoices happen too late in the operational process. Production and allocation decisions should happen from confirmed customer order demand.

Correct flow:

```text
Zoho Books Sales Order
    ↓
APC Sales Demand / Job Order
    ↓
Check available stock
    ↓
If stock is available:
    Allocate batch
If stock is short:
    Create Production Requirement
    ↓
Production completed
    ↓
Batch created / released
    ↓
Quality testing completed
    ↓
COA generated and approved
    ↓
Batch becomes available for allocation
    ↓
Dispatch
```

Production requirement calculation:

```text
Production Required Quantity =
Demand Quantity
- Available Free Stock
- Already Allocated Quantity
- Relevant Scheduled / WIP Production Quantity
```

If the result is greater than zero, create or update a Production Requirement.

## Batch Allocation Logic

Batch allocation must follow FIFO.

Allocation rules:

1. Product must match.
2. Grade/specification must match.
3. Packaging type and UOM must match where applicable.
4. Batch must be quality-approved/released through the correct quality checklist.
5. Batch must not be blocked, rejected, expired, cancelled, or fully allocated.
6. Available quantity must be greater than zero.
7. Oldest manufacturing date should be allocated first.
8. If manufacturing date is missing, use batch creation date.
9. If dates are equal, use batch name or creation timestamp as the tie-breaker.

FIFO allocation example:

```text
Demand Quantity: 8,000 KG

Available batches:
BATCH-001 | 3,000 KG | MFG: Jan 1 | COA-001
BATCH-002 | 4,000 KG | MFG: Jan 5 | COA-002
BATCH-003 | 5,000 KG | MFG: Jan 9 | COA-003

System allocation:
BATCH-001 → 3,000 KG
BATCH-002 → 4,000 KG
BATCH-003 → 1,000 KG
```

## COA Logic

COA must come from the actual allocated batch.

Do not randomly select the first COA for a product.

Correct rule:

```text
Allocated Batch → Linked COA → Dispatch COA
```

If one dispatch uses one batch, attach one COA.

If one dispatch uses multiple batches, attach multiple COAs, one per batch.

The dispatch document must preserve batch-level traceability.

Required validations:

- User cannot dispatch a batch without approved COA.
- User cannot attach a COA that belongs to another batch.
- User cannot dispatch rejected or blocked batches.
- User cannot dispatch expired batches.
- User cannot dispatch more than allocated quantity.
- User cannot allocate more than available free stock.
- User cannot allocate a batch that is already fully allocated.
- COA attached to dispatch must match the actual dispatched batch.

## Recommended Batch and COA DocTypes

Use or create equivalent models as needed.

Do not duplicate existing DocTypes unnecessarily. Reuse or extend existing models where practical.

Recommended DocTypes:

- APC Sales Demand
- APC Sales Demand Item
- APC Production Requirement
- APC Batch
- APC Batch Allocation
- APC Batch Allocation Detail
- APC COA
- APC Dispatch Order
- APC Dispatch Batch Detail
- Zoho Sync Log

### APC Sales Demand

Recommended fields:

- Zoho Sales Order ID
- Customer
- Sales Order Date
- Required Dispatch Date
- Status
- Total Demand Quantity
- Total Allocated Quantity
- Total Production Required Quantity

### APC Sales Demand Item

Recommended fields:

- Item/Product
- Grade
- Specification
- Packaging Type
- UOM
- Demand Quantity
- Allocated Quantity
- Production Required Quantity
- Warehouse
- Status

### APC Batch

Recommended fields:

- Product
- Grade
- Specification
- Packaging Type
- Batch Quantity
- Available Quantity
- Allocated Quantity
- Manufacturing Date
- Expiry Date
- Warehouse
- Quality Status
- Batch Status
- Linked COA

### APC COA

Recommended fields:

- Batch
- Product
- Test Parameters
- Approval Status
- Approved By
- Approved Date
- COA PDF / Print Format

### APC Batch Allocation

Recommended fields:

- Sales Demand
- Customer
- Allocation Status
- Allocation Date

### APC Batch Allocation Detail

Recommended fields:

- Sales Demand Item
- Product
- Batch
- COA
- Required Quantity
- Allocated Quantity
- Warehouse
- Manufacturing Date
- FIFO Sequence

### APC Dispatch Batch Detail

Recommended fields:

- Dispatch Order
- Batch
- Dispatched Quantity
- COA
- Manufacturing Date
- Quality Status

## Incoterm-Driven Logic

The `Job Order.determine_booking_requirement()` method in `job_order.py` is the central routing logic.

This system is for APC sales Job Orders, where APC is the seller/exporter.

### EXW — Ex Works

Customer arranges pickup from APC location.

APC responsibility:

- Make goods available at APC premises/warehouse.
- Internal site security and gate pass may still be required.
- APC does not arrange external transport.
- APC does not arrange sea freight.
- APC does not arrange destination clearance.
- APC does not arrange destination delivery.

System behavior:

- APC external Transport Schedule: usually not required.
- Shipping Booking: not required.
- Security/Gate Pass: may be required for site exit control.
- Customer pickup details should be captured.
- If the existing system creates a Transport Schedule for EXW, it should represent pickup coordination/security control, not APC-arranged transportation.

### FOB — Free On Board

APC delivers goods loaded on board the buyer-nominated vessel at the port of loading.

Customer/buyer arranges sea freight.

APC responsibility:

- Local transport from APC warehouse/factory to origin port.
- Export clearance.
- Port loading / handover to vessel.
- Coordination with buyer’s nominated vessel/forwarder.

Customer responsibility:

- Sea freight.
- Marine insurance unless separately agreed.
- Destination port clearance.
- Destination inland delivery.

System behavior:

- Origin Transport Schedule required.
- Shipping coordination required.
- Sea freight booking is by customer/buyer.
- APC may still need vessel, CRO, port, cutoff, and loading details.
- Do not mark origin transport as `Not Required`.

### CFR — Cost and Freight

APC arranges and pays sea freight to the named destination port.

Risk transfers after goods are loaded on board at the origin port, but APC still pays freight to the destination port.

APC responsibility:

- Local transport from APC warehouse/factory to origin port.
- Export clearance.
- Port loading.
- Sea freight booking/payment to named destination port.

Customer responsibility:

- Marine insurance unless separately agreed.
- Destination port clearance.
- Destination port charges where applicable by contract.
- Destination inland delivery.

System behavior:

- Origin Transport Schedule required.
- Shipping Booking required.
- Sea Freight Arranged By = APC.
- Origin Transport Arranged By = APC.
- Insurance Required = No, unless separately agreed.
- Destination Clearance By = Customer.
- Destination Delivery By = Customer.
- Do not use `Supplier Arranged` for CFR sales Job Orders.

### CIF — Cost, Insurance and Freight

CIF is similar to CFR, but APC also arranges marine insurance.

APC responsibility:

- Local transport from APC warehouse/factory to origin port.
- Export clearance.
- Port loading.
- Sea freight booking/payment to named destination port.
- Marine insurance.

Customer responsibility:

- Destination port clearance.
- Destination inland delivery.
- Import duties and taxes unless otherwise agreed.

System behavior:

- Origin Transport Schedule required.
- Shipping Booking required.
- Insurance tracking required.
- Sea Freight Arranged By = APC.
- Origin Transport Arranged By = APC.
- Insurance Arranged By = APC.
- Destination Clearance By = Customer.
- Destination Delivery By = Customer.

### DAP — Delivered At Place

APC delivers goods to the named destination place, but customer handles import clearance, duties, and taxes.

APC responsibility:

- Origin transport.
- Export clearance.
- Main carriage / sea freight / air freight / road freight as applicable.
- Destination inland movement up to the named place.
- Delivery coordination.

Customer responsibility:

- Import clearance.
- Import duties and taxes.

System behavior:

- Transport Schedule required.
- Shipping Booking required if international shipment.
- Destination delivery tracking required.
- Destination Clearance By = Customer.
- Destination Delivery By = APC.
- Do not treat DAP as `no internal booking`.

### DDP — Delivered Duty Paid

APC delivers goods to the customer’s named place and handles import clearance, duties, and taxes.

APC responsibility:

- Origin transport.
- Export clearance.
- Main carriage.
- Insurance if required by contract.
- Destination clearance.
- Duties and taxes.
- Destination inland delivery.
- Final delivery to named place.

Customer responsibility:

- Receive goods at destination.

System behavior:

- Transport Schedule required.
- Shipping Booking required if international shipment.
- Destination clearance tracking required.
- Destination delivery tracking required.
- Duty/tax/compliance tracking required.
- Do not treat DDP as `no internal booking`.
- DDP requires the highest level of operational tracking.

## Incoterm Responsibility Matrix

| Incoterm | Origin Transport APC → Port | Sea Freight | Marine Insurance | Destination Clearance | Destination Delivery |
|---|---|---|---|---|---|
| EXW | Customer | Customer | Customer | Customer | Customer |
| FOB | APC | Customer | Customer | Customer | Customer |
| CFR | APC | APC | Customer / Optional | Customer | Customer |
| CIF | APC | APC | APC | Customer | Customer |
| DAP | APC | APC | Optional / APC | Customer | APC |
| DDP | APC | APC | Optional / APC | APC | APC |

## Incoterm System Rules

Use this logic for sales Job Orders:

```python
if incoterm == "EXW":
    origin_transport_required = False
    origin_transport_by = "Customer"
    sea_freight_required = False
    sea_freight_by = "Customer"
    insurance_required = False
    insurance_by = "Customer"
    destination_clearance_by = "Customer"
    destination_delivery_by = "Customer"

elif incoterm == "FOB":
    origin_transport_required = True
    origin_transport_by = "APC"
    sea_freight_required = False
    sea_freight_by = "Customer"
    insurance_required = False
    insurance_by = "Customer"
    destination_clearance_by = "Customer"
    destination_delivery_by = "Customer"

elif incoterm == "CFR":
    origin_transport_required = True
    origin_transport_by = "APC"
    sea_freight_required = True
    sea_freight_by = "APC"
    insurance_required = False
    insurance_by = "Customer"
    destination_clearance_by = "Customer"
    destination_delivery_by = "Customer"

elif incoterm == "CIF":
    origin_transport_required = True
    origin_transport_by = "APC"
    sea_freight_required = True
    sea_freight_by = "APC"
    insurance_required = True
    insurance_by = "APC"
    destination_clearance_by = "Customer"
    destination_delivery_by = "Customer"

elif incoterm == "DAP":
    origin_transport_required = True
    origin_transport_by = "APC"
    sea_freight_required = True
    sea_freight_by = "APC"
    insurance_required = False
    insurance_by = "Optional/APC"
    destination_clearance_by = "Customer"
    destination_delivery_by = "APC"

elif incoterm == "DDP":
    origin_transport_required = True
    origin_transport_by = "APC"
    sea_freight_required = True
    sea_freight_by = "APC"
    insurance_required = False
    insurance_by = "Optional/APC"
    destination_clearance_by = "APC"
    destination_delivery_by = "APC"
```

## Required Incoterm Fields on Job Order

Recommended fields:

- Incoterm
- Named Place / Named Port
- Port of Loading
- Port of Discharge
- Final Destination
- Origin Transport Required
- Origin Transport Arranged By
- Sea Freight Required
- Sea Freight Arranged By
- Insurance Required
- Insurance Arranged By
- Destination Clearance By
- Destination Delivery By
- Booking Requirement
- Transport Status
- Shipping Status
- Insurance Status
- Security Review Status
- Dispatch Readiness Status

Avoid vague labels such as:

```text
Supplier Arranged
Transport Not Required
```

unless the transaction is explicitly a purchase/import flow.

For APC sales Job Orders, prefer:

```text
APC Arranged
Customer Arranged
Not Applicable
Pending
Scheduled
Completed
```

## Document Event Flow

Status changes propagate bidirectionally through hooks in `hooks.py`.

Important current event patterns:

1. Shipping Booking `on_update` syncs to Job Order through `shipping_booking_events.py`.
2. Transport Schedule `on_update` syncs to both Job Order and Shipping Booking through `transport_events.py`.
3. Security Inspection `on_update` creates or updates QC Report and Loading DN through `security_events.py`.

When changing status logic, always check whether linked documents also need updating.

Use `update_modified=False` where needed to avoid unnecessary recursive updates.

Example pattern:

```python
def sync_status_to_job_order(self):
    if not self.job_order:
        return

    frappe.db.set_value(
        "Job Order",
        self.job_order,
        {
            "transport_schedule": self.name,
            "transport_status": self.get_job_order_transport_status(),
        },
        update_modified=False,
    )
```

## Auto-Creation Triggers

Documents are auto-created through controller methods, not only workflows.

Current examples:

- `Shipping Booking._handle_cro_received()` calls `generate_transportation()` and creates Transport Schedule.
- `Transport Schedule.ensure_outward_follow_up_records()` creates Security Draft DN and Transport PO Request.
- `Security Inspection.report_to_qc()` creates QC Report Request.
- `Security Inspection.create_loading_delivery_note()` creates Loading Delivery Note.

When adding new automation, follow the same server-side controller pattern.

Do not place critical business logic only in client scripts.

## Permission Model

Custom permission conditions are defined in `hooks.py`.

Current pattern:

```python
permission_query_conditions = {
    "Shipping Booking": "apc_operations.shipping.permissions.get_shipping_booking_permission",
    "Transport Schedule": "apc_operations.shipping.permissions.get_transport_permission",
}
```

Modify `permissions.py` to change visibility rules.

Always consider permission impact when adding new DocTypes, reports, dashboards, or APIs.

## Key Implementation Patterns

### DocType Naming Conventions

Current naming conventions:

- Job Order: `JO-{YYYY}-{#####}`
- Shipping Booking: `SB-{YYYY}-{#####}`
- Transport Schedule: `TRN-{YYYY}-{#####}`
- Security Dispatch: `SEC-{YYYY}-{#####}`
- Security Inspection: `SEC-INS-{YYYY}-{#####}`
- Loading Delivery Note: `LDN-{YYYY}-{#####}`

Keep internal document names stable.

For list views, prefer using `title_field` or visible columns instead of renaming records.

Example:

- Transport Schedule internal ID: `TRN-2026-0002`
- Display title: linked Job Order number, such as `JO-2026-00024`

### Creating Linked Documents

Use this pattern:

```python
def create_linked_document(self):
    existing = frappe.db.exists("Target DocType", {"source_field": self.name})

    if existing:
        if not self.linked_field:
            self.db_set("linked_field", existing, update_modified=False)
        return existing

    doc = frappe.new_doc("Target DocType")
    doc.source_field = self.name
    doc.insert(ignore_permissions=True)

    self.db_set("linked_field", doc.name, update_modified=False)
    return doc.name
```

Before creating a new linked document, always check whether one already exists.

### Whitelisted API Methods

Add new API methods carefully.

Example:

```python
@frappe.whitelist()
def my_new_method(param):
    return frappe.get_all("DocType", filters={"field": param})
```

If the project uses custom whitelisted method mappings in `hooks.py`, update them when needed.

## Recommended Service Modules

For core logic, prefer reusable Python services instead of putting everything in DocType controllers.

Recommended service modules:

```text
apc_operations/shipping/services/
├── incoterm_service.py
├── batch_allocation_service.py
├── production_requirement_service.py
├── coa_service.py
├── dispatch_validation_service.py
└── zoho_sync_service.py
```

Expected functions:

```python
get_available_batches(product, grade=None, packaging_type=None, warehouse=None)

calculate_free_stock(batch)

calculate_production_requirement(sales_demand_item)

create_production_requirement_if_shortage(sales_demand)

allocate_batches_fifo(sales_demand)

release_allocation(allocation)

validate_dispatch_batches(dispatch_order)

attach_batch_coas_to_dispatch(dispatch_order)

determine_incoterm_responsibilities(job_order)

apply_incoterm_defaults(job_order)
```

## Testing

Test files follow Frappe convention:

```text
test_{doctype_name}.py
```

Example test pattern:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestJobOrder(FrappeTestCase):
    def setUp(self):
        self.job_order = frappe.get_doc({
            "doctype": "Job Order",
            "customer": "_Test Customer",
            "date": "2026-04-27",
            "terms_of_delivery": "FOB",
        })

    def test_booking_requirement_determination(self):
        self.job_order.determine_booking_requirement()
        self.assertEqual(self.job_order.booking_requirement, "Shipping Coordination")
```

Required tests for Incoterm logic:

- EXW should not require APC external transport or sea freight.
- FOB should require APC origin transport but customer sea freight.
- CFR should require APC origin transport and APC sea freight.
- CIF should require APC origin transport, APC sea freight, and APC insurance.
- DAP should require APC destination delivery but customer import clearance.
- DDP should require APC destination clearance and APC destination delivery.

Required tests for batch allocation:

- FIFO allocation by manufacturing date.
- Partial allocation from multiple batches.
- Insufficient stock creates production requirement.
- Rejected batch cannot be allocated.
- Blocked batch cannot be allocated.
- Expired batch cannot be allocated.
- Missing COA blocks dispatch.
- COA from another batch is rejected.
- Cannot dispatch more than allocated quantity.
- Allocation should be safe against double allocation.

## Critical Files for Common Tasks

| Task | Primary File |
|---|---|
| Add DocType field | `shipping/doctype/{name}/{name}.json` then migrate |
| Add business logic | `shipping/doctype/{name}/{name}.py` |
| Add reusable business logic | `shipping/services/{service_name}.py` |
| Add client-side JS | `shipping/doctype/{name}/{name}.js` then build |
| Add dashboard API | `shipping/api.py` |
| Scheduled jobs | `hooks.py` `scheduler_events` |
| Role permissions | DocType JSON `permissions` array |
| Permission query filters | `shipping/permissions.py` |
| Workflow triggers | `hooks.py` `doc_events` |
| Patches | `patches/` |

## Known Constraints

1. **No complete Zoho Books integration yet**

   Loading Delivery Note has fields such as `receivables_status` and `invoice_reference`, but no complete Zoho Books API integration exists.

   Transport PO Request may have fields such as `zoho_books_reference`, but no full sync logic exists.

2. **Production module may be incomplete**

   Production may be described in documentation, but production demand, production requirement, batch creation, and batch allocation may not be fully implemented yet.

3. **Batch allocation engine may be missing or incomplete**

   FIFO allocation, free stock calculation, COA linkage, and dispatch validation may need to be implemented or hardened.

4. **Gate Pass items may not be fully populated**

   Gate Pass may be created by Transport Schedule, but items may not be auto-populated from Security Inspection.

5. **Currency conversion should not be assumed**

   No reliable currency conversion logic should be assumed unless explicitly implemented.

6. **Incoterm logic may be wrong in existing code**

   Existing code may incorrectly use supplier-arranged terminology for APC sales Job Orders.

   For sales Job Orders, APC is the seller/exporter. CFR/CIF should not be treated as supplier-arranged by default.

## Default Analysis Task

When asked to analyze the project, inspect the codebase for:

1. Functional gaps.
2. Bugs in status synchronization.
3. Missing workflow steps.
4. Frappe/ERPNext design issues.
5. Missing server-side validations.
6. Incorrect Incoterm responsibility logic.
7. Missing Zoho Books integration points.
8. Batch allocation and COA traceability risks.
9. Permission issues.
10. Dashboard/report inaccuracies.

Report in this priority order:

1. Critical bugs blocking workflow.
2. Data integrity risks.
3. Incorrect Incoterm or responsibility logic.
4. Missing validation logic.
5. Missing integration points.
6. Missing DocTypes or fields.
7. Dashboard/report mismatches.
8. Efficiency improvements.
9. Code cleanup.

Think like a senior Frappe developer:

- Suggest specific DocType changes with field names.
- Recommend controller and hook implementations.
- Prefer server-side business logic over client-only scripts.
- Use reusable service modules for core logic.
- Consider permissions.
- Consider migrations and patches.
- Add test cases.
- Keep finance/accounting in Zoho Books unless explicitly requested.

## Current Product Direction

The system should eventually support this high-level operational flow:

```text
Zoho Books Sales Order
    ↓
APC Job Order / Sales Demand
    ↓
Demand quantity calculation
    ↓
Free stock check
    ↓
FIFO batch allocation
    ↓
Production requirement if shortage
    ↓
Quality approval
    ↓
COA approval
    ↓
Transport scheduling
    ↓
Shipping booking / shipping coordination
    ↓
Security review
    ↓
Loading delivery note
    ↓
Dispatch completion
    ↓
Zoho Books update / invoice integration point
```

Do not implement invoicing, payables, receivables, accounting, or collections inside APC Operations unless explicitly instructed.

Only create clean integration points for Zoho Books.