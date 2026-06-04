# APC Operations System - Setup Documentation

## Overview
This document describes the implementation of the APC Operations System on Frappe Framework v15.

**Date Created:** 2026-04-26  
**App Version:** 0.0.1  
**Frappe Version:** 15.106.0  
**Site:** apc.local

---

## 1. App Structure Created

### Directory Structure
```
apps/apc_operations/
├── apc_operations/
│   ├── __init__.py
│   ├── hooks.py
│   ├── modules.txt              # Contains: Shipping
│   ├── patches.txt
│   ├── pyproject.toml
│   ├── README.md
│   ├── config/
│   ├── public/
│   ├── templates/
│   ├── www/
│   └── shipping/
│       ├── __init__.py
│       ├── doctype/
│       │   ├── __init__.py
│       │   ├── bill_of_lading/
│       │   │   ├── __init__.py
│       │   │   ├── bill_of_lading.json
│       │   │   └── bill_of_lading.py
│       │   ├── container_detail/
│       │   │   ├── __init__.py
│       │   │   ├── container_detail.json
│       │   │   └── container_detail.py
│       │   ├── delivery_order/
│       │   │   ├── __init__.py
│       │   │   ├── delivery_order.json
│       │   │   └── delivery_order.py
│       │   ├── delivery_order_item/
│       │   │   ├── __init__.py
│       │   │   ├── delivery_order_item.json
│       │   │   └── delivery_order_item.py
│       │   ├── gate_pass/
│       │   │   ├── __init__.py
│       │   │   ├── gate_pass.json
│       │   │   └── gate_pass.py
│       │   └── gate_pass_item/
│       │       ├── __init__.py
│       │       ├── gate_pass_item.json
│       │       └── gate_pass_item.py
│       ├── number_card/
│       │   ├── open_gate_passes/
│       │   │   └── open_gate_passes.json
│       │   ├── pending_delivery_orders/
│       │   │   └── pending_delivery_orders.json
│       │   └── shipments_in_transit/
│       │       └── shipments_in_transit.json
│       └── workspace/
│           └── shipping/
│               └── shipping.json
└── requirements.txt
```

---

## 2. DocTypes Created

### 2.1 Gate Pass (Document)
**Module:** Shipping  
**Type:** Submittable Document  
**Naming Series:** GPOUT-.YYYY.- / GPIN-.YYYY.-

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| naming_series | Select | Yes | Series for auto-numbering |
| gate_pass_type | Select (In/Out) | Yes | Entry or Exit |
| posting_date | Date | Yes | Date of gate pass |
| posting_time | Time | No | Time of gate pass |
| company | Link (Company) | Yes | Company reference |
| vehicle_no | Data | Yes | Vehicle number |
| driver_name | Data | No | Driver name |
| driver_phone | Data | No | Driver phone |
| customer | Link (Customer) | No | Customer reference |
| customer_name | Data (fetch) | No | Auto-fetched customer name |
| delivery_order | Link (Delivery Order) | No | Linked delivery order |
| bill_of_lading | Link (Bill of Lading) | No | Linked BL |
| items | Table (Gate Pass Item) | No | Items in this gate pass |
| status | Select (Draft/Submitted/In Transit/Delivered/Cancelled) | Yes | Current status |

**Permissions:**
- System Manager: Full access (Create, Read, Write, Delete, Submit)
- Shipping Coordinator: Full access
- All: Read only

---

### 2.2 Delivery Order (Document)
**Module:** Shipping  
**Type:** Submittable Document  
**Naming Series:** DO-.YYYY.-

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| naming_series | Select | Yes | Series for auto-numbering |
| customer | Link (Customer) | Yes | Customer |
| customer_name | Data (fetch) | No | Auto-fetched name |
| posting_date | Date | Yes | Order date |
| company | Link (Company) | Yes | Company |
| shipping_address | Link (Address) | No | Delivery address |
| shipping_address_name | Small Text (fetch) | No | Address details |
| destination | Data | No | Destination city/location |
| port_of_loading | Data | No | POL for exports |
| port_of_discharge | Data | No | POD for exports |
| items | Table (Delivery Order Item) | Yes | Items to deliver |
| total_qty | Float (read-only) | No | Auto-calculated |
| total_net_weight | Float (read-only) | No | Auto-calculated |
| total_gross_weight | Float (read-only) | No | Auto-calculated |
| status | Select | Yes | Document status |
| remarks | Text Editor | No | Additional notes |

**Permissions:** Same as Gate Pass

---

### 2.3 Bill of Lading (Document)
**Module:** Shipping  
**Type:** Submittable Document  
**Naming Series:** BL-.YYYY.-

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| naming_series | Select | Yes | Series for auto-numbering |
| bl_number | Data | Yes | Actual BL number from carrier |
| bl_date | Date | Yes | BL issue date |
| company | Link (Company) | Yes | Company |
| delivery_order | Link (Delivery Order) | No | Reference to DO |
| shipper | Link (Customer) | Yes | Shipper party |
| shipper_address | Small Text | No | Shipper address |
| consignee | Data | Yes | Consignee name |
| notify_party | Data | No | Notify party |
| vessel_name | Data | No | Vessel name |
| voyage_number | Data | No | Voyage number |
| port_of_loading | Data | Yes | POL |
| port_of_discharge | Data | Yes | POD |
| place_of_delivery | Data | No | Final delivery place |
| container_details | Table (Container Detail) | No | Container information |
| total_packages | Int (read-only) | No | Total packages |
| total_net_weight | Float (read-only) | No | Total net weight |
| total_gross_weight | Float (read-only) | No | Total gross weight |
| total_cbm | Float (read-only) | No | Total volume |
| marks_and_nos | Text | No | Marks & numbers |
| description_of_goods | Text Editor | No | Cargo description |
| freight_terms | Select (Prepaid/Collect/Third Party) | No | Freight terms |
| freight_amount | Currency | No | Freight cost |
| status | Select (Draft/Submitted/In Transit/Arrived/Delivered/Cancelled) | Yes | Shipment status |
| remarks | Text Editor | No | Notes |

**Permissions:** Same as Gate Pass

---

### 2.4 Child Table DocTypes

#### Gate Pass Item (Table)
| Field | Type | Required |
|-------|------|----------|
| item_code | Link (Item) | Yes |
| item_name | Data (fetch) | No |
| description | Text Editor | No |
| qty | Float | Yes |
| uom | Link (UOM) | Yes |
| net_weight | Float | No |
| gross_weight | Float | No |
| remarks | Data | No |

#### Delivery Order Item (Table)
Same as Gate Pass Item + `no_of_packages` (Int)

#### Container Detail (Table)
| Field | Type | Required |
|-------|------|----------|
| container_number | Data | Yes |
| container_type | Select | Yes |
| seal_number | Data | No |
| no_of_packages | Int | No |
| net_weight | Float | No |
| gross_weight | Float | No |
| cbm | Float | No |

**Container Type Options:**
- 20' GP
- 20' HC
- 40' GP
- 40' HC
- 45' HC

---

## 3. Workspace Created

**File:** `apc_operations/shipping/workspace/shipping/shipping.json`

### Workspace Configuration
| Property | Value |
|----------|-------|
| Name | Shipping |
| Title | Shipping |
| Label | Shipping |
| Module | Shipping |
| Icon | shipping |
| Public | Yes |
| Is Hidden | No |
| Sequence ID | 1.0 |

### Shortcuts (Colored Tiles)
| Label | Link To | Color | View |
|-------|---------|-------|------|
| Gate Pass | Gate Pass | Blue | List |
| Delivery Order | Delivery Order | Green | List |
| Bill of Lading | Bill of Lading | Orange | List |
| View All Shipments | Gate Pass | Cyan | List |

### Quick Links
| Label | DocType | Type |
|-------|---------|------|
| New Gate Pass | Gate Pass | New |
| New Delivery Order | Delivery Order | New |
| New Bill of Lading | Bill of Lading | New |

### Links Section
**Documents:**
- Gate Pass (with onboarding)
- Delivery Order (with onboarding)
- Bill of Lading (with onboarding)

**Reports:**
- Shipping Activity
- Container Tracking

**Masters:**
- Customer

### Roles
- System Manager
- Shipping Coordinator
- All

---

## 4. Number Cards Created

| Name | DocType | Filter | Color |
|------|---------|--------|-------|
| Open Gate Passes | Gate Pass | status = Submitted | Green (#29CD42) |
| Pending Delivery Orders | Delivery Order | status = Submitted | Purple (#761ACB) |
| Shipments in Transit | Bill of Lading | status = In Transit | Red (#CB2929) |

**Function:** Count  
**Show Percentage Stats:** Yes  
**Stats Time Interval:** Daily

---

## 5. Database Configuration

### Module Def
- **Name:** Shipping
- **App Name:** apc_operations
- **Module Name:** Shipping

### Installed Apps (apps.txt)
```
frappe
apc_operations
```

### Site Config (sites/apc.local/site_config.json)
```json
{
  "db_name": "_f1147d3c17448983",
  "db_password": "***",
  "db_type": "mariadb",
  "developer": 1
}
```

---

## 6. Known Issues & Fixes

### Issue 1: KeyError: 'type' in Workspace
**Error:** `KeyError: 'type'` when loading Shipping workspace

**Cause:** The `content` field in workspace JSON had cards without a `"type"` key.

**Fix Applied:**
1. Changed content from card definitions to empty array: `"content": "[]"`
2. Updated database: `UPDATE tabWorkspace SET content='[]' WHERE name='Shipping';`
3. Cleared all caches

### Issue 2: Workspace Not Visible
**Possible Causes:**
1. Browser cache still has old format
2. Redis cache not cleared
3. Workspace permissions issue

**Troubleshooting Steps:**
```bash
# 1. Clear site cache
source env/bin/activate
bench --site apc.local clear-cache

# 2. Clear website cache
bench --site apc.local clear-website-cache

# 3. Rebuild assets
bench --site apc.local build

# 4. Clear browser cache (Browser DevTools → Application → Clear Storage)
```

---

## 7. How to Access the Shipping Module

### Method 1: Direct URL
Navigate to: `http://apc.local:8000/app/shipping`

### Method 2: From Desk
1. Login to Frappe Desk
2. Look for "Shipping" in the left sidebar (icon: 🚢)
3. Click to open the workspace

### Method 3: Search
1. Use the search bar (Ctrl+K)
2. Type "Gate Pass", "Delivery Order", or "Bill of Lading"

---

## 8. Next Steps (Phase 1 Continuation)

### Transportation Module (Pending)
DocTypes to create:
- Vehicle Master
- Driver Master
- Transport Order
- Weighment/Weight Bridge
- Trip Sheet
- Fuel Log

### Zoho Integration Setup (Pending)
- OAuth 2.0 configuration
- API credentials setup
- Initial sync tests

---

## 9. Commands Reference

### Install/Reinstall App
```bash
source env/bin/activate
bench --site apc.local install-app apc_operations --force
```

### Migrate Database
```bash
bench --site apc.local migrate
```

### Clear Caches
```bash
bench --site apc.local clear-cache
bench --site apc.local clear-website-cache
```

### Rebuild Assets
```bash
bench --site apc.local build
```

### Start Development Server
```bash
bench start
```

---

## 10. File Locations Summary

| Component | File Path |
|-----------|-----------|
| App Config | `apps/apc_operations/pyproject.toml` |
| Hooks | `apps/apc_operations/apc_operations/hooks.py` |
| Gate Pass DocType | `apps/apc_operations/apc_operations/shipping/doctype/gate_pass/gate_pass.json` |
| Delivery Order DocType | `apps/apc_operations/apc_operations/shipping/doctype/delivery_order/delivery_order.json` |
| Bill of Lading DocType | `apps/apc_operations/apc_operations/shipping/doctype/bill_of_lading/bill_of_lading.json` |
| Workspace | `apps/apc_operations/apc_operations/shipping/workspace/shipping/shipping.json` |
| Number Cards | `apps/apc_operations/apc_operations/shipping/number_card/*` |

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-26
