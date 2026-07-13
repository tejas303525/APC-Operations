 # APC Operations Claude Instructions

  This repository is the APC Operations Frappe application.

  ## Working rules

  - Do not make code changes unless explicitly asked.
  - For audit tasks, use the `apc-code-audit` skill.
  - Always inspect both server-side Python and client-side JavaScript before deciding root cause.
  - Always check DocType JSON fields before assuming a field exists.
  - Always check print formats when the issue involves Delivery Note, Delivery Order, COA, or Loading DN.
  - Prefer small patches over rewrites.
  - Mention migration or patch requirements if a change affects existing records.

  ## Common APC areas

  Important flows:
  - Job Order
  - Shipping Booking
  - Transport Schedule
  - Security Inspection
  - Loading Delivery Note
  - Delivery Order
  - Delivery Note
  - QC / COA
  - Batch Allocation
  - Zoho Books sync

  ## Review expectations
  - Exact files inspected
  - Exact broken field/method references
  - Business impact
  Claude Skills
  In Claude, skills are added as a separate package, not by putting them in AGENTS.md.
