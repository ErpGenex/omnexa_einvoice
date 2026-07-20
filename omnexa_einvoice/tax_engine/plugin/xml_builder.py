# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Minimal authority-shaped XML per country spec."""

from __future__ import annotations

import html
from typing import Any

from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def build_invoice_xml(document: dict[str, Any], spec: CountryPluginSpec) -> str:
	seller = document.get("seller") or {}
	totals = document.get("totals") or {}
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Line {i}"))
		lines_xml.append(
			f'<Line id="{i}"><Description>{desc}</Description>'
			f'<Quantity>{line.get("qty", 1)}</Quantity>'
			f'<Amount>{line.get("amount", 0)}</Amount></Line>'
		)
	lines_block = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<{spec.xml_root_tag} xmlns="{spec.xml_namespace}" Country="{spec.country_code}" Authority="{spec.authority_code}">
  <UUID>{html.escape(document.get("uuid") or "")}</UUID>
  <Reference>{html.escape(document.get("reference_name") or "")}</Reference>
  <IssueDateTime>{html.escape(document.get("issue_datetime") or "")}</IssueDateTime>
  <Currency>{spec.default_currency}</Currency>
  <Seller>
    <Name>{html.escape(seller.get("name") or "")}</Name>
    <TaxRegistration>{html.escape(seller.get("tax_registration") or "")}</TaxRegistration>
  </Seller>
  <TaxTotal>{totals.get("tax_total", 0)}</TaxTotal>
  <PayableAmount>{totals.get("grand_total", 0)}</PayableAmount>
  <Lines>
{lines_block}
  </Lines>
</{spec.xml_root_tag}>
"""
