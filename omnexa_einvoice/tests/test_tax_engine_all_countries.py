# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_core.omnexa_core.integration_hub import get_default_hub

from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_COUNTRY_CODES, xml_markers_for_country
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2

PAYLOAD = {
	"company": "Test",
	"seller_name": "Test Seller",
	"tax_registration_number": "100000000000003",
	"buyer": {"name": "Buyer", "tax_registration": "200000000000004"},
	"lines": [{"description": "Service", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 5}],
	"totals": {"net_total": 100, "tax_total": 5, "grand_total": 105},
}

# Representative hub adapters (one per engine family)
HUB_SAMPLE = ("MX", "BR", "AE", "DE", "CO", "JO", "IN")


class TestTaxEngineAllCountries(FrappeTestCase):
	def test_phase1_all_plugin_countries(self):
		frappe.flags.in_test = True
		for code in sorted(PLUGIN_COUNTRY_CODES):
			with self.subTest(country=code):
				result = run_country_phase1(
					{**PAYLOAD, "reference_name": f"SI-{code}-XML"},
					country_code=code,
				)
				self.assertTrue(result.get("ok"), result)
				xml = result.get("signed_xml") or ""
				self.assertTrue(xml)
				for marker in xml_markers_for_country(code):
					self.assertIn(marker, xml, f"{code} missing {marker}")
				self.assertTrue(result.get("framework"))

	def test_phase2_sample_countries(self):
		frappe.flags.in_test = True
		for code in ("MX", "IT", "ZA", "TR", "AE"):
			with self.subTest(country=code):
				result = run_country_phase2(
					{**PAYLOAD, "reference_name": f"SI-{code}-P2"},
					country_code=code,
					sync=True,
				)
				self.assertTrue(result.get("ok"))
				self.assertTrue((result.get("api") or {}).get("mock"))

	def test_hub_dispatch_sample(self):
		hub = get_default_hub()
		for code in HUB_SAMPLE:
			with self.subTest(country=code):
				adapter = f"einvoice_{code.lower()}"
				result = hub.dispatch(
					adapter,
					{
						"reference_name": f"SI-HUB-{code}",
						"document_type": "invoice",
						"company": "Test",
					},
					idempotency_key=f"hub-smoke-{code}",
				)
				self.assertEqual(result.status, "completed")
				phase1 = (result.data or {}).get("phase1") or {}
				self.assertTrue(phase1.get("signed_xml"))
