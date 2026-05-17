# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
E-Invoice auto-send after sign (Live) and scheduled batch submit.
Mirrors erpnext_egypt_compliance submission_mode Manual / Live / Batch.
E-Receipt is never auto-sent from here.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings
from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent

SUBMISSION_MODE_MANUAL = "manual"
SUBMISSION_MODE_LIVE = "live"
SUBMISSION_MODE_BATCH = "batch"


def normalize_submission_mode(mode: str | None) -> str:
	value = (mode or "Manual").strip().lower()
	if value in (SUBMISSION_MODE_LIVE, "live"):
		return SUBMISSION_MODE_LIVE
	if value in (SUBMISSION_MODE_BATCH, "batch"):
		return SUBMISSION_MODE_BATCH
	return SUBMISSION_MODE_MANUAL


def branch_submission_mode(branch: str) -> str:
	if not branch:
		return SUBMISSION_MODE_MANUAL
	return normalize_submission_mode(
		frappe.db.get_value("Branch", branch, "eta_einvoice_submission_mode")
	)


def branch_batch_size(branch: str) -> int:
	return max(1, cint(frappe.db.get_value("Branch", branch, "eta_einvoice_batch_size") or 10))


def branch_send_delay_hours(branch: str) -> float:
	return max(0.0, flt(frappe.db.get_value("Branch", branch, "eta_einvoice_send_delay_hours") or 0))


def live_send_requires_browser(branch: str) -> bool:
	"""USB signing agent must re-sign in the browser before ETA send."""
	return uses_browser_signing_agent(branch)


def maybe_enqueue_live_send_after_sign(submission_name: str) -> dict:
	"""
	After E-Invoice sign: enqueue server-side ETA send when mode is Live and signer is remote/windows_app.
	Signing-agent branches return browser_live=True for the client to call Send.
	"""
	doc = frappe.get_doc("E Invoice Submission", submission_name)
	if doc.submission_kind == "E-Receipt":
		return {"enqueued": False, "browser_live": False}
	branch = (doc.branch or "").strip()
	if branch_submission_mode(branch) != SUBMISSION_MODE_LIVE:
		return {"enqueued": False, "browser_live": False}
	if live_send_requires_browser(branch):
		return {"enqueued": False, "browser_live": True}
	_enqueue_send(submission_name, job_name=f"eta_live_{submission_name}")
	return {"enqueued": True, "browser_live": False}


def _enqueue_send(submission_name: str, *, job_name: str) -> None:
	frappe.enqueue(
		method="omnexa_einvoice.e_invoice.auto_submit.send_submission_to_eta_background",
		queue="short",
		name=submission_name,
		user=frappe.session.user,
		job_name=job_name,
		now=False,
	)


def send_submission_to_eta_background(name: str, user: str | None = None) -> None:
	"""Background job: POST signed document to ETA (server can re-sign remote/HMAC)."""
	if user:
		frappe.set_user(user)
	try:
		from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
			send_submission_to_eta,
		)

		send_submission_to_eta(name)
	except Exception:
		frappe.log_error(
			title=_("E-Invoice auto-send failed"),
			message=frappe.get_traceback(),
		)
		raise


def _submission_passes_delay(submission_name: str, delay_hours: float) -> bool:
	if delay_hours <= 0:
		return True
	modified = frappe.db.get_value("E Invoice Submission", submission_name, "modified")
	if not modified:
		return True
	if isinstance(modified, str):
		modified = frappe.utils.get_datetime(modified)
	threshold = now_datetime() - timedelta(hours=delay_hours)
	return modified <= threshold


def get_signed_submissions_for_batch(branch: str, *, limit: int | None = None) -> list[str]:
	"""Signed E-Invoice submissions not yet completed (batch candidates)."""
	limit = limit or branch_batch_size(branch)
	return frappe.get_all(
		"E Invoice Submission",
		filters={
			"submission_kind": "E-Invoice",
			"branch": branch,
			"status": "Signed",
			"docstatus": 0,
		},
		pluck="name",
		order_by="modified asc",
		limit=limit,
	)


def process_branch_einvoice_batch(branch: str) -> int:
	"""Enqueue ETA send for one branch (remote/windows_app only)."""
	branch = (branch or "").strip()
	if not branch or branch_submission_mode(branch) != SUBMISSION_MODE_BATCH:
		return 0
	if live_send_requires_browser(branch):
		frappe.logger("omnexa_einvoice").info(
			"Batch skip branch=%s: signing_agent requires browser send", branch
		)
		return 0
	try:
		get_eta_invoice_branch_settings(branch)
	except Exception:
		return 0

	delay = branch_send_delay_hours(branch)
	enqueued = 0
	for name in get_signed_submissions_for_batch(branch):
		if not _submission_passes_delay(name, delay):
			continue
		_enqueue_send(name, job_name=f"eta_batch_{name}")
		enqueued += 1
	return enqueued


def autosubmit_einvoice_batch_process() -> None:
	"""Hourly: send signed E-Invoices for branches in Batch mode."""
	branches = frappe.get_all(
		"Branch",
		filters={"eta_einvoice_enabled": 1, "eta_einvoice_submission_mode": "Batch"},
		pluck="name",
	)
	for branch in branches:
		try:
			count = process_branch_einvoice_batch(branch)
			if count:
				frappe.logger("omnexa_einvoice").info("Batch enqueued %s submissions for %s", count, branch)
		except Exception:
			frappe.log_error(
				title=_("E-Invoice batch auto-send"),
				message=frappe.get_traceback(),
			)
