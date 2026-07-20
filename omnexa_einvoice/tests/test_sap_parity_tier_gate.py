# Copyright (c) 2026, ErpGenEx
"""SAP eDocument parity — tier gate only (EG/SA paths not modified)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.country_catalog import integration_tier_for_country
from omnexa_einvoice.tax_engine.plugin.tier_gate import assert_live_production_allowed


class TestSapParityTierGate(FrappeTestCase):
	def test_eg_sa_bypass_plugin_gate(self):
		self.assertIsNone(assert_live_production_allowed("EG"))
		self.assertIsNone(assert_live_production_allowed("SA"))

	def test_mx_sandbox_blocks_live_without_throw_on_call(self):
		tier = integration_tier_for_country("MX")
		self.assertNotEqual(tier, "production")
		with self.assertRaises(frappe.ValidationError):
			assert_live_production_allowed("MX")

	def test_catalog_has_tier_for_uat_countries(self):
		for code in ("AE", "IN", "BR", "DE", "FR"):
			self.assertTrue(integration_tier_for_country(code))
