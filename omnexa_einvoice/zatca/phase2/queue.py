# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 2 background queue with retries."""

from __future__ import annotations

from typing import Any

import frappe

from omnexa_einvoice.zatca import audit


def enqueue_phase2_submission(payload: dict[str, Any], *, log_name: str | None = None) -> str:
	reference = (payload.get("reference_name") or "").strip()
	job_id = f"zatca-phase2-{reference}"
	frappe.enqueue(
		"omnexa_einvoice.zatca.phase2.queue.process_phase2_job",
		queue="long",
		timeout=600,
		job_name=job_id,
		payload=payload,
		log_name=log_name,
	)
	audit.log_zatca_event(
		"phase2_queued",
		company=payload.get("company"),
		reference=reference,
		phase="phase2",
		document_type=payload.get("document_type"),
		ok=True,
	)
	return job_id


def process_phase2_job(payload: dict, log_name: str | None = None):
	from omnexa_einvoice.zatca.phase2.service import run_phase2

	try:
		result = run_phase2(payload, sync=True)
		if log_name:
			frappe.db.set_value(
				"ZATCA Submission Log",
				log_name,
				{
					"status": result.get("zatca_status") or "Submitted",
					"response_payload": frappe.as_json(result.get("api") or {})
	},
			)
	except Exception as exc:
		if log_name:
			frappe.db.set_value(
				"ZATCA Submission Log",
				log_name,
				{"status": "Failed", "error_message": str(exc)[:140]
	},
			)
		raise
