# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import json

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import dispatch_submission


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

	def test_merge_company_profiles_into_extra_json(self):
		co = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
		if not co or not frappe.db.exists("DocType", "Tax Authority Profile"):
			return

		def _cleanup_profiles():
			frappe.db.delete("Tax Authority Profile", {"company": co})
			frappe.db.delete("Signing Profile", {"company": co})

		self.addCleanup(_cleanup_profiles)
		_cleanup_profiles()

		frappe.get_doc(
			{
				"doctype": "Tax Authority Profile",
				"company": co,
				"default_einvoice_adapter": "einvoice_stub",
				"taxpayer_registration_id": "EINV-MERGE-TIN",
				"zatca_reporting_phase": "phase1",
				"require_e_invoice_for_sales_invoice": 0,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Signing Profile",
				"company": co,
				"default_signer_mode": "remote",
			}
		).insert(ignore_permissions=True)

		doc = frappe.get_doc(
			{
				"doctype": "E Invoice Submission",
				"reference_doctype": "User",
				"reference_name": frappe.session.user,
				"company": co,
				"adapter_name": "einvoice_stub",
				"document_type": "invoice",
				"operation": "submit",
			}
		)
		doc.insert(ignore_permissions=True)
		doc.reload()
		extra = json.loads(doc.extra_json or "{}")
		self.assertEqual(extra.get("taxpayer_rin"), "EINV-MERGE-TIN")
		self.assertEqual(extra.get("phase"), "phase1")
		self.assertEqual(extra.get("signer_mode"), "remote")
