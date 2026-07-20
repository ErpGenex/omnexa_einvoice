# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.countries.mexico_pac_client import submit_cfdi_timbrado
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2
from omnexa_einvoice.tax_engine.plugin.specs import get_spec


class TestMexicoPacClient(FrappeTestCase):
	def test_submit_cfdi_mock(self):
		frappe.flags.in_test = True
		xml = """<?xml version="1.0"?><cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"/>"""
		out = submit_cfdi_timbrado(
			company="Test",
			spec=get_spec("MX"),
			uuid="mx-uuid",
			hash_b64="abc",
			signed_xml=xml,
			document={"reference_name": "SI-MX-PAC"
	},
		)
		self.assertTrue(out.get("ok"))
		self.assertTrue(out.get("mock"))
		self.assertTrue(out.get("sat_uuid"))

	def test_phase2_pipeline_mexico(self):
		frappe.flags.in_test = True
		p1 = run_country_phase1(
			{
				"company": "Test",
				"reference_name": "SI-MX-P2",
				"seller_name": "Seller",
				"tax_registration_number": "XAXX010101000",
				"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100
	}],
				"totals": {"net_total": 100, "tax_total": 16, "grand_total": 116}
	},
			country_code="MX",
		)
		p2 = run_country_phase2(
			{"company": "Test", "reference_name": "SI-MX-P2", "phase1": p1
	},
			country_code="MX",
			sync=True,
		)
		self.assertTrue(p2.get("ok"))
		self.assertTrue((p2.get("api") or {}).get("sat_uuid"))
