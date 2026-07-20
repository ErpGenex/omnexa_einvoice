# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.branch_country_tax import (
	get_branch_tab_labels_for_doc,
	country_tab_label,
	get_all_country_tab_labels,
	get_branch_tax_panel,
	resolve_tax_provider,
)
from omnexa_einvoice.tax_engine.branch_intl_tax import branch_intl_tax_as_settings
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings
from omnexa_einvoice.tests.test_helpers import create_intl_branch, get_or_create_test_company


class TestBranchCountryTax(FrappeTestCase):
	def test_resolve_tax_provider_de(self):
		out = resolve_tax_provider("DE")
		self.assertEqual(out["provider"], "einvoice_de")

	def test_country_tab_labels(self):
		self.assertEqual(country_tab_label("EG"), "Egypt ETA")
		self.assertEqual(country_tab_label("SA"), "Saudi ZATCA")
		self.assertIn("Germany", country_tab_label("DE"))
		labels = get_all_country_tab_labels()
		self.assertIn("MX", labels)
		self.assertIn("DE", labels)

	def test_tab_label_from_select_value(self):
		labels = get_branch_tab_labels_for_doc("DE — Germany")
		self.assertEqual(labels["country_code"], "DE")
		self.assertIn("Germany", labels["tab_break_country_tax"])

	def test_branch_intl_settings_from_branch_doc(self):
		co = get_or_create_test_company()
		branch = create_intl_branch(co, country_code="DE")
		self.addCleanup(lambda: frappe.delete_doc("Branch", branch, force=1, ignore_permissions=True))
		doc = frappe.get_doc("Branch", branch)
		settings = branch_intl_tax_as_settings(doc)
		self.assertTrue(settings)
		self.assertEqual(settings.tax_registration_number, "12345678901")
		resolved = get_country_tax_settings(doc.company, "DE", branch=branch)
		self.assertTrue(resolved)

	def test_get_panel_plugin(self):
		co = get_or_create_test_company()
		branch = create_intl_branch(co, country_code="DE")
		self.addCleanup(lambda: frappe.delete_doc("Branch", branch, force=1, ignore_permissions=True))
		doc = frappe.get_doc("Branch", branch)
		panel = get_branch_tax_panel(doc.company, doc.country_code, branch=branch)
		self.assertEqual(panel["kind"], "plugin")
