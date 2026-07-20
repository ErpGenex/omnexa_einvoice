# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""High-level ZATCA submission API (whitelisted)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.zatca.dispatch import process_zatca_hub_request
from omnexa_einvoice.zatca.phase1.service import run_phase1
from omnexa_einvoice.zatca.phase2.service import run_phase2


@frappe.whitelist()
def process_zatca_invoice(
	reference_name: str,
	document_type: str = "tax_invoice",
	phase: str = "phase1",
	company: str | None = None,
	branch: str | None = None,
	csid_reference: str | None = None,
	document_json: str | None = None,
) -> dict[str, Any]:
	"""Process a ZATCA invoice without modifying Sales Invoice DocType."""
	payload: dict[str, Any] = {
		"reference_name": reference_name,
		"document_type": document_type,
		"phase": phase,
		"company": company or frappe.defaults.get_user_default("Company"),
		"branch": branch,
		"csid_reference": csid_reference,
	}
	if document_json:
		payload["document"] = frappe.parse_json(document_json)
	if phase == "phase1":
		return run_phase1(payload)
	if phase == "phase2":
		return run_phase2(payload, sync=bool(frappe.form_dict.get("sync")))
	result = process_zatca_hub_request(payload)
	return {"ok": True, "hub": result.as_dict() if hasattr(result, "as_dict") else result}
