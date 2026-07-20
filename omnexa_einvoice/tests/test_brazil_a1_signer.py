# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import datetime

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.brazil_a1_signer import sign_nfe_a1, validate_sefaz_config
from omnexa_einvoice.tax_engine.plugin.engines.brazil import build_nfe_xml
from omnexa_einvoice.tax_engine.plugin.signing_providers import build_signing_context, sign_with_provider


def _test_a1_pems() -> tuple[str, str]:
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
	subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BR A1 UAT")])
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


class TestBrazilA1Signer(FrappeTestCase):
	def test_sign_injects_ds_signature(self):
		private_pem, cert_pem = _test_a1_pems()
		xml = build_nfe_xml(
			{
				"uuid": "BRTESTUUID123",
				"reference_name": "SI-BR-A1",
				"issue_datetime": "2026-05-20T12:00:00",
				"seller": {"tax_registration": "11222333000181", "name": "Emit"
	},
				"lines": [{"description": "Produto", "qty": 1, "rate": 10, "net_amount": 10
	}],
				"totals": {"net_total": 10, "grand_total": 10}
	}
		)
		out = sign_nfe_a1(xml, private_key_pem=private_pem, certificate_pem=cert_pem)
		self.assertIn("Signature", out["signed_xml"])
		self.assertEqual(out["signer"], "a1:xmldsig-scaffold")

	def test_provider_routes_br_a1(self):
		private_pem, cert_pem = _test_a1_pems()
		xml = build_nfe_xml({"uuid": "X", "reference_name": "1", "totals": {
	}, "lines": []
	})
		ctx = build_signing_context(
			country_code="BR",
			settings=frappe._dict(api_environment="sandbox"),
			config={
				"signing_mode": "a1",
				"a1_private_key_pem": private_pem,
				"a1_certificate_pem": cert_pem
	},
		)
		out = sign_with_provider(xml, ctx)
		self.assertEqual(out["signer"], "a1:xmldsig-scaffold")

	def test_validate_sefaz_config(self):
		self.assertGreaterEqual(len(validate_sefaz_config({})), 3)
