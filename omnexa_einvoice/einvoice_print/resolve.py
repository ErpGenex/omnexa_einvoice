# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Resolve Print Format name per country / Sales Invoice."""

from __future__ import annotations

import frappe
from frappe import _

from omnexa_einvoice.einvoice_print.design_catalog import get_print_design
from omnexa_einvoice.einvoice_print.context import _branch_country


PRINT_FORMAT_PREFIX = "E-Invoice — "


def print_format_name_for_country(country_code: str) -> str:
	code = (country_code or "EG").strip().upper()
	design = get_print_design(code)
	label = design.label_en
	return f"{PRINT_FORMAT_PREFIX}{label} ({code})"


@frappe.whitelist()
def get_print_format_for_sales_invoice(docname: str) -> str:
	"""Return installed Print Format name for this invoice's branch country."""
	if not frappe.db.exists("Sales Invoice", docname):
		frappe.throw(_("Sales Invoice {0} not found.").format(docname))
	doc = frappe.get_doc("Sales Invoice", docname)
	code = _branch_country(doc)
	name = print_format_name_for_country(code)
	if frappe.db.exists("Print Format", name):
		return name
	# fallback generic
	fallback = f"{PRINT_FORMAT_PREFIX}Auto"
	if frappe.db.exists("Print Format", fallback):
		return fallback
	return name
