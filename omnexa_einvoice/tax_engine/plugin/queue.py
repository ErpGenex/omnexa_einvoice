# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from typing import Any

import frappe


def enqueue_phase2(
	payload: dict,
	*,
	country_code: str,
	log_name: str | None = None,
	phase1: dict[str, Any] | None = None,
) -> str:
	ref = (payload.get("reference_name") or "").strip()
	code = (country_code or "").strip().upper()
	job_id = f"tax-plugin-{code}-{ref}"
	frappe.enqueue(
		"omnexa_einvoice.tax_engine.plugin.queue.process_phase2_job",
		queue="long",
		timeout=600,
		job_name=job_id,
		payload=payload,
		country_code=code,
		log_name=log_name,
		phase1=phase1,
	)
	return job_id


def process_phase2_job(
	payload: dict,
	country_code: str,
	log_name: str | None = None,
	phase1: dict[str, Any] | None = None,
):
	"""Background Phase 2 — reuses phase1 when provided (no duplicate XML generation)."""
	code = (country_code or "").strip().upper()

	if code == "AE":
		from omnexa_einvoice.uae.service import execute_uae_phase2_submit, run_phase1 as uae_run_phase1

		if not phase1:
			phase1 = uae_run_phase1(payload)
		execute_uae_phase2_submit(payload, phase1=phase1)
		return

	from omnexa_einvoice.tax_engine.plugin.pipeline import (
		execute_country_phase2_submit,
		run_country_phase1,
	)

	if not phase1:
		phase1 = run_country_phase1(payload, country_code=code)
	execute_country_phase2_submit(payload, country_code=code, phase1=phase1)
