# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA UBL 2.1 invoice builder (ERPGENEX — not ERPNext hooks)."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from typing import Any

from frappe.utils import flt, now_datetime

from omnexa_einvoice.zatca.constants import (
	COUNTRY_CODE_SA,
	DOCUMENT_CREDIT_NOTE,
	DOCUMENT_SIMPLIFIED_INVOICE,
	DOCUMENT_TAX_INVOICE,
)

NS = {
	"": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
	"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
	"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
	"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}


def _sub(parent, tag: str, text: str | None = None, **attrs) -> ET.Element:
	prefix, local = tag.split(":") if ":" in tag else ("", tag)
	if prefix:
		qname = f"{{{NS[prefix]}}}{local}"
	else:
		qname = f"{{{NS['']}}}{local}"
	el = ET.SubElement(parent, qname, attrib={k: str(v) for k, v in attrs.items()})
	if text is not None:
		el.text = str(text)
	return el


def invoice_type_code(document_type: str, is_simplified: bool) -> tuple[str, str]:
	"""Return (type_code, name attribute) per ZATCA."""
	if document_type == DOCUMENT_CREDIT_NOTE:
		return "381", "0100000" if is_simplified else "0100000"
	if document_type == DOCUMENT_SIMPLIFIED_INVOICE or is_simplified:
		return "388", "0200000"
	return "388", "0100000"


def build_ubl_invoice_xml(
	payload: dict[str, Any],
	*,
	icv: int,
	previous_hash: str,
	seller: dict[str, Any],
	buyer: dict[str, Any] | None = None,
) -> tuple[str, str]:
	"""Return (xml_string, uuid)."""
	inv_uuid = payload.get("uuid") or str(uuid.uuid4())
	document_type = payload.get("document_type") or DOCUMENT_TAX_INVOICE
	is_simplified = document_type == DOCUMENT_SIMPLIFIED_INVOICE
	type_code, type_name = invoice_type_code(document_type, is_simplified)
	issue_dt = payload.get("issue_datetime") or now_datetime().isoformat()
	currency = payload.get("currency") or "SAR"
	reference = payload.get("reference_name") or ""

	ET.register_namespace("", NS[""])
	ET.register_namespace("cac", NS["cac"])
	ET.register_namespace("cbc", NS["cbc"])
	ET.register_namespace("ext", NS["ext"])

	root = ET.Element(f"{{{NS['']}}}Invoice")

	# UBLExtensions placeholder — populated after signing
	exts = _sub(root, "ext:UBLExtensions")
	ext = _sub(exts, "ext:UBLExtension")
	_sub(ext, "ext:ExtensionContent")

	_sub(root, "cbc:UBLVersionID", "2.1")
	_sub(root, "cbc:ProfileID", "reporting:1.0")
	_sub(root, "cbc:ID", reference)
	_sub(root, "cbc:UUID", inv_uuid)
	_sub(root, "cbc:IssueDate", issue_dt[:10])
	_sub(root, "cbc:IssueTime", issue_dt[11:19] if len(issue_dt) > 11 else "00:00:00")
	_sub(root, "cbc:InvoiceTypeCode", type_code, name=type_name)
	_sub(root, "cbc:DocumentCurrencyCode", currency)
	_sub(root, "cbc:TaxCurrencyCode", currency)

	# ICV
	icv_ref = _sub(root, "cac:AdditionalDocumentReference")
	_sub(icv_ref, "cbc:ID", "ICV")
	_sub(icv_ref, "cbc:UUID", str(icv))
	# PIH
	if previous_hash:
		pih_ref = _sub(root, "cac:AdditionalDocumentReference")
		_sub(pih_ref, "cbc:ID", "PIH")
		attach = _sub(pih_ref, "cac:Attachment")
		_sub(attach, "cbc:EmbeddedDocumentBinaryObject", previous_hash, mimeCode="text/plain")

	# QR placeholder
	qr_ref = _sub(root, "cac:AdditionalDocumentReference")
	_sub(qr_ref, "cbc:ID", "QR")

	supplier = _sub(root, "cac:AccountingSupplierParty")
	party = _sub(supplier, "cac:Party")
	_sub(party, "cbc:RegistrationName", seller.get("name_ar") or seller.get("name"))
	tax_scheme = _sub(party, "cac:PartyTaxScheme")
	_sub(tax_scheme, "cbc:CompanyID", seller.get("vat_registration"))
	ts = _sub(tax_scheme, "cac:TaxScheme")
	_sub(ts, "cbc:ID", "VAT")

	if buyer and not is_simplified:
		customer = _sub(root, "cac:AccountingCustomerParty")
		cparty = _sub(customer, "cac:Party")
		_sub(cparty, "cbc:RegistrationName", buyer.get("name") or "Customer")
		if buyer.get("vat_registration"):
			ctax = _sub(cparty, "cac:PartyTaxScheme")
			_sub(ctax, "cbc:CompanyID", buyer.get("vat_registration"))
			cts = _sub(ctax, "cac:TaxScheme")
			_sub(cts, "cbc:ID", "VAT")

	totals = payload.get("totals") or {}
	tax_total_amt = flt(totals.get("tax_total"))
	_sub(root, "cbc:TaxAmount", f"{tax_total_amt:.2f}", currencyID=currency)

	tax_total = _sub(root, "cac:TaxTotal")
	_sub(tax_total, "cbc:TaxAmount", f"{tax_total_amt:.2f}", currencyID=currency)

	legal = _sub(root, "cac:LegalMonetaryTotal")
	_sub(legal, "cbc:LineExtensionAmount", f"{flt(totals.get('net_total')):.2f}", currencyID=currency)
	_sub(legal, "cbc:TaxExclusiveAmount", f"{flt(totals.get('net_total')):.2f}", currencyID=currency)
	_sub(legal, "cbc:TaxInclusiveAmount", f"{flt(totals.get('grand_total')):.2f}", currencyID=currency)
	_sub(legal, "cbc:PayableAmount", f"{flt(totals.get('grand_total')):.2f}", currencyID=currency)

	for idx, line in enumerate(payload.get("lines") or [], start=1):
		iline = _sub(root, "cac:InvoiceLine")
		_sub(iline, "cbc:ID", str(idx))
		_sub(iline, "cbc:InvoicedQuantity", f"{flt(line.get('qty', line.get('quantity', 1))):.2f}")
		_sub(iline, "cbc:LineExtensionAmount", f"{flt(line.get('net_amount')):.2f}", currencyID=currency)
		item = _sub(iline, "cac:Item")
		_sub(item, "cbc:Name", line.get("description") or "Item")
		price = _sub(iline, "cac:Price")
		_sub(price, "cbc:PriceAmount", f"{flt(line.get('unit_price', line.get('rate', 0))):.2f}", currencyID=currency)

	xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
	return xml_bytes.decode("utf-8"), inv_uuid
