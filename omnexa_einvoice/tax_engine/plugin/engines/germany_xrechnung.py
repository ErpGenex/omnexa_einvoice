# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Germany XRechnung (CIUS) UBL 2.1 scaffold with Leitweg-ID."""

from __future__ import annotations

import html
from typing import Any

from omnexa_einvoice.tax_engine.country_catalog import PEPPOL_EU_CUSTOMIZATION


def build_xrechnung_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	config = document.get("germany") or {}
	leitweg = html.escape((config.get("leitweg_id") or buyer.get("leitweg_id") or "")[:50])
	vat = html.escape((seller.get("tax_registration") or "")[:20])
	ref = html.escape(document.get("reference_name") or "")
	doc_type = (document.get("document_type") or "invoice").strip().lower()
	type_code = html.escape(
		str(document.get("invoice_type_code") or ("381" if doc_type == "credit_note" else "380"))
	)
	customization = html.escape(PEPPOL_EU_CUSTOMIZATION)
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Position {i}"))
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f"""    <cac:InvoiceLine>
      <cbc:ID>{i}</cbc:ID>
      <cbc:InvoicedQuantity>{line.get('qty', 1)}</cbc:InvoicedQuantity>
      <cac:Item><cbc:Description>{desc}</cbc:Description></cac:Item>
      <cac:Price><cbc:PriceAmount currencyID="EUR">{amount}</cbc:PriceAmount></cac:Price>
    </cac:InvoiceLine>"""
		)
	lines = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>{customization}</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>{ref}</cbc:ID>
  <cbc:IssueDate>{html.escape((document.get('issue_datetime') or '')[:10])}</cbc:IssueDate>
  <cbc:InvoiceTypeCode>{type_code}</cbc:InvoiceTypeCode>
  <cbc:BuyerReference>{leitweg or 'Leitweg-ID'}</cbc:BuyerReference>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party><cac:PartyTaxScheme><cbc:CompanyID schemeID="VA">{vat or 'DE000000000'}</cbc:CompanyID></cac:PartyTaxScheme></cac:Party>
  </cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="EUR">{totals.get('net_total', 0)}</cbc:LineExtensionAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">{totals.get('grand_total', 0)}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">{totals.get('grand_total', 0)}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
{lines}
</Invoice>
"""
