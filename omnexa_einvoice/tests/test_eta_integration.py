# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from omnexa_core.omnexa_core.constants import DOC_STATUS_ACCEPTED, DOC_STATUS_REJECTED
from omnexa_einvoice.eta_integration import (
	apply_eta_poll_to_submission,
	ensure_eta_access_token,
	eta_token_cache_key,
	eta_token_needs_refresh,
	exchange_eta_token,
	get_cached_eta_token_state,
	map_eta_error_to_message,
	normalize_eta_poll_response,
	set_cached_eta_token_state,
)


class TestETAIntegration(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.conf.omnexa_eta_use_stub_token = 1

	def tearDown(self):
		super().tearDown()
		frappe.cache().delete_value(eta_token_cache_key("test-profile"))
		frappe.cache().delete_value(eta_token_cache_key("default"))
		bucket = getattr(frappe.local, "_omnexa_eta_token_bucket", None)
		if isinstance(bucket, dict):
			bucket.pop("test-profile", None)
			bucket.pop("default", None)

	def test_exchange_token_returns_expiring_state(self):
		state = exchange_eta_token("cid", "secret", environment="preprod")
		self.assertIn("access_token", state)
		self.assertIn("expires_at", state)
		self.assertGreater(int(state.get("expires_in") or 0), 0)

	def test_token_cache_refresh_gate(self):
		set_cached_eta_token_state(
			"test-profile",
			{
				"access_token": "tok",
				"expires_in": 60,
				"expires_at": str(add_to_date(now_datetime(), seconds=300)),
			},
		)
		self.assertFalse(eta_token_needs_refresh(get_cached_eta_token_state("test-profile")))

	def test_ensure_eta_access_token_uses_cache(self):
		first = ensure_eta_access_token(
			"test-profile",
			{"client_id": "a", "client_secret": "b"},
		)
		second = ensure_eta_access_token(
			"test-profile",
			{"client_id": "a", "client_secret": "b"},
		)
		self.assertEqual(first, second)

	def test_normalize_poll_maps_valid_status(self):
		poll = normalize_eta_poll_response({"status": "Valid", "uuid": "eta-uuid-1"}, http_status_code=200)
		self.assertEqual(poll["authority_status"], DOC_STATUS_ACCEPTED)
		self.assertEqual(poll["authority_uuid"], "eta-uuid-1")

	def test_normalize_poll_http_error_marks_rejected(self):
		poll = normalize_eta_poll_response({"status": "Submitted"}, http_status_code=500)
		self.assertEqual(poll["authority_status"], DOC_STATUS_REJECTED)

	def test_map_eta_error_known_code(self):
		msg = map_eta_error_to_message("INVALID_SIGNATURE")
		self.assertIn("signature", msg.lower())

	def test_apply_poll_updates_submission(self):
		d = frappe.new_doc("E-Document Submission")
		d.reference_doctype = "User"
		d.reference_name = "Administrator"
		d.payload_hash = "hash-eta-poll"
		d.authority_status = "Queued"
		d.authority_operation = "submit"
		d.insert(ignore_permissions=True)
		poll = normalize_eta_poll_response(
			{"status": "valid", "uuid": "eta-uuid-poll-001"},
			http_status_code=200,
		)
		apply_eta_poll_to_submission(d.name, poll)
		d.reload()
		self.assertEqual(d.authority_status, DOC_STATUS_ACCEPTED)
		self.assertEqual(d.authority_uuid, "eta-uuid-poll-001")
