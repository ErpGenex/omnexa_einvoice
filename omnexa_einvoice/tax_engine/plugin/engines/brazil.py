# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Brazil NF-e shaped XML (generation scaffold)."""

from __future__ import annotations

import html
from typing import Any

NFE_NS = "http://www.portalfiscal.inf.br/nfe"


def build_nfe_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	dets = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Item {i}"))
		dets.append(
			f'        <det nItem="{i}"><prod><xProd>{desc}</xProd>'
			f"<qCom>{line.get('qty', 1)}</qCom><vUnCom>{line.get('rate', 0)}</vUnCom>"
			f"<vProd>{line.get('net_amount', line.get('amount', 0))}</vProd></prod></det>"
		)
	det_block = "\n".join(dets)
	cnpj = html.escape((seller.get("tax_registration") or "00000000000000")[:14])
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="{NFE_NS}" versao="4.00">
  <NFe>
    <infNFe Id="NFe{html.escape(document.get('uuid') or '')}">
      <ide>
        <cUF>35</cUF>
        <natOp>Venda</natOp>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>{html.escape(document.get('reference_name') or '1')}</nNF>
        <dhEmi>{html.escape(document.get('issue_datetime') or '')}</dhEmi>
        <tpNF>1</tpNF>
        <idDest>1</idDest>
        <tpImp>1</tpImp>
        <finNFe>1</finNFe>
        <indFinal>1</indFinal>
        <indPres>1</indPres>
      </ide>
      <emit><CNPJ>{cnpj}</CNPJ><xNome>{html.escape(seller.get('name') or '')}</xNome></emit>
      <dest><xNome>{html.escape(buyer.get('name') or 'Consumidor')}</xNome></dest>
{det_block}
      <total>
        <ICMSTot>
          <vProd>{totals.get('net_total', 0)}</vProd>
          <vNF>{totals.get('grand_total', 0)}</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
"""
