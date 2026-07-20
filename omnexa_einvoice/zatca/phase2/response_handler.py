# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Parse ZATCA clearance/reporting responses (reference: clearence_util._handle_zatca_response)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import escape_html


def decode_invoice_b64(encoded_invoice: str) -> str:
	return base64.b64decode(encoded_invoice.encode("utf-8")).decode("utf-8")


def get_cleared_invoice_xml(
	response_body: dict[str, Any],
	*,
	request_payload: dict[str, Any],
	is_simplified: bool,
) -> str:
	"""B2B: clearedInvoice from response; B2C: original signed invoice from request."""
	if is_simplified:
		return decode_invoice_b64(request_payload.get("invoice") or "")
	cleared = response_body.get("clearedInvoice") or response_body.get("cleared_invoice")
	if not cleared:
		frappe.throw(_("clearedInvoice missing from ZATCA clearance response."), title=_("ZATCA"))
	return decode_invoice_b64(cleared)


def parse_submission_result(
	status_code: int,
	response_body: dict[str, Any],
	*,
	status_field: str,
) -> dict[str, Any]:
	"""
	Map HTTP status to submission outcome.
	status_field: clearanceStatus | reportingStatus
	"""
	zatca_status = (response_body.get(status_field) or response_body.get("status") or "").strip()
	validation = response_body.get("validationResults") or {}

	if status_code in (200, 202):
		ok = zatca_status.upper() in {"CLEARED", "REPORTED", "PASS", "WARNING"}
		return {
			"ok": ok or bool(zatca_status),
			"http_status": status_code,
			"zatca_status": zatca_status or ("CLEARED" if status_field == "clearanceStatus" else "REPORTED"),
			"validation_results": validation,
			"has_warnings": bool(validation.get("warningMessages")),
			"has_errors": bool(validation.get("errorMessages")),
			"raw": response_body
	}

	if status_code == 303:
		return {
			"ok": False,
			"http_status": status_code,
			"zatca_status": "FAILED",
			"error_message": json.dumps(response_body.get("message", "")),
			"raw": response_body
	}

	if status_code == 400:
		return {
			"ok": False,
			"http_status": status_code,
			"zatca_status": zatca_status or "FAILED",
			"validation_results": validation,
			"error_message": json.dumps(validation or response_body),
			"raw": response_body
	}

	if status_code == 401:
		frappe.throw(_("ZATCA credentials rejected (401). Renew CSID tokens."), title=_("ZATCA"))

	if status_code == 500:
		frappe.throw(_("ZATCA internal server error (500). Retry later."), title=_("ZATCA"))

	frappe.throw(
		_("ZATCA API returned unexpected status {0}.").format(status_code),
		title=_("ZATCA"),
	)


def format_validation_html(validation_results: Any) -> str:
	"""User-facing errors/warnings like reference display_error_ui."""
	if isinstance(validation_results, str):
		try:
			results = json.loads(validation_results)
		except Exception:
			results = {"errorMessages": [{"message": validation_results}]
	}
	else:
		results = validation_results or {}

	errors = results.get("errorMessages") or []
	warnings = results.get("warningMessages") or []
	parts = []
	if errors:
		items = "".join(f"<li>{escape_html((e or {}).get('message', 'Unknown'))}</li>" for e in errors)
		parts.append(f"<p><strong>{_('ZATCA Errors')}:</strong></p><ul>{items}</ul>")
	if warnings:
		items = "".join(f"<li>{escape_html((w or {}).get('message', 'Unknown'))}</li>" for w in warnings)
		parts.append(f"<p><strong>{_('ZATCA Warnings')}:</strong></p><ul>{items}</ul>")
	return "".join(parts)


def raise_if_validation_errors(result: dict[str, Any]) -> None:
	if result.get("has_errors"):
		html = format_validation_html(result.get("validation_results"))
		frappe.throw(html or _("ZATCA validation failed."), title=_("ZATCA Submission Failed"))
