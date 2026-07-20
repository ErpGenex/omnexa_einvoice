# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, requires_real_api
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings


class TestTaxProduction(FrappeTestCase):
	def test_mock_allowed_in_test(self):
		self.assertTrue(allow_mock_api())

	def test_production_requires_live_flag(self):
		settings = frappe._dict(
			enabled=1,
			api_environment="production",
			live_production=0,
			api_base_url="https://asp.example.com",
			tax_registration_number="12345678901",
			client_id="id",
			client_secret="x",
		)
		with patch(
			"omnexa_einvoice.tax_engine.plugin.production_mode.allow_mock_api",
			return_value=False,
		):
			self.assertTrue(requires_real_api(settings))
		with patch(
			"omnexa_einvoice.tax_engine.plugin.production_validate.get_country_tax_settings",
			return_value=settings,
		), patch(
			"omnexa_einvoice.tax_engine.plugin.production_validate.requires_real_api",
			return_value=True,
		):
			with self.assertRaises(frappe.ValidationError):
				validate_production_settings("Test Co", "DE", phase="phase2")
