# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Germany XRechnung — Peppol / KoSIT gateway submit (sandbox mock + live HTTP)."""

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


def get_germany_xrechnung_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "DE", branch=branch)
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
			"gateway_base_url": (config.get("gateway_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"gateway_submit_path": (config.get("gateway_submit_path") or "/xrechnung/v1/invoices").strip(),
			"leitweg_id": (config.get("leitweg_id") or "").strip(),
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None}
	)


def _mock_gateway(*, uuid: str, reference: str) -> dict[str, Any]:
	tracking = f"DE-XR-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACCEPTED",
		"tracking_id": tracking,
		"uuid": tracking,
		"raw": {"trackingId": tracking, "reference": reference
	},
		"mode": "mock",
		"framework": "XRechnung"
	}


def submit_xrechnung_invoice(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "DE", phase="phase2", branch=branch)
	cfg = get_germany_xrechnung_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not cfg.gateway_base_url:
		return _mock_gateway(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_eu_client_for_live(
			cfg,
			title=_("Germany XRechnung"),
			tax_field="leitweg_id",
			tax_label=_("leitweg_id"),
			url_field="gateway_base_url",
			url_label=_("gateway_base_url"),
		)

	url = f"{cfg.gateway_base_url.rstrip('/')}{cfg.gateway_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	apply_basic_auth(headers, cfg.client_id, cfg.client_secret)

	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"leitwegId": cfg.leitweg_id
	}
	res = post_country_json(
		country_code="DE",
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
		frappe.throw(_("Germany XRechnung error ({0}): {1}").format(res.status_code, body), title=_("Germany XRechnung"))

	tracking = body.get("trackingId") or body.get("id") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "ACCEPTED",
		"tracking_id": tracking,
		"uuid": tracking,
		"raw": body,
		"mode": "live",
		"framework": "XRechnung"
	}


@frappe.whitelist()
def test_germany_xrechnung_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("Germany XRechnung"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	cfg = get_germany_xrechnung_settings(comp, branch=branch)
	checklist = validate_required_fields(
		{"gateway_base_url": cfg.gateway_base_url
	},
		[("gateway_base_url", _("gateway_base_url"))],
	)
	mock = _mock_gateway(uuid=frappe.generate_hash(length=10), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(cfg.gateway_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("Germany XRechnung sandbox OK (mock)."),
			"tracking_id": mock["tracking_id"],
			"mode": "mock"
	},
		base_url=cfg.gateway_base_url,
		ready_label=_("KoSIT / XRechnung UAT ready."),
	)
