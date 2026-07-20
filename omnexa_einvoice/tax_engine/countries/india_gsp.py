# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""India GST e-Invoice — GSP/NIC IRN generation (sandbox + live HTTP)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries.india_gst_digest import validate_gsp_config
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_india_gsp_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "IN", branch=branch)
	config: dict[str, Any] = {}
	if settings and settings.get("configuration_json"):
		try:
			config = json.loads(settings.configuration_json)
			if not isinstance(config, dict):
				config = {}
		except json.JSONDecodeError:
			config = {}
	return frappe._dict(
		{
			"gsp_base_url": (config.get("gsp_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"gsp_submit_path": (config.get("gsp_submit_path") or "/einvoice/v1/generate-irn").strip(),
			"gstin": (config.get("gstin") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"gsp_client_id": (config.get("gsp_client_id") or (settings.get("client_id") if settings else "") or "").strip(),
			"gsp_client_secret": get_settings_password(settings, "client_secret") if settings else None,
			"gsp_api_key": get_settings_password(settings, "asp_api_key") if settings else None,
			"gst_signing_secret": (config.get("gst_signing_secret") or "").strip(),
		}
	)


def validate_india_gsp_for_live(company: str, *, branch: str | None = None) -> None:
	gsp = get_india_gsp_settings(company, branch=branch)
	missing = validate_gsp_config(
		{
			"gstin": gsp.gstin,
			"gsp_base_url": gsp.gsp_base_url,
			"gsp_client_id": gsp.gsp_client_id,
			"gsp_api_key": gsp.gsp_api_key,
		}
	)
	if missing:
		frappe.throw(
			_("India live GSP requires: {0}").format(", ".join(missing)),
			title=_("India GSP"),
		)


def _auth_headers(gsp: frappe._dict) -> dict[str, str]:
	headers = {"Accept": "application/json", "Content-Type": "application/json"}
	if gsp.gsp_client_id and gsp.gsp_client_secret:
		token = base64.b64encode(f"{gsp.gsp_client_id}:{gsp.gsp_client_secret}".encode()).decode("ascii")
		headers["Authorization"] = f"Basic {token}"
	elif gsp.gsp_api_key:
		headers["Authorization"] = f"Bearer {gsp.gsp_api_key}"
	return headers


def _mock_irn_response(*, uuid: str, einvoice_json: dict[str, Any]) -> dict[str, Any]:
	doc_no = (einvoice_json.get("DocDtls") or {}).get("No") or uuid[:8]
	irn = f"{uuid.replace('-', '')[:16].upper()}INMOCK"
	signed_qr = f"MOCK-SIGNED-QR-{irn}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACT",
		"irn": irn,
		"ack_no": "MOCK-ACK-001",
		"ack_dt": frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
		"signed_qr_code": signed_qr,
		"raw": {
			"Irn": irn,
			"AckNo": "MOCK-ACK-001",
			"AckDt": frappe.utils.now(),
			"SignedQRCode": signed_qr,
			"DocNo": doc_no,
		},
		"mode": "mock",
		"framework": "GST-IRN",
	}


def submit_gst_irn(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""Phase 2 — generate IRN via GSP (JSON body from Phase 1)."""
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "IN", phase="phase2", branch=branch)
	gsp = get_india_gsp_settings(company, branch=branch)

	try:
		einvoice_json = json.loads(signed_xml) if signed_xml.strip().startswith("{") else {}
	except json.JSONDecodeError:
		frappe.throw(_("India Phase 1 output must be valid GST JSON."), title=_("India GSP"))

	if allow_mock_api() or not gsp.gsp_base_url:
		return _mock_irn_response(uuid=uuid, einvoice_json=einvoice_json)

	if is_live_production_settings(settings):
		validate_india_gsp_for_live(company, branch=branch)

	url = f"{gsp.gsp_base_url.rstrip('/')}{gsp.gsp_submit_path}"
	headers = _auth_headers(gsp)
	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"eInvoiceJson": einvoice_json,
		"gstin": gsp.gstin,
		"country": "IN",
		"framework": spec.authority_code,
	}

	idem = build_idempotency_key(country_code="IN", uuid=uuid, document=document)
	headers["Idempotency-Key"] = idem
	timeout = int(frappe.conf.get("tax_plugin_api_timeout") or 120)
	max_retries = int(frappe.conf.get("tax_plugin_max_retries") or 2)
	res = post_json_with_retry(
		url,
		headers=headers,
		payload=payload,
		timeout=timeout,
		max_retries=max_retries,
	)

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:8000]}

	if res.status_code >= 400:
		frappe.throw(_("India GSP error ({0}): {1}").format(res.status_code, body), title=_("India GSP"))

	irn = body.get("Irn") or body.get("irn") or ""
	signed_qr = body.get("SignedQRCode") or body.get("signedQRCode") or ""
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("Status") or "ACT",
		"irn": irn,
		"ack_no": body.get("AckNo") or body.get("ackNo"),
		"ack_dt": body.get("AckDt") or body.get("ackDt"),
		"signed_qr_code": signed_qr,
		"raw": body,
		"mode": "live",
		"environment": settings.api_environment if settings else "sandbox",
		"framework": "GST-IRN",
	}


@frappe.whitelist()
def test_india_gsp_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	"""Desk test — mock IRN in sandbox, ping GSP in live when configured."""
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("India GSP"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	gsp = get_india_gsp_settings(comp, branch=branch)
	if not gsp.gstin:
		return {
			"ok": False,
			"message": _("Set GSTIN on Branch → Country Tax (Tax Registration Number or configuration_json.gstin)."),
		}
	cfg_check = {
		"gstin": gsp.gstin,
		"gsp_base_url": gsp.gsp_base_url,
		"gsp_client_id": gsp.gsp_client_id,
		"gsp_api_key": gsp.gsp_api_key,
	}
	gsp_checklist = validate_gsp_config(cfg_check)
	if allow_mock_api() or not gsp.gsp_base_url:
		mock = _mock_irn_response(uuid=frappe.generate_hash(length=12), einvoice_json={"DocDtls": {"No": "TEST"}})
		return {
			"ok": True,
			"message": _("India GSP sandbox OK (mock IRN)."),
			"irn": mock["irn"],
			"mode": "mock",
			"gsp_ready": not gsp_checklist,
			"checklist": gsp_checklist or [_("Optional for mock: complete GSP URL and credentials before NIC UAT.")],
		}
	if gsp_checklist:
		return {
			"ok": False,
			"message": _("Complete GSP configuration before live IRN generation."),
			"checklist": gsp_checklist,
		}
	url = f"{gsp.gsp_base_url.rstrip('/')}/health"
	try:
		res = requests.get(url, headers=_auth_headers(gsp), timeout=30)
		return {
			"ok": res.status_code < 500,
			"message": _("GSP endpoint reachable ({0}). Ready for IRN UAT.").format(res.status_code),
			"gsp_base_url": gsp.gsp_base_url,
			"gsp_ready": True,
		}
	except requests.RequestException as exc:
		return {"ok": False, "message": str(exc), "checklist": gsp_checklist}
