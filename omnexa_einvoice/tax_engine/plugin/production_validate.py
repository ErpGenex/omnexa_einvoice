# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Validate Country Tax Settings before live production submission (all plugin countries)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.production_mode import (
	is_live_production_settings,
	requires_real_api,
)
from omnexa_einvoice.tax_engine.plugin.tier_gate import assert_live_production_allowed


def _parse_config(settings) -> dict[str, Any]:
	raw = settings.get("configuration_json") if settings else None
	if not raw or not str(raw).strip():
		return {}
	try:
		parsed = json.loads(raw)
		return parsed if isinstance(parsed, dict) else {}
	except json.JSONDecodeError:
		return {}


def _has_api_credentials(settings, config: dict[str, Any]) -> bool:
	if (settings.get("client_id") or "").strip() and get_settings_password(settings, "client_secret"):
		return True
	if (config.get("api_key") or config.get("bearer_token") or "").strip():
		return True
	if get_settings_password(settings, "asp_api_key"):
		return True
	return False


def validate_production_settings(
	company: str,
	country_code: str,
	*,
	phase: str = "phase2",
	branch: str | None = None,
) -> frappe._dict:
	"""
	Raise if settings are insufficient for live production.
	Returns settings dict when valid (or sandbox/mock path).
	"""
	code = (country_code or "").strip().upper()
	entry = get_catalog_entry(code)
	if not entry:
		frappe.throw(_("Unknown country code {0}.").format(code), title=_("Tax Production"))

	settings = get_country_tax_settings(company, code, branch=branch)
	if not settings:
		if requires_real_api(None):
			frappe.throw(
				_("Enable e-invoice on Branch → Country Tax tab for {0} ({1}).").format(company, code),
				title=_("Tax Production"),
			)
		return frappe._dict()

	if requires_real_api(settings):
		assert_live_production_allowed(code)
		if not settings.get("enabled"):
			frappe.throw(
				_("Enable e-invoice on Branch → Country Tax tab ({0}).").format(code),
				title=_("Tax Production"),
			)
		if not is_live_production_settings(settings):
			frappe.throw(
				_(
					"Turn on <b>Live Production</b> on Branch when {0} API environment is production."
				).format(code),
				title=_("Tax Production"),
			)
		base = (settings.get("api_base_url") or "").strip()
		if not base:
			frappe.throw(
				_("API Base URL is required for live production ({0}).").format(code),
				title=_("Tax Production"),
			)
		tin = (settings.get("tax_registration_number") or "").strip()
		if not tin:
			frappe.throw(
				_("Tax Registration Number is required for {0}.").format(code),
				title=_("Tax Production"),
			)
		config = _parse_config(settings)
		if phase == "phase2" and not _has_api_credentials(settings, config):
			frappe.throw(
				_(
					"Provide Client ID + Client Secret, ASP API Key, or api_key in Configuration JSON for {0}."
				).format(code),
				title=_("Tax Production"),
			)

	if code == "AE":
		tin = (settings.get("uae_seller_tin") or settings.get("tax_registration_number") or "").strip()
		if settings.get("enabled") and requires_real_api(settings):
			if len(tin) != 15 or not tin.isdigit():
				frappe.throw(_("UAE TRN must be 15 digits for live production."), title=_("Tax Production"))

	return settings


def validate_document_for_production(document: dict[str, Any], country_code: str) -> None:
	"""Buyer/seller checks before ASP submit."""
	if not requires_real_api(
		get_country_tax_settings(
			document.get("company") or "",
			country_code,
			branch=document.get("branch"),
		)
	):
		return
	seller = document.get("seller") or {}
	if not (seller.get("tax_registration") or "").strip():
		frappe.throw(_("Seller tax registration is required on the invoice."), title=_("Tax Production"))
	buyer = document.get("buyer") or {}
	if not (buyer.get("name") or "").strip():
		frappe.throw(_("Customer is required for B2B e-invoice submission."), title=_("Tax Production"))
