# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Spain Facturae 3.2 XML scaffold (AEAT / FACe path)."""

from __future__ import annotations

import html
from typing import Any


def build_facturae_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	config = document.get("spain") or {}
	nif = html.escape((seller.get("tax_registration") or config.get("nif") or "")[:20])
	buyer_nif = html.escape((buyer.get("tax_registration") or "")[:20])
	ref = html.escape(document.get("reference_name") or "")
	issue = html.escape((document.get("issue_datetime") or "")[:10])
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Línea {i}"))
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f"""      <InvoiceLine>
        <ItemDescription>{desc}</ItemDescription>
        <Quantity>{line.get('qty', 1)}</Quantity>
        <UnitPriceWithoutTax>{line.get('rate', 0)}</UnitPriceWithoutTax>
        <TotalCost>{amount}</TotalCost>
        <GrossAmount>{amount}</GrossAmount>
      </InvoiceLine>"""
		)
	items = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<fe:Facturae xmlns:fe="http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml">
  <FileHeader>
    <SchemaVersion>3.2.2</SchemaVersion>
    <Modality>I</Modality>
    <InvoiceIssuerType>EM</InvoiceIssuerType>
  </FileHeader>
  <Parties>
    <SellerParty><TaxIdentification><TaxIdentificationNumber>{nif or 'B00000000'}</TaxIdentificationNumber></TaxIdentification></SellerParty>
    <BuyerParty><TaxIdentification><TaxIdentificationNumber>{buyer_nif or 'A00000000'}</TaxIdentificationNumber></TaxIdentification></BuyerParty>
  </Parties>
  <Invoices>
    <Invoice>
      <InvoiceHeader><InvoiceNumber>{ref}</InvoiceNumber><InvoiceDocumentType>FC</InvoiceDocumentType></InvoiceHeader>
      <InvoiceIssueData><IssueDate>{issue}</IssueDate></InvoiceIssueData>
      <InvoiceTotals>
        <TotalGrossAmount>{totals.get('net_total', 0)}</TotalGrossAmount>
        <TotalTaxOutputs>{totals.get('tax_total', 0)}</TotalTaxOutputs>
        <InvoiceTotal>{totals.get('grand_total', 0)}</InvoiceTotal>
      </InvoiceTotals>
      <Items>
{items}
      </Items>
    </Invoice>
  </Invoices>
</fe:Facturae>
"""
