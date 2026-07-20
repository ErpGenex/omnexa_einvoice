# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.einvoice_print.context import get_sales_invoice_print_context
from omnexa_einvoice.einvoice_print.design_catalog import all_country_codes_for_print, get_print_design
from omnexa_einvoice.einvoice_print.resolve import print_format_name_for_country


class TestEInvoicePrint(FrappeTestCase):
	def test_print_design_per_country(self):
		for code in ("EG", "SA", "DE", "AE", "MX"):
			design = get_print_design(code)
			self.assertEqual(design.country_code, code)
			self.assertTrue(design.primary_color.startswith("#"))

	def test_print_formats_installed(self):
		codes = all_country_codes_for_print()
		self.assertGreater(len(codes), 30)
		for code in codes:
			name = print_format_name_for_country(code)
			self.assertTrue(
				frappe.db.exists("Print Format", name),
				msg=f"Missing Print Format: {name}",
			)

	def test_print_context_keys(self):
		si = frappe.get_all("Sales Invoice", limit=1)
		if not si:
			self.skipTest("No Sales Invoice in site")
		ctx = get_sales_invoice_print_context(si[0].name)
		for key in ("country_code", "design_dict", "seller", "buyer", "lines", "tax"):
			self.assertIn(key, ctx)
