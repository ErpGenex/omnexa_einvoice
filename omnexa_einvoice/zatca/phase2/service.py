# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 2 — sign locally then clearance or reporting."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.zatca import audit
from omnexa_einvoice.zatca.constants import DOCUMENT_SIMPLIFIED_INVOICE
from omnexa_einvoice.zatca.phase1.service import run_phase1
from omnexa_einvoice.zatca.phase2.clearance import submit_clearance
from omnexa_einvoice.zatca.phase2.queue import enqueue_phase2_submission
from omnexa_einvoice.zatca.phase2.reporting import submit_reporting
from omnexa_einvoice.zatca.settings import get_company_settings
from omnexa_einvoice.zatca.submission_log import create_submission_log, update_submission_log


def _resolve_phase2_settings(payload: dict[str, Any]):
	company = (payload.get("company") or "").strip()
	branch = (payload.get("branch") or "").strip() or None
	csid_ref = (payload.get("csid_reference") or "").strip()
	if branch:
		from omnexa_einvoice.zatca.branch_settings import branch_has_zatca

		if branch_has_zatca(branch):
			return get_company_settings(company, branch=branch)
	if company and frappe.db.exists("ZATCA Company Settings", {"company": company, "enabled": 1
	}):
		return get_company_settings(company, branch=branch)
	if csid_ref:
		return None
	frappe.throw(_("company with ZATCA Company Settings or csid_reference is required for Phase 2."))


def run_phase2(payload: dict[str, Any], *, sync: bool = False) -> dict[str, Any]:
	settings = _resolve_phase2_settings(payload)
	if settings and settings.zatca_phase != "Phase 2" and not (payload.get("csid_reference") or "").strip():
		frappe.msgprint(_("ZATCA Company Settings phase is not Phase 2 — API submit may fail without CSID."))

	log_name = None
	if frappe.db.table_exists("tabZATCA Submission Log"):
		log_name = create_submission_log(payload, phase="phase2", status="Draft")
	phase1_result = run_phase1(payload)
	if log_name:
		update_submission_log(
			log_name,
			status="Signed",
			uuid=phase1_result.get("uuid"),
			invoice_hash=phase1_result.get("invoice_hash"),
			qr_base64=phase1_result.get("qr_base64"),
		)

	if not settings:
		return {
			"ok": True,
			"phase": "phase2",
			"status": "queued",
			"message": _("ZATCA Phase 2 queued (awaiting company CSID configuration)."),
			"phase1": phase1_result,
			"log_name": log_name
	}

	signed_xml = phase1_result.get("signed_xml") or ""
	uuid = phase1_result.get("uuid") or ""
	hash_b64 = phase1_result.get("hash_b64") or ""
	document_type = (payload.get("document_type") or "").strip().lower()

	if frappe.conf.get("zatca_mock_api") or frappe.flags.in_test:
		api_result = {"ok": True, "mock": True, "status": "REPORTED"
	}
		zatca_status = "Reported" if document_type == DOCUMENT_SIMPLIFIED_INVOICE else "Cleared"
	else:
		if not sync:
			job_id = enqueue_phase2_submission(payload, log_name=log_name)
			return {
				"ok": True,
				"phase": "phase2",
				"status": "queued",
				"message": "ZATCA Phase 2 queued for API submission.",
				"phase1": phase1_result,
				"job_id": job_id,
				"log_name": log_name
	}
		try:
			if document_type == DOCUMENT_SIMPLIFIED_INVOICE:
				api_result = submit_reporting(
					settings=settings,
					signed_xml=signed_xml,
					invoice_hash_b64=hash_b64,
					uuid=uuid,
				)
				zatca_status = "Reported"
			else:
				api_result = submit_clearance(
					settings=settings,
					signed_xml=signed_xml,
					invoice_hash_b64=hash_b64,
					uuid=uuid,
				)
				zatca_status = "Cleared"
		except Exception as exc:
			update_submission_log(log_name, status="Failed", error_message=str(exc))
			audit.log_zatca_event(
				"phase2_failed",
				company=(settings.company if settings else payload.get("company")),
				reference=payload.get("reference_name"),
				phase="phase2",
				ok=False,
				details={"error": str(exc)
	},
			)
			raise

	zatca_field_status = api_result.get("clearance_status") or api_result.get("reporting_status")
	log_updates = {
		"status": zatca_status,
		"zatca_status": zatca_field_status,
		"response_payload": frappe.as_json(api_result.get("raw") or api_result)
	}
	if api_result.get("qr_tlv"):
		log_updates["qr_base64"] = api_result.get("qr_tlv")
	if log_name:
		update_submission_log(log_name, **log_updates)

	return {
		"ok": True,
		"phase": "phase2",
		"status": "submitted",
		"zatca_status": zatca_status,
		"phase1": phase1_result,
		"api": api_result,
		"log_name": log_name,
		"cleared_invoice_xml": api_result.get("cleared_invoice_xml")
	}
