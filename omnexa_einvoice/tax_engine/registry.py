# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Country code → IntegrationHub adapter name. Extend via hook only."""

from __future__ import annotations

import frappe

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code


def get_country_provider_map() -> dict[str, str]:
	"""Merge built-in registry with ``omnexa_tax_country_providers`` hook."""
	providers = {code: meta.adapter_name for code, meta in COUNTRY_REGISTRY.items()}
	for path in frappe.get_hooks("omnexa_tax_country_providers", default=None) or []:
		try:
			extra = frappe.get_attr(path)()
			if isinstance(extra, dict):
				for code, adapter in extra.items():
					providers[(code or "").strip().upper()] = adapter
		except Exception:
			frappe.log_error(
				title="omnexa_tax_country_providers hook failed",
				message=f"Hook: {path}\n{frappe.get_traceback()}",
			)
	return providers


def resolve_adapter_name(country_code: str | None) -> str:
	"""
	Resolve hub adapter from ISO country code.
	Default EG preserves all existing Egypt sites when country_code is empty.
	"""
	code = normalize_country_code(country_code or "EG")
	providers = get_country_provider_map()
	adapter = providers.get(code)
	if not adapter:
		frappe.throw(
			frappe._("No tax provider registered for country {0}.").format(code),
			title=frappe._("Tax Provider"),
		)
	return adapter


def get_country_meta(country_code: str):
	code = normalize_country_code(country_code)
	return COUNTRY_REGISTRY.get(code)
