# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 2 HTTP client."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.zatca.phase2.constants import (
	ACCEPT_LANGUAGE,
	API_VERSION_HEADER,
	PATH_CLEARANCE,
	PATH_COMPLIANCE_CSID,
	PATH_COMPLIANCE_INVOICE,
	PATH_PRODUCTION_CSID,
	PATH_REPORTING,
	ZATCA_HOST,
)


def api_url(portal: str, path_template: str) -> str:
	return f"{ZATCA_HOST}{path_template.format(portal=portal)}"


def _basic_auth_header(token: str, secret: str) -> str:
	raw = f"{token}:{secret}".encode()
	return "Basic " + base64.b64encode(raw).decode("ascii")


def zatca_request(
	method: str,
	url: str,
	*,
	token: str | None = None,
	secret: str | None = None,
	otp: str | None = None,
	json_body: dict | None = None,
	extra_headers: dict | None = None,
	timeout: int = 120,
) -> tuple[int, dict[str, Any]]:
	headers = {
		"Accept": "application/json",
		"Content-Type": "application/json",
		"Accept-Version": API_VERSION_HEADER,
		"Accept-Language": ACCEPT_LANGUAGE
	}
	if otp:
		headers["OTP"] = str(otp)
	if token and secret:
		headers["Authorization"] = _basic_auth_header(token, secret)
	if extra_headers:
		headers.update(extra_headers)

	try:
		res = requests.request(
			method.upper(),
			url,
			headers=headers,
			json=json_body,
			timeout=timeout,
		)
	except requests.RequestException as exc:
		frappe.throw(_("ZATCA API request failed: {0}").format(exc), title=_("ZATCA"))

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": res.text[:4000]
	}

	return res.status_code, body


def zatca_request_strict(
	method: str,
	url: str,
	**kwargs,
) -> dict[str, Any]:
	"""Raise on HTTP >= 400 (onboarding CSID)."""
	status, body = zatca_request(method, url, **kwargs)
	if status >= 400:
		msg = body.get("message") or body.get("errors") or body.get("raw") or str(body)
		frappe.throw(_("ZATCA API error ({0}): {1}").format(status, msg), title=_("ZATCA"))
	return body


def clearance_headers() -> dict[str, str]:
	return {"Clearance-Status": "1"
	}


def request_compliance_csid(portal: str, csr_base64: str, otp: str) -> dict[str, Any]:
	url = api_url(portal, PATH_COMPLIANCE_CSID)
	return zatca_request_strict("POST", url, otp=otp, json_body={"csr": csr_base64
	})


def request_production_csid(portal: str, compliance_request_id: str, token: str, secret: str) -> dict[str, Any]:
	url = api_url(portal, PATH_PRODUCTION_CSID)
	return zatca_request_strict(
		"POST",
		url,
		token=token,
		secret=secret,
		json_body={"compliance_request_id": compliance_request_id
	},
	)


def submit_clearance_api(portal: str, payload: dict, token: str, secret: str) -> tuple[int, dict[str, Any]]:
	url = api_url(portal, PATH_CLEARANCE)
	return zatca_request(
		"POST",
		url,
		token=token,
		secret=secret,
		json_body=payload,
		extra_headers=clearance_headers(),
	)


def submit_reporting_api(portal: str, payload: dict, token: str, secret: str) -> tuple[int, dict[str, Any]]:
	url = api_url(portal, PATH_REPORTING)
	return zatca_request("POST", url, token=token, secret=secret, json_body=payload)


def submit_compliance_invoice_api(
	portal: str, payload: dict, token: str, secret: str
) -> tuple[int, dict[str, Any]]:
	url = api_url(portal, PATH_COMPLIANCE_INVOICE)
	return zatca_request("POST", url, token=token, secret=secret, json_body=payload)
