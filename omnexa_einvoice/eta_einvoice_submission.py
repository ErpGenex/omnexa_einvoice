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


def coerce_agent_signed_document_json(raw_json: str | None, document: dict | None = None) -> str | None:
	"""Exact Chilkat Emit JSON for ETA POST — prevents 4043 message-digest mismatch."""
	text = (raw_json or "").strip()
	if text:
		return text
	if not document:
		return None
	return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def normalize_agent_signed_document(agent_doc: dict) -> dict:
	"""Do not re-format numbers — only drop duplicate internalId alias."""
	doc = json.loads(json.dumps(agent_doc, ensure_ascii=False))
	doc.pop("internalId", None)
	return doc


def build_e_invoice_submit_body_bytes(signed_document_json: str) -> bytes:
	"""POST body with Chilkat-exact document JSON (Temp-ETR style, no requests json= re-encode)."""
	raw = (signed_document_json or "").strip()
	if not raw.startswith("{"):
		frappe.throw(_("Invalid signed_document_json from signing agent."), title=_("E-Invoice"))
	return ('{"documents":[' + raw + "]}").encode("utf-8")


def sign_e_invoice_submission(
	doc,
	source,
	branch: str,
	*,
	client_signature: str | None = None,
	agent_signed_document: dict | None = None,
	agent_signed_document_json: str | None = None,
	agent_canonical_json: str | None = None,
) -> dict:
	"""Build invoice JSON + sign (browser USB agent / HMAC / CLI). PIN always from Branch."""
	assert_e_invoice_submission(doc)
	agent_doc = coerce_agent_signed_document(agent_signed_document)
	signed_json = coerce_agent_signed_document_json(agent_signed_document_json, agent_doc)
	if agent_doc:
		if signed_json:
			document = normalize_agent_signed_document(json.loads(signed_json))
		else:
			document = normalize_agent_signed_document(agent_doc)
			signed_json = coerce_agent_signed_document_json(None, document)
		validate_invoice_document(document, strict_datetime=False)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else ""
		if not signature:
			signature = (client_signature or "").strip()
		if not signature:
			frappe.throw(_("USB agent did not return a signature."), title=_("E-Invoice Signing"))
		signer_method = "signing_agent_chilkat"
		unsigned = json.loads(signed_json or json.dumps(document, ensure_ascii=False))
		unsigned.pop("signatures", None)
		canonical_for_hash = (agent_canonical_json or "").strip() or invoice_canonical_json(unsigned)
		doc.signature_value = signature
		doc.canonical_hash = hashlib.sha256(canonical_for_hash.encode("utf-8")).hexdigest()
		doc.eta_uuid = ""
		doc.integration_message = _("Signed via {0}.").format(signer_method)
		return {
			"document": document,
			"signed_document_json": signed_json,
			"signer_canonical_json": agent_canonical_json or "",
			"signer_method": signer_method,
		}
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
	agent_signed_document_json: str | None = None,
) -> tuple[dict, str, str, str, str | None]:
	"""Refresh issue time, re-sign, return document + hash + method + signature + raw JSON for POST."""
	agent_doc = coerce_agent_signed_document(agent_signed_document)
	signed_json = coerce_agent_signed_document_json(agent_signed_document_json, agent_doc)
	if agent_doc:
		if signed_json:
			document = normalize_agent_signed_document(json.loads(signed_json))
		else:
			document = normalize_agent_signed_document(agent_doc)
			signed_json = coerce_agent_signed_document_json(None, document)
		validate_invoice_document(document, strict_datetime=True)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else (client_signature or "").strip()
		if not signature:
			frappe.throw(_("USB agent signed document is missing signature."), title=_("E-Invoice"))
		unsigned = json.loads(signed_json or json.dumps(document, ensure_ascii=False))
		unsigned.pop("signatures", None)
		canonical = invoice_canonical_json(unsigned)
		return (
			document,
			hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
			"signing_agent_chilkat",
			signature,
			signed_json,
		)

	stored_json = (payload.get("signed_document_json") or "").strip()
	if stored_json and not agent_signed_document:
		document = normalize_agent_signed_document(json.loads(stored_json))
		validate_invoice_document(document, strict_datetime=True)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else ""
		if not signature:
			frappe.throw(_("Signed submission is missing signature."), title=_("E-Invoice"))
		unsigned = json.loads(stored_json)
		unsigned.pop("signatures", None)
		canonical = invoice_canonical_json(unsigned)
		method = (payload.get("signer_method") or "signing_agent_chilkat").strip()
		return (
			document,
			hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
			method,
			signature,
			stored_json,
		)

	stored = json.loads(json.dumps(payload.get("document") or payload, ensure_ascii=False))
	if stored.get("signatures") and not agent_signed_document:
		document = normalize_agent_signed_document(stored)
		validate_invoice_document(document, strict_datetime=True)
		sigs = document.get("signatures") or []
		signature = (sigs[0].get("value") or "").strip() if sigs else ""
		unsigned = json.loads(json.dumps(document, ensure_ascii=False))
		unsigned.pop("signatures", None)
		canonical = invoice_canonical_json(unsigned)
		method = (payload.get("signer_method") or "signing_agent_chilkat").strip()
		fallback_json = coerce_agent_signed_document_json(None, document)
		return (
			document,
			hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
			method,
			signature,
			fallback_json,
		)

	document = sanitize_invoice_for_eta(stored)
	document = refresh_invoice_datetime(document)
	validate_invoice_document(document, strict_datetime=True)
	canonical = invoice_canonical_json(document)
	signature, signer_method = sign_eta_invoice_document(
		document, branch, client_signature=client_signature
	)
	document["signatures"] = eta_invoice_signature_block(signature)
	return (
		document,
		hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
		signer_method,
		signature,
		coerce_agent_signed_document_json(None, document),
	)


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
