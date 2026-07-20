# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.jofotara_client import submit_jofotara_invoice
from omnexa_einvoice.tax_engine.countries.latam_authority_client import submit_latam_authority
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2
from omnexa_einvoice.tax_engine.plugin.specs import get_spec


class TestLatamJordanClients(FrappeTestCase):
	def test_ar_mock_submit(self):
		frappe.flags.in_test = True
		xml = """<?xml version="1.0"?><LatamTaxInvoice Country="AR"/>"""
		out = submit_latam_authority(
			company="Test",
			country_code="AR",
			spec=get_spec("AR"),
			uuid="ar-u",
			hash_b64="x",
			signed_xml=xml,
			document={"reference_name": "SI-AR"
	},
		)
		self.assertTrue(out.get("mock"))

	def test_jo_mock_submit(self):
		frappe.flags.in_test = True
		xml = """<?xml version="1.0"?><JoFotaraInvoice/>"""
		out = submit_jofotara_invoice(
			company="Test",
			spec=get_spec("JO"),
			uuid="jo-u",
			hash_b64="x",
			signed_xml=xml,
			document={"reference_name": "SI-JO"
	},
		)
		self.assertTrue(out.get("mock"))

	def test_ar_phase2_pipeline(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(
			{
				"company": "Test",
				"reference_name": "SI-AR-P2",
				"seller_name": "Seller",
				"tax_registration_number": "20123456789",
				"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100
	}],
				"totals": {"net_total": 100, "tax_total": 21, "grand_total": 121}
	},
			country_code="AR",
		)
		p2 = run_country_phase2(
			{"company": "Test", "phase1": p1
	},
			country_code="AR",
			sync=True,
		)
		self.assertTrue(p2.get("ok"))
