# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.ereceipt_console import _match_eta_status, _parse_names


class TestEreceiptConsole(FrappeTestCase):
	def test_parse_names(self):
		self.assertEqual(_parse_names('["A","B"]'), ["A", "B"])
		self.assertEqual(_parse_names("INV-1"), ["INV-1"])

	def test_match_eta_status(self):
		sub = frappe._dict(status="Signed")
		self.assertTrue(_match_eta_status(sub, "ready"))
		self.assertFalse(_match_eta_status(sub, "completed"))
		self.assertTrue(_match_eta_status(None, "pending"))
