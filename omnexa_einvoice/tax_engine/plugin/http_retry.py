# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""HTTP helpers for international tax ASP calls (retry, idempotency)."""

from __future__ import annotations

import time
from typing import Any

import frappe
import requests
from frappe import _


def build_idempotency_key(
	*,
	country_code: str,
	uuid: str,
	document: dict[str, Any] | None = None,
	config: dict[str, Any] | None = None,
) -> str:
	cfg = config or {}
	explicit = (cfg.get("idempotency_key") or "").strip()
	if explicit:
		return explicit[:128]
	ref = ""
	if document:
		ref = (document.get("reference_name") or "").strip()
	base = uuid or ref or "no-uuid"
	return f"{country_code}-{base}"[:128]


def post_json_with_retry(
	url: str,
	*,
	headers: dict[str, str],
	payload: dict[str, Any],
	timeout: int,
	max_retries: int,
	backoff_seconds: float = 1.0,
) -> requests.Response:
	"""POST with retries on network errors, HTTP 429, and 5xx."""
	last_exc: Exception | None = None
	attempts = max(0, int(max_retries)) + 1
	for attempt in range(attempts):
		try:
			res = requests.post(url, headers=headers, json=payload, timeout=timeout)
			if res.status_code == 429 and attempt < attempts - 1:
				time.sleep(backoff_seconds * (2**attempt))
				continue
			if res.status_code >= 500 and attempt < attempts - 1:
				time.sleep(backoff_seconds * (2**attempt))
				continue
			return res
		except requests.RequestException as exc:
			last_exc = exc
			if attempt >= attempts - 1:
				frappe.throw(_("Tax API request failed: {0}").format(exc), title=_("Tax Plugin"))
			time.sleep(backoff_seconds * (2**attempt))
	if last_exc:
		frappe.throw(_("Tax API request failed: {0}").format(last_exc), title=_("Tax Plugin"))
	frappe.throw(_("Tax API request failed."), title=_("Tax Plugin"))
