# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Build ZATCA API invoice payload from signed UBL XML (reference: common_util.generate_invoice_payload_from_xml)."""

from __future__ import annotations

import base64
from typing import Any

import frappe
from frappe import _


def build_payload_from_signed_xml(signed_xml: str) -> dict[str, Any]:
	"""
	Extract uuid, invoiceHash (DigestValue), and base64 invoice for ZATCA APIs.
	Matches ZATCA expectation when the signed XML embeds the digest in ds:Reference.
	"""
	xml_bytes = signed_xml.encode("utf-8")
	try:
		from lxml import etree
	except ImportError:
		frappe.throw(_("ZATCA payload parsing requires lxml."), title=_("ZATCA"))

	namespaces = {
		"ds": "http://www.w3.org/2000/09/xmldsig#",
		"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
	}
	root = etree.fromstring(xml_bytes)

	digest_el = root.find(".//ds:SignedInfo/ds:Reference/ds:DigestValue", namespaces)
	if digest_el is None or not (digest_el.text or "").strip():
		# Fallback: caller may pass hash separately
		raise frappe.ValidationError(_("DigestValue not found in signed XML."))

	uuid_el = root.find(".//cbc:UUID", namespaces) or root.find("cbc:UUID", namespaces)
	if uuid_el is None or not (uuid_el.text or "").strip():
		raise frappe.ValidationError(_("UUID not found in signed XML."))

	return {
		"uuid": uuid_el.text.strip(),
		"invoiceHash": digest_el.text.strip(),
		"invoice": base64.b64encode(xml_bytes).decode("ascii"),
	}


def build_invoice_api_payload(
	*,
	signed_xml: str,
	uuid: str | None = None,
	invoice_hash_b64: str | None = None,
) -> dict[str, str]:
	"""Prefer digest from XML; allow explicit hash/uuid overrides from Phase 1 service."""
	if signed_xml and ("DigestValue" in signed_xml or "ds:DigestValue" in signed_xml):
		try:
			return build_payload_from_signed_xml(signed_xml)
		except frappe.ValidationError:
			pass
	if not uuid or not invoice_hash_b64:
		frappe.throw(_("uuid and invoice_hash_b64 are required when XML has no DigestValue."))
	return {
		"invoiceHash": invoice_hash_b64,
		"uuid": uuid,
		"invoice": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
	}
