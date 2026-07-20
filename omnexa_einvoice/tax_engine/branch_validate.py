# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Branch.validate — sync tax_provider from country_code (does not touch ETA credentials)."""

from __future__ import annotations

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import (
	branch_country_label_for_code,
	country_display_name,
	normalize_country_code,
)
from omnexa_einvoice.tax_engine.plugin.tier_gate import validate_branch_intl_production_flags
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name


def validate_branch_tax_country(doc, method=None) -> None:
	"""Keep tax_provider aligned with country_code; warn if ETA enabled on non-Egypt branch."""
	code = normalize_country_code(doc.get("country_code"))
	if not code:
		code = "EG"
	if doc.meta.has_field("country_iso"):
		doc.country_iso = code
	doc.country_code = branch_country_label_for_code(code)

	if doc.meta.has_field("country_name"):
		doc.country_name = country_display_name(code)

	provider = resolve_adapter_name(code)

	if doc.meta.has_field("tax_provider"):
		doc.tax_provider = provider

	validate_branch_intl_production_flags(doc)

	if code != "EG":
		if int(doc.get("eta_einvoice_enabled") or 0) or int(doc.get("eta_ereceipt_enabled") or 0):
			doc.eta_einvoice_enabled = 0
			doc.eta_ereceipt_enabled = 0
			frappe.msgprint(
				_(
					"Egypt ETA was turned off because Country is {0}. "
					"Use the national provider ({1}) instead."
				).format(code, provider),
				indicator="orange",
				title=_("Tax country"),
			)
