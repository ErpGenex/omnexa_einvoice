# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from unittest.mock import patch

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
	validate_sales_invoice_eta_billing_type,
)
from omnexa_einvoice.tests.test_helpers import create_eta_branch, get_or_create_test_company


class TestSalesInvoiceEtaBilling(FrappeTestCase):
	def test_billing_type_defaults_regular(self):
		doc = frappe._dict(doctype="Sales Invoice", eta_billing_type="Regular")
		self.assertEqual(get_eta_billing_type(doc), ETA_BILLING_REGULAR)
		self.assertFalse(sales_invoice_is_eta_billing(doc))

	def test_non_egypt_branch_forces_regular_billing(self):
		if not frappe.get_meta("Sales Invoice").has_field("eta_billing_type"):
			return
		doc = frappe._dict(
			doctype="Sales Invoice",
			branch="TEST-AR",
			eta_billing_type=ETA_BILLING_EINVOICE,
		)
		doc.meta = frappe.get_meta("Sales Invoice")
		with patch("omnexa_einvoice.sales_invoice_eta.sales_invoice_is_egypt_branch", return_value=False):
			validate_sales_invoice_eta_billing_type(doc)
			self.assertEqual(doc.eta_billing_type, ETA_BILLING_REGULAR)
			self.assertEqual(get_eta_billing_type(doc), ETA_BILLING_REGULAR)

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
		co = get_or_create_test_company()
		if not frappe.get_meta("Sales Invoice").has_field("eta_billing_type"):
			return
		branch_name = create_eta_branch(
			co, einvoice=True, require_einvoice_before_si=1
		)
		try:
			doc = frappe._dict(
				doctype="Sales Invoice",
				name="ETA-BILL-REG",
				company=co,
				branch=branch_name,
				eta_billing_type=ETA_BILLING_REGULAR,
				flags=frappe._dict(),
			)
			sales_invoice_before_submit(doc, None)
		finally:
			frappe.delete_doc("Branch", branch_name, force=1, ignore_permissions=True)
