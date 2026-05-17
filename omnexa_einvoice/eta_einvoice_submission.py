# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
E-Invoice submission helpers only (build, sign via agent/HMAC, send).
Must not be used for E-Receipt.
"""

from __future__ import annotations

import hashlib
import json

import frappe
from frappe import _

from omnexa_einvoice.eta_invoice import (
	build_eta_invoice_document,
	eta_invoice_signature_block,
	invoice_canonical_json,
	parse_invoice_submission_response,
	refresh_invoice_datetime,
	sanitize_invoice_for_eta,
	validate_invoice_document,
)
from omnexa_einvoice.eta_invoice_signing import sign_eta_invoice_document


def assert_e_invoice_submission(doc) -> None:
	if doc.submission_kind != "E-Invoice":
		frappe.throw(_("Not an E-Invoice submission."), title=_("E-Invoice"))


def build_unsigned_e_invoice_document(source, branch: str) -> dict:
	document = sanitize_invoice_for_eta(build_eta_invoice_document(source, branch=branch))
	validate_invoice_document(document, strict_datetime=False)
	return document


def coerce_agent_signed_document(raw) -> dict | None:
	"""Document JSON returned by epass2003_agent (Chilkat-built, ITIDA-compatible)."""
	if not raw:
		return None
	if isinstance(raw, str):
		raw = json.loads(raw)
	if not isinstance(raw, dict):
		return None
	if isinstance(raw.get("document"), dict):
		return raw["document"]
	return raw


def sign_e_invoice_submission(
	doc,
	source,
	branch: str,
	*,
	client_signature: str | None = None,
	agent_signed_document: dict | None = None,
) -> dict:
	"""Build invoice JSON + sign (browser USB agent / HMAC / CLI). PIN always from Branch."""
	assert_e_invoice_submission(doc)
	agent_doc = coerce_agent_signed_document(agent_signed_document)
	if agent_doc:
		document = sanitize_invoice_for_eta(json.loads(json.dumps(agent_doc, ensure_ascii=False)))
		validate_invoice_document(document, strict_datetime=False)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else ""
		if not signature:
			signature = (client_signature or "").strip()
		if not signature:
			frappe.throw(_("USB agent did not return a signature."), title=_("E-Invoice Signing"))
		signer_method = "signing_agent_chilkat"
	else:
		document = build_unsigned_e_invoice_document(source, branch)
		signature, signer_method = sign_eta_invoice_document(
			document, branch, client_signature=client_signature
		)
		document["signatures"] = eta_invoice_signature_block(signature)

	unsigned = json.loads(json.dumps(document, ensure_ascii=False))
	unsigned.pop("signatures", None)
	canonical = invoice_canonical_json(unsigned)
	doc.signature_value = signature
	doc.canonical_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
	doc.eta_uuid = ""
	doc.integration_message = _("Signed via {0}.").format(signer_method)
	return {"document": document, "signer_method": signer_method}


def prepare_e_invoice_for_send(
	payload: dict,
	branch: str,
	*,
	client_signature: str | None = None,
	agent_signed_document: dict | None = None,
) -> tuple[dict, str, str, str]:
	"""Refresh issue time, re-sign, return document + hash + method + signature. PIN from Branch only."""
	agent_doc = coerce_agent_signed_document(agent_signed_document)
	if agent_doc:
		document = sanitize_invoice_for_eta(json.loads(json.dumps(agent_doc, ensure_ascii=False)))
		validate_invoice_document(document, strict_datetime=True)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else (client_signature or "").strip()
		if not signature:
			frappe.throw(_("USB agent signed document is missing signature."), title=_("E-Invoice"))
		unsigned = json.loads(json.dumps(document, ensure_ascii=False))
		unsigned.pop("signatures", None)
		canonical = invoice_canonical_json(unsigned)
		return document, hashlib.sha256(canonical.encode("utf-8")).hexdigest(), "signing_agent_chilkat", signature

	stored = json.loads(json.dumps(payload.get("document") or payload, ensure_ascii=False))
	if stored.get("signatures") and not agent_signed_document:
		document = sanitize_invoice_for_eta(stored)
		validate_invoice_document(document, strict_datetime=True)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else ""
		unsigned = json.loads(json.dumps(document, ensure_ascii=False))
		unsigned.pop("signatures", None)
		canonical = invoice_canonical_json(unsigned)
		method = (payload.get("signer_method") or "signing_agent_chilkat").strip()
		return document, hashlib.sha256(canonical.encode("utf-8")).hexdigest(), method, signature

	document = sanitize_invoice_for_eta(stored)
	document = refresh_invoice_datetime(document)
	validate_invoice_document(document, strict_datetime=True)
	canonical = invoice_canonical_json(document)
	signature, signer_method = sign_eta_invoice_document(
		document, branch, client_signature=client_signature
	)
	document["signatures"] = eta_invoice_signature_block(signature)
	return document, hashlib.sha256(canonical.encode("utf-8")).hexdigest(), signer_method, signature


def prepare_e_invoice_for_send_unsigned(payload: dict) -> dict:
	"""Refresh datetime for send; browser agent signs afterward."""
	document = sanitize_invoice_for_eta(
		json.loads(json.dumps(payload.get("document") or payload, ensure_ascii=False))
	)
	document = refresh_invoice_datetime(document)
	validate_invoice_document(document, strict_datetime=True)
	unsigned = json.loads(json.dumps(document, ensure_ascii=False))
	unsigned.pop("signatures", None)
	return unsigned


def build_e_invoice_submit_body(document: dict) -> dict:
	return {"documents": [document]}


def apply_e_invoice_send_result(doc, document: dict, response_body: dict, http_status: int) -> dict:
	parsed = parse_invoice_submission_response(response_body, http_status)
	ok = parsed["ok"] and http_status in (200, 201, 202)
	doc.status = "Completed" if ok else "Failed"
	doc.provider_reference = (parsed["submission_id"] or parsed["authority_uuid"] or doc.canonical_hash or "")[
		:140
	]
	doc.authority_uuid = parsed["authority_uuid"] or ""
	doc.eta_uuid = doc.authority_uuid
	doc.integration_message = parsed["message"]
	doc.eta_error_code = parsed["error_code"]
	if ok:
		doc.result_data = json.dumps({"document": document, "eta_response": response_body}, ensure_ascii=False)[
			:20000
		]
	else:
		doc.result_data = json.dumps(response_body, ensure_ascii=False)[:20000]
	return {"ok": ok, "parsed": parsed}
