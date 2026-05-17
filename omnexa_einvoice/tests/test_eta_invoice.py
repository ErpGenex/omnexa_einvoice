# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.eta_invoice import (
	build_eta_invoice_document,
	invoice_canonical_json,
	parse_invoice_submission_response,
	validate_invoice_document,
)


class TestETAInvoice(FrappeTestCase):
	def test_build_eta_invoice_has_required_roots(self):
		si = frappe.db.get_value(
			"Sales Invoice",
			{"docstatus": 1, "eta_billing_type": "E-Invoice"},
			"name",
		)
		if not si:
			self.skipTest("No submitted E-Invoice Sales Invoice")
		doc = frappe.get_doc("Sales Invoice", si)
		branch = doc.branch or frappe.db.get_value("Branch", {"company": doc.company}, "name")
		if not branch:
			self.skipTest("No branch")
		payload = build_eta_invoice_document(doc, branch=branch)
		for key in ("issuer", "receiver", "invoiceLines", "taxTotals", "documentType"):
			self.assertIn(key, payload)
		self.assertEqual(payload["documentType"], "I")
		self.assertEqual(payload["internalID"], si)
		validate_invoice_document(payload, strict_datetime=False)

	def test_invoice_canonical_excludes_signatures(self):
		doc = {"documentType": "I", "internalID": "1", "signatures": [{"signatureType": "I", "value": "x"}]}
		canon = invoice_canonical_json(doc)
		self.assertNotIn("signatures", canon)

	def test_parse_invoice_submission_accepted_documents(self):
		body = {
			"submissionId": "SUB123",
			"acceptedDocuments": [{"uuid": "a" * 64}],
			"header": {"statusCode": "Success"},
		}
		parsed = parse_invoice_submission_response(body, 202)
		self.assertTrue(parsed["ok"])
		self.assertEqual(parsed["submission_id"], "SUB123")
