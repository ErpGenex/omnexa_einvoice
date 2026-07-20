# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.tier_gate import assert_live_production_allowed


class TestTierGate(FrappeTestCase):
	def test_scaffold_country_blocks_live_production(self):
		with self.assertRaises(frappe.ValidationError):
			assert_live_production_allowed("AR")

	def test_sandbox_country_blocks_live_production(self):
		with self.assertRaises(frappe.ValidationError):
			assert_live_production_allowed("DE")

	def test_eg_sa_skip_plugin_gate(self):
		assert_live_production_allowed("EG")
		assert_live_production_allowed("SA")

	def test_validate_production_settings_blocks_de_live(self):
		settings = frappe._dict(
			enabled=1,
			api_environment="production",
			live_production=1,
			api_base_url="https://asp.example.com",
			tax_registration_number="12345678901",
			client_id="id",
		)
		with patch(
			"omnexa_einvoice.tax_engine.plugin.production_validate.get_country_tax_settings",
			return_value=settings,
		), patch(
			"omnexa_einvoice.tax_engine.plugin.production_validate.requires_real_api",
			return_value=True,
		), patch(
			"omnexa_einvoice.tax_engine.plugin.production_validate.get_settings_password",
			return_value="secret",
		):
			with self.assertRaises(frappe.ValidationError):
				validate_production_settings("Test Co", "DE", phase="phase2")
