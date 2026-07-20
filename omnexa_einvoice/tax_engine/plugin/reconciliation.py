# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Reconciliation worker for international tax submissions (plugin only)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code
from omnexa_einvoice.tax_engine.plugin.lifecycle import ACCEPTED, FAILED, SUBMITTED, normalize_authority_status


def enqueue_reconciliation(log_name: str, *, delay_seconds: int = 300) -> str | None:
	if not log_name or not frappe.db.table_exists("tabCountry Tax Submission Log"):
		return None
	job_id = f"tax-reconcile-{log_name}"
	frappe.enqueue(
		"omnexa_einvoice.tax_engine.plugin.reconciliation.reconcile_submission_log",
		queue="short",
		timeout=300,
		job_name=job_id,
		log_name=log_name,
		at_front=False,
		enqueue_after_commit=True,
	)
	return job_id


def reconcile_submission_log(log_name: str) -> dict[str, Any]:
	"""Poll ASP status when configured; update Country Tax Submission Log."""
	if not frappe.db.exists("Country Tax Submission Log", log_name):
		return {"ok": False, "error": "log not found"
	}

	log = frappe.get_doc("Country Tax Submission Log", log_name)
	code = normalize_country_code(log.country_code)
	if code in ("EG", "SA"):
		return {"ok": False, "skipped": True, "reason": "EG/SA use dedicated reconciliation"
	}

	if log.status in (ACCEPTED, "Accepted", "Failed", "Cancelled"):
		return {"ok": True, "skipped": True, "status": log.status
	}

	config = _log_poll_config(log)
	if not config.get("poll_enabled"):
		return {"ok": True, "skipped": True, "reason": "poll_disabled"
	}

	# Placeholder: ASP-specific poll URLs are per-country wave. Until wired, normalize stored response.
	raw = {}
	if log.response_payload:
		try:
			raw = json.loads(log.response_payload)
		except json.JSONDecodeError:
			raw = {"raw": log.response_payload
	}

	status = normalize_authority_status(
		str(raw.get("status") or log.authority_status or raw.get("clearanceStatus") or "")
	)
	updates: dict[str, Any] = {"authority_status": status
	}
	if status == ACCEPTED:
		updates["status"] = "Accepted"
	elif status == FAILED:
		updates["status"] = "Failed"
	else:
		updates["status"] = SUBMITTED

	frappe.db.set_value("Country Tax Submission Log", log_name, updates, update_modified=True)
	return {"ok": True, "log_name": log_name, **updates}


def _log_poll_config(log) -> dict[str, Any]:
	branch = frappe.db.get_value(
		"Branch",
		{"company": log.company
	},
		["name", "intl_tax_configuration_json"],
		as_dict=True,
	)
	if not branch or not branch.get("intl_tax_configuration_json"):
		return {"poll_enabled": False
	}
	try:
		cfg = json.loads(branch.intl_tax_configuration_json)
		return cfg if isinstance(cfg, dict) else {}
	except json.JSONDecodeError:
		return {"poll_enabled": False
	}
