# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Invoice XML signing — international plugin only (Egypt uses eta_* / USB)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings
from omnexa_einvoice.tax_engine.plugin.signing_providers import (
	build_signing_context,
	sign_with_provider,
	sign_xml_scaffold,
)

__all__ = ["sign_invoice_xml", "sign_xml_scaffold"]


def sign_invoice_xml(
	xml_text: str,
	*,
	country_code: str,
	company: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Production-aware signing for plugin countries (via signing_providers)."""
	code = (country_code or "").strip().upper()
	if code in ("EG", "SA"):
		frappe.throw(
			_("Use Egypt ETA or Saudi ZATCA signing — not the international plugin signer."),
			title=_("Tax Signing"),
		)

	settings = (
		get_country_tax_settings(company or "", code, branch=branch)
		if company or branch
		else None
	)
	config: dict[str, Any] = {}
	if settings and settings.get("configuration_json"):
		try:
			config = json.loads(settings.configuration_json)
			if not isinstance(config, dict):
				config = {}
		except json.JSONDecodeError:
			config = {}

	if code == "MX" and (company or branch):
		from omnexa_einvoice.tax_engine.countries.mexico_pac import get_mexico_pac_settings

		pac = get_mexico_pac_settings(company or "", branch=branch)
		if pac.get("csd_private_key_pem"):
			config.setdefault("csd_private_key_pem", pac.csd_private_key_pem)
		if pac.get("csd_certificate_pem"):
			config.setdefault("csd_certificate_pem", pac.csd_certificate_pem)
		if pac.csd_private_key_pem and not config.get("signing_mode"):
			config.setdefault("signing_mode", "csd")

	if code == "IN" and (company or branch):
		from omnexa_einvoice.tax_engine.countries.india_gsp import get_india_gsp_settings

		gsp = get_india_gsp_settings(company or "", branch=branch)
		if gsp.gstin:
			config.setdefault("gstin", gsp.gstin)
		if gsp.gst_signing_secret:
			config.setdefault("gst_signing_secret", gsp.gst_signing_secret)
		if gsp.gstin and not config.get("signing_mode"):
			config.setdefault("signing_mode", "digest")

	if code == "BR" and (company or branch):
		from omnexa_einvoice.tax_engine.countries.brazil_sefaz import get_brazil_sefaz_settings

		sefaz = get_brazil_sefaz_settings(company or "", branch=branch)
		if sefaz.a1_private_key_pem:
			config.setdefault("a1_private_key_pem", sefaz.a1_private_key_pem)
		if sefaz.a1_certificate_pem:
			config.setdefault("a1_certificate_pem", sefaz.a1_certificate_pem)
		if sefaz.a1_private_key_pem and not config.get("signing_mode"):
			config.setdefault("signing_mode", "a1")

	if code == "AE" and (company or branch):
		from omnexa_einvoice.uae.settings import uae_effective_settings

		uae = uae_effective_settings(company or "", branch=branch)
		if uae.asp_signing_private_key_pem:
			config.setdefault("asp_signing_private_key_pem", uae.asp_signing_private_key_pem)
		if uae.asp_signing_certificate_pem:
			config.setdefault("asp_signing_certificate_pem", uae.asp_signing_certificate_pem)
		if uae.asp_signing_private_key_pem and not config.get("signing_mode"):
			config.setdefault("signing_mode", "xmldsig")

	if company or branch:
		from omnexa_einvoice.tax_engine.countries.national_signers import merge_country_signing_config

		config = merge_country_signing_config(code, company or "", branch, config)

	ctx = build_signing_context(country_code=code, settings=settings, config=config)
	return sign_with_provider(xml_text, ctx)
