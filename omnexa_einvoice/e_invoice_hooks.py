# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Document hooks: optional e-invoice gate on Sales Invoice (off by default per company profile)."""

from __future__ import annotations

import frappe
from frappe import _


def sales_invoice_before_submit(doc, method=None) -> None:
	"""Block Sales Invoice submit when company policy requires a dispatched e-invoice submission."""
	if getattr(doc.flags, "ignore_e_invoice_requirement", False):
		return
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	if doc.doctype != "Sales Invoice":
		return
	if not doc.get("company"):
		return
	if not frappe.db.exists("DocType", "Tax Authority Profile"):
		return
	need = frappe.db.get_value(
		"Tax Authority Profile",
		{"company": doc.company},
		"require_e_invoice_for_sales_invoice",
	)
	if not need:
		return
	ok = frappe.db.exists(
		"E Invoice Submission",
		{
			"reference_doctype": "Sales Invoice",
			"reference_name": doc.name,
			"status": ["in", ["Queued", "Completed"]],
		},
	)
	if ok:
		return
	frappe.throw(
		_(
			"Company policy requires an e-invoice submission for this Sales Invoice. "
			"Create an E Invoice Submission linked to this document, dispatch it, then submit again."
		)
	)
