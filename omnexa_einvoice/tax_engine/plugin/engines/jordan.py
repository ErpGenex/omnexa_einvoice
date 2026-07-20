# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Jordan JoFotara / ISTD shaped XML (generation scaffold)."""

from __future__ import annotations

import html
from typing import Any

JOFOTARA_NS = "https://jofotara.gov.jo/invoice/v1"


def build_jordan_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Line {i}"))
		lines_xml.append(
			f'    <Line number="{i}"><Description>{desc}</Description>'
			f'<Quantity>{line.get("qty", 1)}</Quantity>'
			f'<UnitPrice>{line.get("rate", 0)}</UnitPrice>'
			f'<LineTotal>{line.get("net_amount", line.get("amount", 0))}</LineTotal></Line>'
		)
	lines_block = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<JoFotaraInvoice xmlns="{JOFOTARA_NS}">
  <UUID>{html.escape(document.get('uuid') or '')}</UUID>
  <InvoiceNumber>{html.escape(document.get('reference_name') or '')}</InvoiceNumber>
  <IssueDateTime>{html.escape(document.get('issue_datetime') or '')}</IssueDateTime>
  <Currency>JOD</Currency>
  <Seller>
    <Name>{html.escape(seller.get('name') or '')}</Name>
    <TaxNumber>{html.escape(seller.get('tax_registration') or '')}</TaxNumber>
  </Seller>
  <Buyer>
    <Name>{html.escape(buyer.get('name') or '')}</Name>
    <TaxNumber>{html.escape(buyer.get('tax_registration') or '')}</TaxNumber>
  </Buyer>
  <Totals>
    <NetAmount>{totals.get('net_total', 0)}</NetAmount>
    <TaxAmount>{totals.get('tax_total', 0)}</TaxAmount>
    <GrandTotal>{totals.get('grand_total', 0)}</GrandTotal>
  </Totals>
  <Lines>
{lines_block}
  </Lines>
</JoFotaraInvoice>
"""
