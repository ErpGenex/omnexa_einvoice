# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Mexico SAT CFDI 4.0 shaped XML (generation scaffold)."""

from __future__ import annotations

import html
from typing import Any

CFDI_NS = "http://www.sat.gob.mx/cfd/4"


def build_cfdi_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Concepto {i}"))
		qty = line.get("qty", 1)
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f'    <cfdi:Concepto ClaveProdServ="01010101" Cantidad="{qty}" '
			f'Descripcion="{desc}" ValorUnitario="{line.get("rate", 0)}" Importe="{amount}" />'
		)
	concepts = "\n".join(lines_xml)
	rfc_emisor = html.escape(seller.get("tax_registration") or "XAXX010101000")
	rfc_receptor = html.escape(buyer.get("tax_registration") or "XAXX010101000")
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="{CFDI_NS}" Version="4.0" Serie="A" Folio="{html.escape(document.get('reference_name') or '')}"
  Fecha="{html.escape(document.get('issue_datetime') or '')}" SubTotal="{totals.get('net_total', 0)}"
  Total="{totals.get('grand_total', 0)}" Moneda="MXN" TipoDeComprobante="I" Exportacion="01" MetodoPago="PUE" FormaPago="01">
  <cfdi:Emisor Rfc="{rfc_emisor}" Nombre="{html.escape(seller.get('name') or '')}" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{rfc_receptor}" Nombre="{html.escape(buyer.get('name') or 'Publico General')}" UsoCFDI="G03"/>
  <cfdi:Conceptos>
{concepts}
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="{totals.get('tax_total', 0)}">
    <cfdi:Traslados>
      <cfdi:Traslado Base="{totals.get('net_total', 0)}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{totals.get('tax_total', 0)}"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
</cfdi:Comprobante>
"""
