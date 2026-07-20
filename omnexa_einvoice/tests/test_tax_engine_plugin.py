# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_core.omnexa_core.integration_hub import get_default_hub

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.plugin.service import run_phase1, run_phase2
from omnexa_einvoice.tax_engine.submission import PLUGIN_COUNTRY_CODES

PAYLOAD = {
	"reference_name": "SI-PLUGIN-TEST",
	"company": "Test",
	"seller_name": "Test Seller",
	"tax_registration_number": "100000000000003"
	}


class TestTaxEnginePlugin(FrappeTestCase):
	def test_all_plugin_countries_pipeline_enabled(self):
		for code in sorted(PLUGIN_COUNTRY_CODES):
			self.assertTrue(COUNTRY_REGISTRY[code].pipeline_enabled)

	def test_phase1_all_countries(self):
		for code in sorted(PLUGIN_COUNTRY_CODES):
			with self.subTest(country=code):
				result = run_phase1({**PAYLOAD, "reference_name": f"SI-{code}-P1"
	}, country_code=code)
				self.assertTrue(result.get("ok"))
				self.assertEqual(result.get("phase"), "phase1")
				self.assertTrue(result.get("signed_xml"))
				self.assertTrue(result.get("invoice_hash"))
				self.assertTrue(result.get("framework"), code)

	def test_phase2_sync_mock_all_countries(self):
		frappe.flags.in_test = True
		for code in sorted(PLUGIN_COUNTRY_CODES):
			with self.subTest(country=code):
				result = run_phase2(
					{**PAYLOAD, "reference_name": f"SI-{code}-P2"
	},
					country_code=code,
					sync=True,
				)
				self.assertTrue(result.get("ok"))
				self.assertEqual(result.get("phase"), "phase2")
				self.assertTrue(result.get("api", {}).get("mock"))

	def test_hub_phase1_completed_mexico(self):
		hub = get_default_hub()
		result = hub.dispatch(
			"einvoice_mx",
			{
				"reference_name": "SI-MX-HUB",
				"document_type": "invoice",
				"company": "Test"
	},
			idempotency_key="mx-hub-phase1",
		)
		self.assertEqual(result.status, "completed")
		self.assertIn("MX", result.provider_reference)
		self.assertTrue((result.data or {}).get("phase1"))
