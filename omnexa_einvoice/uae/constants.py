# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""UAE FTA / Peppol PINT AE constants (2025-Q2 baseline)."""

from __future__ import annotations

COUNTRY_CODE_AE = "AE"
CURRENCY_AED = "AED"

# Peppol PINT AE (MoF / FTA technical framework)
CUSTOMIZATION_ID = (
	"urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:ae:2025-Q2:pint-ae-1p0@ae-1p0"
)
PROFILE_ID = "urn:peppol:bis:billing"
PROFILE_EXECUTION_ID = "00000000-0000-0000-0000-000000000000"

INVOICE_TYPE_TAX = "380"
INVOICE_TYPE_CREDIT = "381"

TAX_SCHEME_VAT = "VAT"
PEPPOL_EAS_UAE_TIN = "0235"

DEFAULT_VAT_RATE = 5.0
