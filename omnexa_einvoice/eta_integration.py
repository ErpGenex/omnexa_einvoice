# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Egypt ETA integration helpers: OAuth token cache, poll normalization, E-Document Submission updates.

This module lives in the **omnexa_einvoice** app so e-Invoice / e-Receipt logic stays installable
separately from ``omnexa_core``.
"""

from __future__ import annotations

import json
import time
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from omnexa_einvoice.eta_receipt import ETA_TOKEN_URLS

from omnexa_core.omnexa_core.constants import (
	DOC_STATUS_ACCEPTED,
	DOC_STATUS_QUEUED,
	DOC_STATUS_REJECTED,
	DOC_STATUS_SENT,
	DOC_STATUS_SUBMITTED,
)

ETA_TOKEN_CACHE_PREFIX = "omnexa_eta_token:"


def _local_token_bucket() -> dict[str, dict[str, Any]]:
	bucket = getattr(frappe.local, "_omnexa_eta_token_bucket", None)
	if bucket is None:
		bucket = {}
		frappe.local._omnexa_eta_token_bucket = bucket
	return bucket


# Map common ETA / portal status strings to E-Document Submission authority_status options.
ETA_AUTHORITY_STATUS_MAP = {
	"draft": DOC_STATUS_QUEUED,
	"queued": DOC_STATUS_QUEUED,
	"pending": DOC_STATUS_QUEUED,
	"sent": DOC_STATUS_SENT,
	"submitted": DOC_STATUS_SUBMITTED,
	"valid": DOC_STATUS_ACCEPTED,
	"accepted": DOC_STATUS_ACCEPTED,
	"invalid": DOC_STATUS_REJECTED,
	"rejected": DOC_STATUS_REJECTED,
	"cancelled": DOC_STATUS_REJECTED,
	"canceled": DOC_STATUS_REJECTED,
}


def eta_token_cache_key(profile_key: str) -> str:
	return f"{ETA_TOKEN_CACHE_PREFIX}{(profile_key or 'default').strip() or 'default'}"


def get_cached_eta_token_state(profile_key: str) -> dict[str, Any] | None:
	pk = (profile_key or "default").strip() or "default"
	local = _local_token_bucket().get(pk)
	if isinstance(local, dict):
		return local
	val = frappe.cache().get_value(eta_token_cache_key(pk))
	if isinstance(val, dict):
		_local_token_bucket()[pk] = val
	return val if isinstance(val, dict) else None


def set_cached_eta_token_state(profile_key: str, state: dict[str, Any]) -> None:
	pk = (profile_key or "default").strip() or "default"
	_local_token_bucket()[pk] = state
	expires_in = int(state.get("expires_in") or 3600)
	ttl = max(60, min(expires_in, 86400))
	frappe.cache().set_value(eta_token_cache_key(pk), state, expires_in_sec=ttl)


def eta_token_needs_refresh(state: dict[str, Any] | None, skew_seconds: int = 120) -> bool:
	if not state or not state.get("access_token"):
		return True
	exp_ts = state.get("expires_at_ts")
	if isinstance(exp_ts, (int, float)):
		return time.time() >= float(exp_ts) - skew_seconds
	exp = state.get("expires_at")
	if not exp:
		return True
	try:
		exp_dt = get_datetime(exp)
	except Exception:
		return True
	return now_datetime() >= add_to_date(exp_dt, seconds=-skew_seconds)


def exchange_eta_token(
	client_id: str,
	client_secret: str,
	environment: str = "preprod",
	pos_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
	"""Obtain access token from ETA identity API (OAuth2 client_credentials).

	For e-Receipt (POS), ETA requires ``posserial`` / ``pososversion`` headers on the token request.
	"""
	client_id = (client_id or "").strip()
	client_secret = (client_secret or "").strip()
	if not client_id or not client_secret:
		frappe.throw(_("ETA client_id and client_secret are required."), title=_("ETA Auth"))
	from omnexa_einvoice.branch_eta import _is_masked_secret

	if _is_masked_secret(client_secret):
		frappe.throw(
			_(
				"ETA client secret is missing or masked. Open Branch → Egypt ETA, "
				"type the E-Receipt Client Secret again, and save."
			),
			title=_("ETA Auth"),
		)

	conf = frappe.get_conf() or {}
	use_stub = bool(conf.get("omnexa_eta_use_stub_token"))
	if use_stub:
		token = frappe.generate_hash(length=24)
		expires_in = 3500
		expires_at = add_to_date(now_datetime(), seconds=expires_in)
		return {
			"access_token": token,
			"token_type": "Bearer",
			"expires_in": expires_in,
			"expires_at_ts": time.time() + expires_in,
			"expires_at": str(expires_at),
			"environment": (environment or "preprod").strip(),
		}

	from omnexa_einvoice.branch_eta import normalize_eta_environment

	env = normalize_eta_environment(environment)
	token_url = ETA_TOKEN_URLS.get(env, ETA_TOKEN_URLS["preprod"])
	data = {
		"grant_type": "client_credentials",
		"client_id": client_id,
		"client_secret": client_secret,
		"scope": "",
	}
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"Accept": "application/json",
	}
	if pos_headers:
		for key, value in pos_headers.items():
			headers[key] = "" if value is None else str(value).strip()

	try:
		res = requests.post(token_url, data=data, headers=headers, timeout=30)
	except requests.RequestException as exc:
		frappe.throw(_("ETA token request failed: {0}").format(exc), title=_("ETA Auth"))

	if res.status_code >= 300:
		body_lower = (res.text or "").lower()
		hint = ""
		if pos_headers:
			if "invalid_client" in body_lower:
				hint = _(
					" For e-Receipt: wrong Client ID/Secret, or preprod credentials used on production."
				)
			elif "unauthorized_client" in body_lower:
				hint = _(
					" Client is valid but not authorized for this POS. Register the POS serial on "
					"invoicing.eta.gov.eg and use the POS e-Receipt credentials (not B2B invoice credentials)."
				)
			else:
				hint = _(
					" For e-Receipt: verify Client ID/Secret, environment (prod), and POS Device Serial on Branch."
				)
		frappe.throw(
			_("ETA token exchange failed ({0}): {1}{2}").format(res.status_code, res.text[:500], hint),
			title=_("ETA Auth"),
		)

	body = res.json()
	access_token = (body.get("access_token") or "").strip()
	if not access_token:
		frappe.throw(_("ETA token response missing access_token."), title=_("ETA Auth"))

	expires_in = int(body.get("expires_in") or 3600)
	expires_at = add_to_date(now_datetime(), seconds=expires_in)
	return {
		"access_token": access_token,
		"token_type": body.get("token_type") or "Bearer",
		"expires_in": expires_in,
		"expires_at_ts": time.time() + expires_in,
		"expires_at": str(expires_at),
		"environment": env,
	}


def ensure_eta_access_token(profile_key: str, credentials: dict[str, Any] | None = None) -> str:
	"""Return a usable access token, using cache or credential exchange."""
	profile_key = (profile_key or "default").strip() or "default"
	cached = get_cached_eta_token_state(profile_key)
	if not eta_token_needs_refresh(cached):
		return str(cached["access_token"])

	creds = credentials or {}
	token_state = exchange_eta_token(
		client_id=str(creds.get("client_id") or ""),
		client_secret=str(creds.get("client_secret") or ""),
		environment=str(creds.get("environment") or "preprod"),
		pos_headers=creds.get("pos_headers") if isinstance(creds.get("pos_headers"), dict) else None,
	)
	set_cached_eta_token_state(profile_key, token_state)
	return str(token_state["access_token"])


def normalize_eta_poll_response(body: dict[str, Any], http_status_code: int = 200) -> dict[str, Any]:
	"""Normalize ETA poll / notification JSON into E-Document Submission fields."""
	raw_status = (
		body.get("status")
		or body.get("documentStatus")
		or body.get("Status")
		or body.get("document_status")
		or ""
	)
	key = str(raw_status).strip().lower()
	if http_status_code >= 400:
		authority_status = DOC_STATUS_REJECTED
	else:
		authority_status = ETA_AUTHORITY_STATUS_MAP.get(key, DOC_STATUS_SENT)
	uuid = (
		body.get("uuid")
		or body.get("submissionUUID")
		or body.get("submissionUuid")
		or body.get("internalId")
		or ""
	)
	err = body.get("errorCode") or body.get("error") or body.get("rejectionReason") or ""
	return {
		"authority_status": authority_status,
		"authority_uuid": str(uuid).strip(),
		"eta_error_code": str(err).strip() if err else "",
		"http_status_code": int(http_status_code),
		"raw": body,
	}


def map_eta_error_to_message(eta_error_code: str) -> str:
	"""Map known ETA error codes to short operator-facing messages (extend per SDK)."""
	code = (eta_error_code or "").strip()
	known = {
		"401": _("Authentication failed; refresh ETA token or check credentials."),
		"403": _("ETA rejected the request; check registration and environment."),
		"INVALID_SIGNATURE": _("Invalid document signature; check e-seal / signer."),
		"INVALID_DOCUMENT": _("Document failed ETA validation; review mapped fields."),
	}
	return str(known.get(code, _("ETA error {0}").format(code)))


def apply_eta_poll_to_submission(submission_name: str, poll: dict[str, Any]) -> None:
	"""Persist normalized poll outcome on an E-Document Submission (typically after submit)."""
	doc = frappe.get_doc("E-Document Submission", submission_name)
	doc.authority_status = poll["authority_status"]
	if poll.get("authority_uuid"):
		doc.authority_uuid = str(poll["authority_uuid"]).strip()
	doc.eta_error_code = (poll.get("eta_error_code") or "")[:140]
	code = poll.get("http_status_code")
	doc.http_status_code = int(code) if code not in (None, "") else None
	raw = poll.get("raw")
	doc.response_body = (json.dumps(raw, default=str) if raw else "")[:140]
	doc.save(ignore_permissions=True)
