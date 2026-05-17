# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import unittest
from unittest.mock import patch

from omnexa_einvoice.e_invoice.auto_submit import (
	SUBMISSION_MODE_LIVE,
	normalize_submission_mode,
	process_branch_einvoice_batch,
)
from omnexa_einvoice.eta_invoice import _default_delivery_block


class TestEInvoiceAutoSubmit(unittest.TestCase):
	def test_normalize_submission_mode(self):
		self.assertEqual(normalize_submission_mode("Live"), SUBMISSION_MODE_LIVE)
		self.assertEqual(normalize_submission_mode("BATCH"), "batch")
		self.assertEqual(normalize_submission_mode(""), "manual")

	def test_delivery_block_has_compliance_fields(self):
		d = _default_delivery_block()
		self.assertIn("netWeight", d)
		self.assertIn("countryOfOrigin", d)
		self.assertIn("terms", d)

	def test_batch_skips_signing_agent_branch(self):
		branch = "TEST-BATCH-SKIP"
		if not __import__("frappe").db.exists("Branch", branch):
			self.skipTest("fixture branch missing")
		with patch(
			"omnexa_einvoice.e_invoice.auto_submit.branch_submission_mode",
			return_value="batch",
		):
			with patch(
				"omnexa_einvoice.e_invoice.auto_submit.live_send_requires_browser",
				return_value=True,
			):
				count = process_branch_einvoice_batch(branch)
		self.assertEqual(count, 0)
