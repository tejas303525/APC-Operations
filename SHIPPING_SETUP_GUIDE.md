# Shipping + Transportation Module Setup Instructions

## Overview
This module provides a complete shipping workflow: J.O → Freight Container → DG/NDG → Vessel Booking → CRO Details → Auto Generate Transportation → Payables tracking

## Installation

### 1. Install the App
```bash
cd /home/it/Project/APC_Operations/frappe-bench
bench --site [your-site-name] install-app apc_operations
```

### 2. Migrate Database
```bash
bench --site [your-site-name] migrate
```

### 3. Create Required Roles
```bash
bench --site [your-site-name] execute "apc_operations.setup.create_roles"
```

## DocTypes Created

### Core Shipping DocTypes
1. **Vessel Booking** - Booking details with shipping line, container info, port details
2. **CRO Details** - Cargo Receipt Order with vessel details, charges
3. **Transport Schedule** - Auto-generated transport with pickup schedules
4. **Security Dispatch** - Auto-created dispatch for security department
5. **Shipping Line** - Master data for shipping lines
6. **Port** - Master data for ports

### Supporting DocTypes
- Delivery Order
- Gate Pass
- Bill of Lading
- Container Detail

## Automated Features

### When CRO is Saved:
1. ✅ Transport Schedule auto-generated (pickup 3 days before cutoff)
2. ✅ Security Dispatch created
3. ✅ Payables team notified
4. ✅ Status updates propagated to linked records

### Scheduled Jobs (Reminders):
- **Hourly**: Check upcoming cutoffs, pending pull outs, pending CROs, pending transport
- **Daily 8:00 AM**: Morning reminders
- **Daily 4:00 PM**: Evening reminders
- **Daily**: Daily summary email to managers

## Permission Setup

### Roles Required:
- **Shipping Manager**: Full access to all shipping documents
- **Shipping User**: Create, read, update vessel bookings and CROs
- **Transportation Manager**: Full access to transport schedules
- **Transportation User**: Create, update transport schedules
- **Security Manager**: Access to security dispatches
- **Security User**: View security dispatches

### Assign Roles:
```bash
bench --site [your-site-name] execute "frappe.core.doctype.user.user.add_role" --args="['user@example.com', 'Shipping Manager']"
```

## Dashboard Cards

### Number Cards (Today's Actions):
1. Pending CROs
2. Pending Pull Outs (within 3 days)
3. Upcoming Cutoffs (within 7 days)
4. Pending Transport
5. Open Gate Passes
6. DG Pending Approval

### Action Buttons:
- Book Vessel
- Enter CRO Details
- Generate Transport
- View Shipments

## API Endpoints

### Dashboard Data
```javascript
frappe.call({
    method: 'apc_operations.shipping.api.get_dashboard_data',
    callback: (r) => { console.log(r.message); }
});
```

### Create Transport from CRO
```javascript
frappe.call({
    method: 'apc_operations.shipping.doctype.cro_details.cro_details.create_transport_from_cro',
    args: { cro_name: 'CRO-2026-00001' },
    callback: (r) => { console.log(r.message); }
});
```

### Get Shipment Timeline
```javascript
frappe.call({
    method: 'apc_operations.shipping.api.get_shipment_timeline',
    args: { shipment_name: 'VB-2026-00001' },
    callback: (r) => { console.log(r.message); }
});
```

### Bulk Generate Transport
```javascript
frappe.call({
    method: 'apc_operations.shipping.api.bulk_generate_transport',
    args: { cro_list: JSON.stringify(['CRO-2026-00001', 'CRO-2026-00002']) },
    callback: (r) => { console.log(r.message); }
});
```

### Quick Create Vessel Booking
```javascript
frappe.call({
    method: 'apc_operations.shipping.api.quick_create_vessel_booking',
    args: {
        data: {
            shipping_line: 'Maersk',
            vessel_name: 'Vessel XYZ',
            container_type: '40FT Standard',
            container_count: 2,
            port_of_loading: 'Singapore',
            port_of_discharge: 'Rotterdam',
            cargo_description: 'Test Cargo',
            cargo_weight: 25.5,
            vessel_date: '2026-05-15',
            cutoff_date: '2026-05-12',
            pull_out_date: '2026-05-09',
            freight_rate: 1500,
            currency: 'USD'
        }
    },
    callback: (r) => { console.log(r.message); }
});
```

## Field Reference

### Vessel Booking Fields:
| Field | Type | Required |
|-------|------|----------|
| shipping_line | Link(Shipping Line) | Yes |
| container_type | Select | Yes |
| container_count | Int | Yes |
| port_of_loading | Link(Port) | Yes |
| port_of_discharge | Link(Port) | Yes |
| cargo_description | Small Text | Yes |
| cargo_weight | Float | Yes |
| is_dangerous_goods | Check | No |
| vessel_name | Data | Yes |
| vessel_date | Date | Yes |
| cutoff_date | Date | Yes |
| pull_out_date | Date | Yes |
| freight_rate | Currency | Yes |
| thc | Currency | No |
| tluc | Currency | No |
| export_declaration | Currency | No |

### CRO Details Fields:
| Field | Type | Required |
|-------|------|----------|
| cro_number | Data | Yes (unique) |
| vessel_booking | Link(Vessel Booking) | Auto |
| shipping_line | Link(Shipping Line) | Auto |
| vessel_name | Data | Auto |
| cro_status | Select | Auto |
| transport_status | Select | Auto |
| linked_transport | Link(Transport Schedule) | Auto |

## Validation Rules

1. Cutoff date cannot be after vessel date (ETD)
2. Pull out date cannot be after cutoff date
3. Scheduled pickup must be before cutoff date
4. CRO Number must be unique
5. Transport must be completed before submission

## Testing

### Run Tests
```bash
bench --site [your-site-name] run-tests --app apc_operations --module shipping
```

### Verify Installation
```bash
bench --site [your-site-name] execute "frappe.get_doc('DocType', 'Vessel Booking').name"
```

## Troubleshooting

### Issue: DocTypes not visible
```bash
bench --site [your-site-name] reload-doc apc_operations shipping
bench --site [your-site-name] clear-cache
```

### Issue: Number cards not showing
```bash
bench --site [your-site-name] execute "frappe.clear_cache()"
```

### Issue: Scheduled jobs not running
```bash
bench --site [your-site-name] enable-scheduler
bench restart
```

## File Structure
```
apc_operations/
├── apc_operations/
│   ├── hooks.py
│   ├── modules.txt
│   ├── shipping/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── reminders.py
│   │   ├── notifications.py
│   │   ├── permissions.py
│   │   ├── jinja_filters.py
│   │   ├── cro_events.py
│   │   ├── transport_events.py
│   │   ├── vessel_events.py
│   │   ├── gate_pass_events.py
│   │   ├── doctype/
│   │   │   ├── vessel_booking/
│   │   │   ├── cro_details/
│   │   │   ├── transport_schedule/
│   │   │   ├── security_dispatch/
│   │   │   ├── shipping_line/
│   │   │   ├── port/
│   │   │   ├── ...
│   │   ├── workspace/
│   │   │   └── shipping/
│   │   │       └── shipping.json
│   │   ├── number_card/
│   │   │   ├── pending_cros/
│   │   │   ├── pending_pull_outs/
│   │   │   ├── upcoming_cutoffs/
│   │   │   ├── pending_transport/
│   │   │   ├── open_gate_passes/
│   │   │   └── dg_pending_approval/
│   │   └── public/
│   │       └── js/
│   │           ├── shipping_dashboard.js
│   │           ├── vessel_booking.js
│   │           ├── cro_details.js
│   │           └── transport_schedule.js
```

## Support
For issues or enhancements, contact the development team.
