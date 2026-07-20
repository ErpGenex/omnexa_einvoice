# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared UBL 2.1 builder for Peppol-style e-invoicing countries."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from frappe.utils import flt

NS = {
	"": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
	"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
	"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


@dataclass(frozen=True)
class UblCountryProfile:
	country_code: str
	currency: str
	customization_id: str
	profile_id: str
	profile_execution_id: str
	invoice_type_code: str = "380"
	vat_percent: str = "5"
	tax_scheme_id: str = "VAT"


def _sub(parent, tag: str, text: str | None = None, **attrs) -> ET.Element:
	prefix, local = tag.split(":") if ":" in tag else ("", tag)
	qname = f"{{{NS[prefix]}}}{local}" if prefix else f"{{{NS['']}}}{local}"
	el = ET.SubElement(parent, qname, attrib={k: str(v) for k, v in attrs.items()})
	if text is not None:
		el.text = str(text)
	return el


def _party(party_el, tin: str, name: str, country_code: str) -> None:
	_sub(party_el, "cbc:RegistrationName", name)
	if tin:
		tax_scheme = _sub(party_el, "cac:PartyTaxScheme")
		_sub(tax_scheme, "cbc:CompanyID", tin)
		ts = _sub(tax_scheme, "cac:TaxScheme")
		_sub(ts, "cbc:ID", "VAT")
	addr = _sub(party_el, "cac:PostalAddress")
	country_el = _sub(addr, "cac:Country")
	_sub(country_el, "cbc:IdentificationCode", country_code)


def build_ubl_invoice(document: dict[str, Any], profile: UblCountryProfile) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	currency = document.get("currency") or profile.currency
	inv_uuid = document.get("uuid") or ""
	reference = document.get("reference_name") or ""
	issue_dt = document.get("issue_datetime") or ""
	issue_date = issue_dt[:10]
	issue_time = issue_dt[11:19] if len(issue_dt) > 11 else "00:00:00"
	invoice_type = document.get("invoice_type_code") or profile.invoice_type_code

	ET.register_namespace("", NS[""])
	ET.register_namespace("cac", NS["cac"])
	ET.register_namespace("cbc", NS["cbc"])

	root = ET.Element(f"{{{NS['']}}}Invoice")
	_sub(root, "cbc:CustomizationID", profile.customization_id)
	_sub(root, "cbc:ProfileID", profile.profile_id)
	_sub(root, "cbc:ProfileExecutionID", profile.profile_execution_id)
	_sub(root, "cbc:ID", reference)
	_sub(root, "cbc:UUID", inv_uuid)
	_sub(root, "cbc:IssueDate", issue_date)
	_sub(root, "cbc:IssueTime", issue_time)
	_sub(root, "cbc:InvoiceTypeCode", invoice_type)
	_sub(root, "cbc:DocumentCurrencyCode", currency)
	_sub(root, "cbc:TaxCurrencyCode", currency)

	supplier = _sub(root, "cac:AccountingSupplierParty")
	sparty = _sub(supplier, "cac:Party")
	_party(sparty, seller.get("tax_registration") or "", seller.get("name") or "", profile.country_code)

	if buyer.get("name") or buyer.get("tax_registration"):
		customer = _sub(root, "cac:AccountingCustomerParty")
		cparty = _sub(customer, "cac:Party")
		_party(cparty, buyer.get("tax_registration") or "", buyer.get("name") or "Customer", profile.country_code)

	tax_total_amt = flt(totals.get("tax_total"))
	tax_total = _sub(root, "cac:TaxTotal")
	_sub(tax_total, "cbc:TaxAmount", f"{tax_total_amt:.2f}", currencyID=currency)
	tax_subtotal = _sub(tax_total, "cac:TaxSubtotal")
	_sub(tax_subtotal, "cbc:TaxableAmount", f"{flt(totals.get('net_total')):.2f}", currencyID=currency)
	_sub(tax_subtotal, "cbc:TaxAmount", f"{tax_total_amt:.2f}", currencyID=currency)
	cat = _sub(tax_subtotal, "cac:TaxCategory")
	_sub(cat, "cbc:ID", "S")
	_sub(cat, "cbc:Percent", profile.vat_percent)
	tscheme = _sub(cat, "cac:TaxScheme")
	_sub(tscheme, "cbc:ID", profile.tax_scheme_id)

	legal = _sub(root, "cac:LegalMonetaryTotal")
	_sub(legal, "cbc:LineExtensionAmount", f"{flt(totals.get('net_total')):.2f}", currencyID=currency)
	_sub(legal, "cbc:TaxExclusiveAmount", f"{flt(totals.get('net_total')):.2f}", currencyID=currency)
	_sub(legal, "cbc:TaxInclusiveAmount", f"{flt(totals.get('grand_total')):.2f}", currencyID=currency)
	_sub(legal, "cbc:PayableAmount", f"{flt(totals.get('grand_total')):.2f}", currencyID=currency)

	for idx, line in enumerate(document.get("lines") or [], start=1):
		net = flt(line.get("net_amount", line.get("amount")))
		qty = flt(line.get("qty", 1)) or 1
		rate = flt(line.get("rate", 0))
		iline = _sub(root, "cac:InvoiceLine")
		_sub(iline, "cbc:ID", str(idx))
		_sub(iline, "cbc:InvoicedQuantity", f"{qty:.2f}", unitCode="EA")
		_sub(iline, "cbc:LineExtensionAmount", f"{net:.2f}", currencyID=currency)
		item = _sub(iline, "cac:Item")
		_sub(item, "cbc:Name", line.get("description") or "Item")
		tcat = _sub(item, "cac:ClassifiedTaxCategory")
		_sub(tcat, "cbc:ID", "S")
		_sub(tcat, "cbc:Percent", profile.vat_percent)
		ts = _sub(tcat, "cac:TaxScheme")
		_sub(ts, "cbc:ID", profile.tax_scheme_id)
		price = _sub(iline, "cac:Price")
		_sub(price, "cbc:PriceAmount", f"{rate:.2f}", currencyID=currency)

	return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
