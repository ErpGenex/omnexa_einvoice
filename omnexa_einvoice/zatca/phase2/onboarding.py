# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA CSR generation and CSID onboarding (aligned with ZATCA_Integration reference flow)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.zatca.phase2.api_client import request_compliance_csid, request_production_csid
from omnexa_einvoice.zatca.phase2.constants import ENVIRONMENT_PORTALS
from omnexa_einvoice.zatca.phase2.credentials import (
	build_certificate_pem_from_token,
	create_public_key_pem,
)
from omnexa_einvoice.zatca.phase2.csr_builder import build_zatca_csr


@frappe.whitelist()
def generate_csr_for_settings(settings_name: str) -> dict[str, Any]:
	"""Generate ZATCA-compliant CSR + private key on settings document."""
	doc = frappe.get_doc("ZATCA Company Settings", settings_name)
	csr_data = build_zatca_csr(doc)
	doc.private_key = csr_data["private_key_pem"]
	doc.csr_pem = csr_data["csr_pem"]
	doc.save(ignore_permissions=True)
	return {"ok": True, "csr_base64": csr_data["csr_base64"]
	}


@frappe.whitelist()
def onboard_compliance_csid(settings_name: str, otp: str) -> dict[str, Any]:
	doc = frappe.get_doc("ZATCA Company Settings", settings_name)
	if not doc.csr_pem and not doc.get_password("private_key", raise_exception=False):
		generate_csr_for_settings(settings_name)
		doc.reload()

	portal = ENVIRONMENT_PORTALS.get(doc.zatca_environment or "sandbox", "developer-portal")
	csr_b64 = doc.csr_pem
	if csr_b64 and "BEGIN" in csr_b64:
		import base64

		csr_b64 = base64.b64encode(csr_b64.encode()).decode("ascii")
	elif not csr_b64:
		csr_b64 = build_zatca_csr(doc)["csr_base64"]

	body = request_compliance_csid(portal, csr_b64, (otp or "").strip())
	token = body.get("binarySecurityToken") or body.get("binary_security_token") or ""
	secret = body.get("secret") or ""
	request_id = str(body.get("requestID") or body.get("request_id") or "")
	if not token or not secret:
		frappe.throw(_("Unexpected compliance CSID response from ZATCA."), title=_("ZATCA"))

	doc.compliance_security_token = token
	doc.compliance_secret = secret
	doc.compliance_request_id = request_id
	if token:
		cert_body = build_certificate_pem_from_token(token)
		doc.certificate_pem = cert_body
		doc.public_key_pem = create_public_key_pem(cert_body)
	doc.save(ignore_permissions=True)
	return {"ok": True, "compliance_request_id": request_id
	}


@frappe.whitelist()
def onboard_production_csid(settings_name: str) -> dict[str, Any]:
	doc = frappe.get_doc("ZATCA Company Settings", settings_name)
	if not doc.compliance_request_id:
		frappe.throw(_("Run compliance CSID onboarding first."), title=_("ZATCA"))
	portal = ENVIRONMENT_PORTALS.get(doc.zatca_environment or "sandbox", "developer-portal")
	token = doc.get_password("compliance_security_token")
	secret = doc.get_password("compliance_secret")
	body = request_production_csid(portal, doc.compliance_request_id, token, secret)
	ptoken = body.get("binarySecurityToken") or body.get("binary_security_token") or ""
	psecret = body.get("secret") or ""
	if not ptoken or not psecret:
		frappe.throw(_("Unexpected production CSID response from ZATCA."), title=_("ZATCA"))

	doc.production_security_token = ptoken
	doc.production_secret = psecret
	if ptoken:
		cert_body = build_certificate_pem_from_token(ptoken)
		doc.certificate_pem = cert_body
		doc.public_key_pem = create_public_key_pem(cert_body)
	doc.zatca_phase = "Phase 2"
	doc.save(ignore_permissions=True)
	return {"ok": True, "disposition": body.get("dispositionMessage")
	}
