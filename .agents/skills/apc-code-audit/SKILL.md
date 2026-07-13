---
name: apc-code-audit
description: Use this skill to audit the APC Operations Frappe/ERP codebase for bugs, broken workflows, missing links, unsafe assumptions, schema mismatches, print format issues, client/server drift, and production-readiness gaps. Trigger when the user asks for APC code audit, workflow audit, bug audit, security/QC/transport audit, delivery note audit, job order audit, or review before implementing changes.
---

# APC Code Audit Skill

You are auditing the APC Operations codebase. This is a Frappe/ERP-style operations system involving Job Orders, Transport Schedule, Shipping Booking, Security Inspection, QC, COA, Batch Allocation, Loading Delivery Note, Delivery Order, Zoho Books integration, print formats, and production/dispatch workflows.

## Primary rule

Audit first. Do not modify files unless the user explicitly asks to patch or implement fixes.

## Audit goals

Find real issues in the codebase, not theoretical problems. Prioritize bugs that can break operations, create wrong documents, lose customer/container data, miscalculate quantities/costs, or allow invalid workflow transitions.

## APC workflow areas to inspect

Focus on these modules and flows:

1. Job Order
   - Export/import job order handling.
   - Container type, container quantity, packaging profile, package quantity, planned quantity, gross/tare/net calculations.
   - Client-side JS recalculation vs server-side calculation.
   - Child table scripts not loaded or functions missing from the parent form.

2. Shipping / Transport
   - Shipping Booking to Transport Schedule mapping.
   - Container number and seal number propagation.
   - Vehicle, driver, transporter, dispatch, delivery status transitions.
   - Transport charges, fuel cost, additional charges, and total cost calculations.
   - Partial delivery booking flows.

3. Security
   - Security Inspection gate-in/gate-out flow.
   - Loading Entry rows.
   - Actual loaded quantity and actual package/unit count.
   - Whether Delivery Note can be issued only after required security loading data exists.
   - Truck/container release controls.

4. QC / COA / Batch
   - Batch creation and approval assumptions.
   - COA generation, QC manager approval, test parameter min/max/specification behavior.
   - Dispatch QC checks.
   - Whether approved batches are required before allocation/loading.
   - Print format data accuracy.

5. Delivery Note / Delivery Order / Loading DN
   - Difference between operational Delivery Order and accounting Delivery Note.
   - Draft Loading DN, final Loading DN, and Delivery Order print formats.
   - Whether print formats pull the correct linked fields.
   - Whether document naming and status flow is clear.

6. Zoho Books integration
   - GET/POST/PUT integration correctness.
   - Customer, invoice, delivery note, COA, and item sync risks.
   - Idempotency, duplicate prevention, error logging, and retry behavior.

7. Frappe correctness
   - Whitelisted methods and permission checks.
   - DocType field names vs code references.
   - Hooks, client scripts, custom scripts, patches, fixtures, and migrations.
   - Server/client mismatch.
   - Missing imports, wrong method paths, circular dependencies.
   - Use of `frappe.db.get_value`, `frappe.get_doc`, `frappe.db.exists`, and transaction boundaries.
   - Validation logic in `validate`, `before_save`, `on_submit`, `on_cancel`, and custom API methods.

## Required audit method

Follow this sequence:

1. Identify repo structure
   - Find app name, module layout, hooks, doctypes, public JS, print formats, patches, and tests.
   - Summarize the relevant files before judging.

2. Map the workflow
   - Build a short document flow from Job Order to Booking to Security/QC to Delivery Note/Delivery Order/Zoho.
   - Mention which DocTypes and methods participate.

3. Check field contracts
   - Compare field names used in Python, JS, print formats, and JSON responses.
   - Flag any field referenced in code but missing from DocType JSON.
   - Flag any DocType field that exists but is never populated.

4. Check calculations
   - Verify package quantity, net weight, tare weight, gross weight, total cost, currency, loaded quantity, and variance calculations.
   - Look for recalculation happening only on client side when it should also be enforced server side.

5. Check workflow guards
   - Verify invalid transitions are blocked.
   - Check whether documents can be submitted with missing container, seal, QC, batch, loading, or package count data.
   - Check partial delivery and cancellation paths.

6. Check UI and print formats
   - Verify JS files are actually loaded.
   - Verify child table handlers are available on parent forms.
   - Verify print formats pull data from the correct linked document.
   - Flag styling issues only after data correctness issues.

7. Check tests and migration safety
   - Identify existing tests.
   - Recommend exact tests to add.
   - Mention if patches are needed for existing records.

## Output format

Return the audit in this structure:

# APC Code Audit Report

## Executive Summary
- Overall risk: Low / Medium / High / Critical
- Main operational risk
- Main technical risk
- Whether code changes are recommended now

## Workflow Map
Explain the current flow in plain English.

## Findings

For each finding use:

### Finding N: Short title
- Severity: Critical / High / Medium / Low
- Area: Job Order / Shipping / Security / QC / Batch / Zoho / Print Format / Frappe / Tests
- Files involved:
  - `path/to/file.py`
  - `path/to/file.js`
- What is wrong:
- Why it matters operationally:
- Evidence from code:
- Recommended fix:
- Suggested test:

## Missing Data / Unknowns
List anything that could not be verified from the repo.

## Safe Fix Plan
Group fixes into:
1. No-risk fixes
2. Medium-risk fixes
3. Needs business confirmation

## Test Plan
Give exact commands or Frappe tests to run.

## Final Recommendation
Say whether to patch now, investigate further, or create a phased plan.

## Important behavior rules

- Do not invent files, fields, or methods.
- If a field or method cannot be found, say it was not found.
- Prefer exact file paths and function names.
- Do not recommend broad rewrites unless the current design is clearly broken.
- For each issue, explain the business impact in APC operations terms.
- If asked to patch, make the smallest safe change first.
- After patching, summarize changed files and how to verify.
