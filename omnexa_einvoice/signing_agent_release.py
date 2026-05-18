# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""USB signing agent Windows release — download from E-Invoice workspace."""

from __future__ import annotations

import json
import os
from pathlib import Path

import frappe
from frappe import _

ZIP_NAME = "OmnexaESigningAgent-win64.zip"
VERSION_NAME = "signing_agent_version.json"


def _downloads_dir() -> Path:
	return Path(frappe.get_app_path("omnexa_einvoice", "public", "downloads"))


@frappe.whitelist()
def get_signing_agent_release() -> dict:
	"""Info for E-Invoice workspace download page."""
	downloads = _downloads_dir()
	zip_path = downloads / ZIP_NAME
	version_path = downloads / VERSION_NAME
	meta = {}
	if version_path.is_file():
		try:
			meta = json.loads(version_path.read_text(encoding="utf-8"))
		except Exception:
			meta = {}

	available = zip_path.is_file()
	out = {
		"available": available,
		"filename": ZIP_NAME,
		"download_url": f"/assets/omnexa_einvoice/downloads/{ZIP_NAME}" if available else None,
		"size_bytes": zip_path.stat().st_size if available else 0,
		"version": meta.get("version") or "",
		"port": meta.get("port") or 5002,
		"health_url": meta.get("health_url") or "http://127.0.0.1:5002/health",
		"build_path": "omnexa_einvoice/signing_agent/build_signing_agent_exe.bat",
	}
	if not available:
		out["message"] = _(
			"Release ZIP not uploaded yet. Build on Windows with signing_agent/build_signing_agent_exe.bat, then bench build."
		)
	return out
