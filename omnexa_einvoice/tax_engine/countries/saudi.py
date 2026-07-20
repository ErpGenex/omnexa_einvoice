# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Saudi Arabia ZATCA — isolated under ``omnexa_einvoice.zatca``."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.zatca.constants import DOCUMENT_SIMPLIFIED_INVOICE, DOCUMENT_TAX_INVOICE
from omnexa_einvoice.zatca.dispatch import process_zatca_hub_request
from omnexa_einvoice.zatca.phase1.service import run_phase1
from omnexa_einvoice.zatca.phase2.service import run_phase2


def dispatch_zatca_for_sales_invoice(
	doc,
	*,
	branch: str | None = None,
	phase: str = "phase1",
	document_type: str | None = None,
) -> dict[str, Any]:
	"""Run ZATCA for a Sales Invoice on a Saudi branch (no Sales Invoice hooks)."""
	company = doc.company
	if branch:
		from omnexa_einvoice.zatca.branch_settings import branch_has_zatca

		if not branch_has_zatca(branch):
			frappe.throw(
				_("Enable ZATCA on Branch → Saudi ZATCA tab for branch {0}.").format(branch),
				title=_("ZATCA"),
			)
	else:
		settings_name = frappe.db.get_value(
			"ZATCA Company Settings", {"company": company, "enabled": 1}, "name"
		)
		if not settings_name:
			frappe.throw(
				_("Enable ZATCA on Branch → Saudi ZATCA tab, or ZATCA Company Settings for {0}.").format(
					company
				),
				title=_("ZATCA"),
			)

	doc_type = document_type or DOCUMENT_TAX_INVOICE
	payload = {
		"reference_name": doc.name,
		"document_type": doc_type,
		"phase": phase,
		"company": company,
		"branch": branch,
	}
	if phase == "phase1":
		return run_phase1(payload)
	if phase == "phase2":
		return run_phase2(payload, sync=bool(frappe.form_dict.get("sync")))
	result = process_zatca_hub_request(payload)
	return {"ok": True, "result": result.as_dict() if hasattr(result, "as_dict") else result}


def map_customer_type_to_document_type(customer_type: str | None) -> str:
	"""B2B → tax_invoice, B2C → simplified (reference: clearence_util)."""
	if (customer_type or "").strip() == "Individual":
		return DOCUMENT_SIMPLIFIED_INVOICE
	return DOCUMENT_TAX_INVOICE
