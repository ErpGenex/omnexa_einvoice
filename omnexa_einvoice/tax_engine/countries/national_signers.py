# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""National signing scaffolds for W-B / W-C / W-D (UAT prep — not certified HSM modules)."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.plugin.xmldsig_scaffold import sign_xml_enveloped

# Configuration keys merged from Country Tax Settings (see merge_country_signing_config).
SIGNING_KEY_ALIASES: dict[str, tuple[str, ...]] = {
	"private_key_pem": (
		"signing_private_key_pem",
		"fatturapa_private_key_pem",
		"a1_private_key_pem",
		"asp_signing_private_key_pem",
		"csd_private_key_pem",
	),
	"certificate_pem": (
		"signing_certificate_pem",
		"fatturapa_certificate_pem",
		"a1_certificate_pem",
		"asp_signing_certificate_pem",
		"csd_certificate_pem",
	),
}


def _key_from_config(config: dict[str, Any], aliases: tuple[str, ...]) -> str:
	for name in aliases:
		val = (config.get(name) or "").strip()
		if val:
			return val
	return ""


def sign_fatturapa_cades(
	xml_text: str,
	*,
	private_key_pem: str,
	certificate_pem: str = "",
	passphrase: str | None = None,
) -> dict[str, Any]:
	return sign_xml_enveloped(
		xml_text,
		private_key_pem=private_key_pem,
		certificate_pem=certificate_pem,
		passphrase=passphrase,
		signed_element_localname="FatturaElettronica",
		signer_label="cades:fatturapa-scaffold",
	)


def sign_ksef_fa2_token(
	xml_text: str,
	*,
	ksef_token: str = "",
	private_key_pem: str = "",
	certificate_pem: str = "",
) -> dict[str, Any]:
	"""KSeF UAT: session token digest on FA root, or XML-DSig when A1 key provided."""
	if private_key_pem:
		out = sign_xml_enveloped(
			xml_text,
			private_key_pem=private_key_pem,
			certificate_pem=certificate_pem,
			signed_element_localname="FA",
			signer_label="ksef:xmldsig-scaffold",
		)
		out["signing_family"] = "ksef"
		return out

	try:
		from lxml import etree
	except ImportError:
		frappe.throw(_("KSeF signing requires lxml."), title=_("KSeF"))

	doc = etree.fromstring(xml_text.encode("utf-8"))
	targets = doc.xpath("//*[local-name()='FA']")
	if not targets:
		frappe.throw(_("KSeF XML must contain FA root."), title=_("KSeF"))
	root = targets[0]
	canonical = etree.tostring(root, method="c14n", exclusive=True)
	digest = hashlib.sha256(canonical).digest()
	hash_hex = digest.hex()
	token_material = (ksef_token or "KSEF-UAT").encode()
	session_digest = hashlib.sha256(token_material + canonical).hexdigest()
	root.set("KSeFSessionDigest", session_digest)
	if ksef_token:
		root.set("KSeFSessionToken", ksef_token[:64])
	signed_xml = etree.tostring(doc, encoding="UTF-8", xml_declaration=True).decode("utf-8")
	return {
		"hash_hex": hash_hex,
		"hash_b64": base64.b64encode(digest).decode("ascii"),
		"signature_b64": session_digest,
		"signed_xml": signed_xml,
		"signer": "ksef:token-scaffold",
		"signing_family": "ksef",
	}


def sign_cufe_digest(xml_text: str, *, country_code: str = "CO") -> dict[str, Any]:
	"""Colombia / LATAM authority digest attribute (CUFE-style scaffold)."""
	try:
		from lxml import etree
	except ImportError:
		frappe.throw(_("DIAN signing requires lxml."), title=_("DIAN"))

	doc = etree.fromstring(xml_text.encode("utf-8"))
	targets = doc.xpath(
		"//*[local-name()='Invoice' or local-name()='LatamTaxInvoice' or local-name()='JoFotaraInvoice']"
	)
	if not targets:
		frappe.throw(_("No Invoice/LatamTaxInvoice to sign."), title=_("Tax Signing"))
	root = targets[0]
	canonical = etree.tostring(root, method="c14n", exclusive=True)
	digest = hashlib.sha256(canonical).digest()
	hash_hex = digest.hex()
	cufe = hashlib.sha256(f"{country_code}:{hash_hex}".encode()).hexdigest()[:64].upper()
	root.set("AuthorityDigest", cufe)
	root.set("CUFE-SHA384", cufe[:48])
	signed_xml = etree.tostring(doc, encoding="UTF-8", xml_declaration=True).decode("utf-8")
	return {
		"hash_hex": hash_hex,
		"hash_b64": base64.b64encode(digest).decode("ascii"),
		"signature_b64": cufe,
		"signed_xml": signed_xml,
		"signer": f"digest:{country_code.lower()}-cufe-scaffold",
		"signing_family": "digest" if country_code in ("AR", "CL", "PE") else "xmldsig",
	}


def sign_jofotara_digest(xml_text: str) -> dict[str, Any]:
	return sign_cufe_digest(xml_text, country_code="JO")


def merge_country_signing_config(
	country_code: str,
	company: str,
	branch: str | None,
	config: dict[str, Any],
) -> dict[str, Any]:
	"""Load signing-related keys from country settings into config."""
	code = (country_code or "").upper()
	out = dict(config)

	if code == "IT":
		from omnexa_einvoice.tax_engine.countries.italy_sdi import get_italy_sdi_settings

		s = get_italy_sdi_settings(company, branch=branch)
		out.setdefault("partita_iva", s.partita_iva)
		if s.fatturapa_private_key_pem:
			out.setdefault("fatturapa_private_key_pem", s.fatturapa_private_key_pem)
		if s.fatturapa_certificate_pem:
			out.setdefault("fatturapa_certificate_pem", s.fatturapa_certificate_pem)
		if out.get("fatturapa_private_key_pem") and not out.get("signing_mode"):
			out.setdefault("signing_mode", "cades")
	elif code == "PL":
		from omnexa_einvoice.tax_engine.countries.poland_ksef_client import get_poland_ksef_settings

		s = get_poland_ksef_settings(company, branch=branch)
		out.setdefault("nip", s.nip)
		if s.token:
			out.setdefault("ksef_token", s.token)
		if s.ksef_private_key_pem:
			out.setdefault("ksef_private_key_pem", s.ksef_private_key_pem)
		if s.ksef_certificate_pem:
			out.setdefault("ksef_certificate_pem", s.ksef_certificate_pem)
		if out.get("ksef_token") or out.get("ksef_private_key_pem"):
			out.setdefault("signing_mode", "ksef")
	elif code in ("AR", "CL", "PE", "JO"):
		if not out.get("signing_mode"):
			out.setdefault("signing_mode", "digest")
	elif code in ("ES", "CO", "DE", "FR", "OM", "BH", "KW", "QA", "TR", "ZA", "KE", "UG"):
		key = _key_from_config(out, SIGNING_KEY_ALIASES["private_key_pem"])
		if key and not out.get("signing_mode"):
			out.setdefault("signing_mode", "xmldsig")

	return out
