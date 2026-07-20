# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Peppol / EN16931 UBL for EU and international countries."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.tax_engine.country_catalog import PEPPOL_BIS_PROFILE, PEPPOL_EU_CUSTOMIZATION, get_catalog_entry
from omnexa_einvoice.tax_engine.plugin.engines.ubl_common import UblCountryProfile, build_ubl_invoice


def build_peppol_xml(document: dict[str, Any], *, country_code: str) -> str:
	entry = get_catalog_entry(country_code)
	code = country_code.upper()
	doc_type = (document.get("document_type") or "invoice").strip().lower()
	type_code = document.get("invoice_type_code") or ("381" if doc_type == "credit_note" else "380")
	profile = UblCountryProfile(
		code,
		document.get("currency") or (entry.currency if entry else "EUR"),
		(entry.customization_id if entry else "") or PEPPOL_EU_CUSTOMIZATION,
		PEPPOL_BIS_PROFILE,
		"00000000-0000-0000-0000-000000000000",
		invoice_type_code=str(type_code),
		vat_percent=(entry.vat_percent if entry else "0"),
	)
	return build_ubl_invoice(document, profile)
