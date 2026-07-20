# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Block live production for plugin countries until integration_tier is production.

Egypt (EG) and Saudi (SA) are out of scope — they use dedicated ETA/ZATCA paths.
"""

from __future__ import annotations

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import (
	integration_tier_for_country,
	normalize_country_code,
	production_ready_for_tier,
)


def is_plugin_country_code(country_code: str) -> bool:
	code = normalize_country_code(country_code)
	return code not in ("EG", "SA") and bool(code)


def assert_live_production_allowed(country_code: str) -> None:
	"""Raise if this country is not certified for Live Production (plugin only)."""
	code = normalize_country_code(country_code)
	if code in ("EG", "SA"):
		return
	tier = integration_tier_for_country(code)
	if production_ready_for_tier(tier):
		return
	frappe.throw(
		_(
			"Live production is not available for {0} yet (integration tier: <b>{1}</b>). "
			"Use sandbox / test API only until this country is certified. "
			"See Docs/2026-05-19_GLOBAL_EINVOICE_REMEDIATION/."
		).format(code, tier),
		title=_("International e-Invoice"),
	)


def validate_branch_intl_production_flags(doc) -> None:
	"""Branch.validate — intl tax live flags (never touches eta_* fields)."""
	code = normalize_country_code(doc.get("country_iso") or doc.get("country_code"))
	if code in ("EG", "SA"):
		return
	if not is_plugin_country_code(code):
		return

	live = int(doc.get("intl_tax_live_production") or 0)
	env = (doc.get("intl_tax_api_environment") or "").strip().lower()
	if live:
		assert_live_production_allowed(code)
	if env == "production":
		assert_live_production_allowed(code)
		if not live:
			frappe.msgprint(
				_(
					"API environment is production but Live Production is off for {0}. "
					"Enable Live Production only after UAT, or use sandbox."
				).format(code),
				indicator="orange",
				title=_("International e-Invoice"),
			)
