import frappe
from frappe.model.sync import get_doc_files
import os

frappe.init(site="apc.local", sites_path=".")
frappe.connect()

folder = "/home/it/Project/APC_Operations/frappe-bench/apps/apc_operations/apc_operations/dispatch"
files = get_doc_files([], folder)
print("Files found in dispatch folder:")
for f in files:
    print(f)
