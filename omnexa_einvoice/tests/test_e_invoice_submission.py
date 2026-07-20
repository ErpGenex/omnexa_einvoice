# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
	_recover_ereceipt_from_hub_queue,
	dispatch_submission,
	get_cloud_signing_bridge_status,
)
from omnexa_einvoice.tests.test_helpers import create_eta_branch, get_or_create_test_company, stub_submission_fields


class TestEInvoiceSubmission(FrappeTestCase):
	def test_cloud_signing_bridge_status_empty_branch(self):
		out = get_cloud_signing_bridge_status("")
		self.assertFalse(out.get("ok"))
		self.assertTrue(any(c.get("step") == "branch" for c in out.get("checks") or []))
		self.assertGreaterEqual(len(out.get("flow_steps") or []), 4)

	def test_stub_dispatch_sets_queued(self):
		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "User",
				"reference_name": frappe.session.user,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
				**stub_submission_fields()}
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
				**stub_submission_fields()}
		)
		doc.insert()
		dispatch_submission(doc.name)
		with self.assertRaises(ValidationError):
			dispatch_submission(doc.name)

	def _ereceipt_si_ref(self) -> tuple[str, str] | None:
		si = frappe.db.get_value(
			"Sales Invoice", {"docstatus": 1, "eta_billing_type": "E-Receipt"
	}, "name"
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
				"operation": "submit"
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
				"integration_message": "Queued for ETA submit"
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
		co = get_or_create_test_company()
		branch_name = create_eta_branch(co, ereceipt=True, einvoice=True)
		self.addCleanup(lambda: frappe.delete_doc("Branch", branch_name, force=1, ignore_permissions=True))

		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"company": co,
				"branch": branch_name,
				"adapter_name": "einvoice_eta",
				"document_type": "invoice",
				"operation": "submit",
				"submission_channel": "API",
				"submission_kind": "E-Invoice"
	}
		)
		doc._merge_branch_defaults()
		extra = json.loads(doc.extra_json or "{}")
		self.assertEqual(extra.get("taxpayer_rin"), "123456789")
		self.assertEqual(extra.get("signer_mode"), "remote")
		self.assertEqual(extra.get("branch"), branch_name)
