# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Colombia DIAN UBL 2.1 invoice scaffold with CUFE placeholder."""

from __future__ import annotations

import hashlib
import html
from typing import Any

def _cufe_seed(document: dict[str, Any]) -> str:
	totals = document.get("totals") or {}
	seller = document.get("seller") or {}
	parts = [
		document.get("reference_name") or "",
		seller.get("tax_registration") or "",
		str(totals.get("net_total", 0)),
		str(totals.get("tax_total", 0)),
		str(totals.get("grand_total", 0)),
	]
	return "|".join(parts)


def build_dian_ubl_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	config = document.get("colombia") or {}
	nit = html.escape((seller.get("tax_registration") or config.get("nit") or "")[:20])
	cufe = hashlib.sha384(_cufe_seed(document).encode("utf-8")).hexdigest()
	ref = html.escape(document.get("reference_name") or "")
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Line {i}"))
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f"""    <cac:InvoiceLine>
      <cbc:ID>{i}</cbc:ID>
      <cbc:InvoicedQuantity>{line.get('qty', 1)}</cbc:InvoicedQuantity>
      <cac:Item><cbc:Description>{desc}</cbc:Description></cac:Item>
      <cac:Price><cbc:PriceAmount>{amount}</cbc:PriceAmount></cac:Price>
    </cac:InvoiceLine>"""
		)
	lines = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
  xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1"
  xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">
  <ext:UBLExtensions>
    <ext:UBLExtension>
      <ext:ExtensionContent>
        <sts:DianExtensions>
          <sts:InvoiceControl><sts:SoftwareID>{html.escape(config.get('software_id') or 'OMNEXA-SW')}</sts:SoftwareID></sts:InvoiceControl>
          <sts:InvoiceSource><sts:IdentificationCode listAgencyID="6" listSchemeURI="urn:oasis:names:specification:ubl:codelist:gc:CountryIdentificationCode-2.1">CO</sts:IdentificationCode></sts:InvoiceSource>
        </sts:DianExtensions>
      </ext:ExtensionContent>
    </ext:UBLExtension>
  </ext:UBLExtensions>
  <cbc:CustomizationID>10</cbc:CustomizationID>
  <cbc:ProfileID>DIAN 2.1</cbc:ProfileID>
  <cbc:ID>{ref}</cbc:ID>
  <cbc:UUID schemeName="CUFE-SHA384">{cufe}</cbc:UUID>
  <cbc:IssueDate>{html.escape((document.get('issue_datetime') or '')[:10])}</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party><cac:PartyTaxScheme><cbc:CompanyID>{nit or '900000000'}</cbc:CompanyID></cac:PartyTaxScheme></cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party><cac:PartyTaxScheme><cbc:CompanyID>{html.escape((buyer.get('tax_registration') or '')[:20])}</cbc:CompanyID></cac:PartyTaxScheme></cac:Party>
  </cac:AccountingCustomerParty>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount>{totals.get('net_total', 0)}</cbc:LineExtensionAmount>
    <cbc:TaxInclusiveAmount>{totals.get('grand_total', 0)}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount>{totals.get('grand_total', 0)}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
{lines}
</Invoice>
"""
