# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""India GST e-Invoice (IRN) — NIC JSON schema v1.1 shaped payload (GSP/ASP path)."""

from __future__ import annotations

import json
from typing import Any

from frappe.utils import flt


def build_gst_irn_json(document: dict[str, Any]) -> str:
	"""
	Build NIC e-Invoice JSON (simplified mandatory blocks for Phase 1).
	Not Peppol UBL — IRN generation uses this JSON via GSP/ASP.
	"""
	seller = document.get("seller") or {}
	buyer = document.get("buyer") or {}
	totals = document.get("totals") or {}
	lines = document.get("lines") or []
	ref = document.get("reference_name") or ""
	issue_date = (document.get("issue_datetime") or "")[:10]

	item_list = []
	for i, line in enumerate(lines, start=1):
		qty = flt(line.get("qty", 1)) or 1
		rate = flt(line.get("rate", 0))
		amount = flt(line.get("net_amount", line.get("amount", 0))) or qty * rate
		tax = flt(line.get("tax_amount", 0))
		item_list.append(
			{
				"SlNo": str(i),
				"PrdDesc": (line.get("description") or f"Item {i
	}")[:300],
				"IsServc": "N",
				"HsnCd": (line.get("hsn_code") or line.get("item_code") or "998311")[:8],
				"Qty": qty,
				"Unit": "NOS",
				"UnitPrice": rate,
				"TotAmt": amount,
				"AssAmt": amount,
				"GstRt": 18,
				"IgstAmt": tax,
				"TotItemVal": amount + tax
	}
		)

	payload = {
		"Version": "1.1",
		"TranDtls": {
			"TaxSch": "GST",
			"SupTyp": "B2B",
			"RegRev": "N",
			"IgstOnIntra": "N"
	},
		"DocDtls": {
			"Typ": "INV",
			"No": ref[:16],
			"Dt": issue_date
	},
		"SellerDtls": {
			"Gstin": (seller.get("tax_registration") or "")[:15],
			"LglNm": (seller.get("name") or "")[:100],
			"Addr1": (seller.get("address") or "Address")[:100],
			"Loc": (seller.get("city") or "City")[:50],
			"Pin": int(seller.get("pincode") or 110001),
			"Stcd": (seller.get("state_code") or "07")[:2]
	},
		"BuyerDtls": {
			"Gstin": (buyer.get("tax_registration") or "URP")[:15],
			"LglNm": (buyer.get("name") or "Buyer")[:100],
			"Pos": (buyer.get("state_code") or "07")[:2],
			"Addr1": (buyer.get("address") or "Address")[:100],
			"Loc": (buyer.get("city") or "City")[:50],
			"Pin": int(buyer.get("pincode") or 110001),
			"Stcd": (buyer.get("state_code") or "07")[:2]
	},
		"ValDtls": {
			"AssVal": flt(totals.get("net_total", 0)),
			"CgstVal": 0,
			"SgstVal": 0,
			"IgstVal": flt(totals.get("tax_total", 0)),
			"TotInvVal": flt(totals.get("grand_total", 0))},
		"ItemList": item_list,
		"EwbDtls": {
	},
		"_meta": {
			"uuid": document.get("uuid"),
			"currency": document.get("currency") or "INR",
			"framework": "GST-IRN"}
	}
	return json.dumps(payload, ensure_ascii=False, indent=2)
