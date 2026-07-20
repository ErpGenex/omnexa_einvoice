# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import unittest

import frappe

from omnexa_einvoice.eta_invoice_signing import assert_eta_invoice_document_shape


class TestETAPathSeparation(unittest.TestCase):
	def test_receipt_json_rejected_by_invoice_signing_guard(self):
		receipt_like = {"header": {"uuid": "x"}, "seller": {"rin": "1"}}
		with self.assertRaises(frappe.ValidationError):
			assert_eta_invoice_document_shape(receipt_like)

	def test_ereceipt_module_has_no_invoice_signing_import(self):
		import omnexa_einvoice.eta_ereceipt_submission as mod

		source = open(mod.__file__, encoding="utf-8").read()
		self.assertNotIn("from omnexa_einvoice.eta_invoice_signing", source)
		self.assertNotIn("from omnexa_einvoice.eta_signing_agent", source)
