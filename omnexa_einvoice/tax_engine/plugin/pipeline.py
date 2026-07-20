# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Shared Phase 1 / Phase 2 pipeline — production gates for all plugin countries."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings
from omnexa_einvoice.tax_engine.plugin.archive import archive_artifacts
from omnexa_einvoice.tax_engine.plugin.engines.document_enrich import build_enriched_document
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api
from omnexa_einvoice.tax_engine.plugin.production_validate import (
	validate_document_for_production,
	validate_production_settings,
)
from omnexa_einvoice.tax_engine.plugin.registry import get_engine, is_dedicated_module
from omnexa_einvoice.tax_engine.plugin.document_validate import validate_document_xml
from omnexa_einvoice.tax_engine.plugin.lifecycle import ACCEPTED, map_api_result_to_log_status
from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key
from omnexa_einvoice.tax_engine.plugin.signing import sign_invoice_xml
from omnexa_einvoice.tax_engine.plugin.signing_providers import signing_family_for_country
from omnexa_einvoice.tax_engine.plugin.specs import get_spec
from omnexa_einvoice.tax_engine.plugin.submission_log import create_log, update_log


def run_country_phase1(payload: dict[str, Any], *, country_code: str) -> dict[str, Any]:
	code = normalize_country_code(country_code)
	if is_dedicated_module(code):
		from omnexa_einvoice.uae.service import run_phase1 as uae_run_phase1

		return uae_run_phase1(payload)

	company = payload.get("company") or ""
	branch = payload.get("branch") or ""
	validate_production_settings(company, code, phase="phase1", branch=branch or None)

	engine = get_engine(code)
	spec = get_spec(code)
	meta = COUNTRY_REGISTRY.get(code)
	document = build_enriched_document(payload, country_code=code)
	validate_document_for_production(document, code)
	xml_text = engine.build_xml(document)
	config: dict = {}
	settings_row = get_country_tax_settings(company, code, branch=branch or None) if company or branch else None
	if settings_row and settings_row.get("configuration_json"):
		try:
			config = json.loads(settings_row.configuration_json)
			if not isinstance(config, dict):
				config = {}
		except json.JSONDecodeError:
			config = {}
	validate_document_xml(xml_text, code, config=config)
	sign_data = sign_invoice_xml(
		xml_text, country_code=code, company=company, branch=branch or None
	)
	company = document.get("company") or company or ""
	paths = archive_artifacts(
		country_code=code,
		company=company,
		reference_name=document.get("reference_name") or "",
		uuid=document.get("uuid") or "",
		xml_text=sign_data.get("signed_xml") or xml_text,
		document=document,
		extra={
			"authority": engine.authority_code,
			"phase": "phase1",
			"framework": engine.framework,
			"signer": sign_data.get("signer"),
			"production": not allow_mock_api(),
		},
	)
	idem = build_idempotency_key(
		country_code=code,
		uuid=document.get("uuid") or "",
		document=document,
		config=config,
	)
	sign_family = sign_data.get("signing_family") or signing_family_for_country(code)
	log_name = create_log(
		{
			"company": company,
			"reference_name": document.get("reference_name"),
			"reference_doctype": document.get("reference_doctype") or "Sales Invoice",
			"idempotency_key": idem,
			"signing_family": sign_family,
		},
		country_code=code,
		phase="phase1",
		status="Signed",
	)
	if log_name:
		update_log(
			log_name,
			uuid=document.get("uuid"),
			invoice_hash=sign_data.get("hash_hex"),
			archive_paths=json.dumps(paths),
			idempotency_key=idem,
			signing_family=sign_family,
		)
	return {
		"ok": True,
		"phase": "phase1",
		"country_code": code,
		"authority": engine.authority_code,
		"framework": engine.framework,
		"label": meta.label if meta else code,
		"uuid": document.get("uuid"),
		"signed_xml": sign_data.get("signed_xml"),
		"invoice_hash": sign_data.get("hash_hex"),
		"hash_b64": sign_data.get("hash_b64"),
		"signer": sign_data.get("signer"),
		"document": document,
		"archive_paths": paths,
		"log_name": log_name,
	}


def execute_country_phase2_submit(
	payload: dict[str, Any],
	*,
	country_code: str,
	phase1: dict[str, Any],
) -> dict[str, Any]:
	"""ASP submit only — reuses an existing Phase 1 result (no XML regeneration)."""
	from omnexa_einvoice.tax_engine.plugin.country_api_router import submit_country_invoice

	code = normalize_country_code(country_code)
	log_name = phase1.get("log_name")
	company = payload.get("company") or (phase1.get("document") or {}).get("company") or ""
	document = phase1.get("document") or {}

	try:
		api_result = submit_country_invoice(
			country_code=code,
			company=company,
			uuid=phase1.get("uuid") or "",
			hash_b64=phase1.get("hash_b64") or "",
			signed_xml=phase1.get("signed_xml") or "",
			document=document,
		)
		api_result.setdefault("framework", phase1.get("framework"))
	except Exception as exc:
		if log_name:
			update_log(log_name, status="Failed", error_message=str(exc)[:140])
		raise

	log_status = map_api_result_to_log_status(api_result)
	log_updates: dict[str, Any] = {
		"status": log_status,
		"authority_status": api_result.get("status"),
		"response_payload": frappe.as_json(api_result.get("raw") or api_result),
	}
	if api_result.get("idempotency_key"):
		log_updates["idempotency_key"] = api_result["idempotency_key"]
	if log_status == ACCEPTED:
		log_updates["status"] = "Accepted"
	if code == "IN" and api_result.get("irn"):
		log_updates["uuid"] = api_result["irn"]
	if code == "MX" and api_result.get("sat_uuid"):
		log_updates["uuid"] = api_result["sat_uuid"]
	if code == "IT" and api_result.get("sdi_id"):
		log_updates["uuid"] = api_result["sdi_id"]
	if code == "BR" and api_result.get("chave_acesso"):
		log_updates["uuid"] = api_result["chave_acesso"]
	if code == "PL" and api_result.get("ksef_number"):
		log_updates["uuid"] = api_result["ksef_number"]
	if code == "ES" and api_result.get("registro_id"):
		log_updates["uuid"] = api_result["registro_id"]
	if code == "CO" and api_result.get("cufe"):
		log_updates["uuid"] = api_result["cufe"]
	if code == "DE" and api_result.get("tracking_id"):
		log_updates["uuid"] = api_result["tracking_id"]
	if code == "FR" and api_result.get("flow_id"):
		log_updates["uuid"] = api_result["flow_id"]
	if code == "AE" and (api_result.get("asp_reference") or api_result.get("uuid")):
		log_updates["uuid"] = api_result.get("asp_reference") or api_result.get("uuid")
	if code in ("AR", "CL", "PE", "JO") and (
		api_result.get("authority_reference") or api_result.get("uuid")
	):
		log_updates["uuid"] = api_result.get("authority_reference") or api_result.get("uuid")

	if log_name:
		update_log(log_name, **log_updates)
		try:
			from omnexa_einvoice.tax_engine.plugin.reconciliation import enqueue_reconciliation

			enqueue_reconciliation(log_name)
		except Exception:
			pass

	return {
		"ok": True,
		"phase": "phase2",
		"status": "submitted",
		"phase1": phase1,
		"api": api_result,
		"log_name": log_name,
	}


def run_country_phase2(payload: dict[str, Any], *, country_code: str, sync: bool = False) -> dict[str, Any]:
	code = normalize_country_code(country_code)
	if is_dedicated_module(code):
		from omnexa_einvoice.uae.service import run_phase2 as uae_run_phase2

		return uae_run_phase2(payload, sync=sync)

	from omnexa_einvoice.tax_engine.plugin.queue import enqueue_phase2

	phase1 = payload.get("phase1") or run_country_phase1(payload, country_code=code)
	log_name = phase1.get("log_name")

	if not sync:
		job_id = enqueue_phase2(payload, country_code=code, log_name=log_name, phase1=phase1)
		return {
			"ok": True,
			"phase": "phase2",
			"status": "queued",
			"job_id": job_id,
			"phase1": phase1,
			"log_name": log_name,
		}

	return execute_country_phase2_submit(payload, country_code=code, phase1=phase1)
