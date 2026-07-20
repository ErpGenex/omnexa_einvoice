# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.mexico_csd_signer import (
	sign_cfdi_csd,
	validate_csd_config,
)
from omnexa_einvoice.tax_engine.plugin.engines.mexico import build_cfdi_xml
from omnexa_einvoice.tax_engine.plugin.signing_providers import build_signing_context, sign_with_provider


def _test_csd_pems() -> tuple[str, str]:
	import datetime

	from cryptography import x509
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import rsa
	from cryptography.x509.oid import NameOID

	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	now = datetime.datetime.now(datetime.timezone.utc)
	private_pem = key.private_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PrivateFormat.TraditionalOpenSSL,
		encryption_algorithm=serialization.NoEncryption(),
	).decode()
	subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "UAT CSD")])
	cert = (
		x509.CertificateBuilder()
		.subject_name(subject)
		.issuer_name(issuer)
		.public_key(key.public_key())
		.serial_number(123456789)
		.not_valid_before(now)
		.not_valid_after(now + datetime.timedelta(days=365))
		.sign(key, hashes.SHA256())
	)
	cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
	return private_pem, cert_pem


class TestMexicoCsdSigner(FrappeTestCase):
	def test_sign_injects_sello(self):
		private_pem, cert_pem = _test_csd_pems()
		xml = build_cfdi_xml(
			{
				"reference_name": "SI-MX-CSD",
				"issue_datetime": "2026-05-20T12:00:00",
				"seller": {"tax_registration": "EKU9003173C9", "name": "Emisor"},
				"buyer": {"tax_registration": "XAXX010101000", "name": "Receptor"},
				"lines": [{"description": "Servicio", "qty": 1, "rate": 100, "net_amount": 100}],
				"totals": {"net_total": 100, "tax_total": 16, "grand_total": 116},
			}
		)
		out = sign_cfdi_csd(xml, private_key_pem=private_pem, certificate_pem=cert_pem)
		self.assertIn("Sello=", out["signed_xml"])
		self.assertIn("Certificado=", out["signed_xml"])
		self.assertEqual(out["signer"], "csd:cades-scaffold")

	def test_signing_provider_routes_mx_csd(self):
		private_pem, cert_pem = _test_csd_pems()
		xml = build_cfdi_xml({"reference_name": "X", "totals": {}, "lines": []})
		ctx = build_signing_context(
			country_code="MX",
			settings=frappe._dict(api_environment="sandbox"),
			config={
				"signing_mode": "csd",
				"csd_private_key_pem": private_pem,
				"csd_certificate_pem": cert_pem,
			},
		)
		out = sign_with_provider(xml, ctx)
		self.assertEqual(out["signer"], "csd:cades-scaffold")

	def test_validate_csd_config(self):
		missing = validate_csd_config({})
		self.assertGreaterEqual(len(missing), 2)
