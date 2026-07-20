# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
Compliance invoice checks after Compliance CSID (reference: ComplianceCSID.validate_zatca_compliance_csid).
Runs Phase 1 sample invoices and posts them to the compliance invoice API.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.zatca.constants import DOCUMENT_SIMPLIFIED_INVOICE, DOCUMENT_TAX_INVOICE
from omnexa_einvoice.zatca.phase1.service import run_phase1
from omnexa_einvoice.zatca.phase2.api_client import submit_compliance_invoice_api
from omnexa_einvoice.zatca.phase2.constants import ENVIRONMENT_PORTALS
from omnexa_einvoice.zatca.phase2.payload import build_invoice_api_payload
from omnexa_einvoice.zatca.settings import get_compliance_auth


def _submit_compliance_sample(settings, document_type: str, reference: str) -> tuple[bool, str | None]:
	phase1 = run_phase1(
		{
			"company": settings.company,
			"reference_name": reference,
			"document_type": document_type,
			"taxpayer_registration_id": settings.vat_registration_number,
			"seller_name": settings.organization_name,
			"seller_name_ar": settings.organization_name_ar
	}
	)
	signed_xml = phase1.get("signed_xml") or ""
	payload = build_invoice_api_payload(
		signed_xml=signed_xml,
		uuid=phase1.get("uuid"),
		invoice_hash_b64=phase1.get("hash_b64"),
	)
	portal = ENVIRONMENT_PORTALS.get(settings.zatca_environment or "sandbox", "developer-portal")
	token, secret = get_compliance_auth(settings)
	status, body = submit_compliance_invoice_api(portal, payload, token, secret)
	if status in (200, 202):
		return True, payload.get("invoiceHash")
	if status == 406:
		# Already submitted — treat as success (reference behaviour)
		return True, payload.get("invoiceHash")
	return False, None


@frappe.whitelist()
def validate_compliance_invoices(settings_name: str) -> dict[str, Any]:
	"""Validate standard + simplified samples against ZATCA compliance API."""
	doc = frappe.get_doc("ZATCA Company Settings", settings_name)
	settings = frappe._dict(doc.as_dict())
	invoice_type = (doc.csr_invoice_type or "1100").strip()
	results: dict[str, bool] = {}

	if invoice_type in ("1100", "1000"):
		ref = f"ZATCA-COMP-STD-{doc.company}"
		ok, _ = _submit_compliance_sample(settings, DOCUMENT_TAX_INVOICE, ref)
		results["standard_invoice"] = ok
		doc.standard_invoice_validated = 1 if ok else 0

	if invoice_type in ("1100", "0100"):
		ref = f"ZATCA-COMP-SIM-{doc.company}"
		ok, _ = _submit_compliance_sample(settings, DOCUMENT_SIMPLIFIED_INVOICE, ref)
		results["simplified_invoice"] = ok
		doc.simplified_invoice_validated = 1 if ok else 0

	doc.compliance_validated = 1 if all(results.values()) else 0
	doc.save(ignore_permissions=True)

	if not all(results.values()):
		frappe.throw(
			_("Compliance validation incomplete: {0}").format(results),
			title=_("ZATCA Compliance"),
		)
	return {"ok": True, "results": results
	}
