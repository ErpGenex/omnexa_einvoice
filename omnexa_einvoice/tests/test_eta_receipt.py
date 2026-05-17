# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.eta_receipt import (
	build_eta_receipt_document,
	encode_eta_receipt_submission,
	generate_receipt_uuid,
	parse_receipt_submission_response,
	refresh_receipt_datetime,
	serialize_eta,
	validate_receipt_document,
)
class TestETAReceipt(FrappeTestCase):
	def test_serialize_eta_uppercase_keys(self):
		data = {"header": {"uuid": "", "receiptNumber": "1"}, "totalAmount": 10.0}
		out = serialize_eta(data)
		self.assertIn('"HEADER"', out)
		self.assertIn('"UUID"', out)
		self.assertIn('"RECEIPTNUMBER"', out)

	def test_generate_receipt_uuid_is_64_hex(self):
		doc = {
			"header": {"uuid": "", "receiptNumber": "T-1", "dateTimeIssued": "2026-05-16T12:00:00Z"},
			"documentType": {"receiptType": "s", "typeVersion": "1.2"},
			"seller": {"rin": "123", "companyTradeName": "Co", "deviceSerialNumber": "DEV1"},
			"buyer": {"type": "P", "name": "Cash"},
			"itemData": [],
			"totalSales": 0,
			"netAmount": 0,
			"totalAmount": 0,
		}
		uuid_val = generate_receipt_uuid(doc)
		self.assertTrue(re.fullmatch(r"[a-f0-9]{64}", uuid_val))

	def test_uuid_changes_when_receipt_number_changes(self):
		base = {
			"header": {"uuid": "", "receiptNumber": "A", "dateTimeIssued": "2026-05-16T12:00:00Z"},
			"documentType": {"receiptType": "s", "typeVersion": "1.2"},
			"totalSales": 1,
			"netAmount": 1,
			"totalAmount": 1,
		}
		u1 = generate_receipt_uuid(base)
		base["header"]["receiptNumber"] = "B"
		u2 = generate_receipt_uuid(base)
		self.assertNotEqual(u1, u2)

	def test_encode_eta_receipt_submission_powerbuilder_wrapper(self):
		doc = {
			"header": {"uuid": "a" * 64, "receiptNumber": "1"},
			"totalAmount": 1,
		}
		raw = encode_eta_receipt_submission(doc)
		text = raw.decode("utf-8")
		self.assertTrue(text.startswith('{"receipts":['))
		self.assertTrue(text.endswith("]}"))
		self.assertIn('"uuid"', text)

	def test_refresh_receipt_datetime_regenerates_uuid(self):
		doc = {
			"header": {
				"uuid": "a" * 64,
				"receiptNumber": "1",
				"dateTimeIssued": "2020-01-01T00:00:00Z",
			},
			"documentType": {"receiptType": "s", "typeVersion": "1.2"},
			"seller": {"rin": "1", "companyTradeName": "Co", "deviceSerialNumber": "D"},
			"buyer": {"name": "X"},
			"itemData": [{"internalCode": "1"}],
			"totalSales": 10,
			"netAmount": 10,
			"totalAmount": 10,
			"taxTotals": [],
		}
		old = doc["header"]["uuid"]
		updated = refresh_receipt_datetime(doc)
		self.assertNotEqual(updated["header"]["uuid"], old)
		self.assertTrue(re.fullmatch(r"[a-f0-9]{64}", updated["header"]["uuid"]))

	def test_resolve_line_tax_zero_rule(self):
		row = frappe._dict({"qty": 1, "rate": 80, "amount": 80, "tax_rule": "k651uem5rm"})
		doc = frappe._dict({"default_tax_rule": None})
		if not frappe.db.exists("Tax Rule", "k651uem5rm"):
			self.skipTest("Tax Rule k651uem5rm not on site")
		from omnexa_einvoice.eta_receipt import _resolve_line_tax

		amount, rate = _resolve_line_tax(row, doc)
		self.assertEqual(rate, 0.0)
		self.assertEqual(amount, 0.0)

	def test_expected_t1_amount_rule42(self):
		from omnexa_einvoice.eta_receipt import _expected_t1_amount

		self.assertEqual(_expected_t1_amount(100.0, 14.0), 14.0)
		self.assertEqual(_expected_t1_amount(80.0, 0.0), 0.0)

	def test_parse_receipt_submission_response_accepted_documents(self):
		body = {
			"submissionId": "57JNQ4PT5GNP3YJQN0AEHMKK10",
			"acceptedDocuments": [{"uuid": "a" * 64, "receiptNumber": "1"}],
			"rejectedDocuments": [],
			"header": {"statusCode": "Success"},
		}
		parsed = parse_receipt_submission_response(body, 200)
		self.assertTrue(parsed["ok"])
		self.assertEqual(parsed["submission_id"], "57JNQ4PT5GNP3YJQN0AEHMKK10")
		self.assertEqual(parsed["authority_uuid"], "a" * 64)

	def test_parse_receipt_submission_response_detects_waf_html(self):
		parsed = parse_receipt_submission_response(
			{"raw": "<html><title>Request Rejected</title></html>"}, 200
		)
		self.assertFalse(parsed["ok"])
		self.assertEqual(parsed["error_code"], "ETA_WAF_BLOCKED")

	def test_validate_receipt_document_rejects_bad_uuid(self):
		doc = {
			"documentType": {"receiptType": "s"},
			"header": {"dateTimeIssued": "2026-05-16T12:00:00Z", "receiptNumber": "1", "uuid": "short"},
			"seller": {"rin": "1", "companyTradeName": "Co", "deviceSerialNumber": "D"},
			"buyer": {"name": "X"},
			"itemData": [{"x": 1}],
			"totalSales": 10,
			"netAmount": 10,
			"totalAmount": 10,
			"taxTotals": [],
		}
		with self.assertRaises(frappe.ValidationError):
			validate_receipt_document(doc, strict_datetime=False)

	def test_validate_receipt_document_accepts_balanced_totals(self):
		doc = {
			"documentType": {"receiptType": "s", "typeVersion": "1.2"},
			"header": {
				"dateTimeIssued": "2026-05-16T12:00:00Z",
				"receiptNumber": "1",
				"uuid": "c" * 64,
			},
			"seller": {"rin": "1", "companyTradeName": "Co", "deviceSerialNumber": "D"},
			"buyer": {"name": "X"},
			"itemData": [{"internalCode": "1"}],
			"totalSales": 100,
			"netAmount": 100,
			"totalAmount": 114,
			"taxTotals": [{"taxType": "T1", "amount": 14}],
		}
		validate_receipt_document(doc, strict_datetime=False)
