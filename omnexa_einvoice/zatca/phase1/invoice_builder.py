# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 1 invoice document builder (JSON + minimal XML skeleton)."""

from __future__ import annotations

import hashlib
import json
import uuid
import xml.etree.ElementTree as ET
from typing import Any

from frappe.utils import flt, now_datetime

from omnexa_einvoice.zatca.constants import (
	COUNTRY_CODE_SA,
	DOCUMENT_SIMPLIFIED_INVOICE,
	DOCUMENT_TAX_INVOICE,
)


def _invoice_profile_code(document_type: str) -> str:
	"""UBL profile: simplified vs standard (placeholder codes)."""
	if document_type == DOCUMENT_SIMPLIFIED_INVOICE:
		return "0200000"
	return "0100000"


def build_invoice_payload(
	document_type: str,
	*,
	company: str,
	reference_name: str,
	seller_name: str,
	seller_name_ar: str,
	vat_registration: str,
	issue_datetime: str | None = None,
	currency: str = "SAR",
	line_items: list[dict[str, Any]] | None = None,
	totals: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""Canonical dict for ZATCA Phase 1 (before XML/signing)."""
	issue_datetime = issue_datetime or now_datetime().isoformat()
	lines = line_items or [
		{
			"description": "Line 1",
			"quantity": 1,
			"unit_price": 100,
			"net_amount": 100,
			"tax_rate": 15,
			"tax_amount": 15
	}
	]
	t = totals or {}
	net = flt(t.get("net_total") or sum(flt(row.get("net_amount")) for row in lines))
	tax = flt(t.get("tax_total") or sum(flt(row.get("tax_amount")) for row in lines))
	grand = flt(t.get("grand_total") or net + tax)

	return {
		"uuid": str(uuid.uuid4()),
		"document_type": document_type,
		"profile_id": _invoice_profile_code(document_type),
		"company": company,
		"reference_name": reference_name,
		"country": COUNTRY_CODE_SA,
		"issue_datetime": issue_datetime,
		"currency": currency,
		"seller": {
			"name": seller_name,
			"name_ar": seller_name_ar or seller_name,
			"vat_registration": vat_registration
	},
		"lines": lines,
		"totals": {
			"net_total": net,
			"tax_total": tax,
			"grand_total": grand}
	}


def build_ubl_xml_skeleton(payload: dict[str, Any]) -> str:
	"""Minimal UBL 2.1-shaped XML for Phase 1 scaffold (full schema in later tasks)."""
	root = ET.Element(
		"Invoice",
		{
			"xmlns": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
			"xmlns:cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
			"xmlns:cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
	},
	)
	ET.SubElement(root, "cbc:ID").text = payload.get("reference_name") or ""
	ET.SubElement(root, "cbc:UUID").text = payload.get("uuid") or ""
	ET.SubElement(root, "cbc:IssueDate").text = (payload.get("issue_datetime") or "")[:10]
	ET.SubElement(root, "cbc:DocumentCurrencyCode").text = payload.get("currency") or "SAR"
	ET.SubElement(root, "cbc:ProfileID").text = payload.get("profile_id") or ""

	supplier = ET.SubElement(root, "cac:AccountingSupplierParty")
	party = ET.SubElement(supplier, "cac:Party")
	ET.SubElement(party, "cbc:RegistrationName").text = (payload.get("seller") or {}).get("name") or ""

	tax_total = flt((payload.get("totals") or {}).get("tax_total"))
	ET.SubElement(root, "cbc:TaxAmount", currencyID=payload.get("currency") or "SAR").text = f"{tax_total:.2f}"

	legal = ET.SubElement(root, "cac:LegalMonetaryTotal")
	grand = flt((payload.get("totals") or {}).get("grand_total"))
	ET.SubElement(legal, "cbc:PayableAmount", currencyID=payload.get("currency") or "SAR").text = f"{grand:.2f}"

	return ET.tostring(root, encoding="unicode", xml_declaration=True)


def payload_to_json(payload: dict[str, Any]) -> str:
	return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def hash_xml_sha256(xml_text: str) -> str:
	return hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
