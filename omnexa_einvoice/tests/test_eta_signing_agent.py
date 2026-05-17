# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import unittest
from unittest.mock import MagicMock, patch

import frappe

from omnexa_einvoice.eta_invoice import build_usb_signing_test_document, validate_invoice_document
from omnexa_einvoice.eta_signing_agent import (
	is_local_signing_agent_url,
	prepare_branch_usb_signing_test,
	sign_invoice_via_signing_agent,
	test_signing_agent_connection,
)


class TestETASigningAgent(unittest.TestCase):
	def test_sign_invoice_via_agent_success(self):
		doc = {"documentType": "I", "internalID": "INV-1"}
		mock_resp = MagicMock()
		mock_resp.status_code = 200
		mock_resp.json.return_value = {
			"success": True,
			"signatures": [{"signatureType": "I", "value": "c2lnbmF0dXJl"}],
		}
		with patch("omnexa_einvoice.eta_signing_agent.requests.post", return_value=mock_resp) as post:
			sig = sign_invoice_via_signing_agent(doc, agent_url="http://127.0.0.1:5002", pin="1234")
		self.assertEqual(sig, "c2lnbmF0dXJl")
		post.assert_called_once()
		payload = post.call_args.kwargs.get("json") or post.call_args[1].get("json")
		self.assertEqual(payload["invoice"]["internalID"], "INV-1")
		self.assertNotIn("signatures", payload["invoice"])
		self.assertEqual(payload["pin"], "1234")

	def test_sign_invoice_via_agent_failure(self):
		mock_resp = MagicMock()
		mock_resp.status_code = 500
		mock_resp.json.return_value = {"success": False, "message": "Token not found"}
		mock_resp.text = ""
		with patch("omnexa_einvoice.eta_signing_agent.requests.post", return_value=mock_resp):
			with self.assertRaises(frappe.ValidationError):
				sign_invoice_via_signing_agent({"internalID": "x"}, agent_url="http://127.0.0.1:5002")

	def test_usb_signing_test_document_validates(self):
		branch = frappe.db.get_value(
			"Branch", {"eta_einvoice_enabled": 1, "eta_invoice_rin": ["!=", ""]}, "name"
		)
		if not branch:
			self.skipTest("No branch with e-Invoice RIN configured")
		doc = build_usb_signing_test_document(branch)
		validate_invoice_document(doc, strict_datetime=False)
		self.assertTrue(str(doc.get("internalID") or "").startswith("OMNEXA-TEST-"))
		self.assertEqual(len(doc.get("invoiceLines") or []), 1)

	def test_localhost_health_skips_server_ping_on_linux(self):
		self.assertTrue(is_local_signing_agent_url("http://127.0.0.1:5002"))
		branch = frappe.db.get_value("Branch", {"eta_einvoice_enabled": 1}, "name")
		if not branch:
			self.skipTest("No e-Invoice branch")
		with patch("omnexa_einvoice.eta_signing_agent.platform.system", return_value="Linux"):
			with patch("omnexa_einvoice.eta_signing_agent.signing_agent_health") as health:
				from omnexa_einvoice.eta_signing_agent import run_branch_usb_signing_test_on_server

				result = run_branch_usb_signing_test_on_server(branch)
		health.assert_not_called()
		self.assertTrue(result.get("browser_sign_required"))
		if result.get("ok"):
			ping = [c for c in result["checks"] if c.get("step") == "agent_ping"]
			self.assertTrue(ping and ping[0].get("ok"))

	def test_agent_sign_payload_includes_pin(self):
		branch = frappe.db.get_value("Branch", {"eta_einvoice_enabled": 1}, "name")
		if not branch:
			self.skipTest("No e-Invoice branch")
		from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
			build_agent_sign_payload,
			get_agent_sign_payload_for_branch_test,
		)

		result = get_agent_sign_payload_for_branch_test(branch)
		payload = result.get("agent_payload") or {}
		self.assertTrue((payload.get("pin") or "").strip())
		self.assertTrue((payload.get("usb_token_pin") or "").strip())
		self.assertTrue((payload.get("pin_b64") or "").strip())
		self.assertEqual(payload.get("token_type"), "epass2003")
		self.assertIn("invoice", payload)

	def test_prepare_branch_usb_signing_test_returns_checks(self):
		branch = frappe.db.get_value("Branch", {"eta_einvoice_enabled": 1}, "name")
		if not branch:
			self.skipTest("No e-Invoice branch")
		result = prepare_branch_usb_signing_test(branch)
		self.assertIn("checks", result)
		self.assertIsInstance(result["checks"], list)
		if result.get("ok"):
			self.assertTrue(result.get("usb_pin_b64"))
			self.assertIn("document", result)
