# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
E-Receipt submission helpers only.
No imports from eta_invoice_signing, eta_signing_agent, or invoice USB signing.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from omnexa_einvoice.eta_receipt import (
	build_eta_receipt_document,
	encode_eta_receipt_submission,
	ensure_receipt_uuid,
	parse_receipt_submission_response,
	refresh_receipt_datetime,
	validate_receipt_document,
)


def assert_e_receipt_submission(doc) -> None:
	if doc.submission_kind != "E-Receipt":
		frappe.throw(_("Not an E-Receipt submission."), title=_("E-Receipt"))


def sign_e_receipt_submission(doc, source, branch: str) -> dict:
	"""Build receipt JSON + UUID — no USB signing agent."""
	assert_e_receipt_submission(doc)
	payload = build_eta_receipt_document(source, branch=branch)
	validate_receipt_document(payload, strict_datetime=False)
	doc.eta_uuid = payload.get("header", {}).get("uuid", "")
	doc.canonical_hash = doc.eta_uuid
	doc.signature_value = ""
	return {"document": payload}


def prepare_e_receipt_for_send(document: dict) -> dict:
	"""Refresh datetime + UUID before ETA submit."""
	document = refresh_receipt_datetime(document)
	document = ensure_receipt_uuid(document)
	validate_receipt_document(document, strict_datetime=True)
	return document


def encode_e_receipt_body(document: dict) -> bytes:
	return encode_eta_receipt_submission(document)


def apply_e_receipt_send_result(doc, document: dict, response_body: dict, http_status: int) -> dict:
	parsed = parse_receipt_submission_response(response_body, http_status)
	ok = parsed["ok"] and http_status in (200, 201, 202)
	doc.status = "Completed" if ok else "Failed"
	doc.provider_reference = (parsed["submission_id"] or parsed["authority_uuid"] or doc.eta_uuid or "")[:140]
	doc.authority_uuid = parsed["authority_uuid"] or doc.eta_uuid
	doc.integration_message = parsed["message"]
	doc.eta_error_code = parsed["error_code"]
	if ok:
		doc.result_data = json.dumps({"document": document, "eta_response": response_body}, ensure_ascii=False)[
			:20000
		]
	else:
		doc.result_data = json.dumps(response_body, ensure_ascii=False)[:20000]
	return {"ok": ok, "parsed": parsed}
