# -*- coding: utf-8 -*-
"""
PIN + Chilkat unlock for epass2003_agent (Temp-ETR compatible).
Copy with epass2003_agent.py to D:\\python\\ on Windows.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

ERP_RESOLVE_METHOD = (
	"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission."
	"e_invoice_submission.resolve_usb_sign_session"
)

_session_secrets_cache: dict[str, dict[str, str]] = {}


def fetch_erp_sign_session_secrets(data: dict[str, Any]) -> dict[str, str]:
	"""One-time fetch: PIN + chilkat_unlock_code from ERP (same sign_session as USB PIN)."""
	session_id = (data.get("sign_session") or "").strip()
	if not session_id:
		return {}
	if session_id in _session_secrets_cache:
		return _session_secrets_cache[session_id]

	erp_base = (data.get("erp_base_url") or os.getenv("ERP_BASE_URL") or "").strip().rstrip("/")
	if not erp_base:
		return {}
	try:
		import requests

		url = f"{erp_base}/api/method/{ERP_RESOLVE_METHOD}"
		res = requests.get(url, params={"session_id": session_id}, timeout=30)
		body = res.json() if res.content else {}
		msg = body.get("message") if isinstance(body, dict) else {}
		if isinstance(msg, dict):
			secrets = {
				"pin": (msg.get("pin") or msg.get("usb_token_pin") or "").strip(),
				"chilkat_unlock_code": (msg.get("chilkat_unlock_code") or "").strip(),
			}
			if secrets.get("pin"):
				logger.info(
					"ERP sign_session: pin_len=%s chilkat_key=%s",
					len(secrets["pin"]),
					"yes" if secrets.get("chilkat_unlock_code") else "no",
				)
			_session_secrets_cache[session_id] = secrets
			return secrets
		logger.error("ERP sign_session failed: HTTP %s %s", res.status_code, (res.text or "")[:300])
	except Exception as exc:
		logger.error("ERP sign_session request error: %s", exc)
	return {}


def resolve_chilkat_unlock_code(data: dict[str, Any]) -> str:
	"""ERP session → body field → env (see chilkat_license.py)."""
	direct = (data.get("chilkat_unlock_code") or data.get("CHILKAT_UNLOCK_CODE") or "").strip()
	if direct:
		return direct
	secrets = fetch_erp_sign_session_secrets(data)
	return (secrets.get("chilkat_unlock_code") or "").strip()


def fetch_pin_from_erp_sign_session(data: dict[str, Any]) -> str:
	secrets = fetch_erp_sign_session_secrets(data)
	return (secrets.get("pin") or "").strip()


def resolve_token_pin(data: dict[str, Any]) -> str:
	"""Plain pin, base64 fields, or ERP sign_session (no PIN in browser JSON)."""
	pin = (data.get("pin") or data.get("usb_token_pin") or "").strip()
	if pin:
		return pin
	for key in ("pin_b64", "usb_pin_b64", "signing_secret_b64"):
		raw = (data.get(key) or "").strip()
		if not raw:
			continue
		try:
			decoded = base64.b64decode(raw).decode("utf-8").strip()
			if decoded:
				return decoded
		except Exception:
			continue
	return fetch_pin_from_erp_sign_session(data)
