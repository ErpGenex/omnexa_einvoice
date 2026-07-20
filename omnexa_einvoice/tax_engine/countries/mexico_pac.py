# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Mexico SAT PAC / timbrado configuration (Phase 1 scaffold)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password


def get_mexico_pac_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	"""PAC URL + credentials from Branch intl settings / configuration JSON."""
	settings = get_country_tax_settings(company, "MX", branch=branch)
	if not settings:
		return frappe._dict()
	config: dict[str, Any] = {}
	if settings.get("configuration_json"):
		try:
			config = json.loads(settings.configuration_json)
			if not isinstance(config, dict):
				config = {}
		except json.JSONDecodeError:
			config = {}
	return frappe._dict(
		{
			"pac_base_url": (config.get("pac_base_url") or settings.get("api_base_url") or "").strip(),
			"pac_provider": (config.get("pac_provider") or "").strip(),
			"pac_username": (config.get("pac_username") or settings.get("client_id") or "").strip(),
			"pac_password": get_settings_password(settings, "client_secret"),
			"csd_certificate_pem": config.get("csd_certificate_pem") or "",
			"csd_private_key_pem": config.get("csd_private_key_pem") or ""
	}
	)


def validate_mexico_pac_for_live(company: str, *, branch: str | None = None) -> None:
	"""Raise when live MX production is enabled but PAC/CSD is incomplete."""
	pac = get_mexico_pac_settings(company, branch=branch)
	if not pac.pac_base_url:
		frappe.throw(
			_("Mexico live production requires pac_base_url in Configuration JSON or API Base URL."),
			title=_("Mexico PAC"),
		)
	if not pac.csd_private_key_pem:
		frappe.throw(
			_("Mexico live production requires csd_private_key_pem in Configuration JSON."),
			title=_("Mexico PAC"),
		)
	if not pac.csd_certificate_pem:
		frappe.throw(
			_("Mexico live production requires csd_certificate_pem in Configuration JSON."),
			title=_("Mexico PAC"),
		)
