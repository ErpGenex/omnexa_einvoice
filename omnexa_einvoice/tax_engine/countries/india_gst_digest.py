# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""India GST IRN — canonical JSON digest signing (GSP/NIC UAT prep)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

import frappe
from frappe import _


def _strip_meta(data: Any) -> Any:
	if isinstance(data, dict):
		return {k: _strip_meta(v) for k, v in data.items() if k != "_meta"}
	if isinstance(data, list):
		return [_strip_meta(x) for x in data]
	return data


def canonical_gst_json_bytes(json_text: str) -> bytes:
	"""NIC-style stable serialization (sorted keys, no _meta) for hash / UAT."""
	data = json.loads(json_text)
	payload = _strip_meta(data)
	return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_gst_irn_digest(
	json_text: str,
	*,
	signing_secret: str = "",
) -> dict[str, Any]:
	"""Phase 1 digest: SHA-256 canonical JSON; optional HMAC in _meta for GSP UAT."""
	canonical = canonical_gst_json_bytes(json_text)
	digest = hashlib.sha256(canonical).digest()
	hash_hex = digest.hex()
	hash_b64 = base64.b64encode(digest).decode("ascii")

	try:
		data = json.loads(json_text)
	except json.JSONDecodeError as exc:
		frappe.throw(_("Invalid GST JSON: {0}").format(exc), title=_("India GST"))

	if not isinstance(data, dict):
		frappe.throw(_("GST IRN payload must be a JSON object."), title=_("India GST"))

	meta = dict(data.get("_meta") or {})
	meta["InvoiceHash"] = hash_hex
	meta["CanonicalAlg"] = "SHA256-sorted-json"
	if signing_secret:
		meta["DigestSig"] = hmac.new(
			signing_secret.encode("utf-8"),
			canonical,
			hashlib.sha256,
		).hexdigest()
	data["_meta"] = meta
	signed_json = json.dumps(data, ensure_ascii=False, indent=2)

	sig_b64 = meta.get("DigestSig") or base64.b64encode(f"IN-DIGEST:{hash_hex}".encode()).decode("ascii")
	return {
		"hash_hex": hash_hex,
		"hash_b64": hash_b64,
		"signature_b64": sig_b64,
		"signed_xml": signed_json,
		"signer": "digest:gst-irn-scaffold",
		"signing_family": "digest"
	}


def validate_gsp_config(config: dict[str, Any]) -> list[str]:
	missing: list[str] = []
	if not (config.get("gstin") or "").strip():
		missing.append(_("gstin (or Branch Tax Registration Number)"))
	if not (config.get("gsp_base_url") or "").strip():
		missing.append(_("gsp_base_url or API Base URL"))
	auth = (config.get("gsp_client_id") or "").strip() or (config.get("gsp_api_key") or "").strip()
	if not auth:
		missing.append(_("gsp_client_id + client_secret, or asp_api_key"))
	return missing
