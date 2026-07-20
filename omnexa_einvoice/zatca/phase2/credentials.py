# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Certificate / public key helpers (reference: utils.build_certificate_data, create_public_key)."""

from __future__ import annotations

import base64


def build_certificate_pem_from_token(binary_security_token: str) -> str:
	"""Decode ZATCA binarySecurityToken to PEM body (stored without headers)."""
	raw = base64.b64decode((binary_security_token or "").encode("utf-8")).decode("utf-8")
	return raw.strip()


def create_public_key_pem(certificate_body: str) -> str:
	from cryptography import x509
	from cryptography.hazmat.backends import default_backend
	from cryptography.hazmat.primitives import serialization

	body = (certificate_body or "").strip()
	if "BEGIN CERTIFICATE" not in body:
		body = f"-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----"
	cert = x509.load_pem_x509_certificate(body.encode(), default_backend())
	public_key = cert.public_key()
	return public_key.public_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PublicFormat.SubjectPublicKeyInfo,
	).decode()
