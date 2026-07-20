# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.dispatch import dispatch_tax_for_document, list_supported_countries


class TestTaxEngineDispatch(FrappeTestCase):
	def test_list_supported_countries_includes_plugin_rows(self):
		rows = {r["country_code"]: r for r in list_supported_countries()}
		self.assertTrue(rows["MX"]["pipeline_enabled"])
		self.assertFalse(rows["MX"]["production_ready"])
		self.assertEqual(rows["IN"]["integration_tier"], "sandbox")
		self.assertTrue(rows["SA"]["production_ready"])
		self.assertTrue(rows["EG"]["production_ready"])

	@patch("omnexa_einvoice.tax_engine.dispatch.is_egypt_branch", return_value=False)
	@patch("omnexa_einvoice.tax_engine.dispatch.resolve_tax_provider_for_branch")
	@patch("frappe.get_doc")
	def test_dispatch_mx_phase1(self, mock_get_doc, mock_routing, _mock_egypt):
		mock_routing.return_value = {"country_code": "MX", "tax_provider": "einvoice_mx"}
		mock_get_doc.return_value = frappe._dict(
			name="SI-MX-DISPATCH",
			company="Test",
			branch="BR-MX",
		)
		frappe.flags.in_test = True
		result = dispatch_tax_for_document(
			"Sales Invoice",
			"SI-MX-DISPATCH",
			branch="BR-MX",
			phase="phase1",
		)
		self.assertTrue(result.get("ok"))
		self.assertEqual(result.get("phase"), "phase1")

	def test_dispatch_rejects_eg_pos_invoice(self):
		with patch(
			"omnexa_einvoice.tax_engine.dispatch.resolve_tax_provider_for_branch",
			return_value={"country_code": "EG", "tax_provider": "einvoice_eta"},
		):
			with patch(
				"omnexa_einvoice.tax_engine.dispatch.is_egypt_branch",
				return_value=True,
			):
				if not frappe.db.exists("DocType", "POS Invoice"):
					self.skipTest("POS Invoice not installed")
				pos = frappe.db.get_value("POS Invoice", {}, "name")
				if not pos:
					self.skipTest("No POS Invoice on site")
				with self.assertRaises(frappe.ValidationError):
					dispatch_tax_for_document("POS Invoice", pos)
