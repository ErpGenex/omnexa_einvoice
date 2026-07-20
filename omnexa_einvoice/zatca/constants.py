# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA constants — no Egypt/ETA imports."""

from __future__ import annotations

ADAPTER_NAME = "einvoice_zatca"

PHASE_1 = "phase1"
PHASE_2 = "phase2"
PHASES = {PHASE_1, PHASE_2}

DOCUMENT_TAX_INVOICE = "tax_invoice"
DOCUMENT_SIMPLIFIED_INVOICE = "simplified_invoice"
DOCUMENT_CREDIT_NOTE = "credit_note"
DOCUMENT_TYPES = {
	DOCUMENT_TAX_INVOICE,
	DOCUMENT_SIMPLIFIED_INVOICE,
	DOCUMENT_CREDIT_NOTE}

# ZATCA TLV QR tags (Phase 1)
TLV_TAG_SELLER_NAME = 1
TLV_TAG_VAT_REGISTRATION = 2
TLV_TAG_TIMESTAMP = 3
TLV_TAG_INVOICE_TOTAL = 4
TLV_TAG_VAT_TOTAL = 5

COUNTRY_CODE_SA = "SA"
