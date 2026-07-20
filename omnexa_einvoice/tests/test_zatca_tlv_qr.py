# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import base64
import unittest

from omnexa_einvoice.zatca.phase1.tlv_qr import build_tlv_bytes, build_tlv_qr_base64


class TestZatcaTlvQr(unittest.TestCase):
	def test_tlv_five_tags_and_base64(self):
		raw = build_tlv_bytes(
			seller_name="شركة تجريبية",
			vat_registration="300000000000003",
			timestamp="2026-05-19T12:00:00Z",
			invoice_total_with_vat="115.00",
			vat_amount="15.00",
		)
		self.assertTrue(len(raw) > 20)
		b64 = build_tlv_qr_base64(
			seller_name="شركة تجريبية",
			vat_registration="300000000000003",
			timestamp="2026-05-19T12:00:00Z",
			invoice_total_with_vat="115.00",
			vat_amount="15.00",
		)
		decoded = base64.b64decode(b64)
		self.assertEqual(decoded, raw)

	def test_tlv_rejects_oversized_value(self):
		with self.assertRaises(ValueError):
			build_tlv_bytes(
				seller_name="x" * 300,
				vat_registration="300000000000003",
				timestamp="2026-05-19T12:00:00Z",
				invoice_total_with_vat="1.00",
				vat_amount="0.15",
			)
