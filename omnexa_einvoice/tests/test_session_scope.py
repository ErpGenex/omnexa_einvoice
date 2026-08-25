# Copyright (c) 2026, Omnexa
from frappe.tests.utils import FrappeTestCase


class TestWave4SessionScope(FrappeTestCase):
	def test_vertical_dashboard(self):
		from omnexa_einvoice.vertical_dashboard_api import get_vertical_dashboard

		out = get_vertical_dashboard()
		self.assertEqual(out.get("app"), "omnexa_einvoice")
		self.assertIn("uses_session_context", out)
