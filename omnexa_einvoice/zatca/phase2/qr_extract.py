# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Extract TLV QR string from cleared UBL XML (reference: clearence_util.extract_qr_code_from_cleared_invoice)."""

from __future__ import annotations

import base64


def extract_qr_tlv_base64(cleared_invoice_xml: str) -> str | None:
	try:
		from lxml import etree
	except ImportError:
		return None

	namespaces = {
		"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
		"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
	}
	root = etree.fromstring(cleared_invoice_xml.encode("utf-8"))
	for ref in root.findall(".//cac:AdditionalDocumentReference", namespaces):
		id_el = ref.find("./cbc:ID", namespaces)
		if id_el is None or (id_el.text or "").strip() != "QR":
			continue
		emb = ref.find("./cac:Attachment/cbc:EmbeddedDocumentBinaryObject", namespaces)
		if emb is not None and emb.text:
			raw = emb.text.strip()
			try:
				return base64.b64decode(raw).decode("utf-8")
			except Exception:
				return raw
	return None
