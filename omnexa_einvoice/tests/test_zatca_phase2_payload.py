# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import unittest

from omnexa_einvoice.zatca.phase2.payload import build_invoice_api_payload
from omnexa_einvoice.zatca.phase2.response_handler import parse_submission_result


class TestZatcaPhase2Payload(unittest.TestCase):
	def test_build_payload_explicit_hash(self):
		p = build_invoice_api_payload(
			signed_xml="<Invoice><cbc:UUID>u-1</cbc:UUID></Invoice>",
			uuid="u-1",
			invoice_hash_b64="abc123",
		)
		self.assertEqual(p["uuid"], "u-1")
		self.assertEqual(p["invoiceHash"], "abc123")

	def test_parse_success_clearance(self):
		r = parse_submission_result(
			200,
			{"clearanceStatus": "CLEARED", "validationResults": {}
	},
			status_field="clearanceStatus",
		)
		self.assertTrue(r["ok"])
		self.assertEqual(r["zatca_status"], "CLEARED")
