# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.plugin.signing import sign_invoice_xml
from omnexa_einvoice.tax_engine.plugin.signing_providers import (
	build_signing_context,
	sign_with_provider,
	sign_xml_scaffold,
	signing_family_for_country,
)


class TestSigningProviders(FrappeTestCase):
	def test_family_for_mexico_is_cades(self):
		self.assertEqual(signing_family_for_country("MX"), "cades")

	def test_eg_blocked_from_plugin_signer(self):
		with self.assertRaises(frappe.ValidationError):
			sign_invoice_xml("<x/>", country_code="EG", company="Test")

	def test_scaffold_in_test_mode(self):
		out = sign_xml_scaffold("<Invoice/>", country_code="DE")
		self.assertTrue(out["signer"].startswith("scaffold"))

	def test_live_blocks_scaffold(self):
		settings = frappe._dict(
			enabled=1,
			live_production=1,
			api_environment="production",
		)
		with patch(
			"omnexa_einvoice.tax_engine.plugin.signing_providers.requires_real_api",
			return_value=True,
		), patch(
			"omnexa_einvoice.tax_engine.plugin.signing_providers.is_live_production_settings",
			return_value=True,
		):
			ctx = build_signing_context(
				country_code="DE",
				settings=settings,
				config={},
			)
			with self.assertRaises(frappe.ValidationError):
				sign_with_provider("<Invoice/>", ctx)
