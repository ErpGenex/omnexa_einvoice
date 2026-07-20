# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Gulf countries — UBL 2.1 profiles (OM, BH, KW, QA)."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.tax_engine.plugin.engines.ubl_common import UblCountryProfile, build_ubl_invoice

GULF_PROFILES: dict[str, UblCountryProfile] = {
	"OM": UblCountryProfile(
		"OM",
		"OMR",
		"urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:om:2025-Q2:pint-om-1p0@om-1p0",
		"urn:peppol:bis:billing",
		"00000000-0000-0000-0000-000000000000",
		vat_percent="5",
	),
	"BH": UblCountryProfile(
		"BH",
		"BHD",
		"urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:bh:2025-Q2:pint-bh-1p0@bh-1p0",
		"urn:peppol:bis:billing",
		"00000000-0000-0000-0000-000000000000",
		vat_percent="10",
	),
	"KW": UblCountryProfile(
		"KW",
		"KWD",
		"urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:kw:2025-Q2:pint-kw-1p0@kw-1p0",
		"urn:peppol:bis:billing",
		"00000000-0000-0000-0000-000000000000",
		vat_percent="0",
	),
	"QA": UblCountryProfile(
		"QA",
		"QAR",
		"urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:qa:2025-Q2:pint-qa-1p0@qa-1p0",
		"urn:peppol:bis:billing",
		"00000000-0000-0000-0000-000000000000",
		vat_percent="0",
	)}


def build_gulf_xml(document: dict[str, Any], *, country_code: str) -> str:
	code = country_code.upper()
	profile = GULF_PROFILES.get(code)
	if not profile:
		raise ValueError(f"No Gulf profile for {code}")
	return build_ubl_invoice(document, profile)
