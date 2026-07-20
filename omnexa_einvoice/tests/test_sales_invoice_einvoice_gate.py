# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.e_invoice_hooks import sales_invoice_before_submit
from omnexa_einvoice.tests.test_helpers import create_eta_branch, get_or_create_test_company, stub_submission_fields


class TestSalesInvoiceEinvoiceGate(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._co = get_or_create_test_company()
		self._branch = None
		self._require_einvoice = 0

	def _ensure_branch(self, require_einvoice: int = 0):
		if not self._co:
			return None
		if self._branch and frappe.db.exists("Branch", self._branch):
			if require_einvoice != self._require_einvoice:
				frappe.db.set_value(
					"Branch",
					self._branch,
					"eta_require_einvoice_before_si_submit",
					require_einvoice,
				)
				self._require_einvoice = require_einvoice
			return self._branch
		self._require_einvoice = require_einvoice
		self._branch = create_eta_branch(
			self._co,
			ereceipt=True,
			einvoice=True,
			require_einvoice_before_si=require_einvoice,
		)
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
				"branch": branch,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
				**stub_submission_fields(self._co)}
		)
		# No real Sales Invoice row in DB for this test name; skip custom validate + link check.
		sub.flags.ignore_validate = True
		sub.insert(ignore_permissions=True, ignore_links=True)
		sub_name = frappe.db.get_value("E Invoice Submission", {"reference_name": si_name
	}, "name")
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
				"branch": branch,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
				**stub_submission_fields(self._co)}
		)
		sub.flags.ignore_validate = True
		sub.insert(ignore_permissions=True, ignore_links=True)
		sub_name = frappe.db.get_value("E Invoice Submission", {"reference_name": si_name
	}, "name")
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
