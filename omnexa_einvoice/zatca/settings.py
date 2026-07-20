# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Resolve ZATCA Company Settings — no Egypt imports."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def get_company_settings(company: str, branch: str | None = None) -> frappe._dict:
	"""ZATCA settings: Branch (SA tab) first, then legacy ZATCA Company Settings."""
	if branch:
		from omnexa_einvoice.zatca.branch_settings import branch_has_zatca, branch_to_zatca_settings

		if branch_has_zatca(branch):
			return branch_to_zatca_settings(branch)

	company = (company or "").strip()
	if not company:
		frappe.throw(_("Company is required for ZATCA."), title=_("ZATCA"))
	name = frappe.db.get_value("ZATCA Company Settings", {"company": company}, "name")
	if not name:
		frappe.throw(
			_("ZATCA Company Settings not found for {0}. Create settings under ZATCA workspace.").format(
				company
			),
			title=_("ZATCA"),
		)
	doc = frappe.get_doc("ZATCA Company Settings", name)
	if not doc.enabled:
		frappe.throw(_("ZATCA is not enabled for company {0}.").format(company), title=_("ZATCA"))
	return frappe._dict(doc.as_dict())


def get_private_key_pem(settings: frappe._dict) -> str:
	if settings.get("_from_branch"):
		key = settings.get("private_key") or ""
		if not key and settings.name:
			key = frappe.get_doc("Branch", settings.name).get_password("zatca_private_key", raise_exception=False) or ""
		if key:
			return key
	key = settings.get_password("private_key", raise_exception=False) if hasattr(settings, "get_password") else ""
	if not key and isinstance(settings, dict) and not settings.get("_from_branch"):
		doc = frappe.get_doc("ZATCA Company Settings", settings.name)
		key = doc.get_password("private_key", raise_exception=False)
	if not key:
		frappe.throw(_("ZATCA private key missing. Run CSR / onboarding."), title=_("ZATCA"))
	return key


def get_production_auth(settings: frappe._dict) -> tuple[str, str]:
	if settings.get("_from_branch"):
		doc = frappe.get_doc("Branch", settings.name)
		token = doc.get_password("zatca_production_security_token", raise_exception=False)
		secret = doc.get_password("zatca_production_secret", raise_exception=False)
	else:
		doc = frappe.get_doc("ZATCA Company Settings", settings.name)
		token = doc.get_password("production_security_token", raise_exception=False)
		secret = doc.get_password("production_secret", raise_exception=False)
	if not token or not secret:
		frappe.throw(_("Production CSID token/secret missing on ZATCA Company Settings."), title=_("ZATCA"))
	return token, secret


def get_compliance_auth(settings: frappe._dict) -> tuple[str, str]:
	if settings.get("_from_branch"):
		doc = frappe.get_doc("Branch", settings.name)
		token = doc.get_password("zatca_compliance_security_token", raise_exception=False)
		secret = doc.get_password("zatca_compliance_secret", raise_exception=False)
	else:
		doc = frappe.get_doc("ZATCA Company Settings", settings.name)
		token = doc.get_password("compliance_security_token", raise_exception=False)
		secret = doc.get_password("compliance_secret", raise_exception=False)
	if not token or not secret:
		frappe.throw(_("Compliance CSID token/secret missing."), title=_("ZATCA"))
	return token, secret


def next_icv_and_pih(settings: frappe._dict) -> tuple[int, str]:
	if settings.get("_from_branch"):
		doc = frappe.get_doc("Branch", settings.name)
		icv = int(doc.zatca_icv_counter or 0) + 1
		pih = (doc.zatca_last_invoice_hash or "").strip()
	else:
		doc = frappe.get_doc("ZATCA Company Settings", settings.name)
		icv = int(doc.icv_counter or 0) + 1
		pih = (doc.last_invoice_hash or "").strip()
	return icv, pih


def update_chain(settings: frappe._dict, icv: int, invoice_hash_hex: str) -> None:
	if settings.get("_from_branch"):
		from omnexa_einvoice.zatca.branch_settings import update_branch_chain

		update_branch_chain(settings.name, icv, invoice_hash_hex)
		return
	frappe.db.set_value(
		"ZATCA Company Settings",
		settings.name,
		{"icv_counter": icv, "last_invoice_hash": invoice_hash_hex},
		update_modified=True,
	)


def settings_to_seller_dict(settings: frappe._dict) -> dict[str, Any]:
	return {
		"name": settings.organization_name,
		"name_ar": settings.organization_name_ar,
		"vat_registration": settings.vat_registration_number,
		"street": settings.street,
		"building": settings.building_number,
		"city": settings.city,
		"district": settings.district,
		"postal_code": settings.postal_code,
		"country": settings.country_code or "SA",
	}
