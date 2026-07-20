# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.country_catalog import (
	branch_country_options,
	country_display_name,
	normalize_country_code,
)


class TestCountryDisplayName(FrappeTestCase):
	def test_normalize_from_label(self):
		self.assertEqual(normalize_country_code("DE — Germany"), "DE")
		self.assertEqual(normalize_country_code("SA"), "SA")

	def test_display_name_known(self):
		self.assertEqual(country_display_name("DE", lang="en"), "Germany")
		self.assertEqual(country_display_name("EG", lang="en"), "Egypt")
		self.assertEqual(country_display_name("EG", lang="ar"), "مصر")

	def test_branch_select_options_one_row_per_country(self):
		opts = branch_country_options().split("\n")
		self.assertEqual(len(opts), len(set(opts)))
		self.assertTrue(any(line.startswith("CO —") for line in opts))
		self.assertNotIn("CO", opts)
