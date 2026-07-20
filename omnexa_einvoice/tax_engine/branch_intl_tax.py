# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""International e-invoice settings on Branch (same pattern as Egypt ETA on Branch)."""

from __future__ import annotations

import frappe

from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code

INTL_DEPENDS = "eval:doc.country_code && !['EG','SA'].includes(doc.country_code)"
INTL_ENABLED_DEPENDS = "eval:doc.country_code && !['EG','SA'].includes(doc.country_code) && doc.intl_tax_enabled"
UAE_DEPENDS = "eval:doc.country_code=='AE' && doc.intl_tax_enabled"


def branch_intl_tax_as_settings(branch_doc) -> frappe._dict | None:
	"""Map Branch intl_* fields to Country Tax Settings-shaped dict for the plugin pipeline."""
	code = normalize_country_code(branch_doc.country_code) if branch_doc else ""
	if not branch_doc or code in ("EG", "SA"):
		return None
	if not int(branch_doc.get("intl_tax_enabled") or 0):
		return None
	return frappe._dict(
		{
			"name": branch_doc.name,
			"doctype": "Branch",
			"_from_branch": True,
			"company": branch_doc.company,
			"country_code": code,
			"enabled": 1,
			"live_production": int(branch_doc.get("intl_tax_live_production") or 0),
			"auto_submit_on_si_submit": int(branch_doc.get("intl_tax_auto_submit_on_si_submit") or 0),
			"api_environment": branch_doc.get("intl_tax_api_environment") or "sandbox",
			"api_base_url": branch_doc.get("intl_tax_api_base_url") or "",
			"tax_registration_number": branch_doc.get("intl_tax_registration_number") or "",
			"tax_authority_name": branch_doc.get("intl_tax_authority_name") or "",
			"signing_mode": branch_doc.get("intl_tax_signing_mode") or "scaffold",
			"client_id": branch_doc.get("intl_tax_client_id") or "",
			"configuration_json": branch_doc.get("intl_tax_configuration_json") or "",
			"remarks": branch_doc.get("intl_tax_remarks") or "",
			"uae_seller_tin": branch_doc.get("intl_uae_seller_tin") or "",
			"uae_peppol_sender_id": branch_doc.get("intl_uae_peppol_sender_id") or "",
			"uae_peppol_receiver_id": branch_doc.get("intl_uae_peppol_receiver_id") or "",
			"uae_legal_name_ar": branch_doc.get("intl_uae_legal_name_ar") or "",
			"uae_invoice_type_code": branch_doc.get("intl_uae_invoice_type_code") or "380",
			"uae_asp_submit_path": branch_doc.get("intl_uae_asp_submit_path") or "/einvoice/v1/submit"
	}
	)


def get_password_from_branch(branch: str, fieldname: str) -> str:
	if not branch or not fieldname:
		return ""
	try:
		return (frappe.get_doc("Branch", branch).get_password(fieldname, raise_exception=False) or "").strip()
	except Exception:
		return ""
