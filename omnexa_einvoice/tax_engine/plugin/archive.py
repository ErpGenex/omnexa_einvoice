# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Archive plugin artifacts under site private files."""

from __future__ import annotations

import json
import os
from typing import Any

import frappe


def archive_artifacts(
	*,
	country_code: str,
	company: str,
	reference_name: str,
	uuid: str,
	xml_text: str,
	document: dict[str, Any],
	extra: dict | None = None,
) -> dict[str, str]:
	base = frappe.get_site_path(
		"private",
		"files",
		"tax_plugin",
		country_code,
		frappe.scrub(company or "unknown"),
	)
	os.makedirs(base, exist_ok=True)
	prefix = frappe.scrub(reference_name or uuid)[:80]
	xml_path = os.path.join(base, f"{prefix}.xml")
	json_path = os.path.join(base, f"{prefix}.json")
	with open(xml_path, "w", encoding="utf-8") as fh:
		fh.write(xml_text)
	with open(json_path, "w", encoding="utf-8") as fh:
		json.dump({"document": document, "meta": extra or {}
	}, fh, indent=2, default=str)
	return {"xml": xml_path, "json": json_path
	}
