# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.uae.constants import CUSTOMIZATION_ID, PROFILE_ID
from omnexa_einvoice.uae.service import run_phase1, run_phase2
from omnexa_einvoice.uae.ubl_builder import build_pint_ae_ubl


class TestUaePhase1(FrappeTestCase):
	def test_ubl_contains_pint_ae_markers(self):
		document = {
			"uuid": "550e8400-e29b-41d4-a716-446655440000",
			"reference_name": "SI-AE-UBL",
			"issue_datetime": "2026-05-19T10:00:00",
			"currency": "AED",
			"invoice_type_code": "380",
			"seller": {"name": "Seller LLC", "tax_registration": "100000000000003"},
			"buyer": {"name": "Buyer LLC", "tax_registration": "200000000000004"},
			"lines": [{"description": "Service", "qty": 1, "rate": 100, "net_amount": 100, "tax_amount": 5}],
			"totals": {"net_total": 100, "tax_total": 5, "grand_total": 105},
		}
		xml = build_pint_ae_ubl(document)
		self.assertIn(CUSTOMIZATION_ID, xml)
		self.assertIn(PROFILE_ID, xml)
		self.assertIn("urn:oasis:names:specification:ubl:schema:xsd:Invoice-2", xml)
		self.assertIn("AccountingSupplierParty", xml)
		self.assertIn("100000000000003", xml)

	def test_phase1_pipeline(self):
		frappe.flags.in_test = True
		result = run_phase1(
			{
				"reference_name": "SI-AE-PINT-TEST",
				"company": "Test",
				"tax_registration_number": "100000000000003",
				"seller_name": "Test Seller",
			}
		)
		self.assertTrue(result.get("ok"))
		self.assertEqual(result.get("framework"), "PINT-AE")
		self.assertIn("CustomizationID", result.get("signed_xml") or "")

	def test_phase2_mock(self):
		frappe.flags.in_test = True
		result = run_phase2(
			{"reference_name": "SI-AE-P2-TEST", "company": "Test", "tax_registration_number": "100000000000003"},
			sync=True,
		)
		self.assertTrue(result.get("ok"))
		self.assertTrue(result.get("api", {}).get("mock"))
