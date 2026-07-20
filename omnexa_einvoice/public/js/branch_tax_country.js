// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Branch tax country: name beside code + labeled select options. */

const TAX_COUNTRY_LABELS = {
	EG: __("Egypt ETA"),
	SA: __("Saudi ZATCA"),
};

function parse_country_code(raw) {
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

function apply_country_select_options(frm, rows) {
	const options = (rows || []).map((row) => row.label).join("\n");
	if (options) {
		frm.set_df_property("country_code", "options", options);
	}
}

function sync_country_name(frm, code, name) {
	if (frm.fields_dict.country_name) {
		frm.set_value("country_name", name || code);
	}
}

async function load_country_select_options(frm) {
	const r = await frappe.call({
		method: "omnexa_einvoice.tax_engine.branch_country_tax.get_branch_country_select_options",
	});
	const rows = r.message || [];
	apply_country_select_options(frm, rows);
	return rows;
}

function hide_eta_form_sections(frm, code) {
	const is_eg = code === "EG";
	const etaFields = [
		"tab_break_eta",
		"eta_setup_help",
		"eta_ereceipt_enabled",
		"eta_einvoice_enabled",
	];
	for (const fieldname of etaFields) {
		if (frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", is_eg ? 0 : 1);
		}
	}
}

function apply_intl_live_production_gate(frm, panel) {
	const fieldname = "intl_tax_live_production";
	if (!frm.fields_dict[fieldname]) {
		return;
	}
	const code = parse_country_code(frm.doc.country_code);
	if (code === "EG" || code === "SA") {
		return;
	}
	const ready = panel && panel.production_ready;
	const tier = (panel && panel.integration_tier) || "scaffold";
	if (ready) {
		frm.set_df_property(fieldname, "read_only", 0);
		frm.set_df_property(
			fieldname,
			"description",
			__("Enable only after ASP/government UAT is complete.")
		);
		return;
	}
	if (frm.doc[fieldname]) {
		frm.set_value(fieldname, 0);
	}
	frm.set_df_property(fieldname, "read_only", 1);
	frm.set_df_property(
		fieldname,
		"description",
		__(
			"Not available for {0} yet (tier: {1}). Sandbox/test only until certified.",
			[code, tier]
		)
	);
}

function sync_country_iso_field(frm, code) {
	if (!frm.fields_dict.country_iso || !code) {
		return;
	}
	if (frm.doc.country_iso !== code) {
		frm.set_value("country_iso", code);
	}
}

async function refresh_branch_country_display(frm) {
	const rows = await load_country_select_options(frm);
	const code = parse_country_code(frm.doc.country_code);
	sync_country_iso_field(frm, code);
	if (omnexa.einvoice && omnexa.einvoice.purgeForeignTaxToolbarGroups) {
		omnexa.einvoice.purgeForeignTaxToolbarGroups(frm);
	}
	hide_eta_form_sections(frm, code);
	const row = rows.find((r) => r.code === code);
	sync_country_name(frm, code, row ? row.name : "");

	frappe.call({
		method: "omnexa_einvoice.tax_engine.branch_country_tax.resolve_tax_provider",
		args: { country_code: code },
		callback(res) {
			const msg = res.message || {};
			if (msg.provider) {
				frm.set_value("tax_provider", msg.provider);
			}
			if (msg.country_name) {
				sync_country_name(frm, code, msg.country_name);
			}
		},
	});

	if (code !== "EG") {
		frappe.call({
			method: "omnexa_einvoice.tax_engine.branch_country_tax.get_branch_tax_panel",
			args: {
				company: frm.doc.company,
				country_code: code,
				branch: frm.doc.name,
			},
			callback(res) {
				const data = res.message || {};
				const label = data.tab_label || data.label || TAX_COUNTRY_LABELS[code] || code;
				frm.dashboard.add_indicator(`${code} — ${label}`, "blue");
				if (data.integration_tier && data.integration_tier !== "production") {
					frm.dashboard.add_indicator(
						`${code}: ${data.integration_tier}`,
						data.integration_tier === "sandbox" ? "orange" : "yellow"
					);
				}
				apply_intl_live_production_gate(frm, data);
			},
		});
		if (frm.doc.eta_einvoice_enabled || frm.doc.eta_ereceipt_enabled) {
			frappe.show_alert({
				message: __("Egypt ETA applies only to branches with Country EG."),
				indicator: "orange",
			});
		}
	}
}

frappe.ui.form.on("Branch", {
	async onload(frm) {
		await refresh_branch_country_display(frm);
	},
	async refresh(frm) {
		await refresh_branch_country_display(frm);
	},
	async country_code(frm) {
		await refresh_branch_country_display(frm);
	},
	async country_iso(frm) {
		await refresh_branch_country_display(frm);
	},
});
