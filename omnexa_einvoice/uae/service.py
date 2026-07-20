# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""UAE PINT AE Phase 1 + Phase 2 orchestration."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.plugin.archive import archive_artifacts
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_document_for_production, validate_production_settings
from omnexa_einvoice.tax_engine.plugin.signing import sign_invoice_xml
from omnexa_einvoice.tax_engine.plugin.submission_log import create_log, update_log
from omnexa_einvoice.uae.api_client import submit_to_asp
from omnexa_einvoice.uae.document import build_from_payload
from omnexa_einvoice.uae.ubl_builder import build_pint_ae_ubl


def run_phase1(payload: dict[str, Any]) -> dict[str, Any]:
	company = payload.get("company") or ""
	branch = payload.get("branch") or None
	validate_production_settings(company, "AE", phase="phase1", branch=branch)
	document = build_from_payload(payload)
	document["branch"] = branch or document.get("branch")
	validate_document_for_production(document, "AE")
	xml_text = build_pint_ae_ubl(document)
	sign_data = sign_invoice_xml(
		xml_text, country_code="AE", company=document.get("company") or company, branch=branch
	)
	company = document.get("company") or company or ""
	paths = archive_artifacts(
		country_code="AE",
		company=company,
		reference_name=document.get("reference_name") or "",
		uuid=document.get("uuid") or "",
		xml_text=sign_data.get("signed_xml") or xml_text,
		document=document,
		extra={"authority": "UAE_PEPPOL", "phase": "phase1", "framework": "PINT-AE"},
	)
	log_name = create_log(
		{
			"company": company,
			"reference_name": document.get("reference_name"),
			"reference_doctype": document.get("reference_doctype") or "Sales Invoice",
		},
		country_code="AE",
		phase="phase1",
		status="Signed",
	)
	if log_name:
		update_log(
			log_name,
			uuid=document.get("uuid"),
			invoice_hash=sign_data.get("hash_hex"),
			archive_paths=json.dumps(paths),
		)
	return {
		"ok": True,
		"phase": "phase1",
		"country_code": "AE",
		"authority": "UAE_PEPPOL",
		"framework": "PINT-AE",
		"label": _("UAE e-Invoicing"),
		"uuid": document.get("uuid"),
		"signed_xml": sign_data.get("signed_xml"),
		"invoice_hash": sign_data.get("hash_hex"),
		"hash_b64": sign_data.get("hash_b64"),
		"document": document,
		"archive_paths": paths,
		"log_name": log_name,
	}


def execute_uae_phase2_submit(payload: dict[str, Any], *, phase1: dict[str, Any]) -> dict[str, Any]:
	"""ASP submit only — reuses existing Phase 1 result."""
	from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api

	log_name = phase1.get("log_name")
	company = payload.get("company") or (phase1.get("document") or {}).get("company") or ""
	status = "Submitted"

	if allow_mock_api():
		api_result = {"ok": True, "mock": True, "status": "ACCEPTED", "authority": "UAE_PEPPOL"}
	else:
		try:
			api_result = submit_to_asp(
				company=company,
				uuid=phase1.get("uuid") or "",
				hash_b64=phase1.get("hash_b64") or "",
				signed_xml=phase1.get("signed_xml") or "",
				document=phase1.get("document") or {},
			)
		except Exception as exc:
			if log_name:
				update_log(log_name, status="Failed", error_message=str(exc)[:140])
			raise

	if log_name:
		update_log(
			log_name,
			status=status,
			authority_status=api_result.get("status"),
			response_payload=frappe.as_json(api_result.get("raw") or api_result),
		)

	return {
		"ok": True,
		"phase": "phase2",
		"status": "submitted",
		"phase1": phase1,
		"api": api_result,
		"log_name": log_name,
	}


def run_phase2(payload: dict[str, Any], *, sync: bool = False) -> dict[str, Any]:
	from omnexa_einvoice.tax_engine.plugin.queue import enqueue_phase2

	phase1 = payload.get("phase1") or run_phase1(payload)
	log_name = phase1.get("log_name")

	if not sync:
		job_id = enqueue_phase2(payload, country_code="AE", log_name=log_name, phase1=phase1)
		return {
			"ok": True,
			"phase": "phase2",
			"status": "queued",
			"job_id": job_id,
			"phase1": phase1,
			"log_name": log_name,
		}

	return execute_uae_phase2_submit(payload, phase1=phase1)
