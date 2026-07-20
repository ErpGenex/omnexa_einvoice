# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.branch_tax_connection import (
	get_branch_tax_test_spec,
	test_branch_tax_connection,
)


class TestBranchTaxConnection(FrappeTestCase):
	def test_spec_for_eg_branch(self):
		branch = frappe.get_all(
			"Branch",
			filters={"country_code": "EG"},
			limit=1,
			pluck="name",
		)
		if not branch:
			self.skipTest("No EG branch")
		spec = get_branch_tax_test_spec(branch=branch[0])
		self.assertEqual(spec["country_code"], "EG")
		self.assertIn("ETA", spec["button_label"])

	def test_spec_for_non_eg_branch(self):
		branch = frappe.get_all(
			"Branch",
			filters={"country_iso": ["!=", "EG"]},
			limit=1,
			pluck="name",
		)
		if not branch:
			self.skipTest("No non-EG branch")
		spec = get_branch_tax_test_spec(branch=branch[0])
		iso = frappe.db.get_value("Branch", branch[0], "country_iso")
		self.assertEqual(spec["country_code"], (iso or "").upper())
		self.assertNotIn("ETA", spec["button_label"])

	def test_connection_returns_kind(self):
		branch = frappe.get_all("Branch", limit=1, pluck="name")
		if not branch:
			self.skipTest("No branch")
		out = test_branch_tax_connection(branch=branch[0])
		self.assertIn("kind", out)
		self.assertIn("country_code", out)
