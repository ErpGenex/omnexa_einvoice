# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import datetime

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.national_signers import (
	sign_cufe_digest,
	sign_fatturapa_cades,
	sign_jofotara_digest,
	sign_ksef_fa2_token,
)
from omnexa_einvoice.tax_engine.plugin.engines.italy_fatturapa import build_fatturapa_xml
from omnexa_einvoice.tax_engine.plugin.engines.jordan import build_jordan_xml
from omnexa_einvoice.tax_engine.plugin.engines.latam import build_latam_xml
from omnexa_einvoice.tax_engine.plugin.engines.poland_ksef import build_ksef_fa2_xml


def _pems() -> tuple[str, str]:
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
	subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "UAT")])
	cert = (
		x509.CertificateBuilder()
		.subject_name(subject)
		.issuer_name(issuer)
		.public_key(key.public_key())
		.serial_number(1)
		.not_valid_before(now)
		.not_valid_after(now + datetime.timedelta(days=30))
		.sign(key, hashes.SHA256())
	)
	return private_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


class TestNationalSigners(FrappeTestCase):
	def test_fatturapa_cades(self):
		priv, cert = _pems()
		xml = build_fatturapa_xml(
			{
				"reference_name": "SI-IT-1",
				"issue_datetime": "2026-05-20",
				"seller": {"tax_registration": "IT123", "name": "S"},
				"buyer": {"name": "B"},
				"lines": [{"description": "S", "qty": 1, "rate": 10, "net_amount": 10}],
				"totals": {"net_total": 10, "tax_total": 2, "grand_total": 12},
			}
		)
		out = sign_fatturapa_cades(xml, private_key_pem=priv, certificate_pem=cert)
		self.assertIn("Signature", out["signed_xml"])

	def test_ksef_token_digest(self):
		xml = build_ksef_fa2_xml(
			{
				"reference_name": "SI-PL-1",
				"issue_datetime": "2026-05-20",
				"seller": {"tax_registration": "5252525252", "name": "S"},
				"lines": [],
				"totals": {"net_total": 0, "tax_total": 0, "grand_total": 0},
			}
		)
		out = sign_ksef_fa2_token(xml, ksef_token="test-token")
		self.assertIn("KSeFSessionDigest", out["signed_xml"])

	def test_latam_digest_ar(self):
		xml = build_latam_xml(
			{
				"uuid": "latam-uuid",
				"reference_name": "SI-AR-1",
				"totals": {"net_total": 1, "tax_total": 0, "grand_total": 1},
				"lines": [],
			},
			country_code="AR",
		)
		out = sign_cufe_digest(xml, country_code="AR")
		self.assertIn("AuthorityDigest", out["signed_xml"])

	def test_jofotara_digest(self):
		xml = build_jordan_xml(
			{
				"uuid": "jo-1",
				"reference_name": "SI-JO-1",
				"seller": {"name": "S", "tax_registration": "123"},
				"lines": [],
				"totals": {},
			}
		)
		out = sign_jofotara_digest(xml)
		self.assertIn("AuthorityDigest", out["signed_xml"])
