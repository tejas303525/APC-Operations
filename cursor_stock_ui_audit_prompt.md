# APC Operations Stock UI Audit & Creation Task

## Context
This is an APC Operations System built on Frappe Framework v15 for Asia Petrochemicals LLC. The system handles outward movement operations including sales demand, batch allocation, production requirements, and dispatch.

## Current State (Backend Exists)

The following backend code exists and is functional:

1. **APC Batch DocType** (`/apps/apc_operations/apc_operations/inventory/doctype/apc_batch/`)
   - Fields: product, grade, specification, batch_quantity, available_quantity, allocated_quantity, manufacturing_date, expiry_date, batch_status, quality_status, warehouse, linked_coa
   - Naming: `BATCH-{YYYY}-{#####}`
   - Python controller with FIFO allocation logic

2. **Batch Allocation Service** (`/apps/apc_operations/apc_operations/services/batch_allocation.py`)
   - `get_available_batches()` - FIFO batch retrieval
   - `calculate_free_stock()` - Free stock calculation
   - `allocate_batches_fifo()` - Automatic allocation
   - `validate_dispatch_batches()` - COA validation

3. **Dashboard API** (`/apps/apc_operations/apc_operations/services/dashboard.py`)
   - Stock summary by product/warehouse
   - Low stock alerts
   - Expiring batches
   - Demand fulfillment reports

4. **Related DocTypes:**
   - APC Sales Demand
   - APC Batch Allocation
   - APC Batch Allocation Detail
   - APC Production Requirement
   - APC COA
   - APC Dispatch Order

## Task: Audit and Create Missing UI

### Step 1: Audit Existing UI

Check if the following UI components exist in the codebase. Look for:

1. **JavaScript files** for DocTypes (`*.js` files alongside `*.py` and `*.json`)
2. **Page directories** with HTML/JS files for dashboards
3. **Report definitions** in JSON or Python
4. **Workspace definitions** for the Inventory module

Specific files to check:
```
/apps/apc_operations/apc_operations/inventory/doctype/apc_batch/apc_batch.js
/apps/apc_operations/apc_operations/inventory/doctype/apc_coa/apc_coa.js
/apps/apc_operations/apc_operations/sales/doctype/apc_sales_demand/apc_sales_demand.js
/apps/apc_operations/apc_operations/sales/doctype/apc_batch_allocation/apc_batch_allocation.js
/apps/apc_operations/apc_operations/inventory/page/
/apps/apc_operations/apc_operations/inventory/workspace/
```

### Step 2: Create Missing UI Components

#### A. APC Batch DocType JavaScript (`apc_batch.js`)

Create client-side enhancements:

```javascript
frappe.ui.form.on('APC Batch', {
    refresh(frm) {
        // Add dashboard button
        // Show allocation summary
        // Add quick actions based on status
    },
    
    batch_status(frm) {
        // Validate status changes
    },
    
    linked_coa(frm) {
        // Auto-sync quality status from COA
    }
});
```

Required buttons/actions:
- View Allocations (shows where this batch is allocated)
- Release Allocation (if deallocated)
- View COA (link to linked COA)
- Stock Ledger (if implemented)

#### B. Batch Allocation Page

Create a dedicated page at `/apps/apc_operations/apc_operations/inventory/page/batch_allocation_dashboard/`

Components needed:
1. **Page HTML** (`batch_allocation_dashboard.html`)
   - Dashboard layout with cards for KPIs
   - Table for available batches
   - Table for pending demand
   - Allocation action area

2. **Page JS** (`batch_allocation_dashboard.js`)
   - Load dashboard data from `dashboard.py`
   - Filter batches by product/grade/warehouse
   - Allocate button with FIFO logic
   - Show allocation preview before commit

3. **Page JSON** (`batch_allocation_dashboard.json`)
   - Page metadata for Frappe

Key features:
- Left panel: Available batches (sortable by MFG date)
- Right panel: Unallocated demand
- Center: Allocation preview
- Auto-allocate button using FIFO
- Manual allocation override

#### C. Stock Reports

Create these reports if missing:

1. **Batch Stock Ledger** (`batch_stock_ledger.py`)
   - All batches with quantities
   - Filter by product, warehouse, status
   - Group by grade/specification

2. **Stock Availability Report** (`stock_availability_report.py`)
   - Product-wise available stock
   - Allocated vs available breakdown
   - Warehouse summary

3. **FIFO Allocation Report** (`fifo_allocation_report.py`)
   - Shows batches in FIFO order
   - Recommended allocations for pending demand
   - Shortage calculations

#### D. Inventory Workspace

Create workspace file at `/apps/apc_operations/apc_operations/inventory/workspace/inventory/inventory.json`

Should include shortcuts to:
- APC Batch (List)
- APC Batch (New)
- APC COA (List)
- Batch Allocation Dashboard (Page)
- Stock Reports

Shortucts for common actions:
- View Active Batches
- View Pending COA
- View Expiring Batches
- Create Batch Allocation

#### E. Enhance Sales Demand UI

Add to `apc_sales_demand.js`:
- "Calculate Production Requirement" button
- "Allocate Batches" button
- Stock availability indicator per item line
- Link to view batch allocation document

### Step 3: Business Rules to Enforce

From CLAUDE.md, ensure UI enforces:

1. **FIFO Allocation Rules**
   - Oldest manufacturing date first
   - Must match product, grade, specification
   - Only Approved quality status batches
   - Only Active/On Hold batch status

2. **COA Validation**
   - Cannot allocate without approved COA
   - Cannot dispatch without COA
   - COA must belong to the batch

3. **Status Flow**
   - Draft → Confirmed → Allocated → Dispatched
   - Blocked batches cannot be allocated
   - Expired batches cannot be allocated

4. **Allocation Limits**
   - Cannot allocate more than available quantity
   - Cannot over-allocate to multiple demands
   - Show available vs allocated clearly

### Step 4: Testing Checklist

After creating UI, verify:

- [ ] APC Batch list view loads with filters
- [ ] APC Batch form shows all fields correctly
- [ ] Batch Allocation Dashboard page loads
- [ ] FIFO allocation works from dashboard
- [ ] Stock reports generate correctly
- [ ] Inventory workspace shows in sidebar
- [ ] Sales Demand shows allocation buttons
- [ ] COA links work from batch form

## Output Expected

1. List of existing UI components found
2. List of missing components created
3. Summary of changes made
4. Any issues or blockers encountered

## Reference Files

- DocType JSON: `/apps/apc_operations/apc_operations/inventory/doctype/apc_batch/apc_batch.json`
- DocType Python: `/apps/apc_operations/apc_operations/inventory/doctype/apc_batch/apc_batch.py`
- Batch Allocation Service: `/apps/apc_operations/apc_operations/services/batch_allocation.py`
- Dashboard API: `/apps/apc_operations/apc_operations/services/dashboard.py`
- Hooks: `/apps/apc_operations/apc_operations/hooks.py`

## Important Notes

1. This is a **sales/outward movement system** - APC is the seller
2. Stock comes from APC Batch (not Zoho) - Zoho only gets demand
3. Follow Frappe v15 conventions
4. Use existing API methods from batch_allocation.py and dashboard.py
5. Test with `bench start` after changes
6. Run `bench build` after JS changes

Begin audit now. Report what exists and what needs to be created.
