# Copyright (c) 2026, Omnexa and contributors
# License: MIT

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.einvoice_console import get_einvoice_queue
from omnexa_einvoice.ereceipt_console import _match_eta_status


class TestEInvoiceConsole(FrappeTestCase):
	def test_match_eta_status_signed_ready(self):
		sub = frappe._dict(status="Signed")
		self.assertTrue(_match_eta_status(sub, "ready"))
		self.assertFalse(_match_eta_status(sub, "pending"))

	def test_get_einvoice_queue_returns_list(self):
		rows = get_einvoice_queue(limit=10)
		self.assertIsInstance(rows, list)
