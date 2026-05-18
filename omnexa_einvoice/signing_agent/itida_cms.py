# -*- coding: utf-8 -*-
"""
ITIDA / ETA CAdES-BES CMS (Temp-ETR + ETA SDK parsed-cades-bes.txt).

Valid ETA invoice signatures are often 2–4 KB DER because the signing certificate
is embedded (see sdk.invoicing.eta.gov.eg/files/parsed-cades-bes.txt).
Outer PKCS#7 is signedData (1.7.2); inner content uses digestedData (1.7.5).

4062 Invalid Signature usually means the invoice JSON was embedded inside CMS
(attached) or the signed bytes do not match the submitted document JSON.
"""

from __future__ import annotations

import base64
import json
from typing import Any

# PKCS#7 content types (DER OIDs)
_OID_SIGNED_DATA = bytes.fromhex("06092A864886F70D010702")  # 1.2.840.113549.1.7.2
_OID_DIGEST_DATA = bytes.fromhex("06092A864886F70D010705")  # 1.2.840.113549.1.7.5


class ITIDASignatureFormatError(ValueError):
	"""CMS structure ETA rejects (4062 attached / wrong format)."""


def build_itida_canonical_json(document: dict) -> str:
	"""Temp-ETR / ETA serialization: sorted keys, compact, UTF-8."""
	return json.dumps(
		document or {},
		separators=(",", ":"),
		ensure_ascii=False,
		sort_keys=True,
	)


def apply_itida_crypt_options(crypt, chilkat2_module) -> None:
	"""
	Exact order from Docs/Temp-ETR -DB/epass2003_signature.py and separate_screens_system._sign_with_chilkat.
	"""
	cms = chilkat2_module.JsonObject()
	cms.UpdateBool("DigestData", True)
	cms.UpdateBool("OmitAlgorithmIdNull", True)
	cms.UpdateBool("CanonicalizeITIDA", True)
	crypt.CmsOptions = cms.Emit()
	crypt.CadesEnabled = True
	crypt.HashAlgorithm = "sha256"


def apply_itida_signing_attributes(crypt, chilkat2_module) -> None:
	"""CAdES-BES signed attributes (Temp-ETR)."""
	attrs = chilkat2_module.JsonObject()
	attrs.UpdateInt("contentType", 1)
	attrs.UpdateInt("signingTime", 1)
	attrs.UpdateInt("messageDigest", 1)
	attrs.UpdateInt("signingCertificateV2", 1)
	crypt.SigningAttributes = attrs.Emit()


def finalize_itida_crypt_before_sign(crypt) -> None:
	"""After SetSigningCert + CmsOptions + SigningAttributes (Temp-ETR)."""
	crypt.IncludeCertChain = False
	crypt.Charset = "utf-8"
	crypt.EncodingMode = "base64"


def sign_canonical_json_with_crypt(crypt, json_text: str) -> str:
	sig_b64 = crypt.SignStringENC(json_text)
	if not sig_b64:
		raise ITIDASignatureFormatError(
			f"Chilkat SignStringENC failed: {getattr(crypt, 'LastErrorText', '') or 'empty signature'}"
		)
	return sig_b64


def analyze_itida_cms_der(der: bytes) -> dict[str, Any]:
	"""
	Parse CMS like ETA SDK sample: signedData + digestedData, not embedded invoice JSON.
	"""
	info: dict[str, Any] = {
		"der_bytes": len(der),
		"has_digest_data_oid": _OID_DIGEST_DATA in der,
		"has_signed_data_oid": _OID_SIGNED_DATA in der,
		"likely_attached_document": False,
		"encap_content_type": None,
		"encap_content_len": 0,
		"outer_content_type": None,
	}

	try:
		from asn1crypto import cms as acms

		ci = acms.ContentInfo.load(der)
		info["outer_content_type"] = ci["content_type"].native

		if ci["content_type"].native == "signed_data":
			sd = ci["content"]
			encap = sd["encap_content_info"]
			info["encap_content_type"] = encap["content_type"].native

			econtent = encap["content"]
			econtent_len = 0
			if econtent is not None:
				try:
					payload = econtent.native
					if isinstance(payload, bytes):
						econtent_len = len(payload)
					elif payload is not None:
						econtent_len = len(econtent.dump())
				except Exception:
					try:
						econtent_len = len(econtent.dump())
					except Exception:
						econtent_len = 0
			info["encap_content_len"] = econtent_len

			# Attached PKCS#7: encapsulated raw document (JSON/XML) inside CMS → ETA 4062
			if encap["content_type"].native == "data" and econtent_len > 128:
				info["likely_attached_document"] = True
	except Exception as exc:
		info["parse_error"] = str(exc)
		# Heuristic: signedData without any digestedData OID + very large → attached chain/doc
		if info["has_signed_data_oid"] and not info["has_digest_data_oid"] and len(der) > 3500:
			info["likely_attached_document"] = True

	info["itida_ok"] = bool(
		info["has_digest_data_oid"]
		and info["has_signed_data_oid"]
		and not info["likely_attached_document"]
	)
	info["detached_ok"] = info["itida_ok"]
	return info


def validate_itida_signature_b64(signature_b64: str, *, signing_method: str = "") -> dict[str, Any]:
	"""Raise ITIDASignatureFormatError only for true attached/wrong CMS (not cert size)."""
	sig = (signature_b64 or "").strip().replace("\n", "").replace("\r", "")
	if not sig:
		raise ITIDASignatureFormatError("Empty signature.")
	try:
		der = base64.b64decode(sig, validate=True)
	except Exception as exc:
		raise ITIDASignatureFormatError(f"Invalid base64 signature: {exc}") from exc

	info = analyze_itida_cms_der(der)
	info["signing_method"] = signing_method

	if info.get("likely_attached_document"):
		raise ITIDASignatureFormatError(
			f"CMS embeds document content ({info.get('encap_content_len', 0)} bytes) — attached PKCS#7 (ETA 4062). "
			"Use Chilkat with DigestData+CanonicalizeITIDA (Temp-ETR). Do not use PKCS#11 fallback."
		)
	if not info.get("has_digest_data_oid"):
		raise ITIDASignatureFormatError(
			"CMS missing digestedData OID (1.2.840.113549.1.7.5). "
			f"DER={len(der)} bytes method={signing_method or 'unknown'}. "
			"Configure CmsOptions like Temp-ETR epass2003_signature.py."
		)
	if not info.get("has_signed_data_oid"):
		raise ITIDASignatureFormatError(
			"CMS missing signedData OID (1.2.840.113549.1.7.2). "
			"Expected CAdES-BES PKCS#7 wrapper per ETA SDK."
		)
	if not info.get("itida_ok"):
		raise ITIDASignatureFormatError(
			f"CMS structure not ITIDA-compatible (DER {len(der)} bytes). "
			"Match Temp-ETR: Chilkat v10, DigestData, CanonicalizeITIDA, IncludeCertChain=0."
		)
	return info
