# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import json
from typing import Any

import frappe

from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings
from omnexa_einvoice.uae.constants import (
	CUSTOMIZATION_ID,
	INVOICE_TYPE_TAX,
	PEPPOL_EAS_UAE_TIN,
	PROFILE_EXECUTION_ID,
	PROFILE_ID,
)


def get_uae_settings(company: str, branch: str | None = None) -> frappe._dict | None:
	return get_country_tax_settings(company, "AE", branch=branch)


def parse_uae_config(settings: frappe._dict | dict | None) -> dict[str, Any]:
	cfg: dict[str, Any] = {}
	if not settings:
		return cfg
	raw = settings.get("configuration_json") if isinstance(settings, dict) else settings.configuration_json
	if raw and str(raw).strip():
		try:
			parsed = json.loads(raw)
			if isinstance(parsed, dict):
				cfg = parsed
		except json.JSONDecodeError:
			pass
	return cfg


def uae_effective_settings(company: str, branch: str | None = None) -> frappe._dict:
	"""Merged branch / Country Tax Settings + configuration_json for UAE."""
	base = get_uae_settings(company, branch=branch) or frappe._dict()
	cfg = parse_uae_config(base)
	out = frappe._dict(base)
	out.customization_id = (
		cfg.get("customization_id") or out.get("uae_customization_id") or CUSTOMIZATION_ID
	)
	out.profile_id = cfg.get("profile_id") or out.get("uae_profile_id") or PROFILE_ID
	out.profile_execution_id = (
		cfg.get("profile_execution_id") or out.get("uae_profile_execution_id") or PROFILE_EXECUTION_ID
	)
	out.invoice_type_code = (
		cfg.get("invoice_type_code") or out.get("uae_invoice_type_code") or INVOICE_TYPE_TAX
	)
	out.seller_tin = (out.get("uae_seller_tin") or out.get("tax_registration_number") or "").strip()
	out.peppol_sender_id = (out.get("uae_peppol_sender_id") or "").strip()
	if out.peppol_sender_id and "::" not in out.peppol_sender_id and out.seller_tin:
		out.peppol_sender_id = f"{PEPPOL_EAS_UAE_TIN}:{out.seller_tin}"
	out.peppol_receiver_id = (out.get("uae_peppol_receiver_id") or cfg.get("peppol_receiver_id") or "").strip()
	out.legal_name_ar = out.get("uae_legal_name_ar") or ""
	out.asp_submit_path = (cfg.get("asp_submit_path") or out.get("uae_asp_submit_path") or "/einvoice/v1/submit").strip()
	out.asp_signing_private_key_pem = (
		cfg.get("asp_signing_private_key_pem") or cfg.get("signing_private_key_pem") or ""
	)
	out.asp_signing_certificate_pem = (
		cfg.get("asp_signing_certificate_pem") or cfg.get("signing_certificate_pem") or ""
	)
	out.asp_signing_passphrase = (cfg.get("asp_signing_passphrase") or cfg.get("signing_passphrase") or "").strip()
	return out
