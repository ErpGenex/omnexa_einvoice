# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.branch_eta import (
	INVOICE_KIND,
	RECEIPT_KIND,
	branch_requires_einvoice_before_submit,
	get_eta_branch_settings,
)
from omnexa_einvoice.tests.test_helpers import create_eta_branch, get_or_create_test_company


class TestBranchETASettings(FrappeTestCase):
	def test_branch_settings_roundtrip(self):
		co = get_or_create_test_company()
		suffix = frappe.generate_hash(length=6)
		branch_name = create_eta_branch(
			co,
			suffix,
			ereceipt=True,
			einvoice=True,
		)
		self.addCleanup(
			lambda: frappe.delete_doc("Branch", branch_name, force=1, ignore_permissions=True)
		)

		receipt_settings = get_eta_branch_settings(branch_name, kind=RECEIPT_KIND)
		self.assertEqual(receipt_settings.rin, "123456789")
		self.assertEqual(receipt_settings.eta_client_id, f"rcpt-{suffix}")
		invoice_settings = get_eta_branch_settings(branch_name, kind=INVOICE_KIND)
		self.assertEqual(invoice_settings.eta_client_id, f"inv-{suffix}")

		frappe.db.set_value("Branch", branch_name, "eta_require_einvoice_before_si_submit", 1)
		self.assertTrue(branch_requires_einvoice_before_submit(branch_name))

	def test_branch_save_without_usb_pin_when_signing_agent(self):
		"""USB PIN must not block Branch save — only Sign/Send on e-invoices."""
		co = get_or_create_test_company()
		branch_name = create_eta_branch(co, einvoice=True, signing_agent=True, usb_pin="")
		self.addCleanup(
			lambda: frappe.delete_doc("Branch", branch_name, force=1, ignore_permissions=True)
		)
		branch = frappe.get_doc("Branch", branch_name)
		branch.branch_name = "ETA USB PIN Test Updated"
		branch.save(ignore_permissions=True)
