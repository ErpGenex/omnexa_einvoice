# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 1 orchestration — full pipeline."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from omnexa_einvoice.zatca import audit
from omnexa_einvoice.zatca.constants import DOCUMENT_SIMPLIFIED_INVOICE, DOCUMENT_TAX_INVOICE
from omnexa_einvoice.zatca.phase1.archive import archive_phase1_artifacts
from omnexa_einvoice.zatca.phase1.invoice_builder import build_invoice_payload, payload_to_json
from omnexa_einvoice.zatca.phase1.qr_embed import embed_qr_in_ubl, qr_tlv_to_png_base64
from omnexa_einvoice.zatca.phase1.tlv_qr import build_tlv_qr_base64
from omnexa_einvoice.zatca.phase1.ubl_builder import build_ubl_invoice_xml
from omnexa_einvoice.zatca.phase1.xades_signing import sign_ubl_xml
from omnexa_einvoice.zatca.settings import (
	get_company_settings,
	get_private_key_pem,
	next_icv_and_pih,
	settings_to_seller_dict,
	update_chain,
)


def _resolve_settings(payload: dict[str, Any]):
	company = (payload.get("company") or "").strip()
	branch = (payload.get("branch") or "").strip() or None
	if branch:
		from omnexa_einvoice.zatca.branch_settings import branch_has_zatca

		if branch_has_zatca(branch):
			return get_company_settings(company, branch=branch)
	if company and frappe.db.exists("ZATCA Company Settings", {"company": company, "enabled": 1}):
		return get_company_settings(company, branch=branch)
	seller = payload.get("document", {}).get("seller") if isinstance(payload.get("document"), dict) else {}
	seller = seller or {}
	return frappe._dict(
		{
			"name": "",
			"company": company,
			"organization_name": seller.get("name") or payload.get("seller_name"),
			"organization_name_ar": seller.get("name_ar") or payload.get("seller_name_ar"),
			"vat_registration_number": seller.get("vat_registration")
			or payload.get("taxpayer_registration_id"),
			"certificate_pem": "",
			"public_key_pem": "",
		}
	)


def _build_document_payload(payload: dict[str, Any], settings, seller: dict) -> dict[str, Any]:
	document_type = (payload.get("document_type") or DOCUMENT_TAX_INVOICE).strip().lower()
	doc = payload.get("document") or {}
	if doc.get("lines"):
		return {
			"uuid": doc.get("uuid"),
			"document_type": document_type,
			"reference_name": payload.get("reference_name"),
			"issue_datetime": doc.get("issue_datetime"),
			"currency": doc.get("currency") or "SAR",
			"lines": doc.get("lines"),
			"totals": doc.get("totals"),
		}
	return build_invoice_payload(
		document_type,
		company=settings.company or payload.get("company") or "",
		reference_name=payload.get("reference_name") or "",
		seller_name=seller.get("name") or "",
		seller_name_ar=seller.get("name_ar") or "",
		vat_registration=seller.get("vat_registration") or "",
	)


def run_phase1(payload: dict[str, Any]) -> dict[str, Any]:
	"""Generate UBL, sign, TLV QR (tags 1–9), archive."""
	settings = _resolve_settings(payload)
	if settings.name:
		seller = settings_to_seller_dict(settings)
		icv, pih = next_icv_and_pih(settings)
		private_key = get_private_key_pem(settings)
		certificate = (settings.certificate_pem or "").strip()
	else:
		seller = {
			"name": payload.get("seller_name") or "Seller",
			"name_ar": payload.get("seller_name_ar") or payload.get("seller_name") or "بائع",
			"vat_registration": payload.get("taxpayer_registration_id") or "",
		}
		icv, pih = 1, ""
		private_key = None
		certificate = ""

	inv = _build_document_payload(payload, settings, seller)
	buyer = (payload.get("document") or {}).get("buyer")
	xml_text, inv_uuid = build_ubl_invoice_xml(inv, icv=icv, previous_hash=pih, seller=seller, buyer=buyer)

	if private_key and certificate:
		sign_data = sign_ubl_xml(xml_text, private_key_pem=private_key, certificate_pem=certificate)
		signed_xml = xml_text  # extension injection in 1.1; hash/signature in QR
	else:
		from omnexa_einvoice.zatca.phase1.signing import sign_invoice_xml

		sign_data = sign_invoice_xml(xml_text)
		signed_xml = sign_data.get("signed_xml") or xml_text

	totals = inv.get("totals") or {}
	qr_b64 = build_tlv_qr_base64(
		seller_name=seller.get("name_ar") or seller.get("name"),
		vat_registration=seller.get("vat_registration"),
		timestamp=inv.get("issue_datetime") or "",
		invoice_total_with_vat=f"{flt(totals.get('grand_total')):.2f}",
		vat_amount=f"{flt(totals.get('tax_total')):.2f}",
		invoice_hash_hex=sign_data.get("hash_hex") or sign_data.get("invoice_hash") or "",
		signature_b64=sign_data.get("signature") or sign_data.get("signature_b64") or "",
		public_key_b64=settings.public_key_pem if settings.get("public_key_pem") else None,
	)
	signed_xml = embed_qr_in_ubl(signed_xml, qr_b64)
	qr_image_b64 = ""
	try:
		qr_image_b64 = qr_tlv_to_png_base64(qr_b64)
	except Exception as exc:
		frappe.log_error(message=str(exc), title="ZATCA QR image")

	json_text = payload_to_json(inv)
	company = settings.company or payload.get("company") or "Unknown"
	paths = archive_phase1_artifacts(
		company=company,
		reference_name=payload.get("reference_name") or "",
		invoice_uuid=inv_uuid,
		xml_text=signed_xml,
		json_text=json_text,
		qr_base64=qr_b64,
		meta={"icv": icv, "hash": sign_data.get("hash_hex")},
	)

	if settings.name and sign_data.get("hash_hex"):
		update_chain(settings, icv, sign_data["hash_hex"])

	audit.log_zatca_event(
		"phase1_complete",
		company=company,
		reference=payload.get("reference_name"),
		phase="phase1",
		document_type=inv.get("document_type"),
		ok=True,
		details={"uuid": inv_uuid, "icv": icv},
	)

	log_name = None
	if frappe.db.table_exists("tabZATCA Submission Log"):
		from omnexa_einvoice.zatca.submission_log import create_submission_log, update_submission_log

		log_name = create_submission_log(payload, phase="phase1", status="Signed")
		update_submission_log(
			log_name,
			uuid=inv_uuid,
			invoice_hash=sign_data.get("hash_hex"),
			qr_base64=qr_b64,
		)

	hash_hex = sign_data.get("hash_hex") or sign_data.get("invoice_hash")
	return {
		"ok": True,
		"phase": "phase1",
		"uuid": inv_uuid,
		"document_type": inv.get("document_type"),
		"qr_base64": qr_b64,
		"qr_image_base64": qr_image_b64,
		"log_name": log_name,
		"invoice_hash": hash_hex,
		"hash_b64": sign_data.get("hash_b64"),
		"signature": sign_data.get("signature_b64") or sign_data.get("signature"),
		"signed_xml": signed_xml,
		"json": inv,
		"archive_paths": paths,
		"icv": icv,
	}
