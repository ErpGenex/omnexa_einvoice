# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
Branch-based tax provider resolution.

Routing mechanism: Branch.country_code → tax_provider (adapter name).

Egypt (EG): always resolves to ``einvoice_eta`` — existing submission and
``eta_*`` modules handle invoice/receipt; this module does not call them.
"""

from __future__ import annotations

import frappe

from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name

# Until Branch.country_code exists on all sites, infer Egypt from ETA flags.
_ETA_BRANCH_FIELDS = ("eta_einvoice_enabled", "eta_ereceipt_enabled")


def _branch_country_code(branch: str) -> str:
	"""Read country_code from Branch; default EG for legacy rows."""
	if not branch:
		return "EG"
	meta = frappe.get_meta("Branch")
	if meta.has_field("country_code"):
		code = normalize_country_code(frappe.db.get_value("Branch", branch, "country_code"))
		if code:
			return code
	# Legacy sites before migrate: infer from ETA flags
	row = frappe.db.get_value(
		"Branch",
		branch,
		["eta_einvoice_enabled", "eta_ereceipt_enabled"],
		as_dict=True,
	) or {}
	if row.get("eta_einvoice_enabled") or row.get("eta_ereceipt_enabled"):
		return "EG"
	return "EG"


def resolve_tax_provider_for_branch(branch: str | None) -> dict[str, str]:
	"""
	Return {country_code, tax_provider} for a branch.
	Safe to call from new code only — does not alter existing Egypt flows.
	"""
	country_code = _branch_country_code(branch or "")
	tax_provider = resolve_adapter_name(country_code)
	return {"country_code": country_code, "tax_provider": tax_provider
	}


def is_egypt_branch(branch: str | None) -> bool:
	"""True when branch routes to Egypt ETA (invoice or receipt)."""
	if not branch:
		return True
	return resolve_tax_provider_for_branch(branch)["tax_provider"] == "einvoice_eta"
