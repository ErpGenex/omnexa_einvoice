# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""XML-DSig enveloped scaffold for NF-e / PINT UBL (UAT prep — not a certified HSM module)."""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

import frappe
from frappe import _

DS_NS = "http://www.w3.org/2000/09/xmldsig#"


def _require_deps() -> None:
	try:
		import lxml.etree  # noqa: F401
		from cryptography.hazmat.primitives import hashes, serialization  # noqa: F401
	except ImportError:
		frappe.throw(
			_("XML-DSig signing requires: pip install cryptography lxml"),
			title=_("Tax Signing"),
		)


def sign_xml_enveloped(
	xml_text: str,
	*,
	private_key_pem: str,
	certificate_pem: str = "",
	passphrase: str | None = None,
	signed_element_localname: str,
	signer_label: str,
) -> dict[str, Any]:
	"""C14N + RSA-SHA256 on target element; append minimal ds:Signature (UAT scaffold)."""
	_require_deps()
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import padding
	from lxml import etree

	if not (private_key_pem or "").strip():
		frappe.throw(_("Private key PEM is required for XML-DSig."), title=_("Tax Signing"))

	doc = etree.fromstring(xml_text.encode("utf-8"))
	targets = doc.xpath(f"//*[local-name()='{signed_element_localname}']")
	if not targets:
		frappe.throw(
			_("XML has no element local-name()='{0}' to sign.").format(signed_element_localname),
			title=_("Tax Signing"),
		)
	target = targets[0]
	for child in list(target):
		if etree.QName(child).localname == "Signature" and child.tag.startswith(
			"{" + DS_NS
		):
			target.remove(child)

	canonical = etree.tostring(target, method="c14n", exclusive=True)
	digest = hashlib.sha256(canonical).digest()
	hash_hex = digest.hex()
	hash_b64 = base64.b64encode(digest).decode("ascii")

	password = passphrase.encode() if passphrase else None
	private_key = serialization.load_pem_private_key(
		private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
		password=password,
	)
	signature = private_key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
	sig_b64 = base64.b64encode(signature).decode("ascii")

	cert_b64 = ""
	if certificate_pem:
		cert_b64 = re.sub(
			r"-----BEGIN CERTIFICATE-----|-----END CERTIFICATE-----|\s",
			"",
			certificate_pem,
		).strip()

	sig_el = etree.Element(f"{{{DS_NS}}}Signature", nsmap={"ds": DS_NS
	})
	etree.SubElement(sig_el, f"{{{DS_NS}}}SignatureValue").text = sig_b64
	if cert_b64:
		ki = etree.SubElement(sig_el, f"{{{DS_NS}}}KeyInfo")
		x509 = etree.SubElement(ki, f"{{{DS_NS}}}X509Data")
		etree.SubElement(x509, f"{{{DS_NS}}}X509Certificate").text = cert_b64
	target.append(sig_el)

	signed_xml = etree.tostring(
		doc,
		encoding="UTF-8",
		xml_declaration=True,
		pretty_print=False,
	).decode("utf-8")

	return {
		"hash_hex": hash_hex,
		"hash_b64": hash_b64,
		"signature_b64": sig_b64,
		"signed_xml": signed_xml,
		"signer": signer_label,
		"signing_family": "xmldsig"
	}
