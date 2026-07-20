# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
ZATCA-compliant CSR (reference: utils.build_certificate_signing_request + build_csr_extensions).
Reimplemented under MIT — not copied from GPL reference verbatim.
"""

from __future__ import annotations

import base64
from typing import Any

import frappe
from frappe import _


def _require_crypto():
	try:
		from cryptography import x509  # noqa: F401
	except ImportError:
		frappe.throw(_("Install cryptography: pip install cryptography"), title=_("ZATCA"))


def _environment_oid_value(environment: str) -> str:
	env = (environment or "sandbox").lower()
	if env == "sandbox":
		return "TESTZATCA-Code-Signing"
	if env == "simulation":
		return "PREZATCA-Code-Signing"
	return "ZATCA-Code-Signing"


def _encode_custom_oid_string(value: str) -> bytes:
	"""UTF8String ASN.1 wrapper for Microsoft-style OID extension."""
	try:
		import asn1
	except ImportError:
		# Minimal BER UTF8String tag 0x0c
		payload = value.encode("utf-8")
		return bytes([0x0C, len(payload)]) + payload

	encoder = asn1.Encoder()
	encoder.start()
	encoder.write(value, asn1.Numbers.UTF8String)
	return encoder.output()


def build_zatca_csr(doc) -> dict[str, Any]:
	"""Build secp256k1 key + ZATCA CSR from ZATCA Company Settings document."""
	_require_crypto()
	from cryptography import x509
	from cryptography.hazmat.backends import default_backend
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import ec
	from cryptography.x509 import ObjectIdentifier
	from cryptography.x509.oid import NameOID

	private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
	private_pem = private_key.private_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PrivateFormat.PKCS8,
		encryption_algorithm=serialization.NoEncryption(),
	).decode("utf-8")

	vat = (doc.vat_registration_number or "").strip()
	egs_serial = (doc.get("egs_serial_number") or doc.name or "EGS-001")[:64]
	org_unit = (doc.get("organization_unit_name") or doc.company or "Main")[:64]
	org_name = (doc.organization_name or doc.company)[:64]
	common_name = (doc.get("csr_common_name") or doc.organization_name_ar or org_name)[:64]
	country = (doc.country_code or "SA")[:2].upper()
	invoice_type = (doc.csr_invoice_type or "1100").strip()
	location = (doc.get("location_address") or _build_location(doc))[:200]
	industry = (doc.get("industry_business_category") or "Other")[:64]

	subject = x509.Name(
		[
			x509.NameAttribute(NameOID.COUNTRY_NAME, country),
			x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit),
			x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name),
			x509.NameAttribute(NameOID.COMMON_NAME, common_name),
		]
	)

	custom_oid = ObjectIdentifier("1.3.6.1.4.1.311.20.2")
	oid_value = _environment_oid_value(doc.zatca_environment)
	custom_ext = x509.UnrecognizedExtension(custom_oid, _encode_custom_oid_string(oid_value))

	alt_name = x509.SubjectAlternativeName(
		[
			x509.DirectoryName(
				x509.Name(
					[
						x509.NameAttribute(NameOID.SURNAME, egs_serial),
						x509.NameAttribute(NameOID.USER_ID, vat),
						x509.NameAttribute(NameOID.TITLE, invoice_type),
						x509.NameAttribute(ObjectIdentifier("2.5.4.26"), location),
						x509.NameAttribute(NameOID.BUSINESS_CATEGORY, industry),
					]
				)
			)
		]
	)

	builder = x509.CertificateSigningRequestBuilder().subject_name(subject)
	builder = builder.add_extension(custom_ext, critical=False)
	builder = builder.add_extension(alt_name, critical=False)
	csr = builder.sign(private_key, hashes.SHA256(), default_backend())
	csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode("utf-8")

	return {
		"private_key_pem": private_pem,
		"csr_pem": csr_pem,
		"csr_base64": base64.b64encode(csr_pem.encode()).decode("ascii"),
	}


def _build_location(doc) -> str:
	parts = [
		doc.get("building_number"),
		doc.get("street"),
		doc.get("district"),
		doc.get("city"),
		doc.get("postal_code"),
		doc.get("country_code") or "SA",
	]
	return ", ".join(p for p in parts if p)
