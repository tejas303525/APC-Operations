# APC Operations System - Implementation Plan

## Overview
Building a comprehensive operations management system for Asia Petro-Chemicals using Frappe Framework with Zoho integration.

## Modules

### 1. Shipping Module
- **DocTypes:**
  - Bill of Lading (BL)
  - Packing List
  - Certificate of Origin (COO)
  - Commercial Invoice
  - Gate Pass (In/Out)
  - Delivery Order
- **Features:**
  - Track shipments (local & export)
  - Container management
  - Document generation (PDF)
  - Status workflow (Draft → Submitted → In Transit → Delivered)

### 2. Transportation Module
- **DocTypes:**
  - Vehicle Master
  - Driver Master
  - Transport Order
  - Weighment/Weight Bridge
  - Trip Sheet
  - Fuel Log
- **Features:**
  - Vehicle tracking
  - Load/unload management
  - Weight tracking
  - Route optimization

### 3. Quality Control (QC) Module
- **DocTypes:**
  - COA (Certificate of Analysis)
  - Quality Inspection
  - Test Results
  - Product Specifications
- **Features:**
  - Quality parameter tracking
  - Pass/Fail workflows
  - COA generation
  - Inspection scheduling

### 4. Security Module
- **DocTypes:**
  - Gate Entry/Exit
  - Visitor Pass
  - Material Movement
  - Security Checklist
- **Features:**
  - Gate pass validation
  - Vehicle verification
  - Visitor management
  - Material tracking

### 5. Production Module
- **DocTypes:**
  - Production Order
  - Batch/Lot Master
  - Production Entry
  - Raw Material Issue
  - Finished Goods Receipt
- **Features:**
  - Batch tracking
  - Production planning
  - Yield calculation
  - Material consumption tracking

### 6. Admin Module
- **DocTypes:**
  - User Management (RBAC)
  - Company Settings
  - Location/Warehouse Master
  - Customer/Supplier Master
- **Features:**
  - Role-based permissions
  - Multi-company support
  - Audit logs
  - Settings management

## RBAC Structure

### Roles
1. **System Manager** - Full access
2. **Operations Manager** - All modules, no settings
3. **Shipping Coordinator** - Shipping module only
4. **Transport Manager** - Transportation module only
5. **QC Analyst** - QC module only
6. **Security Officer** - Security module only
7. **Production Supervisor** - Production module only
8. **Viewer/Report User** - Read-only access

### Permissions per Role
- DocType-level permissions (Create, Read, Write, Delete, Submit, Cancel)
- Field-level permissions (hide sensitive pricing data)
- Report permissions

## Zoho Integration

### Integration Points
1. **Zoho Books** - Financial transactions, invoices sync
2. **Zoho Inventory** - Stock levels, item masters sync
3. **Zoho CRM** - Customer/Supplier sync
4. **Zoho Creator** - Custom app data sync (if needed)

### Sync Strategy
- **One-way sync:** Frappe → Zoho (master data, transactions)
- **Two-way sync:** Customers, Items, Inventory (periodic pull from Zoho)
- **Real-time:** Webhooks for critical updates
- **Scheduled:** Hourly/Daily batch sync jobs

### API Implementation
- Use Zoho REST APIs (OAuth 2.0 authentication)
- Background jobs for sync operations
- Error handling and retry logic
- Sync logs for audit

## Technical Architecture

### Frappe App Structure
```
apc_operations/
├── apc_operations/
│   ├── __init__.py
│   ├── hooks.py
│   ├── modules.txt
│   ├── patches.txt
│   ├── templates/
│   ├── public/
│   └── config/
├── apc_operations/shipping/
├── apc_operations/transportation/
├── apc_operations/qc/
├── apc_operations/security/
├── apc_operations/production/
├── apc_operations/zoho_integration/
└── requirements.txt
```

### Key Technologies
- **Framework:** Frappe (Python + MariaDB)
- **Frontend:** Frappe UI (Vue.js-based) + HTML/CSS/JS
- **APIs:** REST API + Frappe whitelisted methods
- **Background Jobs:** Frappe RQ (Redis Queue)
- **Scheduler:** Frappe Scheduler for periodic tasks
- **Authentication:** Session-based + API keys for Zoho

## Database Schema (Key DocTypes)

### Shipping
- Bill of Lading: link to Delivery Order, container_no, vessel_name, port_of_loading, port_of_discharge
- Packing List: link to BL, items[], net_weight, gross_weight
- Gate Pass: type (In/Out), vehicle_no, driver_name, materials[]

### Transportation
- Transport Order: source, destination, vehicle, driver, status
- Weighment: first_weight, second_weight, net_weight, transaction_type

### QC
- COA: batch_no, product_code, test_parameters[], decision (Pass/Fail)
- Quality Inspection: inspection_type, sample_size, results[]

### Production
- Production Order: batch_no, product, planned_qty, actual_qty, status
- Batch: batch_no, manufacturing_date, expiry_date, lot_size

## Phase 1 Implementation (MVP)
1. Set up Frappe development environment
2. Create base app structure
3. Implement Core DocTypes (Company, Location, Item)
4. Implement Shipping module (Gate Pass, Delivery Order, BL)
5. Implement Transportation module (Weighment, Transport Order)
6. Basic Zoho integration setup (connection, authentication)

## Phase 2 Implementation
7. QC module (COA, Quality Inspection)
8. Production module (Batch, Production Order)
9. Security module (Gate Entry)
10. Advanced Zoho sync (invoices, items)
11. RBAC configuration
12. Reports and Dashboards

## Phase 3 Implementation
13. Advanced features (workflows, notifications)
14. Mobile-friendly UI optimization
15. Advanced reporting (custom reports)
16. Performance optimization
17. Testing and documentation

## Next Steps
1. Initialize Frappe bench and create app
2. Define DocTypes for Phase 1
3. Set up Zoho API credentials
4. Create basic UI layouts