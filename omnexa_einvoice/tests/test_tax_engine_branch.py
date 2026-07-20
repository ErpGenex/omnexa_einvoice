# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.branch_validate import validate_branch_tax_country


class TestTaxEngineBranch(FrappeTestCase):
	def test_sa_branch_doc_sets_zatca_provider(self):
		branch = frappe.new_doc("Branch")
		branch.country_code = "SA"
		validate_branch_tax_country(branch)
		self.assertEqual(branch.tax_provider, "einvoice_zatca")

	def test_eg_branch_doc_sets_eta_provider(self):
		branch = frappe.new_doc("Branch")
		branch.country_code = "EG"
		validate_branch_tax_country(branch)
		self.assertEqual(branch.tax_provider, "einvoice_eta")

	def test_colombia_iso_code(self):
		branch = frappe.new_doc("Branch")
		branch.country_code = "CO"
		validate_branch_tax_country(branch)
		self.assertEqual(branch.country_iso, "CO")
		self.assertIn("CO —", branch.country_code)
		self.assertEqual(branch.tax_provider, "einvoice_co")

	def test_colombia_select_label(self):
		branch = frappe.new_doc("Branch")
		branch.country_code = "CO — Colombia"
		validate_branch_tax_country(branch)
		self.assertEqual(branch.country_iso, "CO")
		self.assertIn("CO —", branch.country_code)
		self.assertEqual(branch.tax_provider, "einvoice_co")
