# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.e_invoice_hooks import sales_invoice_before_submit


class TestSalesInvoiceEinvoiceGate(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._co = frappe.db.get_value("Company", {}, "name", order_by="creation asc")

	def tearDown(self):
		if self._co:
			frappe.db.delete("Tax Authority Profile", {"company": self._co})
			frappe.db.delete("Signing Profile", {"company": self._co})
			frappe.db.delete("E Invoice Submission", {"reference_name": ["like", "EINV-GATE-%"]})
		super().tearDown()

	def test_hook_skips_when_profile_not_required(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		frappe.get_doc(
			{
				"doctype": "Tax Authority Profile",
				"company": self._co,
				"default_einvoice_adapter": "einvoice_stub",
				"require_e_invoice_for_sales_invoice": 0,
			}
		).insert(ignore_permissions=True)
		doc = frappe._dict(
			doctype="Sales Invoice",
			name="EINV-GATE-001",
			company=self._co,
			flags=frappe._dict(),
		)
		sales_invoice_before_submit(doc, None)

	def test_hook_blocks_when_required_without_submission(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		frappe.get_doc(
			{
				"doctype": "Tax Authority Profile",
				"company": self._co,
				"default_einvoice_adapter": "einvoice_stub",
				"require_e_invoice_for_sales_invoice": 1,
			}
		).insert(ignore_permissions=True)
		doc = frappe._dict(
			doctype="Sales Invoice",
			name="EINV-GATE-002",
			company=self._co,
			flags=frappe._dict(),
		)
		with self.assertRaises(ValidationError):
			sales_invoice_before_submit(doc, None)

	def test_hook_skips_when_ignore_e_invoice_requirement_flag(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		frappe.get_doc(
			{
				"doctype": "Tax Authority Profile",
				"company": self._co,
				"default_einvoice_adapter": "einvoice_stub",
				"require_e_invoice_for_sales_invoice": 1,
			}
		).insert(ignore_permissions=True)
		doc = frappe._dict(
			doctype="Sales Invoice",
			name="EINV-GATE-IGNORE",
			company=self._co,
			flags=frappe._dict(ignore_e_invoice_requirement=True),
		)
		sales_invoice_before_submit(doc, None)

	def test_hook_allows_when_submission_dispatched(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		frappe.get_doc(
			{
				"doctype": "Tax Authority Profile",
				"company": self._co,
				"default_einvoice_adapter": "einvoice_stub",
				"require_e_invoice_for_sales_invoice": 1,
			}
		).insert(ignore_permissions=True)
		si_name = "EINV-GATE-003"
		sub = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "Sales Invoice",
				"reference_name": si_name,
				"company": self._co,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
			}
		)
		# No real Sales Invoice row in DB for this test name; skip custom validate + link check.
		sub.flags.ignore_validate = True
		sub.insert(ignore_permissions=True, ignore_links=True)
		sub_name = frappe.db.get_value("E Invoice Submission", {"reference_name": si_name}, "name")
		frappe.db.set_value("E Invoice Submission", sub_name, "status", "Queued")
		doc = frappe._dict(
			doctype="Sales Invoice",
			name=si_name,
			company=self._co,
			flags=frappe._dict(),
		)
		sales_invoice_before_submit(doc, None)

	def test_hook_allows_when_submission_completed(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		frappe.get_doc(
			{
				"doctype": "Tax Authority Profile",
				"company": self._co,
				"default_einvoice_adapter": "einvoice_stub",
				"require_e_invoice_for_sales_invoice": 1,
			}
		).insert(ignore_permissions=True)
		si_name = "EINV-GATE-004"
		sub = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "Sales Invoice",
				"reference_name": si_name,
				"company": self._co,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
			}
		)
		sub.flags.ignore_validate = True
		sub.insert(ignore_permissions=True, ignore_links=True)
		sub_name = frappe.db.get_value("E Invoice Submission", {"reference_name": si_name}, "name")
		frappe.db.set_value("E Invoice Submission", sub_name, "status", "Completed")
		doc = frappe._dict(
			doctype="Sales Invoice",
			name=si_name,
			company=self._co,
			flags=frappe._dict(),
		)
		sales_invoice_before_submit(doc, None)
