# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Whitelisted APIs for international tax plugin countries."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_COUNTRY_CODES
from omnexa_einvoice.tax_engine.plugin.service import run_phase1, run_phase2


def _validate_plugin_country(country_code: str) -> str:
	code = (country_code or "").strip().upper()
	if code not in PLUGIN_COUNTRY_CODES:
		frappe.throw(_("Country {0} is not supported by the tax plugin console.").format(code))
	meta = COUNTRY_REGISTRY.get(code)
	if not meta or not meta.pipeline_enabled:
		frappe.throw(_("Tax plugin is not enabled for {0}.").format(code))
	return code


@frappe.whitelist()
def process_country_tax_invoice(
	country_code: str,
	reference_name: str,
	*,
	company: str | None = None,
	phase: str = "phase1",
	sync: int | bool = False,
) -> dict[str, Any]:
	"""Desk console: Phase 1 (XML/sign/archive) or Phase 2 (API / queue)."""
	code = _validate_plugin_country(country_code)
	if not (reference_name or "").strip():
		frappe.throw(_("reference_name is required."))
	payload = {
		"reference_name": reference_name.strip(),
		"company": company or frappe.defaults.get_user_default("company"),
		"document_type": "invoice"
	}
	ph = (phase or "phase1").strip().lower()
	if ph == "phase2":
		return run_phase2(payload, country_code=code, sync=bool(sync))
	return run_phase1(payload, country_code=code)
