# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""France PDP / Chorus Pro — Factur-X submit (sandbox mock + live HTTP)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries._eu_authority_uat import validate_eu_client_for_live
from omnexa_einvoice.tax_engine.countries.country_http_uat import (
	apply_basic_auth,
	connection_test_result,
	post_country_json,
	validate_required_fields,
)
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_france_pdp_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "FR", branch=branch)
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
			"pdp_base_url": (config.get("pdp_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"pdp_submit_path": (config.get("pdp_submit_path") or "/facturx/v1/submit").strip(),
			"siret": (config.get("siret") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None}
	)


def _mock_pdp(*, uuid: str, reference: str) -> dict[str, Any]:
	flow_id = f"FR-FX-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACCEPTED",
		"flow_id": flow_id,
		"uuid": flow_id,
		"raw": {"flowId": flow_id, "reference": reference
	},
		"mode": "mock",
		"framework": "Factur-X"
	}


def submit_facturx_pdp(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "FR", phase="phase2", branch=branch)
	cfg = get_france_pdp_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not cfg.pdp_base_url:
		return _mock_pdp(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_eu_client_for_live(
			cfg,
			title=_("France PDP"),
			tax_field="siret",
			tax_label=_("siret"),
			url_field="pdp_base_url",
			url_label=_("pdp_base_url"),
		)

	url = f"{cfg.pdp_base_url.rstrip('/')}{cfg.pdp_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	apply_basic_auth(headers, cfg.client_id, cfg.client_secret)

	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"siret": cfg.siret
	}
	res = post_country_json(
		country_code="FR",
		url=url,
		headers=headers,
		payload=payload,
		document=document,
		uuid=uuid,
	)

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:8000]
	}

	if res.status_code >= 400:
		frappe.throw(_("France PDP error ({0}): {1}").format(res.status_code, body), title=_("France PDP"))

	flow_id = body.get("flowId") or body.get("id") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "ACCEPTED",
		"flow_id": flow_id,
		"uuid": flow_id,
		"raw": body,
		"mode": "live",
		"framework": "Factur-X"
	}


@frappe.whitelist()
def test_france_pdp_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("France PDP"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	cfg = get_france_pdp_settings(comp, branch=branch)
	if not cfg.siret:
		return {"ok": False, "message": _("Set SIRET on tax registration or configuration_json.siret.")
	}
	checklist = validate_required_fields(
		{"pdp_base_url": cfg.pdp_base_url
	},
		[("pdp_base_url", _("pdp_base_url"))],
	)
	mock = _mock_pdp(uuid=frappe.generate_hash(length=10), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(cfg.pdp_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("France PDP sandbox OK (mock)."),
			"flow_id": mock["flow_id"],
			"mode": "mock"
	},
		base_url=cfg.pdp_base_url,
		ready_label=_("PDP / Factur-X UAT ready."),
	)
