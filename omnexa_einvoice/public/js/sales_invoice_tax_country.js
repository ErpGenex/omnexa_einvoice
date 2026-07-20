// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Non-Egypt branch tax actions (ZATCA + international plugin). Egypt uses sales_invoice_einvoice.js only. */

let PLUGIN_TAX_COUNTRIES = null;
let TAX_COUNTRY_LABELS = {
	SA: __("Saudi ZATCA"),
	AE: __("UAE"),
};

async function load_plugin_tax_countries() {
	if (PLUGIN_TAX_COUNTRIES) {
		return PLUGIN_TAX_COUNTRIES;
	}
	const r = await frappe.call({
		method: "omnexa_einvoice.tax_engine.dispatch.list_supported_countries",
	});
	const codes = new Set();
	for (const row of r.message || []) {
		if (!row.pipeline_enabled) {
			continue;
		}
		const code = (row.country_code || "").toUpperCase();
		if (["EG", "SA", "AE"].includes(code)) {
			continue;
		}
		codes.add(code);
		if (row.label) {
			TAX_COUNTRY_LABELS[code] = row.label;
		}
	}
	PLUGIN_TAX_COUNTRIES = codes;
	return codes;
}

function parse_branch_country_code(raw) {
	const text = String(raw || "EG").trim();
	if (!text) {
		return "EG";
	}
	if (text.includes(" — ")) {
		return text.split(" — ", 1)[0].trim().toUpperCase();
	}
	if (text.includes(" - ") && text.length > 4) {
		return text.split(" - ", 1)[0].trim().toUpperCase();
	}
	return text.toUpperCase();
}

async function get_branch_country_code(branch) {
	if (!branch) {
		return "EG";
	}
	const r = await frappe.db.get_value("Branch", branch, ["country_iso", "country_code"]);
	const msg = r.message || {};
	if (msg.country_iso) {
		return String(msg.country_iso).trim().toUpperCase();
	}
	return parse_branch_country_code(msg.country_code || "EG");
}

frappe.provide("omnexa.einvoice");
omnexa.einvoice.parseBranchCountryCode = parse_branch_country_code;
omnexa.einvoice.getBranchCountryCode = get_branch_country_code;

function run_uae(frm, phase) {
	frappe.call({
		method: "omnexa_einvoice.uae.submission.process_uae_invoice",
		args: {
			reference_name: frm.doc.name,
			company: frm.doc.company,
			phase,
			sync: phase === "phase2" ? 1 : 0,
		},
		freeze: true,
		callback(r) {
			frappe.msgprint({
				title: __("UAE e-Invoice"),
				message: `<pre class="small">${frappe.utils.escape_html(
					JSON.stringify(r.message || r, null, 2)
				)}</pre>`,
				indicator: "green",
			});
		},
	});
}

function run_tax_dispatch(frm, phase) {
	frappe.call({
		method: "omnexa_einvoice.tax_engine.dispatch.dispatch_tax_for_document",
		args: {
			reference_doctype: "Sales Invoice",
			reference_name: frm.doc.name,
			branch: frm.doc.branch,
			phase,
		},
		freeze: true,
		callback(r) {
			frappe.msgprint({
				title: __("Tax submission"),
				message: `<pre class="small">${frappe.utils.escape_html(
					JSON.stringify(r.message || r, null, 2)
				)}</pre>`,
				indicator: "green",
			});
		},
	});
}

function run_zatca(frm, phase) {
	frappe.call({
		method: "omnexa_einvoice.zatca.submission.process_zatca_invoice",
		args: {
			reference_name: frm.doc.name,
			document_type: "tax_invoice",
			phase,
			company: frm.doc.company,
			branch: frm.doc.branch,
		},
		freeze: true,
		callback(r) {
			const data = r.message || r;
			if (phase === "phase1" && omnexa.zatca && omnexa.zatca.show_phase1_result) {
				omnexa.zatca.show_phase1_result(data, __("ZATCA Phase 1 (XML + QR)"));
				return;
			}
			frappe.msgprint({
				title: __("ZATCA"),
				message: `<pre class="small">${frappe.utils.escape_html(JSON.stringify(data, null, 2))}</pre>`,
				indicator: "green",
			});
		},
	});
}

function add_plugin_tax_buttons(frm, country, label) {
	frm.add_custom_button(__("Tax Phase 1"), () => run_tax_dispatch(frm, "phase1"), label);
	frm.add_custom_button(__("Tax Phase 2"), () => run_tax_dispatch(frm, "phase2"), label);
	frm.add_custom_button(__("Tax Console"), () => {
		frappe.set_route("international-tax-console");
	}, label);
	frm.add_custom_button(__("Submission Log"), () => {
		frappe.set_route("List", "Country Tax Submission Log", {
			reference_name: frm.doc.name,
		});
	}, label);
}

async function refresh_tax_country_buttons(frm) {
	if (frm.is_new() || !frm.doc.branch || frm.doc.docstatus === 2) {
		return;
	}
	const country = await get_branch_country_code(frm.doc.branch);
	if (country === "EG") {
		return;
	}
		const label = TAX_COUNTRY_LABELS[country] || country;
		if (country === "SA") {
			frm.add_custom_button(__("Phase 1 (XML + QR)"), () => run_zatca(frm, "phase1"), label);
			frm.add_custom_button(__("Phase 2 (API)"), () => run_zatca(frm, "phase2"), label);
			frm.add_custom_button(__("ZATCA Console"), () => frappe.set_route("zatca-console"), label);
			return;
		}
		if (country === "AE") {
			frm.add_custom_button(__("UAE Phase 1 (PINT UBL)"), () => run_uae(frm, "phase1"), label);
			frm.add_custom_button(__("UAE Phase 2 (ASP)"), () => run_uae(frm, "phase2"), label);
			frm.add_custom_button(__("International Tax Console"), () => {
				frappe.set_route("international-tax-console");
			}, label);
			frm.add_custom_button(__("Submission Log"), () => {
				frappe.set_route("List", "Country Tax Submission Log", { reference_name: frm.doc.name });
			}, label);
			return;
		}
		const pluginCountries = await load_plugin_tax_countries();
		if (!pluginCountries.has(country)) {
			return;
		}
		add_plugin_tax_buttons(frm, country, label);
}

frappe.ui.form.on("Sales Invoice", {
	async refresh(frm) {
		await refresh_tax_country_buttons(frm);
	},
	async branch(frm) {
		await refresh_tax_country_buttons(frm);
	},
});
