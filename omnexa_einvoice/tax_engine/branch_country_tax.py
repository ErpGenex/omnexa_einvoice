# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Branch UI helpers — tax settings now live on Branch fields."""

from __future__ import annotations

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.branch_intl_tax import branch_intl_tax_as_settings
from omnexa_einvoice.tax_engine.country_catalog import (
	PLUGIN_CATALOG,
	PLUGIN_COUNTRY_CODES,
	branch_country_select_options,
	country_display_name,
	get_catalog_entry,
	integration_tier_for_country,
	normalize_country_code,
	production_ready_for_tier,
)
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name
from omnexa_einvoice.zatca.branch_settings import branch_has_zatca


def country_tab_label(country_code: str, *, lang: str | None = None) -> str:
	"""Desk tab title — same pattern as ``Egypt ETA`` / ``Saudi ZATCA``."""
	code = normalize_country_code(country_code)
	if code == "EG":
		return _("Egypt ETA")
	if code == "SA":
		return _("Saudi ZATCA")
	entry = get_catalog_entry(code)
	if not entry:
		return code
	use_ar = (lang or frappe.local.lang or "en").startswith("ar")
	if use_ar and entry.label_ar:
		return f"{entry.label_ar} — {entry.framework}"
	return entry.label


@frappe.whitelist()
def get_all_country_tab_labels() -> dict[str, str]:
	"""Country code → tab label for Branch form (all supported countries)."""
	labels = {code: country_tab_label(code) for code in ("EG", "SA")}
	for entry in PLUGIN_CATALOG:
		labels[entry.code] = country_tab_label(entry.code)
	return labels


@frappe.whitelist()
def get_branch_country_tab_label(country_code: str) -> str:
	return country_tab_label(country_code)


@frappe.whitelist()
def get_branch_tab_labels_for_doc(country_code: str) -> dict[str, str]:
	"""Tab labels for current branch country (intl + ZATCA + ETA)."""
	code = normalize_country_code(country_code)
	return {
		"country_code": code,
		"tab_break_eta": country_tab_label("EG"),
		"tab_break_zatca": country_tab_label("SA"),
		"tab_break_country_tax": country_tab_label(code) if code not in ("EG", "SA") else _("Country Tax"),
	}


@frappe.whitelist()
def resolve_tax_provider(country_code: str) -> dict[str, str]:
	code = normalize_country_code(country_code)
	return {
		"country_code": code,
		"provider": resolve_adapter_name(code),
		"country_name": country_display_name(code),
	}


@frappe.whitelist()
def get_branch_country_select_options() -> list[dict[str, str]]:
	"""Branch form: country_code dropdown labels (CODE — name)."""
	return branch_country_select_options()


@frappe.whitelist()
def get_branch_tax_panel(company: str, country_code: str, branch: str | None = None) -> dict:
	"""Summary for Branch tax tab — reads Branch fields directly."""
	code = normalize_country_code(country_code)
	entry = get_catalog_entry(code)
	tab_label = country_tab_label(code)
	base = {
		"country_code": code,
		"provider": resolve_adapter_name(code),
		"label": entry.label if entry else code,
		"label_ar": entry.label_ar if entry else "",
		"framework": entry.framework if entry else "",
		"tab_label": tab_label,
		"kind": "none",
		"configured": False,
	}

	if not branch or not frappe.db.exists("Branch", branch):
		base["message"] = frappe._("Save the branch first.")
		return base

	doc = frappe.get_doc("Branch", branch)

	if code == "SA":
		base["kind"] = "zatca"
		base["configured"] = bool(doc.get("zatca_enabled"))
		base["enabled"] = base["configured"]
		base["environment"] = doc.get("zatca_environment")
		base["zatca_phase"] = doc.get("zatca_phase")
		base["tax_registration_number"] = doc.get("zatca_vat_registration_number")
		base["legal_name"] = doc.get("zatca_organization_name")
		if not base["configured"]:
			base["message"] = frappe._("Enable ZATCA on the Saudi ZATCA tab below.")
		return base

	if code in PLUGIN_COUNTRY_CODES:
		tier = integration_tier_for_country(code)
		base["kind"] = "plugin"
		base["integration_tier"] = tier
		base["production_ready"] = production_ready_for_tier(tier)
		settings = branch_intl_tax_as_settings(doc)
		base["configured"] = bool(settings)
		if settings:
			base.update(
				{
					"enabled": True,
					"live_production": bool(settings.live_production),
					"api_environment": settings.api_environment,
					"api_base_url": settings.api_base_url,
					"tax_registration_number": settings.tax_registration_number,
					"signing_mode": settings.signing_mode,
					"auto_submit_on_si_submit": bool(settings.auto_submit_on_si_submit),
					"settings_name": doc.name,
				}
			)
		else:
			base["message"] = frappe._("Enable E-Invoice on the Country Tax tab below.")
		return base

	return base
