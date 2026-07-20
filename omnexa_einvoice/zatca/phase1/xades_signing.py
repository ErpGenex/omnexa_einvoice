# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 1 XAdES / ECDSA signing (secp256k1, SHA-256)."""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

import frappe
from frappe import _


def _require_signing_deps():
	try:
		import lxml.etree  # noqa: F401
		from cryptography.hazmat.primitives import serialization  # noqa: F401
	except ImportError:
		frappe.throw(
			_("ZATCA signing requires: pip install cryptography lxml"),
			title=_("ZATCA"),
		)


def strip_for_hash(xml_text: str) -> bytes:
	"""Remove UBLExtensions, QR reference, and Signature for invoice hash (C14N)."""
	_require_signing_deps()
	from lxml import etree

	xsl = etree.XML(
		"""<xsl:stylesheet version="1.0"
			xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
			xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
			xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
			xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
			<xsl:output omit-xml-declaration="yes" encoding="utf-8"/>
			<xsl:template match="@*|node()">
				<xsl:copy><xsl:apply-templates select="@*|node()"/></xsl:copy>
			</xsl:template>
			<xsl:template match="//*[local-name()='UBLExtensions']"/>
			<xsl:template match="//*[local-name()='AdditionalDocumentReference'][cbc:ID='QR']"/>
			<xsl:template match="//*[local-name()='Invoice']/*[local-name()='Signature']"/>
		</xsl:stylesheet>"""
	)
	doc = etree.fromstring(xml_text.encode("utf-8"))
	transformed = etree.XSLT(xsl)(doc)
	return etree.tostring(transformed, method="c14n")


def invoice_hash_hex_and_b64(canonical_xml: bytes) -> tuple[str, str]:
	digest = hashlib.sha256(canonical_xml).digest()
	hex_hash = digest.hex()
	b64_hash = base64.b64encode(digest).decode("ascii")
	return hex_hash, b64_hash


def ecdsa_sign_hex_hash(private_key_pem: str, hash_hex: str) -> str:
	_require_signing_deps()
	from cryptography.hazmat.backends import default_backend
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import ec

	key = serialization.load_pem_private_key(
		private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
		password=None,
		backend=default_backend(),
	)
	signature = key.sign(bytes.fromhex(hash_hex), ec.ECDSA(hashes.SHA256()))
	return base64.b64encode(signature).decode("ascii")


def certificate_hash_b64(certificate_body: str) -> str:
	body = re.sub(r"-----BEGIN CERTIFICATE-----|-----END CERTIFICATE-----|\s", "", certificate_body or "")
	digest = hashlib.sha256(body.encode()).digest()
	return base64.b64encode(digest.hex().encode()).decode("ascii")


def sign_ubl_xml(
	xml_text: str,
	*,
	private_key_pem: str,
	certificate_pem: str,
) -> dict[str, Any]:
	"""
	Compute invoice hash, ECDSA signature, and signed properties digest.
	Returns dict with hash_hex, hash_b64, signature_b64, signed_properties_b64.
	Full UBL extension injection is applied in a later step (invoice_builder service).
	"""
	canonical = strip_for_hash(xml_text)
	hash_hex, hash_b64 = invoice_hash_hex_and_b64(canonical)
	signature_b64 = ecdsa_sign_hex_hash(private_key_pem, hash_hex)
	signed_props_b64 = certificate_hash_b64(certificate_pem)
	return {
		"hash_hex": hash_hex,
		"hash_b64": hash_b64,
		"signature_b64": signature_b64,
		"signed_properties_b64": signed_props_b64,
		"canonical_xml": canonical.decode("utf-8", errors="replace"),
	}
