# Copyright (c) 2026, Omnexa and contributors
# License: MIT

from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.e_invoice.usb_session import normalize_browser_agent_url, use_browser_pin_for_usb


class TestUsbAgentUrl(FrappeTestCase):
	def test_normalize_browser_agent_url_local(self):
		self.assertEqual(
			normalize_browser_agent_url("http://127.0.0.1:5002"),
			"http://127.0.0.1:5002",
		)

	def test_normalize_browser_agent_url_cloud_misconfig(self):
		self.assertEqual(
			normalize_browser_agent_url("http://10.0.0.5:5002"),
			"http://127.0.0.1:5002",
		)

	def test_use_browser_pin_for_usb_without_request(self):
		self.assertFalse(use_browser_pin_for_usb())
