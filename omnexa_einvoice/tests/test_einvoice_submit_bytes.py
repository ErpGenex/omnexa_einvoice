# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json
import unittest

from omnexa_einvoice.eta_einvoice_submission import (
	build_e_invoice_submit_body_bytes,
	coerce_agent_signed_document_json,
)


class TestEinvoiceSubmitBytes(unittest.TestCase):
	def test_submit_body_wraps_raw_json(self):
		raw = '{"internalID":"1","totalAmount":100.5,"signatures":[{"signatureType":"I","value":"abc"}]}'
		body = build_e_invoice_submit_body_bytes(raw)
		parsed = json.loads(body.decode("utf-8"))
		self.assertEqual(len(parsed["documents"]), 1)
		self.assertEqual(parsed["documents"][0]["internalID"], "1")
		self.assertEqual(parsed["documents"][0]["totalAmount"], 100.5)

	def test_coerce_prefers_agent_string(self):
		doc = {"internalID": "2", "totalAmount": 10}
		raw = '{"internalID":"2","totalAmount":10}'
		self.assertEqual(coerce_agent_signed_document_json(raw, doc), raw)


if __name__ == "__main__":
	unittest.main()
