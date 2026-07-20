# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Italy FatturaPA (FatturaElettronica) XML — SDI submission format (Phase 1 scaffold)."""

from __future__ import annotations

import html
from typing import Any

FP_NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"


def build_fatturapa_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	config = document.get("italy") or {}
	piva = html.escape((seller.get("tax_registration") or config.get("partita_iva") or "")[:16])
	codice_dest = html.escape((config.get("codice_destinatario") or buyer.get("codice_destinatario") or "0000000")[:7])
	buyer_piva = html.escape((buyer.get("tax_registration") or "")[:16])
	ref = html.escape(document.get("reference_name") or "")
	issue_date = html.escape((document.get("issue_datetime") or "")[:10])
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Linea {i}"))
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f"""        <DettaglioLinee>
          <NumeroLinea>{i}</NumeroLinea>
          <Descrizione>{desc}</Descrizione>
          <Quantita>{line.get('qty', 1)}</Quantita>
          <PrezzoUnitario>{line.get('rate', 0)}</PrezzoUnitario>
          <PrezzoTotale>{amount}</PrezzoTotale>
          <AliquotaIVA>22.00</AliquotaIVA>
        </DettaglioLinee>"""
		)
	dettagli = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica versione="FPR12" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:p="{FP_NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <IdTrasmittente><IdPaese>IT</IdPaese><IdCodice>{piva or '00000000000'}</IdCodice></IdTrasmittente>
      <ProgressivoInvio>1</ProgressivoInvio>
      <FormatoTrasmissione>FPR12</FormatoTrasmissione>
      <CodiceDestinatario>{codice_dest}</CodiceDestinatario>
    </DatiTrasmissione>
    <CedentePrestatore>
      <DatiAnagrafici>
        <IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{piva or '00000000000'}</IdCodice></IdFiscaleIVA>
        <Anagrafica><Denominazione>{html.escape(seller.get('name') or '')}</Denominazione></Anagrafica>
        <RegimeFiscale>{html.escape(config.get('regime_fiscale') or 'RF01')}</RegimeFiscale>
      </DatiAnagrafici>
    </CedentePrestatore>
    <CessionarioCommittente>
      <DatiAnagrafici>
        <IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{buyer_piva or '00000000000'}</IdCodice></IdFiscaleIVA>
        <Anagrafica><Denominazione>{html.escape(buyer.get('name') or 'Cliente')}</Denominazione></Anagrafica>
      </DatiAnagrafici>
    </CessionarioCommittente>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali>
      <DatiGeneraliDocumento>
        <TipoDocumento>TD01</TipoDocumento>
        <Divisa>EUR</Divisa>
        <Data>{issue_date}</Data>
        <Numero>{ref}</Numero>
        <ImportoTotaleDocumento>{totals.get('grand_total', 0)}</ImportoTotaleDocumento>
      </DatiGeneraliDocumento>
    </DatiGenerali>
    <DatiBeniServizi>
{dettagli}
      <DatiRiepilogo>
        <AliquotaIVA>22.00</AliquotaIVA>
        <ImponibileImporto>{totals.get('net_total', 0)}</ImponibileImporto>
        <Imposta>{totals.get('tax_total', 0)}</Imposta>
      </DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>
"""
