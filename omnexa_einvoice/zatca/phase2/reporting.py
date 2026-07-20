# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA reporting — simplified tax invoices (B2C)."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.zatca.phase2.api_client import submit_reporting_api
from omnexa_einvoice.zatca.phase2.constants import ENVIRONMENT_PORTALS
from omnexa_einvoice.zatca.phase2.payload import build_invoice_api_payload
from omnexa_einvoice.zatca.phase2.qr_extract import extract_qr_tlv_base64
from omnexa_einvoice.zatca.phase2.response_handler import (
	get_cleared_invoice_xml,
	parse_submission_result,
	raise_if_validation_errors,
)
from omnexa_einvoice.zatca.settings import get_production_auth


def submit_reporting(
	*,
	settings,
	signed_xml: str,
	invoice_hash_b64: str,
	uuid: str,
) -> dict[str, Any]:
	portal = ENVIRONMENT_PORTALS.get(settings.zatca_environment or "sandbox", "developer-portal")
	token, secret = get_production_auth(settings)
	payload = build_invoice_api_payload(
		signed_xml=signed_xml,
		uuid=uuid,
		invoice_hash_b64=invoice_hash_b64,
	)
	status_code, body = submit_reporting_api(portal, payload, token, secret)
	result = parse_submission_result(status_code, body, status_field="reportingStatus")
	raise_if_validation_errors(result)

	cleared_xml = ""
	qr_tlv = None
	if result.get("ok"):
		try:
			cleared_xml = get_cleared_invoice_xml(
				body, request_payload=payload, is_simplified=True
			)
			qr_tlv = extract_qr_tlv_base64(cleared_xml)
		except Exception:
			pass

	return {
		"ok": result.get("ok"),
		"reporting_status": result.get("zatca_status"),
		"cleared_invoice_xml": cleared_xml,
		"qr_tlv": qr_tlv,
		"validation_results": result.get("validation_results"),
		"http_status": status_code,
		"raw": body
	}
