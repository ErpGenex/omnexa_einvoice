# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
	_recover_ereceipt_from_hub_queue,
	dispatch_submission,
)


class TestEInvoiceSubmission(FrappeTestCase):
	def test_stub_dispatch_sets_queued(self):
		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "User",
				"reference_name": frappe.session.user,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
			}
		)
		doc.insert()
		dispatch_submission(doc.name)
		doc.reload()
		self.assertEqual(doc.status, "Queued")
		self.assertTrue((doc.provider_reference or "").startswith("EINV-"))

	def test_second_dispatch_blocked(self):
		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "User",
				"reference_name": frappe.session.user,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
			}
		)
		doc.insert()
		dispatch_submission(doc.name)
		with self.assertRaises(ValidationError):
			dispatch_submission(doc.name)

	def _ereceipt_si_ref(self) -> tuple[str, str] | None:
		si = frappe.db.get_value(
			"Sales Invoice", {"docstatus": 1, "eta_billing_type": "E-Receipt"}, "name"
		)
		if not si:
			return None
		return "Sales Invoice", si

	def test_ereceipt_dispatch_blocked(self):
		ref = self._ereceipt_si_ref()
		if not ref:
			self.skipTest("No submitted E-Receipt Sales Invoice on site")
		doctype, docname = ref
		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": doctype,
				"reference_name": docname,
				"adapter_name": "einvoice_eta",
				"submission_kind": "E-Receipt",
				"document_type": "receipt",
				"operation": "submit",
			}
		)
		doc.insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("E Invoice Submission", doc.name, force=1, ignore_permissions=True)
		)
		with self.assertRaises(ValidationError):
			dispatch_submission(doc.name)

	def test_recover_ereceipt_from_hub_queue(self):
		ref = self._ereceipt_si_ref()
		if not ref:
			self.skipTest("No submitted E-Receipt Sales Invoice on site")
		doctype, docname = ref
		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": doctype,
				"reference_name": docname,
				"adapter_name": "einvoice_eta",
				"submission_kind": "E-Receipt",
				"document_type": "receipt",
				"operation": "submit",
				"status": "Queued",
				"provider_reference": "ETA-SUBMIT-RECEIPT-X",
				"integration_message": "Queued for ETA submit",
			}
		)
		doc.insert(ignore_permissions=True)
		self.addCleanup(
			lambda: frappe.delete_doc("E Invoice Submission", doc.name, force=1, ignore_permissions=True)
		)
		_recover_ereceipt_from_hub_queue(doc)
		doc.reload()
		self.assertEqual(doc.status, "Draft")
		self.assertEqual(doc.provider_reference, "")

	def test_merge_branch_settings_into_extra_json(self):
		co = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
		if not co:
			return
		branch = frappe.get_doc(
			{
				"doctype": "Branch",
				"company": co,
				"branch_name": "Merge ETA",
				"branch_code": frappe.generate_hash(length=4).upper()[:4],
				"status": "Active",
				"eta_ereceipt_enabled": 1,
				"eta_receipt_rin": "EINV-MERGE-TIN",
				"eta_receipt_client_id": "rc",
				"eta_receipt_client_secret": "rs",
				"eta_pos_device_serial": "P1",
				"eta_activity_code": "1",
				"eta_einvoice_enabled": 1,
				"eta_invoice_rin": "EINV-MERGE-TIN",
				"eta_invoice_client_id": "ic",
				"eta_invoice_client_secret": "is",
				"eta_signer_mode": "remote",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("Branch", branch.name, force=1, ignore_permissions=True))

		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "User",
				"reference_name": frappe.session.user,
				"company": co,
				"branch": branch.name,
				"adapter_name": "einvoice_eta",
				"document_type": "invoice",
				"operation": "submit",
			}
		)
		doc.insert(ignore_permissions=True)
		doc.reload()
		extra = json.loads(doc.extra_json or "{}")
		self.assertEqual(extra.get("taxpayer_rin"), "EINV-MERGE-TIN")
		self.assertEqual(extra.get("signer_mode"), "remote")
		self.assertEqual(extra.get("branch"), branch.name)
