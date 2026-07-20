# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA settings stored on Branch (Saudi branches) — mirrors ZATCA Company Settings field names."""

from __future__ import annotations

import frappe
from frappe import _

# Branch field -> ZATCA settings dict key (same keys as ZATCA Company Settings doctype)
ZATCA_BRANCH_FIELDS: dict[str, str] = {
	"enabled": "zatca_enabled",
	"zatca_phase": "zatca_phase",
	"zatca_environment": "zatca_environment",
	"vat_registration_number": "zatca_vat_registration_number",
	"organization_name": "zatca_organization_name",
	"organization_name_ar": "zatca_organization_name_ar",
	"street": "zatca_street",
	"building_number": "zatca_building_number",
	"city": "zatca_city",
	"district": "zatca_district",
	"postal_code": "zatca_postal_code",
	"csr_invoice_type": "zatca_csr_invoice_type",
	"egs_serial_number": "zatca_egs_serial_number",
	"organization_unit_name": "zatca_organization_unit_name",
	"csr_common_name": "zatca_csr_common_name",
	"industry_business_category": "zatca_industry_business_category",
	"location_address": "zatca_location_address",
	"csr_pem": "zatca_csr_pem",
	"standard_invoice_validated": "zatca_standard_invoice_validated",
	"simplified_invoice_validated": "zatca_simplified_invoice_validated",
	"compliance_validated": "zatca_compliance_validated",
	"certificate_pem": "zatca_certificate_pem",
	"public_key_pem": "zatca_public_key_pem",
	"compliance_request_id": "zatca_compliance_request_id",
	"icv_counter": "zatca_icv_counter",
	"last_invoice_hash": "zatca_last_invoice_hash",
}

ZATCA_PASSWORD_FIELDS = (
	"private_key",
	"compliance_security_token",
	"compliance_secret",
	"production_security_token",
	"production_secret",
)


def branch_has_zatca(branch: str) -> bool:
	return bool(frappe.db.get_value("Branch", branch, "zatca_enabled"))


def branch_to_zatca_settings(branch: str) -> frappe._dict:
	"""Build ZATCA settings dict from Branch document."""
	if not branch:
		frappe.throw(_("Branch is required for ZATCA."), title=_("ZATCA"))
	doc = frappe.get_doc("Branch", branch)
	if (doc.country_code or "").upper() != "SA":
		frappe.throw(_("Branch {0} is not a Saudi (SA) branch.").format(branch), title=_("ZATCA"))
	if not doc.get("zatca_enabled"):
		frappe.throw(_("Enable ZATCA on Branch → Saudi ZATCA tab."), title=_("ZATCA"))

	out: dict = {"name": doc.name, "company": doc.company, "doctype": "Branch", "_from_branch": True}
	for zatca_key, branch_field in ZATCA_BRANCH_FIELDS.items():
		out[zatca_key] = doc.get(branch_field)
	out["country_code"] = "SA"

	for pwd_field in ZATCA_PASSWORD_FIELDS:
		branch_pwd = f"zatca_{pwd_field}"
		out[pwd_field] = doc.get_password(branch_pwd, raise_exception=False) or ""

	return frappe._dict(out)


def update_branch_chain(branch: str, icv: int, invoice_hash_hex: str) -> None:
	frappe.db.set_value(
		"Branch",
		branch,
		{"zatca_icv_counter": icv, "zatca_last_invoice_hash": invoice_hash_hex},
		update_modified=True,
	)
