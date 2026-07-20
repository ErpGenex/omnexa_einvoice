# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Phase 2 HTTP submit to ASP / tax authority (international plugin)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.countries.mexico_pac import validate_mexico_pac_for_live
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.asp_payload import build_asp_payload
from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def _auth_headers(settings, config: dict[str, Any]) -> dict[str, str]:
	headers = {"Accept": "application/json", "Content-Type": "application/json"}
	client_id = (settings.get("client_id") or "").strip()
	secret = get_settings_password(settings, "client_secret")
	if client_id and secret:
		import base64

		token = base64.b64encode(f"{client_id}:{secret}".encode()).decode("ascii")
		headers["Authorization"] = f"Basic {token}"
		return headers
	api_key = get_settings_password(settings, "asp_api_key")
	if not api_key:
		api_key = (config.get("api_key") or config.get("bearer_token") or "").strip()
	if api_key:
		headers["Authorization"] = f"Bearer {api_key}"
	return headers


def submit_invoice_api(
	*,
	country_code: str,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(
		company, country_code, phase="phase2", branch=branch
	)
	if country_code == "MX" and is_live_production_settings(settings):
		validate_mexico_pac_for_live(company, branch=branch)
	config: dict[str, Any] = {}
	if settings.get("configuration_json"):
		try:
			config = json.loads(settings.configuration_json)
			if not isinstance(config, dict):
				config = {}
		except json.JSONDecodeError:
			pass

	base = (settings.api_base_url or "").strip().rstrip("/")
	if not base:
		if allow_mock_api():
			return {
				"ok": True,
				"mock": True,
				"status": "ACCEPTED",
				"authority": spec.authority_code,
				"mode": "mock",
			}
		frappe.throw(_("API Base URL missing on Country Tax Settings."), title=_("Tax Plugin"))

	url = f"{base}{spec.submit_path}"
	headers = _auth_headers(settings, config)
	idem = build_idempotency_key(
		country_code=country_code,
		uuid=uuid,
		document=document,
		config=config,
	)
	headers["Idempotency-Key"] = idem

	payload = build_asp_payload(
		country_code=country_code,
		company=company,
		settings=settings,
		spec=spec,
		uuid=uuid,
		hash_b64=hash_b64,
		signed_xml=signed_xml,
		document=document,
	)
	payload["idempotencyKey"] = idem

	timeout = int(config.get("timeout_seconds") or frappe.conf.get("tax_plugin_api_timeout") or 120)
	retries = int(config.get("retry_count") or 2)
	backoff = float(config.get("retry_backoff_seconds") or 1.0)

	res = post_json_with_retry(
		url,
		headers=headers,
		payload=payload,
		timeout=timeout,
		max_retries=retries,
		backoff_seconds=backoff,
	)

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:8000]}

	if res.status_code >= 400:
		frappe.throw(_("Tax API error ({0}): {1}").format(res.status_code, body), title=_("Tax Plugin"))

	status = body.get("status") or body.get("documentStatus") or body.get("clearanceStatus") or "ACCEPTED"
	return {
		"ok": True,
		"http_status": res.status_code,
		"raw": body,
		"status": status,
		"mode": "live",
		"environment": settings.api_environment,
		"idempotency_key": idem,
	}
