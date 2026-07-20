# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.registry import resolve_adapter_name
from omnexa_einvoice.tax_engine.router import is_egypt_branch, resolve_tax_provider_for_branch


class TestTaxEngineRouter(FrappeTestCase):
	def test_default_country_is_egypt(self):
		self.assertEqual(resolve_adapter_name(None), "einvoice_eta")
		self.assertEqual(resolve_adapter_name(""), "einvoice_eta")

	def test_saudi_resolves_zatca(self):
		self.assertEqual(resolve_adapter_name("SA"), "einvoice_zatca")

	def test_unknown_country_raises(self):
		with self.assertRaises(Exception):
			resolve_adapter_name("XX")

	def test_resolve_for_missing_branch_defaults_eg(self):
		out = resolve_tax_provider_for_branch(None)
		self.assertEqual(out["country_code"], "EG")
		self.assertEqual(out["tax_provider"], "einvoice_eta")
		self.assertTrue(is_egypt_branch(None))
