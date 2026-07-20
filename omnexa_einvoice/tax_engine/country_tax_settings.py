# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Tax settings resolver — Branch-first (like Egypt ETA), legacy Country Tax Settings fallback."""

from __future__ import annotations

import frappe

from omnexa_einvoice.tax_engine.branch_intl_tax import branch_intl_tax_as_settings, get_password_from_branch
from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code


def get_country_tax_settings(
	company: str,
	country_code: str,
	branch: str | None = None,
) -> frappe._dict | None:
	"""
	Resolve plugin-country tax settings.
	Priority: Branch intl_* fields → legacy Country Tax Settings (company + country).
	"""
	country_code = (country_code or "").strip().upper()
	if not country_code or country_code in ("EG", "SA"):
		return None

	if branch and frappe.db.exists("Branch", branch):
		branch_doc = frappe.get_doc("Branch", branch)
		if normalize_country_code(branch_doc.country_code) == country_code:
			settings = branch_intl_tax_as_settings(branch_doc)
			if settings:
				return settings

	company = (company or "").strip()
	if not company:
		return None
	if not frappe.db.exists("DocType", "Country Tax Settings"):
		return None
	name = frappe.db.get_value(
		"Country Tax Settings",
		{"company": company, "country_code": country_code, "enabled": 1
	},
		"name",
	)
	if not name:
		return None
	return frappe.get_doc("Country Tax Settings", name).as_dict()


def get_settings_password(settings: frappe._dict, fieldname: str) -> str:
	"""Read secret from Branch or Country Tax Settings row."""
	if not settings:
		return ""
	if settings.get("_from_branch") and settings.get("name"):
		branch_field = {
			"client_secret": "intl_tax_client_secret",
			"asp_api_key": "intl_tax_asp_api_key"
	}.get(fieldname, fieldname)
		return get_password_from_branch(settings.name, branch_field)
	if settings.get("name") and frappe.db.exists("Country Tax Settings", settings.name):
		try:
			return frappe.get_doc("Country Tax Settings", settings.name).get_password(
				fieldname, raise_exception=False
			) or ""
		except Exception:
			return ""
	return ""
