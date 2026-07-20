# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from omnexa_einvoice.tax_engine.plugin.pipeline import execute_country_phase2_submit, run_country_phase2
from omnexa_einvoice.tax_engine.plugin.queue import process_phase2_job


class TestTaxPhase2Queue(FrappeTestCase):
	def test_async_phase2_passes_phase1_to_enqueue(self):
		phase1 = {
			"ok": True,
			"uuid": "test-uuid",
			"hash_b64": "abc",
			"signed_xml": "<Invoice/>",
			"framework": "PEPPOL-UBL",
			"log_name": None,
			"document": {"company": "Test Co"},
		}
		payload = {"reference_name": "SI-PH2-Q", "company": "Test Co"}

		with patch(
			"omnexa_einvoice.tax_engine.plugin.pipeline.run_country_phase1",
			return_value=phase1,
		) as mock_p1, patch(
			"omnexa_einvoice.tax_engine.plugin.queue.enqueue_phase2",
			return_value="job-1",
		) as mock_enqueue:
			result = run_country_phase2(payload, country_code="DE", sync=False)

		mock_p1.assert_called_once()
		mock_enqueue.assert_called_once()
		_, kwargs = mock_enqueue.call_args
		self.assertEqual(kwargs.get("phase1"), phase1)
		self.assertEqual(result.get("status"), "queued")

	def test_process_phase2_job_skips_phase1_when_provided(self):
		phase1 = {
			"uuid": "u1",
			"hash_b64": "h1",
			"signed_xml": "<x/>",
			"framework": "PEPPOL-UBL",
			"log_name": None,
			"document": {},
		}
		payload = {"reference_name": "SI-JOB", "company": "Test Co"}

		with patch(
			"omnexa_einvoice.tax_engine.plugin.pipeline.run_country_phase1",
		) as mock_p1, patch(
			"omnexa_einvoice.tax_engine.plugin.pipeline.execute_country_phase2_submit",
			return_value={"ok": True, "status": "submitted"},
		) as mock_submit:
			process_phase2_job(payload, "DE", phase1=phase1)

		mock_p1.assert_not_called()
		mock_submit.assert_called_once_with(payload, country_code="DE", phase1=phase1)

	def test_execute_phase2_submit_uses_phase1_fields(self):
		phase1 = {
			"uuid": "u2",
			"hash_b64": "h2",
			"signed_xml": "<Invoice/>",
			"framework": "CFDI-4.0",
			"log_name": None,
			"document": {"company": "Test Co"},
		}
		frappe.flags.in_test = True

		with patch(
			"omnexa_einvoice.tax_engine.plugin.api_client.submit_invoice_api",
		) as mock_api:
			result = execute_country_phase2_submit(
				{"company": "Test Co"},
				country_code="MX",
				phase1=phase1,
			)

		mock_api.assert_not_called()
		self.assertTrue(result.get("ok"))
		self.assertEqual((result.get("api") or {}).get("mock"), True)

	def test_international_hook_enqueues_once(self):
		doc = frappe._dict(
			doctype="Sales Invoice",
			docstatus=1,
			name="SI-AUTO-1",
			company="Test Co",
			branch="BR-DE",
		)
		with patch(
			"omnexa_einvoice.international_tax_hooks.resolve_branch_for_document",
			return_value="BR-DE",
		), patch(
			"omnexa_einvoice.international_tax_hooks.is_egypt_branch",
			return_value=False,
		), patch(
			"omnexa_einvoice.international_tax_hooks.resolve_tax_provider_for_branch",
			return_value={"country_code": "DE"},
		), patch(
			"omnexa_einvoice.international_tax_hooks.get_country_tax_settings",
			return_value=frappe._dict(enabled=1, auto_submit_on_si_submit=1),
		), patch(
			"omnexa_einvoice.international_tax_hooks.enqueue_phase2",
		) as mock_enqueue, patch(
			"omnexa_einvoice.international_tax_hooks.frappe.enqueue",
		) as mock_frappe_enqueue:
			from omnexa_einvoice.international_tax_hooks import sales_invoice_international_tax_on_submit

			sales_invoice_international_tax_on_submit(doc)

		mock_enqueue.assert_called_once()
		mock_frappe_enqueue.assert_not_called()
