# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.zatca.dispatch import process_zatca_hub_request
from omnexa_einvoice.zatca.phase1.service import run_phase1


class TestZatcaPhase1(FrappeTestCase):
	def test_run_phase1_returns_qr_and_xml(self):
		out = run_phase1(
			{
				"reference_name": "ZATCA-TEST-001",
				"document_type": "tax_invoice",
				"company": "Test Company SA",
				"taxpayer_registration_id": "300000000000003",
				"seller_name": "Test Seller EN",
				"seller_name_ar": "بائع تجريبي",
			}
		)
		self.assertTrue(out.get("ok"))
		self.assertTrue(out.get("qr_base64"))
		self.assertTrue(out.get("qr_image_base64"))
		self.assertIn("EmbeddedDocumentBinaryObject", out.get("signed_xml") or "")
		self.assertIn("<?xml", out.get("signed_xml") or "")
		self.assertTrue(out.get("invoice_hash"))

	def test_hub_phase1_completed(self):
		result = process_zatca_hub_request(
			{
				"reference_name": "ZATCA-HUB-001",
				"document_type": "simplified_invoice",
				"phase": "phase1",
				"company": "Test Company SA",
				"taxpayer_registration_id": "300000000000003",
				"seller_name": "Simplified Seller",
			}
		)
		self.assertEqual(result.status, "completed")
		self.assertTrue(result.provider_reference.startswith("ZATCA-SIMPLIFIED_INVOICE"))
		self.assertTrue(result.data.get("zatca", {}).get("qr_base64"))


class TestZatcaIsolation(unittest.TestCase):
	def test_zatca_does_not_import_eta_modules(self):
		import omnexa_einvoice.zatca.dispatch as dispatch

		source_file = dispatch.__file__ or ""
		with open(source_file, encoding="utf-8") as fh:
			text = fh.read()
		self.assertNotIn("eta_invoice", text)
		self.assertNotIn("eta_receipt", text)
		self.assertNotIn("branch_eta", text)
