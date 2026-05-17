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
		self._branch = None

	def _ensure_branch(self, require_einvoice: int = 0):
		if not self._co:
			return None
		if self._branch and frappe.db.exists("Branch", self._branch):
			frappe.db.set_value(
				"Branch",
				self._branch,
				{
					"eta_ereceipt_enabled": 1,
					"eta_receipt_rin": "999",
					"eta_receipt_client_id": "rc",
					"eta_receipt_client_secret": "rs",
					"eta_pos_device_serial": "POS1",
					"eta_activity_code": "1",
					"eta_einvoice_enabled": 1,
					"eta_invoice_rin": "999",
					"eta_invoice_client_id": "ic",
					"eta_invoice_client_secret": "is",
					"eta_require_einvoice_before_si_submit": require_einvoice,
				},
			)
			return self._branch
		self._branch = frappe.get_doc(
			{
				"doctype": "Branch",
				"company": self._co,
				"branch_name": "EINV Gate Test",
				"branch_code": frappe.generate_hash(length=4).upper()[:4],
				"status": "Active",
				"eta_ereceipt_enabled": 1,
				"eta_receipt_rin": "999",
				"eta_receipt_client_id": "rc",
				"eta_receipt_client_secret": "rs",
				"eta_pos_device_serial": "POS1",
				"eta_activity_code": "1",
				"eta_einvoice_enabled": 1,
				"eta_invoice_rin": "999",
				"eta_invoice_client_id": "ic",
				"eta_invoice_client_secret": "is",
				"eta_require_einvoice_before_si_submit": require_einvoice,
			}
		).insert(ignore_permissions=True).name
		return self._branch

	def tearDown(self):
		if self._branch:
			frappe.delete_doc("Branch", self._branch, force=1, ignore_permissions=True)
		if self._co:
			frappe.db.delete("E Invoice Submission", {"reference_name": ["like", "EINV-GATE-%"]})
		super().tearDown()

	def test_hook_skips_when_profile_not_required(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		branch = self._ensure_branch(require_einvoice=0)
		doc = frappe._dict(
			doctype="Sales Invoice",
			name="EINV-GATE-001",
			company=self._co,
			branch=branch,
			flags=frappe._dict(),
		)
		sales_invoice_before_submit(doc, None)

	def test_hook_blocks_when_required_without_submission(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		branch = self._ensure_branch(require_einvoice=1)
		doc = frappe._dict(
			doctype="Sales Invoice",
			name="EINV-GATE-002",
			company=self._co,
			branch=branch,
			eta_billing_type="E-Invoice",
			flags=frappe._dict(),
		)
		with self.assertRaises(ValidationError):
			sales_invoice_before_submit(doc, None)

	def test_hook_skips_when_ignore_e_invoice_requirement_flag(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		branch = self._ensure_branch(require_einvoice=1)
		doc = frappe._dict(
			doctype="Sales Invoice",
			name="EINV-GATE-IGNORE",
			company=self._co,
			branch=branch,
			eta_billing_type="E-Invoice",
			flags=frappe._dict(ignore_e_invoice_requirement=True),
		)
		sales_invoice_before_submit(doc, None)

	def test_hook_allows_when_submission_dispatched(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		branch = self._ensure_branch(require_einvoice=1)
		si_name = "EINV-GATE-003"
		sub = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "Sales Invoice",
				"reference_name": si_name,
				"company": self._co,
				"branch": branch,
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
			branch=branch,
			eta_billing_type="E-Invoice",
			flags=frappe._dict(),
		)
		sales_invoice_before_submit(doc, None)

	def test_hook_allows_when_submission_completed(self):
		if not self._co or not frappe.db.exists("DocType", "Sales Invoice"):
			return
		branch = self._ensure_branch(require_einvoice=1)
		si_name = "EINV-GATE-004"
		sub = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "Sales Invoice",
				"reference_name": si_name,
				"company": self._co,
				"branch": branch,
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
			branch=branch,
			eta_billing_type="E-Invoice",
			flags=frappe._dict(),
		)
		sales_invoice_before_submit(doc, None)
