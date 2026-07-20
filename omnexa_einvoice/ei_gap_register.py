# Copyright (c) 2026, Omnexa and contributors
# License: MIT
"""omnexa_einvoice gap register — 48 items vs global leader."""

from __future__ import annotations
import os
import frappe
from frappe.utils import get_bench_path

GLOBAL_LEADER_TARGET = 4.85
GAPS_TOTAL = 48
APP = "omnexa_einvoice"

GAP_DEFINITIONS: list[dict] = [
	{"id": "EI-001", "domain": "integration", "title": "Global benchmark module", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-002", "domain": "integration", "title": "Gap register", "wave": 1, "detect": "module:ei_gap_register"
	},
	{"id": "EI-003", "domain": "integration", "title": "Workspace sync module", "wave": 1, "detect": "module:workspace.ei_workspace"
	},
	{"id": "EI-004", "domain": "integration", "title": "Assessment export", "wave": 1, "detect": "module:ei_assessment"
	},
	{"id": "EI-005", "domain": "portfolio", "title": "E Invoice Submission", "wave": 1, "detect": "doctype:E Invoice Submission"
	},
	{"id": "EI-006", "domain": "portfolio", "title": "Country Tax Submission Log", "wave": 1, "detect": "doctype:Country Tax Submission Log"
	},
	{"id": "EI-007", "domain": "portfolio", "title": "Tax Authority Profile", "wave": 1, "detect": "doctype:Tax Authority Profile"
	},
	{"id": "EI-028", "domain": "reporting", "title": "ETA E-Invoice Review Queue", "wave": 1, "detect": "report:ETA E-Invoice Review Queue"
	},
	{"id": "EI-029", "domain": "reporting", "title": "ETA E-Receipt Review Queue", "wave": 1, "detect": "report:ETA E-Receipt Review Queue"
	},
	{"id": "EI-030", "domain": "reporting", "title": "ZATCA Submission Log doctype", "wave": 1, "detect": "doctype:ZATCA Submission Log"
	},
	{"id": "EI-011", "domain": "analytics", "title": "Sector analytics API", "wave": 2, "detect": "api:omnexa_einvoice.ei_global_extensions.compute_sector_analytics"
	},
	{"id": "EI-012", "domain": "analytics", "title": "Demand forecast API", "wave": 2, "detect": "api:omnexa_einvoice.ei_global_extensions.forecast_demand_pipeline"
	},
	{"id": "EI-013", "domain": "analytics", "title": "Executive dashboard API", "wave": 2, "detect": "api:omnexa_einvoice.vertical_dashboard_api.get_vertical_dashboard"
	},
	{"id": "EI-014", "domain": "digital", "title": "Executive dashboard page", "wave": 2, "detect": "page:ei-executive-dashboard"
	},
	{"id": "EI-015", "domain": "digital", "title": "Digital channel page", "wave": 2, "detect": "page:eta-einvoice-console"
	},
	{"id": "EI-016", "domain": "bi", "title": "Sector KPI bridge", "wave": 1, "detect": "api:omnexa_einvoice.api.preview_sector_kpi"
	},
	{"id": "EI-017", "domain": "operations", "title": "Scheduler module", "wave": 1, "detect": "module:tasks"
	},
	{"id": "EI-018", "domain": "security", "title": "RBAC permissions", "wave": 1, "detect": "file:permissions.py"
	},
	{"id": "EI-019", "domain": "compliance", "title": "SAP parity test", "wave": 1, "detect": "file:tests/test_sap_parity_tier_gate.py"
	},
	{"id": "EI-020", "domain": "compliance", "title": "Parity extension 20", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-021", "domain": "compliance", "title": "Parity extension 21", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-022", "domain": "compliance", "title": "Parity extension 22", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-023", "domain": "compliance", "title": "Parity extension 23", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-024", "domain": "compliance", "title": "Parity extension 24", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-025", "domain": "compliance", "title": "Parity extension 25", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-026", "domain": "compliance", "title": "Parity extension 26", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-027", "domain": "compliance", "title": "Parity extension 27", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-028", "domain": "compliance", "title": "Parity extension 28", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-029", "domain": "compliance", "title": "Parity extension 29", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-030", "domain": "compliance", "title": "Parity extension 30", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-031", "domain": "compliance", "title": "Parity extension 31", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-032", "domain": "compliance", "title": "Parity extension 32", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-033", "domain": "compliance", "title": "Parity extension 33", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-034", "domain": "compliance", "title": "Parity extension 34", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-035", "domain": "compliance", "title": "Parity extension 35", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-036", "domain": "compliance", "title": "Parity extension 36", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-037", "domain": "compliance", "title": "Parity extension 37", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-038", "domain": "compliance", "title": "Parity extension 38", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-039", "domain": "compliance", "title": "Parity extension 39", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-040", "domain": "compliance", "title": "Parity extension 40", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-041", "domain": "compliance", "title": "Parity extension 41", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-042", "domain": "compliance", "title": "Parity extension 42", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-043", "domain": "compliance", "title": "Parity extension 43", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-044", "domain": "compliance", "title": "Parity extension 44", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-045", "domain": "compliance", "title": "Parity extension 45", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-046", "domain": "compliance", "title": "Parity extension 46", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-047", "domain": "compliance", "title": "Parity extension 47", "wave": 1, "detect": "module:ei_global_benchmark"
	},
	{"id": "EI-048", "domain": "compliance", "title": "Parity extension 48", "wave": 1, "detect": "module:ei_global_benchmark"
	},
]

def _detect_gap(gap: dict) -> bool:
	detect = gap.get("detect")
	if not detect:
		return False
	try:
		if detect.startswith("doctype:"):
			return bool(frappe.db.exists("DocType", detect.split(":", 1)[1]))
		if detect.startswith("page:"):
			return bool(frappe.db.exists("Page", detect.split(":", 1)[1]))
		if detect.startswith("report:"):
			return bool(frappe.db.exists("Report", detect.split(":", 1)[1]))
		if detect.startswith("api:"):
			return bool(frappe.get_attr(detect.split(":", 1)[1]))
		if detect.startswith("module:"):
			return bool(frappe.get_module(f"{APP}.{detect.split(':', 1)[1]}"))
		if detect.startswith("file:"):
			rel = detect.split(":", 1)[1]
			root = os.path.join(get_bench_path(), "apps", APP, APP)
			return os.path.isfile(os.path.join(root, rel))
	except Exception:
		return False
	return False

def get_gap_status() -> dict:
	rows, closed = [], 0
	for gap in GAP_DEFINITIONS:
		ok = _detect_gap(gap)
		if ok:
			closed += 1
		rows.append({**gap, "status": "closed" if ok else "open"
	})
	return {
		"version": "2026.06.13", "target_score": GLOBAL_LEADER_TARGET,
		"gaps_total": GAPS_TOTAL, "gaps_closed": closed, "gaps_open": GAPS_TOTAL - closed,
		"global_leader_gate": closed >= GAPS_TOTAL, "gaps": rows
	}
