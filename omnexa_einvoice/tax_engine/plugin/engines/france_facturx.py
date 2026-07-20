# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""France Factur-X (CII) hybrid invoice scaffold."""

from __future__ import annotations

import html
from typing import Any


def build_facturx_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	config = document.get("france") or {}
	siret = html.escape((seller.get("tax_registration") or config.get("siret") or "")[:20])
	ref = html.escape(document.get("reference_name") or "")
	profile = html.escape(config.get("profile") or "urn:factur-x.eu:1p0:minimum")
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Ligne {i}"))
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f"""      <ram:IncludedSupplyChainTradeLineItem>
        <ram:AssociatedDocumentLineDocument><ram:LineID>{i}</ram:LineID></ram:AssociatedDocumentLineDocument>
        <ram:SpecifiedTradeProduct><ram:Name>{desc}</ram:Name></ram:SpecifiedTradeProduct>
        <ram:SpecifiedLineTradeSettlement>
          <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>{amount}</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation>
        </ram:SpecifiedLineTradeSettlement>
      </ram:IncludedSupplyChainTradeLineItem>"""
		)
	lines = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>{profile}</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{ref}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">{html.escape((document.get('issue_datetime') or '')[:8])}</udt:DateTimeString></ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty><ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">{siret or '00000000000000'}</ram:ID></ram:SpecifiedLegalOrganization></ram:SellerTradeParty>
      <ram:BuyerTradeParty><ram:Name>{html.escape((buyer.get('name') or ''))}</ram:Name></ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>{totals.get('net_total', 0)}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount>{totals.get('tax_total', 0)}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{totals.get('grand_total', 0)}</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
{lines}
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
