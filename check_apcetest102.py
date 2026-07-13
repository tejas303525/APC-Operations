import frappe

frappe.init(site="apc.local")
frappe.connect()

# Check the Delivery Order
do = frappe.db.get_value("Delivery Order", "APCETEST102", [
    "name", "job_order", "operational_status", "do_status",
    "docstatus", "loading_delivery_note", "third_party_loading",
    "commercial_movement", "pre_check_clearance", "sent_to_security_on",
    "truck_arrived_on"
], as_dict=True)

if do:
    print("=== DELIVERY ORDER ===")
    for k, v in do.items():
        print(f"  {k}: {v}")

    # Check Pre-Check Clearance
    pcc_name = do.get("pre_check_clearance")
    if not pcc_name:
        pcc_name = frappe.db.get_value("Pre-Check Clearance", {"delivery_order": "APCETEST102"}, "name")

    if pcc_name:
        pcc = frappe.db.get_value("Pre-Check Clearance", pcc_name, [
            "name", "qc_status", "overall_status", "security_status", "qc_pre_check_status"
        ], as_dict=True)
        print("\n=== PRE-CHECK CLEARANCE ===")
        for k, v in pcc.items():
            print(f"  {k}: {v}")
    else:
        print("\n=== PRE-CHECK CLEARANCE: NOT FOUND ===")

    # Check LDN
    ldn_name = do.get("loading_delivery_note")
    if not ldn_name:
        ldn_name = frappe.db.get_value("Loading Delivery Note", {"transport_delivery_order": "APCETEST102"}, "name")

    if ldn_name:
        ldn = frappe.db.get_value("Loading Delivery Note", ldn_name, [
            "name", "dispatch_confirmed", "final_qc_clearance", "qc_manager_approved", "security_final_check", "status"
        ], as_dict=True)
        print("\n=== LOADING DELIVERY NOTE ===")
        for k, v in ldn.items():
            print(f"  {k}: {v}")
    else:
        print("\n=== LOADING DELIVERY NOTE: NOT FOUND ===")

    # Check SDDN
    if do.get("job_order"):
        sddn = frappe.db.get_value("Security Draft Delivery Note", {"job_order": do["job_order"]}, [
            "name", "security_status", "status", "docstatus"
        ], as_dict=True)
        print("\n=== SECURITY DRAFT DN ===")
        if sddn:
            for k, v in sddn.items():
                print(f"  {k}: {v}")
        else:
            print("  NOT FOUND")

else:
    print("APCETEST102 not found as Delivery Order")
    # Try other doctypes
    for dt in ["Job Order", "Shipping Booking", "Transport Schedule", "Security Inspection"]:
        r = frappe.db.exists(dt, "APCETEST102")
        if r:
            print(f"Found in {dt}: {r}")

frappe.destroy()
