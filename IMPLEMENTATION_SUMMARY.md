# Shipping + Transportation Workflow - Complete Implementation Summary

## Production-Ready Shipping Module for Frappe/ERPNext

---

## 1. Required DocTypes Created

### Core Shipping DocTypes (with JSON + Python)

| DocType | Python File | JSON File |
|---------|-------------|-----------|
| Vessel Booking | vessel_booking.py | vessel_booking.json |
| CRO Details | cro_details.py | cro_details.json |
| Transport Schedule | transport_schedule.py | transport_schedule.json |
| Security Dispatch | security_dispatch.py | security_dispatch.json |
| Shipping Line | shipping_line.py | shipping_line.json |
| Port | port.py | port.json |

### Existing DocTypes (enhanced)
- Delivery Order
- Gate Pass
- Bill of Lading
- Container Detail
- Gate Pass Item
- Delivery Order Item

---

## 2. Exact Field Names (Vessel Booking)

```
# Booking Details Section
- shipping_line (Link: Shipping Line) [Required]
- container_type (Select: 20FT/40FT/etc) [Required]
- container_count (Int) [Required]
- port_of_loading (Link: Port) [Required]
- port_of_discharge (Link: Port) [Required]

# Cargo Details Section
- cargo_description (Small Text) [Required]
- cargo_weight (Float, MT) [Required]
- is_dangerous_goods (Check)
- dg_class (Select: Class 1-9) [Conditional]
- un_number (Data) [Conditional]
- notes (Text Editor)

# Vessel Details Section
- vessel_name (Data) [Required]
- vessel_date (Date, ETD) [Required]
- cutoff_date (Date) [Required]
- pull_out_date (Date) [Required]
- si_cutoff (Date)
- gate_in_date (Date)
- gate_cutoff (Date)
- vgm_cutoff (Date)

# Freight Charges Section
- freight_rate (Currency) [Required]
- currency (Link: Currency, default: USD) [Required]
- total_freight_charges (Currency, Read-only, Calculated)
- thc (Currency)
- tluc (Currency)
- export_declaration (Currency)

# Status Section
- booking_status (Select: Draft/Confirmed/Cancelled)
- cro_status (Select: Pending/Generated/Completed)
- transport_status (Select: Pending/Scheduled/In Progress/Completed)
```

---

## 3. Exact Field Names (CRO Details)

```
- vessel_booking (Link: Vessel Booking)
- cro_number (Data) [Required, Unique]
- cro_date (Date, default: Today)
- shipping_line (Link: Shipping Line)
- vessel_name (Data)
- vessel_date (Date)
- cutoff_date (Date)
- pull_out_date (Date)
- si_cutoff (Date)
- gate_in_date (Date)
- gate_cutoff (Date)
- vgm_cutoff (Date)
- container_count (Int)
- container_type (Data)
- cargo_description (Small Text)
- cargo_weight (Float)
- is_dangerous_goods (Check)
- freight_charges (Currency)
- thc (Currency)
- tluc (Currency)
- export_declaration (Currency)
- total_cost (Currency, Calculated)
- currency (Link: Currency)
- cro_status (Select: Draft/Pending/Generated/Completed)
- transport_status (Select: Pending/Scheduled/In Progress/Completed)
- linked_transport (Link: Transport Schedule)
- linked_dispatch (Link: Security Dispatch)
```

---

## 4. Exact Field Names (Transport Schedule)

```
- cro_details (Link: CRO Details)
- vessel_booking (Link: Vessel Booking)
- shipping_line (Link: Shipping Line)
- vessel_name (Data)
- vessel_date (Date)
- scheduled_pickup_date (Date) [Required]
- scheduled_delivery_date (Date)
- actual_pickup_date (Date)
- actual_delivery_date (Date)
- origin_location (Link: Warehouse)
- destination_location (Link: Warehouse)
- port_of_loading (Link: Port)
- pickup_address (Small Text)
- delivery_address (Small Text)
- transport_type (Select: Export/Import/Internal)
- container_count (Int)
- vehicle_assigned (Link: Vehicle)
- driver_name (Link: Employee)
- cutoff_date (Date)
- pull_out_date (Date)
- transport_status (Select: Pending/Scheduled/In Progress/Completed/Cancelled)
- transport_cost (Currency)
- fuel_cost (Currency)
- additional_charges (Currency)
- total_cost (Currency, Calculated)
- special_instructions (Text Editor)
- notes (Text Editor)
```

---

## 5. Child Tables - None Required

The workflow uses linked DocTypes instead of child tables for better visibility and separate workflows.

---

## 6. Custom Fields - None Required (Self-Contained)

All fields are defined in DocType JSON files. No additional custom fields needed.

---

## 7. Workspace Content JSON

**Location:** `apps/apc_operations/apc_operations/shipping/workspace/shipping/shipping.json`

**Features:**
- Header with title and description
- 4 Action Shortcut Buttons (Book Vessel, Enter CRO, Generate Transport, View Shipments)
- TODAY'S ACTIONS section with 6 Number Cards:
  - Pending CROs
  - Pending Pull Outs
  - Upcoming Cutoffs
  - Pending Transport
  - Open Gate Passes
  - DG Pending Approval
- Quick Links section with 3 Cards
- Navigation links for all DocTypes
- Role-based access (Shipping Manager, Shipping User, Transportation Manager)

---

## 8. Client Scripts

### shipping_dashboard.js
- Dashboard initialization
- Auto-refresh every 5 minutes
- Quick vessel booking dialog
- Bulk transport generation dialog
- Shipment timeline viewer
- Payables notification

### vessel_booking.js
- Form validation
- Auto-calculate totals
- Auto-set pull out date (3 days before cutoff)
- Action buttons (Create CRO, View Transport, Shipment Timeline)
- List view bulk actions
- Status indicators

### cro_details.js
- Vessel booking lookup with auto-fill
- Transport generation confirmation
- Security dispatch creation
- Payables notification trigger
- Cutoff date warnings
- List view bulk transport generation

### transport_schedule.js
- Driver/vehicle queries
- Transport status updates
- Gate pass viewing
- Driver notification
- List view filters for pending pickups

---

## 9. Python Backend Methods

### api.py
- `get_todays_actions()` - Get action counts for dashboard
- `get_dashboard_data()` - Full dashboard data
- `get_shipment_timeline(shipment_name)` - Complete shipment timeline
- `quick_create_vessel_booking(data)` - Quick vessel booking creation
- `bulk_generate_transport(cro_list)` - Bulk transport generation

### cro_details.py
- `CRODetails.generate_transportation()` - Auto-generate transport
- `CRODetails.create_security_dispatch()` - Auto-create security dispatch
- `CRODetails.notify_payables_team()` - Notify payables
- `CRODetails.calculate_pickup_date()` - Calculate pickup (3 days before cutoff)
- `get_pending_cros(days)` - Get pending CROs
- `get_cros_needing_transport()` - Get CROs without transport
- `create_transport_from_cro(cro_name)` - Manual trigger

### transport_schedule.py
- `TransportSchedule.validate_dates()` - Date validation
- `TransportSchedule.update_linked_records()` - Sync status
- `TransportSchedule.create_gate_passes()` - Auto-create gate passes
- `get_pending_transports(days)` - Get pending transports
- `update_transport_status(transport_name, status)` - Update status

### vessel_booking.py
- `VesselBooking.validate_dates()` - Date validation
- `VesselBooking.calculate_total_charges()` - Calculate freight
- `VesselBooking.create_cro_record()` - Auto-create CRO
- `get_upcoming_vessels(days)` - Get vessels with upcoming cutoffs
- `get_vessels_needing_pullout(days)` - Get vessels needing pull out

### security_dispatch.py
- `SecurityDispatch.on_update()` - Update handler
- `get_pending_dispatches()` - Get pending dispatches
- `mark_dispatched(dispatch_name)` - Mark as dispatched

---

## 10. hooks.py Entries

```python
scheduler_events = {
    "hourly": [
        "apc_operations.shipping.reminders.check_upcoming_cutoffs",
        "apc_operations.shipping.reminders.check_pending_pull_outs",
        "apc_operations.shipping.reminders.check_pending_cros",
        "apc_operations.shipping.reminders.check_pending_transport",
    ],
    "daily": [
        "apc_operations.shipping.reminders.send_daily_dashboard_summary",
    ],
    "cron": {
        "0 8 * * *": ["apc_operations.shipping.reminders.send_morning_reminders"],
        "0 16 * * *": ["apc_operations.shipping.reminders.send_evening_reminders"],
    }
}

doc_events = {
    "CRO Details": {
        "on_update": "apc_operations.shipping.cro_events.on_cro_update",
        "after_insert": "apc_operations.shipping.cro_events.on_cro_create",
    },
    "Transport Schedule": {
        "on_update": "apc_operations.shipping.transport_events.on_transport_update",
        "on_submit": "apc_operations.shipping.transport_events.on_transport_submit",
    },
    "Vessel Booking": {
        "on_update": "apc_operations.shipping.vessel_events.on_vessel_update",
        "on_submit": "apc_operations.shipping.vessel_events.on_vessel_submit",
    },
    "Gate Pass": {
        "on_update": "apc_operations.shipping.gate_pass_events.on_gate_pass_update",
    }
}

whitelisted_methods = {
    "get_todays_actions": "apc_operations.shipping.api.get_todays_actions",
    "get_dashboard_data": "apc_operations.shipping.api.get_dashboard_data",
    "create_transport_from_cro": "apc_operations.shipping.doctype.cro_details.cro_details.create_transport_from_cro",
    "update_transport_status": "apc_operations.shipping.doctype.transport_schedule.transport_schedule.update_transport_status",
}
```

---

## 11. Auto-Generation Logic for Transportation

### Trigger: When CRO is saved with CRO Number

**Code Location:** `cro_details.py` - `on_update()` method

```python
def on_update(self):
    if self.has_value_changed("cro_number") and self.cro_number:
        self.generate_transportation()
        self.create_security_dispatch()
        self.notify_payables_team()
        self.update_status("Generated")

def generate_transportation(self):
    pickup_date = self.calculate_pickup_date()  # 3 days before cutoff
    transport = frappe.new_doc("Transport Schedule")
    transport.cro_details = self.name
    transport.vessel_booking = self.vessel_booking
    transport.scheduled_pickup_date = pickup_date
    transport.transport_status = "Scheduled"
    transport.insert()

def calculate_pickup_date(self):
    if self.cutoff_date:
        return add_days(getdate(self.cutoff_date), -3)
    return today()
```

---

## 12. Reminder Automation Logic

**File:** `reminders.py`

### Hourly Jobs:
1. `check_upcoming_cutoffs()` - Vessels with cutoff in 3 days
2. `check_pending_pull_outs()` - Pull outs due in 2 days
3. `check_pending_cros()` - CROs pending for 1+ days
4. `check_pending_transport()` - Transport due within 1 day

### Daily Jobs:
- `send_daily_dashboard_summary()` - Summary to managers

### Cron Jobs:
- 8:00 AM: `send_morning_reminders()` - Morning action items
- 4:00 PM: `send_evening_reminders()` - Evening overdue summary

### Notification Methods:
- Email notifications to relevant users
- System notifications (Notification Log)
- SMS to drivers (if configured)

---

## 13. Permission Setup

**File:** `permissions.py`

### Roles:
- **Shipping Manager**: Full access to Vessel Booking, CRO, Transport
- **Shipping User**: Create/Update vessel bookings and CROs (own records)
- **Transportation Manager**: Full access to Transport Schedule
- **Transportation User**: Create/Update transport schedules
- **Security Manager**: Full access to Security Dispatch
- **Security User**: View Security Dispatch

### Permission Query Conditions:
```python
def get_vessel_booking_permission(user):
    # System Manager/Shipping Manager: Full access
    # Shipping User: Own records only
    # Transportation Manager: Non-cancelled records
```

---

## 14. Dashboard Card Setup

**Location:** `apps/apc_operations/apc_operations/shipping/number_card/`

### Number Cards Created:

| Card | Filter | Color |
|------|--------|-------|
| Pending CROs | cro_status in [Draft, Pending] | Default |
| Pending Pull Outs | pull_out_date in next 3 days, transport_status != Completed | Warning |
| Upcoming Cutoffs | cutoff_date in next 7 days | Warning |
| Pending Transport | transport_status in [Pending, Scheduled, In Progress] | Default |
| Open Gate Passes | status in [Draft, Open] | Success |
| DG Pending Approval | is_dangerous_goods=1, booking_status != Confirmed | Danger |

---

## 15. Bench Console Commands

### Install/Update:
```bash
# Install app
bench --site [site] install-app apc_operations

# Migrate database
bench --site [site] migrate

# Clear cache
bench --site [site] clear-cache

# Reload DocTypes
bench --site [site] reload-doctype Vessel Booking
bench --site [site] reload-doctype CRO Details
bench --site [site] reload-doctype Transport Schedule
```

### Run Scheduled Jobs Manually:
```bash
# Run hourly reminders
bench --site [site] execute apc_operations.shipping.reminders.check_upcoming_cutoffs
bench --site [site] execute apc_operations.shipping.reminders.check_pending_pull_outs

# Run daily summary
bench --site [site] execute apc_operations.shipping.reminders.send_daily_dashboard_summary
```

### Test API:
```bash
# Get dashboard data
bench --site [site] execute apc_operations.shipping.api.get_dashboard_data

# Get today's actions
bench --site [site] execute apc_operations.shipping.api.get_todays_actions
```

---

## File Summary

### Python Files (Backend):
1. `hooks.py` - Main configuration
2. `shipping/__init__.py`
3. `shipping/api.py` - API endpoints
4. `shipping/reminders.py` - Scheduled jobs
5. `shipping/notifications.py` - Email notifications
6. `shipping/permissions.py` - Permission rules
7. `shipping/jinja_filters.py` - Template filters
8. `shipping/cro_events.py` - CRO event handlers
9. `shipping/transport_events.py` - Transport event handlers
10. `shipping/vessel_events.py` - Vessel event handlers
11. `shipping/gate_pass_events.py` - Gate pass event handlers
12. `shipping/doctype/*/vessel_booking.py`
13. `shipping/doctype/*/cro_details.py`
14. `shipping/doctype/*/transport_schedule.py`
15. `shipping/doctype/*/security_dispatch.py`
16. `shipping/doctype/*/shipping_line.py`
17. `shipping/doctype/*/port.py`

### JSON Files (DocType definitions):
1. `shipping/doctype/*/vessel_booking.json`
2. `shipping/doctype/*/cro_details.json`
3. `shipping/doctype/*/transport_schedule.json`
4. `shipping/doctype/*/security_dispatch.json`
5. `shipping/doctype/*/shipping_line.json`
6. `shipping/doctype/*/port.json`

### JavaScript Files (Frontend):
1. `shipping/public/js/shipping_dashboard.js` - Dashboard
2. `shipping/public/js/vessel_booking.js` - Vessel Booking form
3. `shipping/public/js/cro_details.js` - CRO form
4. `shipping/public/js/transport_schedule.js` - Transport form

### Workspace/Number Cards:
1. `shipping/workspace/shipping/shipping.json` - Workspace
2. `shipping/number_card/pending_cros/pending_cros.json`
3. `shipping/number_card/pending_pull_outs/pending_pull_outs.json`
4. `shipping/number_card/upcoming_cutoffs/upcoming_cutoffs.json`
5. `shipping/number_card/pending_transport/pending_transport.json`
6. `shipping/number_card/open_gate_passes/open_gate_passes.json`
7. `shipping/number_card/dg_pending_approval/dg_pending_approval.json`

---

## Business Flow Implementation

```
J.O -> Freight Container -> DG/NDG -> Vessel Booking -> CRO Details -> Save CRO -> Auto Generate Transportation -> Payables

1. User creates Vessel Booking
2. Vessel Booking is submitted -> Auto-creates CRO Details (draft)
3. User enters CRO Number in CRO Details
4. On CRO Save -> Auto triggers:
   - Transport Schedule created (pickup 3 days before cutoff)
   - Security Dispatch created
   - Payables team notified via email
   - Status updates propagated
5. Transportation Manager processes Transport Schedule
6. Driver pickup -> Gate Passes auto-created
7. Delivery complete -> Status updated
```

---

## Ready to Deploy

All files are production-ready and deployable. Follow the setup instructions in `SHIPPING_SETUP_GUIDE.md`.
