# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.india_gsp import submit_gst_irn
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase2
from omnexa_einvoice.tax_engine.plugin.specs import get_spec


class TestIndiaGsp(FrappeTestCase):
	def test_submit_gst_irn_mock(self):
		frappe.flags.in_test = True
		doc = {
			"Version": "1.1",
			"DocDtls": {"Typ": "INV", "No": "SI-1", "Dt": "2026-05-19"},
			"SellerDtls": {"Gstin": "29AABCT1332L000"},
		}
		out = submit_gst_irn(
			company="Test",
			spec=get_spec("IN"),
			uuid="test-uuid-in",
			hash_b64="abc",
			signed_xml=json.dumps(doc),
			document={"branch": None, "reference_name": "SI-IN-GSP"},
		)
		self.assertTrue(out.get("ok"))
		self.assertTrue(out.get("mock"))
		self.assertTrue(out.get("irn"))
		self.assertTrue(out.get("signed_qr_code"))

	def test_phase2_pipeline_india(self):
		frappe.flags.in_test = True
		from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1

		p1 = run_country_phase1(
			{
				"company": "Test",
				"reference_name": "SI-IN-P2",
				"seller_name": "Seller",
				"tax_registration_number": "29AABCT1332L000",
				"buyer": {"name": "Buyer", "tax_registration": "29AABCT1332L001"},
				"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100}],
				"totals": {"net_total": 100, "tax_total": 18, "grand_total": 118},
			},
			country_code="IN",
		)
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-IN-P2", "phase1": p1},
			country_code="IN",
			sync=True,
		)
		self.assertTrue(p2.get("ok"))
		api = p2.get("api") or {}
		self.assertTrue(api.get("irn"))
