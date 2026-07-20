# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Install per-country e-invoice Print Formats for Sales Invoice."""

from __future__ import annotations

from pathlib import Path

import frappe

from omnexa_einvoice.einvoice_print.design_catalog import all_country_codes_for_print, get_print_design
from omnexa_einvoice.einvoice_print.resolve import PRINT_FORMAT_PREFIX, print_format_name_for_country


def _load_template_html() -> str:
	path = Path(__file__).resolve().parents[1] / "einvoice_print" / "templates" / "sales_invoice_einvoice.html"
	return path.read_text(encoding="utf-8")


def _ensure_print_format(name: str, html: str, *, default_language: str = "en") -> None:
	if frappe.db.exists("Print Format", name):
		frappe.db.set_value(
			"Print Format",
			name,
			{
				"html": html,
				"custom_format": 1,
				"print_format_type": "Jinja",
				"disabled": 0,
				"standard": "Yes",
				"default_print_language": default_language
	},
			update_modified=True,
		)
		return
	doc = frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": "Sales Invoice",
			"module": "Omnexa Einvoice",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"standard": "Yes",
			"disabled": 0,
			"default_print_language": default_language,
			"html": html
	}
	)
	doc.insert(ignore_permissions=True)


def execute():
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	html = _load_template_html()
	for code in all_country_codes_for_print():
		name = print_format_name_for_country(code)
		design = get_print_design(code)
		lang = "ar" if design.rtl else "en"
		_ensure_print_format(name, html, default_language=lang)

	# Generic fallback when country format missing
	_ensure_print_format(f"{PRINT_FORMAT_PREFIX}Auto", html)
