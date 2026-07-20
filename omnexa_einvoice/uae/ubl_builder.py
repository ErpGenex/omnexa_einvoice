# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""UBL 2.1 invoice XML aligned with UAE Peppol PINT AE (core mandatory fields)."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.tax_engine.plugin.engines.ubl_common import UblCountryProfile, build_ubl_invoice
from omnexa_einvoice.uae.constants import COUNTRY_CODE_AE, CURRENCY_AED, CUSTOMIZATION_ID, PROFILE_EXECUTION_ID, PROFILE_ID
from omnexa_einvoice.uae.settings import uae_effective_settings


def build_pint_ae_ubl(document: dict[str, Any]) -> str:
	company = document.get("company") or ""
	settings = document.get("uae_settings") or uae_effective_settings(company)
	profile = UblCountryProfile(
		COUNTRY_CODE_AE,
		CURRENCY_AED,
		settings.customization_id or CUSTOMIZATION_ID,
		settings.profile_id or PROFILE_ID,
		settings.profile_execution_id or PROFILE_EXECUTION_ID,
		invoice_type_code=document.get("invoice_type_code") or settings.invoice_type_code,
		vat_percent="5",
	)
	return build_ubl_invoice(document, profile)
