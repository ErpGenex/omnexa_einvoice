# i18n:managed-catalog — bilingual/regional catalog; UI via ar.csv
# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Runtime smoke checks for all international tax countries (run after deploy)."""

from __future__ import annotations

from typing import Any

import frappe

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.country_catalog import (
	PLUGIN_CATALOG,
	PLUGIN_COUNTRY_CODES,
	integration_tier_for_country,
	xml_markers_for_country,
)
from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2

SMOKE_PAYLOAD = {
	"company": "Test",
	"seller_name": "Smoke Seller",
	"tax_registration_number": "100000000000003",
	"buyer": {"name": "Smoke Buyer", "tax_registration": "200000000000004"
	},
	"lines": [{"description": "Item", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 5
	}],
	"totals": {"net_total": 100, "tax_total": 5, "grand_total": 105}
	}


def _run_smoke_internal(*, full: bool = True) -> dict[str, Any]:
	frappe.flags.in_test = True
	codes = sorted(PLUGIN_COUNTRY_CODES) if full else _smoke_sample_codes()
	results: dict[str, Any] = {"countries": {
	}, "ok": True, "tested": len(codes)
	}
	for code in codes:
		entry: dict[str, Any] = {"phase1": None, "phase2": None, "ok": False
	}
		try:
			p1 = run_country_phase1(
				{**SMOKE_PAYLOAD, "reference_name": f"SMOKE-{code}-P1"
	},
				country_code=code,
			)
			xml = p1.get("signed_xml") or ""
			markers = xml_markers_for_country(code)
			missing = [m for m in markers if m not in xml]
			if missing:
				raise ValueError(f"XML missing markers: {missing}")
			p2 = run_country_phase2(
				{**SMOKE_PAYLOAD, "reference_name": f"SMOKE-{code}-P2"
	},
				country_code=code,
				sync=True,
			)
			entry["phase1"] = {"framework": p1.get("framework"), "uuid": p1.get("uuid")
	}
			entry["phase2"] = {"status": p2.get("status"), "mock": (p2.get("api") or {}).get("mock")
	}
			entry["ok"] = True
		except Exception as exc:
			entry["error"] = str(exc)[:500]
			results["ok"] = False
		results["countries"][code] = entry
	return results


def _smoke_sample_codes() -> list[str]:
	"""One country per engine type for fast CI."""
	return ["MX", "BR", "IN", "IT", "PL", "CO", "DE", "ES", "FR", "AE", "JO"]


@frappe.whitelist()
def run_smoke_tests(full: int | bool = True) -> dict[str, Any]:
	"""Desk API: verify Phase 1+2 (full=all plugin countries)."""
	frappe.only_for(("System Manager", "Administrator"))
	return _run_smoke_internal(full=bool(full))


def run_smoke_for_bench() -> None:
	"""bench --site SITE execute omnexa_einvoice.tax_engine.deploy_check.run_smoke_for_bench"""
	out = _run_smoke_internal(full=True)
	if not out.get("ok"):
		frappe.throw(frappe.as_json(out, indent=2))
	print(frappe.as_json(out, indent=2))


def run_smoke_sample_for_bench() -> None:
	"""Fast smoke — one country per engine family."""
	out = _run_smoke_internal(full=False)
	if not out.get("ok"):
		frappe.throw(frappe.as_json(out, indent=2))
	print(frappe.as_json(out, indent=2))


def list_country_status() -> list[dict[str, Any]]:
	rows = []
	for entry in PLUGIN_CATALOG:
		meta = COUNTRY_REGISTRY.get(entry.code)
		rows.append(
			{
				"country_code": entry.code,
				"label": entry.label,
				"label_ar": entry.label_ar,
				"adapter": meta.adapter_name if meta else "",
				"framework": entry.framework,
				"currency": entry.currency,
				"integration_tier": (meta.integration_tier if meta else integration_tier_for_country(entry.code)),
				"pipeline_enabled": bool(meta and meta.pipeline_enabled),
				"production_ready": bool(meta and meta.production_ready)
	}
		)
	for code in ("EG", "SA"):
		meta = COUNTRY_REGISTRY[code]
		rows.append(
			{
				"country_code": code,
				"label": meta.label,
				"label_ar": "مصر" if code == "EG" else "السعودية",
				"adapter": meta.adapter_name,
				"framework": "ETA" if code == "EG" else "ZATCA",
				"currency": "EGP" if code == "EG" else "SAR",
				"integration_tier": "production",
				"pipeline_enabled": True,
				"production_ready": True
	}
		)
	return sorted(rows, key=lambda r: r["country_code"])
