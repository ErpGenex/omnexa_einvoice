# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared HTTP + config helpers for international country UAT clients."""

from __future__ import annotations

import base64
import json
from typing import Any, Callable

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry


def parse_configuration(settings: Any | None) -> dict[str, Any]:
	if not settings:
		return {}
	raw = settings.get("configuration_json") if isinstance(settings, dict) else settings.configuration_json
	if not raw or not str(raw).strip():
		return {}
	try:
		parsed = json.loads(raw)
		return parsed if isinstance(parsed, dict) else {}
	except json.JSONDecodeError:
		return {}


def apply_basic_auth(headers: dict[str, str], client_id: str, client_secret: str | None) -> None:
	if client_id and client_secret:
		token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
		headers["Authorization"] = f"Basic {token}"


def apply_bearer(headers: dict[str, str], token: str | None) -> None:
	if token:
		headers["Authorization"] = f"Bearer {token}"


def post_country_json(
	*,
	country_code: str,
	url: str,
	headers: dict[str, str],
	payload: dict[str, Any],
	document: dict[str, Any] | None = None,
	uuid: str = "",
	config: dict[str, Any] | None = None,
) -> requests.Response:
	cfg = config or {}
	idem = build_idempotency_key(country_code=country_code, uuid=uuid, document=document, config=cfg)
	headers = dict(headers)
	headers["Idempotency-Key"] = idem
	timeout = int(cfg.get("timeout_seconds") or frappe.conf.get("tax_plugin_api_timeout") or 120)
	max_retries = int(cfg.get("retry_count") or frappe.conf.get("tax_plugin_max_retries") or 2)
	return post_json_with_retry(
		url,
		headers=headers,
		payload=payload,
		timeout=timeout,
		max_retries=max_retries,
	)


def validate_required_fields(config: dict[str, Any], required: list[tuple[str, str]]) -> list[str]:
	"""required: list of (config_key, human label)."""
	missing: list[str] = []
	for key, label in required:
		if not (config.get(key) or "").strip():
			missing.append(label)
	return missing


def connection_test_result(
	*,
	allow_mock: bool,
	has_base_url: bool,
	checklist: list[str],
	mock_response: dict[str, Any],
	base_url: str,
	headers: dict[str, str] | None = None,
	ready_label: str = "",
) -> dict[str, Any]:
	if allow_mock or not has_base_url:
		out = dict(mock_response)
		out["ready"] = not checklist
		out["checklist"] = checklist or [
			_("Optional for mock: complete API URL and credentials before authority UAT.")
		]
		return out
	if checklist:
		return {
			"ok": False,
			"message": _("Complete configuration before live submission."),
			"checklist": checklist
	}
	try:
		res = requests.get(base_url.rstrip("/"), headers=headers or {}, timeout=30)
		return {
			"ok": res.status_code < 500,
			"message": _("Endpoint reachable ({0}). {1}").format(
				res.status_code,
				ready_label or _("Ready for UAT."),
			),
			"ready": True
	}
	except requests.RequestException as exc:
		return {"ok": False, "message": str(exc), "checklist": checklist
	}


def throw_if_missing(missing: list[str], *, title: str) -> None:
	if missing:
		frappe.throw(
			_("Live production requires: {0}").format(", ".join(missing)),
			title=title,
		)
