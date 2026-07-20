# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Mexico SAT — PAC timbrado (CFDI XML submit)."""

from __future__ import annotations

import base64
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries.mexico_csd_signer import validate_csd_config
from omnexa_einvoice.tax_engine.countries.mexico_pac import get_mexico_pac_settings, validate_mexico_pac_for_live
from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def _mock_timbrado(*, uuid: str, reference: str) -> dict[str, Any]:
	uuid_timbre = f"TMBR-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "TIMBRADO",
		"uuid": uuid_timbre,
		"sat_uuid": uuid_timbre,
		"raw": {
			"uuid": uuid_timbre,
			"reference": reference,
			"message": "Mock PAC timbrado"
	},
		"mode": "mock",
		"framework": "CFDI-4.0"
	}


def submit_cfdi_timbrado(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "MX", phase="phase2", branch=branch)
	pac = get_mexico_pac_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not pac.pac_base_url:
		return _mock_timbrado(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_mexico_pac_for_live(company, branch=branch)

	url = pac.pac_base_url.rstrip("/")
	if not url.endswith("/timbrado") and not url.endswith("/stamp"):
		url = f"{url}/timbrado"

	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	if pac.pac_username and pac.pac_password:
		token = base64.b64encode(f"{pac.pac_username}:{pac.pac_password}".encode()).decode("ascii")
		headers["Authorization"] = f"Basic {token}"

	payload = {
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"provider": pac.pac_provider,
		"reference": reference
	}

	idem = build_idempotency_key(country_code="MX", uuid=uuid, document=document)
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
		body = {"raw": (res.text or "")[:8000]
	}

	if res.status_code >= 400:
		frappe.throw(_("Mexico PAC error ({0}): {1}").format(res.status_code, body), title=_("Mexico PAC"))

	sat_uuid = body.get("uuid") or body.get("UUID") or body.get("TimbreUUID") or ""
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "TIMBRADO",
		"uuid": sat_uuid or uuid,
		"sat_uuid": sat_uuid,
		"raw": body,
		"mode": "live",
		"environment": settings.api_environment if settings else "sandbox",
		"framework": "CFDI-4.0"
	}


@frappe.whitelist()
def test_mexico_pac_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("Mexico PAC"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	pac = get_mexico_pac_settings(comp, branch=branch)
	config = {
		"pac_base_url": pac.pac_base_url,
		"csd_private_key_pem": pac.csd_private_key_pem,
		"csd_certificate_pem": pac.csd_certificate_pem
	}
	csd_checklist = validate_csd_config(config)
	if allow_mock_api() or not pac.pac_base_url:
		mock = _mock_timbrado(uuid=frappe.generate_hash(length=12), reference="TEST")
		return {
			"ok": True,
			"message": _("Mexico PAC sandbox OK (mock timbrado)."),
			"sat_uuid": mock["sat_uuid"],
			"mode": "mock",
			"csd_ready": not csd_checklist,
			"checklist": csd_checklist or [_("Optional for mock: add CSD PEMs before SAT UAT.")]
	}
	if csd_checklist:
		return {
			"ok": False,
			"message": _("PAC URL configured; complete CSD before live timbrado."),
			"pac_base_url": pac.pac_base_url,
			"checklist": csd_checklist
	}
	try:
		res = requests.get(pac.pac_base_url.rstrip("/"), timeout=30)
		return {
			"ok": res.status_code < 500,
			"message": _("PAC URL reachable ({0}). CSD keys present — ready for timbrado UAT.").format(
				res.status_code
			),
			"pac_base_url": pac.pac_base_url,
			"csd_ready": True
	}
	except requests.RequestException as exc:
		return {"ok": False, "message": str(exc), "checklist": csd_checklist
	}
