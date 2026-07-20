# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Local ZATCA invoice archive (site private files)."""

from __future__ import annotations

import json
import os
from typing import Any

import frappe
from frappe.utils import get_site_path, now_datetime


def archive_phase1_artifacts(
	*,
	company: str,
	reference_name: str,
	invoice_uuid: str,
	xml_text: str,
	json_text: str,
	qr_base64: str,
	meta: dict[str, Any] | None = None,
) -> dict[str, str]:
	"""Write XML/JSON/QR under ``private/files/zatca/{company}/``."""
	base = get_site_path("private", "files", "zatca", frappe.scrub(company))
	os.makedirs(base, exist_ok=True)
	stamp = now_datetime().strftime("%Y%m%d_%H%M%S")
	safe_ref = frappe.scrub(reference_name)[:80]
	prefix = f"{safe_ref}_{invoice_uuid[:8]}_{stamp}"

	paths: dict[str, str] = {}
	for ext, content in (
		("xml", xml_text),
		("json", json_text),
		("qr.txt", qr_base64),
		("meta.json", json.dumps(meta or {}, ensure_ascii=False, indent=2, default=str)),
	):
		fname = f"{prefix}.{ext}"
		full = os.path.join(base, fname)
		with open(full, "w", encoding="utf-8") as fh:
			fh.write(content)
		paths[ext] = full

	return paths
