# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Poland KSeF FA(2) invoice XML (Phase 1 scaffold)."""

from __future__ import annotations

import html
from typing import Any

KSEF_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"


def build_ksef_fa2_xml(document: dict[str, Any]) -> str:
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	config = document.get("poland") or {}
	nip_seller = html.escape((seller.get("tax_registration") or config.get("nip") or "")[:10])
	nip_buyer = html.escape((buyer.get("tax_registration") or "")[:10])
	ref = html.escape(document.get("reference_name") or "")
	issue_date = html.escape((document.get("issue_datetime") or "")[:10])
	lines_xml = []
	for i, line in enumerate(document.get("lines") or [], start=1):
		desc = html.escape(str(line.get("description") or f"Pozycja {i}"))
		amount = line.get("net_amount", line.get("amount", 0))
		lines_xml.append(
			f"""    <FaWiersz>
      <NrWierszaFa>{i}</NrWierszaFa>
      <P_7>{desc}</P_7>
      <P_8A>szt</P_8A>
      <P_8B>{line.get('qty', 1)}</P_8B>
      <P_9A>{line.get('rate', 0)}</P_9A>
      <P_11>{amount}</P_11>
      <P_12>23</P_12>
    </FaWiersz>"""
		)
	wiersze = "\n".join(lines_xml)
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<FA xmlns="{KSEF_NS}">
  <Podmiot1>
    <DaneIdentyfikacyjne>
      <NIP>{nip_seller or '0000000000'}</NIP>
      <Nazwa>{html.escape(seller.get('name') or '')}</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot1>
  <Podmiot2>
    <DaneIdentyfikacyjne>
      <NIP>{nip_buyer or '0000000000'}</NIP>
      <Nazwa>{html.escape(buyer.get('name') or 'Nabywca')}</Nazwa>
    </DaneIdentyfikacyjne>
  </Podmiot2>
  <Fa>
    <KodWaluty>PLN</KodWaluty>
    <P_1>{issue_date}</P_1>
    <P_2>{ref}</P_2>
    <P_13_1>{totals.get('net_total', 0)}</P_13_1>
    <P_14_1>{totals.get('tax_total', 0)}</P_14_1>
    <P_15>{totals.get('grand_total', 0)}</P_15>
{wiersze}
  </Fa>
</FA>
"""
