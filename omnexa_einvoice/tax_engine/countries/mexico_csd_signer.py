# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Mexico SAT CSD signing scaffold for CFDI 4.0 (UAT / PAC timbrado prep).

Uses C14N + RSA-SHA256 on the Comprobante and injects Sello/Certificado attributes.
Full cadena-original XSLT (SAT) is validated with the PAC during UAT — not duplicated here.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

import frappe
from frappe import _

CFDI_NS = "http://www.sat.gob.mx/cfd/4"


def _require_deps() -> None:
	try:
		import lxml.etree  # noqa: F401
		from cryptography.hazmat.primitives import hashes, serialization  # noqa: F401
	except ImportError:
		frappe.throw(
			_("Mexico CSD signing requires: pip install cryptography lxml"),
			title=_("Mexico CSD"),
		)


def _certificate_body_b64(certificate_pem: str) -> str:
	body = re.sub(
		r"-----BEGIN CERTIFICATE-----|-----END CERTIFICATE-----|\s",
		"",
		certificate_pem or "",
	)
	return body.strip()


def _no_certificado_from_pem(certificate_pem: str) -> str:
	"""SAT NoCertificado: 20-digit serial from CSD certificate when available."""
	if not certificate_pem:
		return "00000000000000000000"
	try:
		from cryptography import x509
		from cryptography.hazmat.backends import default_backend

		cert = x509.load_pem_x509_certificate(
			certificate_pem.encode() if isinstance(certificate_pem, str) else certificate_pem,
			default_backend(),
		)
		serial = cert.serial_number
		return f"{serial:020d}"[-20:]
	except Exception:
		return "00000000000000000000"


def canonical_comprobante_bytes(xml_text: str) -> bytes:
	"""C14N of Comprobante without Sello/Certificado/NoCertificado (UAT scaffold)."""
	_require_deps()
	from lxml import etree

	root = etree.fromstring(xml_text.encode("utf-8"))
	tag = etree.QName(root).localname
	if tag != "Comprobante":
		# Wrap or find Comprobante
		found = root.xpath(
			"//*[local-name()='Comprobante']",
			namespaces={"cfdi": CFDI_NS},
		)
		if not found:
			frappe.throw(_("XML must contain a CFDI Comprobante root."), title=_("Mexico CSD"))
		root = found[0]

	for attr in ("Sello", "Certificado", "NoCertificado"):
		if attr in root.attrib:
			del root.attrib[attr]

	return etree.tostring(root, method="c14n", exclusive=True)


def sign_cfdi_csd(
	xml_text: str,
	*,
	private_key_pem: str,
	certificate_pem: str = "",
	passphrase: str | None = None,
) -> dict[str, Any]:
	"""
	Sign CFDI Comprobante with CSD private key (RSA-SHA256 on canonical bytes).
	Returns signed_xml, hash_hex, hash_b64, signature_b64, signer metadata.
	"""
	_require_deps()
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import padding
	from lxml import etree

	if not (private_key_pem or "").strip():
		frappe.throw(_("CSD private key (csd_private_key_pem) is required."), title=_("Mexico CSD"))

	canonical = canonical_comprobante_bytes(xml_text)
	digest = hashlib.sha256(canonical).digest()
	hash_hex = digest.hex()
	hash_b64 = base64.b64encode(digest).decode("ascii")

	password = passphrase.encode() if passphrase else None
	private_key = serialization.load_pem_private_key(
		private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
		password=password,
	)
	signature = private_key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
	sello_b64 = base64.b64encode(signature).decode("ascii")

	doc = etree.fromstring(xml_text.encode("utf-8"))
	comprobante = doc
	if etree.QName(doc).localname != "Comprobante":
		found = doc.xpath("//*[local-name()='Comprobante']")
		if not found:
			frappe.throw(_("XML must contain a CFDI Comprobante root."), title=_("Mexico CSD"))
		comprobante = found[0]

	comprobante.set("Sello", sello_b64)
	if certificate_pem:
		cert_b64 = _certificate_body_b64(certificate_pem)
		comprobante.set("Certificado", cert_b64)
		comprobante.set("NoCertificado", _no_certificado_from_pem(certificate_pem))

	signed_xml = etree.tostring(
		doc,
		encoding="UTF-8",
		xml_declaration=True,
		pretty_print=False,
	).decode("utf-8")

	return {
		"hash_hex": hash_hex,
		"hash_b64": hash_b64,
		"signature_b64": sello_b64,
		"signed_xml": signed_xml,
		"signer": "csd:cades-scaffold",
		"signing_family": "cades",
	}


def validate_csd_config(config: dict[str, Any]) -> list[str]:
	"""Return checklist messages for incomplete CSD/PAC UAT setup."""
	missing: list[str] = []
	if not (config.get("csd_private_key_pem") or "").strip():
		missing.append(_("csd_private_key_pem in Configuration JSON"))
	if not (config.get("csd_certificate_pem") or "").strip():
		missing.append(_("csd_certificate_pem (SAT .cer as PEM)"))
	if not (config.get("pac_base_url") or "").strip():
		missing.append(_("pac_base_url or API Base URL"))
	return missing
