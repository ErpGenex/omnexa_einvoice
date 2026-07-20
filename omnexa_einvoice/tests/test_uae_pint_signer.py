# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import datetime

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.plugin.signing_providers import build_signing_context, sign_with_provider
from omnexa_einvoice.uae.pint_signer import sign_pint_ae_xml, validate_asp_config
from omnexa_einvoice.uae.ubl_builder import build_pint_ae_ubl


def _test_pems() -> tuple[str, str]:
	from cryptography import x509
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import rsa
	from cryptography.x509.oid import NameOID

	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	private_pem = key.private_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PrivateFormat.TraditionalOpenSSL,
		encryption_algorithm=serialization.NoEncryption(),
	).decode()
	now = datetime.datetime.now(datetime.timezone.utc)
	subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "UAE ASP UAT")])
	cert = (
		x509.CertificateBuilder()
		.subject_name(subject)
		.issuer_name(issuer)
		.public_key(key.public_key())
		.serial_number(1)
		.not_valid_before(now)
		.not_valid_after(now + datetime.timedelta(days=365))
		.sign(key, hashes.SHA256())
	)
	return private_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


class TestUaePintSigner(FrappeTestCase):
	def test_sign_pint_invoice(self):
		private_pem, cert_pem = _test_pems()
		xml = build_pint_ae_ubl(
			{
				"company": "Test",
				"reference_name": "SI-AE-SIG",
				"issue_datetime": "2026-05-20",
				"seller": {"tax_registration": "100000000000003", "name": "Seller AE"
	},
				"buyer": {"tax_registration": "100000000000004", "name": "Buyer"
	},
				"lines": [{"description": "Service", "qty": 1, "rate": 100, "amount": 100
	}],
				"totals": {"net_total": 100, "tax_total": 5, "grand_total": 105}
	}
		)
		out = sign_pint_ae_xml(xml, private_key_pem=private_pem, certificate_pem=cert_pem)
		self.assertIn("Signature", out["signed_xml"])
		self.assertEqual(out["signer"], "asp:xmldsig-scaffold")

	def test_provider_routes_ae(self):
		private_pem, cert_pem = _test_pems()
		xml = build_pint_ae_ubl(
			{
				"company": "Test",
				"reference_name": "SI-AE-2",
				"seller": {"tax_registration": "100000000000003", "name": "S"
	},
				"lines": [],
				"totals": {}
	}
		)
		ctx = build_signing_context(
			country_code="AE",
			settings=frappe._dict(api_environment="sandbox"),
			config={
				"signing_mode": "xmldsig",
				"asp_signing_private_key_pem": private_pem,
				"asp_signing_certificate_pem": cert_pem
	},
		)
		out = sign_with_provider(xml, ctx)
		self.assertEqual(out["signer"], "xmldsig:ae-scaffold")

	def test_validate_asp_config(self):
		self.assertGreaterEqual(len(validate_asp_config({})), 3)
