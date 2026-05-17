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


class TestBranchETASettings(FrappeTestCase):
	def test_branch_settings_roundtrip(self):
		co = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
		if not co:
			return
		branch_name = f"ETA-TEST-{frappe.generate_hash(length=6)}"
		branch = frappe.get_doc(
			{
				"doctype": "Branch",
				"company": co,
				"branch_name": "ETA Test Branch",
				"branch_code": frappe.generate_hash(length=4).upper()[:4],
				"status": "Active",
				"eta_ereceipt_enabled": 1,
				"eta_receipt_environment": "preprod",
				"eta_receipt_base_url": "https://api.preprod.invoicing.eta.gov.eg",
				"eta_receipt_client_id": "receipt-client",
				"eta_receipt_client_secret": "receipt-secret",
				"eta_receipt_rin": "123456789",
				"eta_activity_code": "4620",
				"eta_pos_device_serial": "DEV-TEST-01",
				"eta_einvoice_enabled": 1,
				"eta_invoice_environment": "preprod",
				"eta_invoice_client_id": "invoice-client",
				"eta_invoice_client_secret": "invoice-secret",
				"eta_invoice_rin": "123456789",
				"eta_signer_mode": "remote",
			}
		)
		branch.insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("Branch", branch.name, force=1, ignore_permissions=True))

		receipt_settings = get_eta_branch_settings(branch.name, kind=RECEIPT_KIND)
		self.assertEqual(receipt_settings.rin, "123456789")
		self.assertEqual(receipt_settings.eta_client_id, "receipt-client")
		invoice_settings = get_eta_branch_settings(branch.name, kind=INVOICE_KIND)
		self.assertEqual(invoice_settings.eta_client_id, "invoice-client")

		frappe.db.set_value("Branch", branch.name, "eta_require_einvoice_before_si_submit", 1)
		self.assertTrue(branch_requires_einvoice_before_submit(branch.name))
