# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from frappe.tests.utils import FrappeTestCase

from omnexa_core.omnexa_core.integration_hub import get_default_hub

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name


class TestTaxEngineCountries(FrappeTestCase):
	def test_all_builtin_countries_have_adapters(self):
		expected = {
			"EG": "einvoice_eta",
			"SA": "einvoice_zatca",
			"MX": "einvoice_mx",
			"BR": "einvoice_br",
			"AE": "einvoice_ae",
			"DE": "einvoice_de",
			"IT": "einvoice_it",
			"IN": "einvoice_in",
		}
		for code, adapter in expected.items():
			self.assertEqual(resolve_adapter_name(code), adapter)

	def test_hub_registers_plugin_countries(self):
		hub = get_default_hub()
		for code in ("MX", "BR", "DE", "JO"):
			meta = COUNTRY_REGISTRY[code]
			self.assertIn(meta.adapter_name, hub.adapters)

	def test_mexico_hub_dispatch_phase1_completed(self):
		hub = get_default_hub()
		result = hub.dispatch(
			"einvoice_mx",
			{
				"reference_name": "SI-MX-TEST",
				"document_type": "invoice",
				"company": "Test",
			},
			idempotency_key="mx-test-1",
		)
		self.assertEqual(result.status, "completed")
		self.assertIn("MX", result.provider_reference)

	def test_integration_tiers(self):
		self.assertEqual(COUNTRY_REGISTRY["EG"].integration_tier, "production")
		self.assertEqual(COUNTRY_REGISTRY["SA"].integration_tier, "production")
		self.assertTrue(COUNTRY_REGISTRY["EG"].production_ready)
		self.assertTrue(COUNTRY_REGISTRY["SA"].production_ready)
		self.assertEqual(COUNTRY_REGISTRY["IN"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["MX"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["IT"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["BR"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["PL"].integration_tier, "sandbox")
		self.assertFalse(COUNTRY_REGISTRY["IN"].production_ready)
		self.assertTrue(COUNTRY_REGISTRY["IN"].pipeline_enabled)
		self.assertEqual(COUNTRY_REGISTRY["ES"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["CO"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["DE"].integration_tier, "sandbox")
		self.assertEqual(COUNTRY_REGISTRY["FR"].integration_tier, "sandbox")
		self.assertTrue(COUNTRY_REGISTRY["DE"].pipeline_enabled)
		self.assertFalse(COUNTRY_REGISTRY["DE"].production_ready)
