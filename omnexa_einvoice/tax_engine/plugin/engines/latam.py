# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Latin America tax invoice XML (CO, CL, PE, AR scaffold)."""

from __future__ import annotations

import html
from typing import Any

from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry


def build_latam_xml(document: dict[str, Any], *, country_code: str) -> str:
	entry = get_catalog_entry(country_code)
	authority = entry.authority if entry else country_code
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	currency = document.get("currency") or (entry.currency if entry else "USD")
	doc_type = (document.get("document_type") or "invoice").strip().lower()
	invoice_kind = "CN" if doc_type == "credit_note" else "INV"
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Line {i}"))
		lines_xml.append(
			f'    <Line id="{i}"><Description>{desc}</Description>'
			f'<Amount>{line.get("net_amount", line.get("amount", 0))}</Amount></Line>'
		)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<LatamTaxInvoice Country="{html.escape(country_code)}" Authority="{html.escape(authority)}" Currency="{currency}" DocumentType="{invoice_kind}">
  <UUID>{html.escape(document.get('uuid') or '')}</UUID>
  <InvoiceNumber>{html.escape(document.get('reference_name') or '')}</InvoiceNumber>
  <IssueDateTime>{html.escape(document.get('issue_datetime') or '')}</IssueDateTime>
  <Seller><Name>{html.escape(seller.get('name') or '')}</Name><TaxId>{html.escape(seller.get('tax_registration') or '')}</TaxId></Seller>
  <Buyer><Name>{html.escape(buyer.get('name') or '')}</Name><TaxId>{html.escape(buyer.get('tax_registration') or '')}</TaxId></Buyer>
  <NetTotal>{totals.get('net_total', 0)}</NetTotal>
  <TaxTotal>{totals.get('tax_total', 0)}</TaxTotal>
  <GrandTotal>{totals.get('grand_total', 0)}</GrandTotal>
  <Lines>
{chr(10).join(lines_xml)}
  </Lines>
</LatamTaxInvoice>
"""
