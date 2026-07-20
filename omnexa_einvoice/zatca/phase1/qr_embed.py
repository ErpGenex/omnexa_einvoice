# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Embed ZATCA TLV QR into UBL AdditionalDocumentReference (ID=QR)."""

from __future__ import annotations

import base64

import frappe


def embed_qr_in_ubl(xml_text: str, qr_tlv_base64: str) -> str:
	"""Insert base64 TLV into QR document reference (after signing — does not change invoice hash)."""
	qr_tlv_base64 = (qr_tlv_base64 or "").strip()
	if not qr_tlv_base64:
		return xml_text

	try:
		from lxml import etree
	except ImportError:
		return _embed_qr_elementtree(xml_text, qr_tlv_base64)

	namespaces = {
		"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
		"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
	}
	root = etree.fromstring(xml_text.encode("utf-8"))
	qr_ref = None
	for ref in root.findall(".//cac:AdditionalDocumentReference", namespaces):
		id_el = ref.find("./cbc:ID", namespaces)
		if id_el is not None and (id_el.text or "").strip() == "QR":
			qr_ref = ref
			break
	if qr_ref is None:
		qr_ref = etree.SubElement(
			root,
			"{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AdditionalDocumentReference",
		)
		id_el = etree.SubElement(
			qr_ref,
			"{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID",
		)
		id_el.text = "QR"

	attach = qr_ref.find("./cac:Attachment", namespaces)
	if attach is None:
		attach = etree.SubElement(
			qr_ref,
			"{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Attachment",
		)
	emb = attach.find("./cbc:EmbeddedDocumentBinaryObject", namespaces)
	if emb is None:
		emb = etree.SubElement(
			attach,
			"{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}EmbeddedDocumentBinaryObject",
		)
	emb.set("mimeCode", "text/plain")
	emb.text = qr_tlv_base64

	return etree.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def _embed_qr_elementtree(xml_text: str, qr_tlv_base64: str) -> str:
	import xml.etree.ElementTree as ET

	NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
	NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
	root = ET.fromstring(xml_text.encode("utf-8"))
	qr_ref = None
	for ref in root.iter(f"{{{NS_CAC}}}AdditionalDocumentReference"):
		id_el = ref.find(f"{{{NS_CBC}}}ID")
		if id_el is not None and (id_el.text or "").strip() == "QR":
			qr_ref = ref
			break
	if qr_ref is None:
		return xml_text
	attach = qr_ref.find(f"{{{NS_CAC}}}Attachment")
	if attach is None:
		attach = ET.SubElement(qr_ref, f"{{{NS_CAC}}}Attachment")
	emb = attach.find(f"{{{NS_CBC}}}EmbeddedDocumentBinaryObject")
	if emb is None:
		emb = ET.SubElement(attach, f"{{{NS_CBC}}}EmbeddedDocumentBinaryObject")
	emb.set("mimeCode", "text/plain")
	emb.text = qr_tlv_base64
	return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


@frappe.whitelist()
def qr_tlv_to_png_base64(qr_tlv_base64: str) -> str:
	"""Render scannable QR PNG (base64) from ZATCA TLV base64 payload."""
	import io

	import qrcode

	tlv_bytes = base64.b64decode(qr_tlv_base64)
	qr = qrcode.QRCode(box_size=4, border=2)
	qr.add_data(tlv_bytes)
	qr.make(fit=True)
	img = qr.make_image(fill_color="black", back_color="white")
	buf = io.BytesIO()
	img.save(buf, format="PNG")
	return base64.b64encode(buf.getvalue()).decode("ascii")
