# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry
from omnexa_einvoice.tax_engine.plugin.engines.india import build_gst_irn_json
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1


class TestIndiaGstIrn(FrappeTestCase):
	def test_catalog_uses_gst_irn_engine(self):
		entry = get_catalog_entry("IN")
		self.assertEqual(entry.engine, "gst_irn")

	def test_build_gst_irn_json_structure(self):
		doc = {
			"reference_name": "SI-IN-001",
			"issue_datetime": "2026-05-19T10:00:00",
			"seller": {"name": "Seller", "tax_registration": "29AABCT1332L000"},
			"buyer": {"name": "Buyer", "tax_registration": "29AABCT1332L001"},
			"lines": [{"description": "Service", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 18}],
			"totals": {"net_total": 100, "tax_total": 18, "grand_total": 118},
		}
		raw = build_gst_irn_json(doc)
		data = json.loads(raw)
		self.assertEqual(data["Version"], "1.1")
		self.assertIn("DocDtls", data)
		self.assertIn("SellerDtls", data)
		self.assertEqual(data["SellerDtls"]["Gstin"], "29AABCT1332L000")

	def test_phase1_smoke_india(self):
		frappe.flags.in_test = True
		out = run_country_phase1(
			{
				"company": "Test",
				"reference_name": "SMOKE-IN",
				"seller_name": "Seller",
				"tax_registration_number": "29AABCT1332L000",
				"buyer": {"name": "Buyer", "tax_registration": "29AABCT1332L001"},
				"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100}],
				"totals": {"net_total": 100, "tax_total": 18, "grand_total": 118},
			},
			country_code="IN",
		)
		self.assertTrue(out.get("ok"))
		xml = out.get("signed_xml") or ""
		self.assertIn("TranDtls", xml)
		self.assertNotIn("urn:oasis:names:specification:ubl", xml)
