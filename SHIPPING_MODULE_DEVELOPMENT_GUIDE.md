# Shipping Module Development Guide

This guide explains how to make changes to the Shipping module UI and functionality.

---

## Table of Contents
1. [Modifying DocTypes (Fields)](#1-modifying-doctypes-fields)
2. [Modifying Workspace UI](#2-modifying-workspace-ui)
3. [Adding Business Logic (Python)](#3-adding-business-logic-python)
4. [Adding Client Scripts (JavaScript)](#4-adding-client-scripts-javascript)
5. [Adding Print Formats](#5-adding-print-formats)
6. [Adding Reports](#6-adding-reports)
7. [Testing Changes](#7-testing-changes)

---

## 1. Modifying DocTypes (Fields)

### Method A: Using Frappe Desk UI (Easiest for simple changes)

1. **Login** to Desk (http://apc.local:8000)
2. Go to **Settings** → **DocType** → Search for your DocType (e.g., "Gate Pass")
3. Click on the DocType to edit
4. Modify fields in the "Fields" table
5. **Save** and **Migrate**

```bash
source env/bin/activate
bench --site apc.local migrate
```

### Method B: Editing JSON Files (Recommended for complex changes)

**File Location:**
```
apps/apc_operations/apc_operations/shipping/doctype/gate_pass/gate_pass.json
```

**Example: Adding a new field**

```json
{
  "fieldname": "new_field_name",
  "fieldtype": "Data",
  "label": "New Field Label",
  "reqd": 0,
  "description": "Help text for users"
}
```

**Common Field Types:**
| Field Type | Use For | Example Values |
|------------|---------|----------------|
| Data | Text input | "Vehicle Number" |
| Date | Date picker | "Posting Date" |
| Select | Dropdown | "status": "Draft\nSubmitted\nDelivered" |
| Link | Reference to another DocType | "customer": "Customer" |
| Table | Child table | "items": "Gate Pass Item" |
| Check | Boolean checkbox | "is_export": 0/1 |
| Currency | Money amounts | "freight_amount" |
| Float | Decimal numbers | "weight_kg" |
| Int | Whole numbers | "package_count" |
| Text Editor | Rich text | "remarks" |

**After editing JSON, run:**
```bash
source env/bin/activate
bench --site apc.local migrate
```

---

## 2. Modifying Workspace UI

### File Location:
```
apps/apc_operations/apc_operations/shipping/workspace/shipping/shipping.json
```

### Adding a New Shortcut (Colored Tile)

```json
{
  "color": "Red",
  "doc_view": "List",
  "label": "Overdue Shipments",
  "link_to": "Gate Pass",
  "stats_filter": "[[\"Gate Pass\",\"status\",\"=\",\"In Transit\"]]",
  "type": "DocType"
}
```

**Available Colors:** Blue, Green, Orange, Red, Yellow, Purple, Cyan, Pink

### Adding a New Quick Link

```json
{
  "label": "Print Gate Pass",
  "name": "Gate Pass",
  "type": "List"  // Options: New, List, Report
}
```

### Adding a New Link Section

```json
{
  "hidden": 0,
  "is_query_report": 0,
  "label": "Analytics",
  "link_count": 2,
  "link_type": "DocType",
  "onboard": 0,
  "type": "Card Break"
},
{
  "description": "View shipping trends",
  "hidden": 0,
  "is_query_report": 0,
  "label": "Shipping Trends",
  "link_count": 0,
  "link_to": "Gate Pass",
  "link_type": "DocType",
  "onboard": 0,
  "type": "Link"
}
```

**After changes:**
```bash
bench --site apc.local migrate
bench --site apc.local clear-cache
```

---

## 3. Adding Business Logic (Python)

### Controller Methods

**File Location:**
```
apps/apc_operations/apc_operations/shipping/doctype/gate_pass/gate_pass.py
```

**Example: Adding custom validation**

```python
import frappe
from frappe.model.document import Document

class GatePass(Document):
    
    def validate(self):
        """Called before save"""
        # Validate vehicle number format
        if self.vehicle_no and len(self.vehicle_no) < 3:
            frappe.throw("Vehicle number must be at least 3 characters")
        
        # Auto-calculate total weight
        self.calculate_totals()
    
    def before_submit(self):
        """Called before submission"""
        # Set status automatically
        if self.gate_pass_type == "Out":
            self.status = "In Transit"
        
        # Log activity
        frappe.logger().info(f"Gate Pass {self.name} submitted")
    
    def calculate_totals(self):
        """Custom method to calculate totals"""
        total_weight = 0
        for item in self.items:
            if item.gross_weight:
                total_weight += item.gross_weight
        
        self.total_gross_weight = total_weight
    
    @frappe.whitelist()
    def mark_as_delivered(self):
        """Custom API method callable from client"""
        self.status = "Delivered"
        self.save()
        frappe.msgprint(f"Gate Pass {self.name} marked as delivered")
        return {"status": "success"}
```

**Available Hooks:**
| Method | When Called |
|--------|-------------|
| `validate()` | Before save |
| `before_save()` | Before saving document |
| `after_save()` | After saving document |
| `before_submit()` | Before submitting |
| `on_submit()` | After submitting |
| `before_cancel()` | Before cancelling |
| `on_cancel()` | After cancelling |
| `on_trash()` | When deleting |
| `after_insert()` | After first save |

---

### Creating API Methods

**File:** `apps/apc_operations/apc_operations/shipping/api.py`

```python
import frappe
from frappe import _

@frappe.whitelist()
def get_open_gate_passes():
    """Get all open gate passes"""
    return frappe.get_all(
        "Gate Pass",
        filters={"status": ["in", ["Submitted", "In Transit"]]},
        fields=["name", "vehicle_no", "driver_name", "status", "posting_date"]
    )

@frappe.whitelist()
def update_status(gate_pass_name, new_status):
    """Update gate pass status"""
    doc = frappe.get_doc("Gate Pass", gate_pass_name)
    doc.status = new_status
    doc.save()
    frappe.db.commit()
    return {"message": f"Status updated to {new_status}"}

@frappe.whitelist()
def get_shipping_dashboard_stats():
    """Get stats for dashboard"""
    return {
        "open_gate_passes": frappe.db.count("Gate Pass", {"status": "Submitted"}),
        "in_transit": frappe.db.count("Gate Pass", {"status": "In Transit"}),
        "delivered_today": frappe.db.count("Gate Pass", {
            "status": "Delivered",
            "modified": [">=", frappe.utils.today()]
        })
    }
```

**Call from browser console:**
```javascript
frappe.call({
    method: 'apc_operations.shipping.api.get_open_gate_passes',
    callback: function(r) {
        console.log(r.message);
    }
});
```

---

## 4. Adding Client Scripts (JavaScript)

### File Location:
```
apps/apc_operations/apc_operations/shipping/doctype/gate_pass/gate_pass.js
```

**Example: Gate Pass Customizations**

```javascript
frappe.ui.form.on('Gate Pass', {
    // Run when form loads
    refresh: function(frm) {
        // Add custom button
        frm.add_custom_button(__('Mark as Delivered'), function() {
            frappe.confirm('Are you sure?', () => {
                frappe.call({
                    method: 'mark_as_delivered',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frm.reload_doc();
                        }
                    }
                });
            });
        }, __('Actions'));
        
        // Show/hide fields based on type
        if (frm.doc.gate_pass_type === 'In') {
            frm.set_df_property('bill_of_lading', 'hidden', 1);
        }
    },
    
    // Run when gate_pass_type changes
    gate_pass_type: function(frm) {
        if (frm.doc.gate_pass_type === 'Out') {
            frm.set_value('status', 'Submitted');
            frappe.show_alert('Gate Pass set for exit');
        }
    },
    
    // Run when customer is selected
    customer: function(frm) {
        if (frm.doc.customer) {
            // Fetch customer details
            frappe.db.get_doc('Customer', frm.doc.customer)
                .then(doc => {
                    frm.set_value('customer_name', doc.customer_name);
                });
        }
    }
});

// Child table events
frappe.ui.form.on('Gate Pass Item', {
    item_code: function(frm, cdt, cdn) {
        // Auto-fill item details
        var row = locals[cdt][cdn];
        if (row.item_code) {
            frappe.db.get_value('Item', row.item_code, ['item_name', 'stock_uom'])
                .then(r => {
                    frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
                    frappe.model.set_value(cdt, cdn, 'uom', r.message.stock_uom);
                });
        }
    },
    
    gross_weight: function(frm, cdt, cdn) {
        // Auto-calculate totals
        calculate_total_weight(frm);
    }
});

function calculate_total_weight(frm) {
    var total = 0;
    frm.doc.items.forEach(function(row) {
        total += row.gross_weight || 0;
    });
    frm.set_value('total_gross_weight', total);
}
```

**Create the JS file:**
```bash
# Create the file if it doesn't exist
touch apps/apc_operations/apc_operations/shipping/doctype/gate_pass/gate_pass.js
```

**After changes, rebuild:**
```bash
bench --site apc.local build
```

---

## 5. Adding Print Formats

### Method A: Using Desk UI

1. Go to **Settings** → **Print Format**
2. Click **New**
3. Select DocType: "Gate Pass"
4. Design using the HTML editor

### Method B: Creating Print Format File

**Directory:**
```
apps/apc_operations/apc_operations/shipping/print_format/
```

**Create folder and files:**
```bash
mkdir -p apps/apc_operations/apc_operations/shipping/print_format/gate_pass_print
touch apps/apc_operations/apc_operations/shipping/print_format/gate_pass_print/__init__.py
touch apps/apc_operations/apc_operations/shipping/print_format/gate_pass_print/gate_pass_print.json
```

**JSON File:**
```json
{
 "absolute_value": 0,
 "align_labels_right": 0,
 "creation": "2026-04-26 20:00:00.000000",
 "css": "@media print {\n  .page-break { page-break-after: always; }\n}",
 "custom_format": 1,
 "default_print_language": "en",
 "disabled": 0,
 "doc_type": "Gate Pass",
 "docstatus": 0,
 "doctype": "Print Format",
 "font": "Default",
 "format_data": "",
 "html": "<div class=\"gate-pass-print\">\n  <h2>ASIA PETRO-CHEMICALS</h2>\n  <h3>GATE PASS</h3>\n  <hr>\n  <table class=\"info-table\">\n    <tr>\n      <td><strong>Gate Pass No:</strong></td>\n      <td>{{ doc.name }}</td>\n      <td><strong>Date:</strong></td>\n      <td>{{ frappe.format(doc.posting_date) }}</td>\n    </tr>\n    <tr>\n      <td><strong>Type:</strong></td>\n      <td>{{ doc.gate_pass_type }}</td>\n      <td><strong>Status:</strong></td>\n      <td>{{ doc.status }}</td>\n    </tr>\n    <tr>\n      <td><strong>Vehicle:</strong></td>\n      <td>{{ doc.vehicle_no }}</td>\n      <td><strong>Driver:</strong></td>\n      <td>{{ doc.driver_name }}</td>\n    </tr>\n  </table>\n  <hr>\n  <table class=\"items-table\">\n    <thead>\n      <tr>\n        <th>Item</th>\n        <th>Qty</th>\n        <th>Weight</th>\n      </tr>\n    </thead>\n    <tbody>\n      {% for item in doc.items %}\n      <tr>\n        <td>{{ item.item_name }}</td>\n        <td>{{ item.qty }} {{ item.uom }}</td>\n        <td>{{ item.gross_weight }} kg</td>\n      </tr>\n      {% endfor %}\n    </tbody>\n  </table>\n  <hr>\n  <div class=\"signatures\">\n    <table style=\"width: 100%;\">\n      <tr>\n        <td style=\"text-align: center;\">\n          <br><br><br>\n          _______________________<br>\n          Prepared By\n        </td>\n        <td style=\"text-align: center;\">\n          <br><br><br>\n          _______________________<br>\n          Security Officer\n        </td>\n        <td style=\"text-align: center;\">\n          <br><br><br>\n          _______________________<br>\n          Authorized By\n        </td>\n      </tr>\n    </table>\n  </div>\n</div>",
 "line_breaks": 0,
 "margin_bottom": 15.0,
 "margin_left": 15.0,
 "margin_right": 15.0,
 "margin_top": 15.0,
 "modified": "2026-04-26 20:00:00.000000",
 "modified_by": "Administrator",
 "module": "Shipping",
 "name": "Gate Pass Print",
 "owner": "Administrator",
 "page_number": "Hide",
 "print_format_builder": 0,
 "print_format_type": "Jinja",
 "raw_printing": 0,
 "show_section_headings": 0,
 "standard": "Yes"
}
```

**Then migrate:**
```bash
bench --site apc.local migrate
```

---

## 6. Adding Reports

### Method A: Script Report (Python + JS)

**Create Python file:**
```bash
mkdir -p apps/apc_operations/apc_operations/shipping/report/shipping_activity
touch apps/apc_operations/apc_operations/shipping/report/__init__.py
touch apps/apc_operations/apc_operations/shipping/report/shipping_activity/__init__.py
touch apps/apc_operations/apc_operations/shipping/report/shipping_activity/shipping_activity.py
touch apps/apc_operations/apc_operations/shipping/report/shipping_activity/shipping_activity.js
```

**Python (shipping_activity.py):**
```python
import frappe
from frappe import _

def execute(filters=None):
    columns = [
        {"label": _("Gate Pass"), "fieldname": "name", "fieldtype": "Link", "options": "Gate Pass", "width": 120},
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": _("Type"), "fieldname": "gate_pass_type", "fieldtype": "Data", "width": 80},
        {"label": _("Vehicle"), "fieldname": "vehicle_no", "fieldtype": "Data", "width": 120},
        {"label": _("Driver"), "fieldname": "driver_name", "fieldtype": "Data", "width": 150},
        {"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
    ]
    
    data = frappe.get_all(
        "Gate Pass",
        filters=filters or {},
        fields=["name", "posting_date", "gate_pass_type", "vehicle_no", "driver_name", "customer_name", "status"],
        order_by="posting_date desc"
    )
    
    return columns, data
```

**JavaScript (shipping_activity.js):**
```javascript
frappe.query_reports["Shipping Activity"] = {
    "filters": [
        {
            "fieldname": "gate_pass_type",
            "label": __("Gate Pass Type"),
            "fieldtype": "Select",
            "options": "\nIn\nOut",
            "default": ""
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nDraft\nSubmitted\nIn Transit\nDelivered\nCancelled",
            "default": ""
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        }
    ]
};
```

---

## 7. Testing Changes

### Local Development Workflow

```bash
# 1. Make code changes
# Edit your files...

# 2. Clear cache
source env/bin/activate
bench --site apc.local clear-cache

# 3. Migrate database (if DocType/JSON changed)
bench --site apc.local migrate

# 4. Rebuild assets (if JS/CSS changed)
bench --site apc.local build

# 5. Restart bench (if running)
# Press Ctrl+C to stop, then:
bench start
```

### Debugging Tips

**Check Python errors:**
```bash
tail -f logs/frappe.log
```

**Check browser console:**
- Press F12 → Console tab

**Enable developer mode:**
```bash
# Set developer mode in site config
bench --site apc.local set-config developer_mode 1
```

**Check DocType in database:**
```sql
-- MariaDB
SELECT * FROM tabDocField WHERE parent='Gate Pass';
```

---

## Quick Reference Commands

```bash
# Start development server
bench start

# Access site console
bench --site apc.local console

# Run tests
bench --site apc.local run-tests --app apc_operations

# Backup site
bench --site apc.local backup

# Check installed apps
bench --site apc.local list-apps

# Tail logs
bench --site apc.local log

# Clear all caches
bench --site apc.local clear-cache
bench --site apc.local clear-website-cache
bench --site apc.local clear-all-cache
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-26
