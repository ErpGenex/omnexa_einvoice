# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Document hooks: optional e-invoice gate on Sales Invoice (off by default per company profile)."""

from __future__ import annotations

import frappe
from frappe import _

from omnexa_einvoice.branch_eta import branch_requires_einvoice_before_submit, resolve_branch_for_document
from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
	ensure_submission_for_document,
)
from omnexa_einvoice.sales_invoice_eta import ETA_BILLING_EINVOICE, get_eta_billing_type, sales_invoice_is_eta_billing


def sales_invoice_before_submit(doc, method=None) -> None:
	"""Block Sales Invoice submit when branch policy requires e-invoice submission."""
	if getattr(doc.flags, "ignore_e_invoice_requirement", False):
		return
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	if doc.doctype != "Sales Invoice":
		return
	if not doc.get("company"):
		return
	branch = resolve_branch_for_document(doc)
	if get_eta_billing_type(doc) != ETA_BILLING_EINVOICE:
		return
	if not branch or not branch_requires_einvoice_before_submit(branch):
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
			"Branch policy requires an e-invoice for this Sales Invoice. "
			"Open E Invoice Submission, prepare/sign, send to ETA, then submit again."
		)
	)


def sales_invoice_on_submit(doc, method=None) -> None:
	"""Auto-create E Invoice Submission when billing type is ETA."""
	if doc.doctype != "Sales Invoice":
		return
	if not sales_invoice_is_eta_billing(doc):
		return
	ensure_submission_for_document("Sales Invoice", doc.name)


def pos_invoice_on_submit(doc, method=None) -> None:
	"""Auto-create review queue row for ETA e-receipt."""
	if doc.doctype != "POS Invoice":
		return
	ensure_submission_for_document("POS Invoice", doc.name)
