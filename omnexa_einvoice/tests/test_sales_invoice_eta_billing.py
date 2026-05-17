# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.e_invoice_hooks import sales_invoice_before_submit
from omnexa_einvoice.sales_invoice_eta import (
	ETA_BILLING_EINVOICE,
	ETA_BILLING_REGULAR,
	ETA_BILLING_ERECEIPT,
	get_eta_billing_type,
	resolve_submission_kind_for_sales_invoice,
	sales_invoice_is_eta_billing,
)


class TestSalesInvoiceEtaBilling(FrappeTestCase):
	def test_billing_type_defaults_regular(self):
		doc = frappe._dict(doctype="Sales Invoice", eta_billing_type="Regular")
		self.assertEqual(get_eta_billing_type(doc), ETA_BILLING_REGULAR)
		self.assertFalse(sales_invoice_is_eta_billing(doc))

	def test_resolve_submission_kind(self):
		doc = frappe._dict(doctype="Sales Invoice", eta_billing_type=ETA_BILLING_ERECEIPT)
		self.assertEqual(resolve_submission_kind_for_sales_invoice(doc), "E-Receipt")
		doc.eta_billing_type = ETA_BILLING_EINVOICE
		self.assertEqual(resolve_submission_kind_for_sales_invoice(doc), "E-Invoice")

	def test_resolve_raises_for_regular(self):
		doc = frappe._dict(doctype="Sales Invoice", eta_billing_type=ETA_BILLING_REGULAR)
		doc.meta = frappe.get_meta("Sales Invoice")
		with self.assertRaises(ValidationError):
			resolve_submission_kind_for_sales_invoice(doc)

	def test_gate_skips_regular_even_when_branch_requires(self):
		co = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
		if not co or not frappe.get_meta("Sales Invoice").has_field("eta_billing_type"):
			return
		branch = frappe.get_doc(
			{
				"doctype": "Branch",
				"company": co,
				"branch_name": "ETA Billing Test",
				"branch_code": frappe.generate_hash(length=4).upper()[:4],
				"status": "Active",
				"eta_einvoice_enabled": 1,
				"eta_invoice_rin": "1",
				"eta_invoice_client_id": "c",
				"eta_invoice_client_secret": "s",
				"eta_require_einvoice_before_si_submit": 1,
			}
		).insert(ignore_permissions=True)
		try:
			doc = frappe._dict(
				doctype="Sales Invoice",
				name="ETA-BILL-REG",
				company=co,
				branch=branch.name,
				eta_billing_type=ETA_BILLING_REGULAR,
				flags=frappe._dict(),
			)
			sales_invoice_before_submit(doc, None)
		finally:
			branch.delete(ignore_permissions=True)
