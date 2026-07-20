# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared helpers for country plugin modules."""

from __future__ import annotations

from typing import Any

from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationResult

from omnexa_einvoice.tax_engine.constants import CountryTaxMeta


def default_hub_result(payload: dict[str, Any], *, meta: CountryTaxMeta) -> IntegrationResult:
	reference = (payload.get("reference_name") or "").strip()
	document_type = (payload.get("document_type") or "invoice").strip().lower()
	provider_ref = f"{meta.country_code}-{document_type.upper()}-{reference}"
	return IntegrationResult(
		status="queued",
		provider_reference=provider_ref,
		message=_(
			"{0}: enable e-invoice on Branch → Country Tax tab for this branch."
		).format(meta.label, payload.get("company") or ""),
		data={"country_code": meta.country_code, "scaffold": True
	},
	)


def dispatch_sales_invoice_scaffold(
	doc,
	*,
	meta: CountryTaxMeta,
	branch: str | None = None,
	**kwargs,
) -> dict[str, Any]:
	"""Default SI handler until country-specific implementation ships."""
	from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings

	company = doc.company
	settings = get_country_tax_settings(company, meta.country_code)
	if settings and settings.get("enabled"):
		return {
			"ok": True,
			"status": "queued",
			"country_code": meta.country_code,
			"message": _("{0} settings found; API integration pending.").format(meta.label),
			"settings": settings.name
	}
	frappe.msgprint(
		_(
			"{0} is not fully integrated yet. Create <b>Country Tax Settings</b> for {1} / {2}."
		).format(meta.label, company, meta.country_code),
		indicator="orange",
		title=meta.label,
	)
	return {
		"ok": True,
		"status": "scaffold",
		"country_code": meta.country_code,
		"adapter": meta.adapter_name
	}
