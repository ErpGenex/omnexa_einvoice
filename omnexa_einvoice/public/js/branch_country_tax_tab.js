// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Branch tax tabs — tab title = selected country (e.g. Germany e-Invoicing). */

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

function apply_tab_label(frm, fieldname, label) {
	if (!fieldname || !label) {
		return;
	}
	const text = __(label);
	frm.set_df_property(fieldname, "label", text);
	if (frm.meta.docfield_map && frm.meta.docfield_map[fieldname]) {
		frm.meta.docfield_map[fieldname].label = text;
	}
	const tabs = frm.layout && frm.layout.tabs ? frm.layout.tabs : [];
	for (const tab of tabs) {
		if (tab.df && tab.df.fieldname === fieldname) {
			if (typeof tab.set_label === "function") {
				tab.set_label(text);
			} else if (tab.label) {
				tab.label = text;
			}
			if (tab.$link && tab.$link.length) {
				tab.$link.text(text);
			}
		}
	}
	frm.$wrapper
		.find(
			`.nav-link[data-fieldname="${fieldname}"], a[data-fieldname="${fieldname}"], .form-tabs-list [data-fieldname="${fieldname}"]`
		)
		.text(text);
}

async function refresh_branch_tax_tab_labels(frm) {
	const code = parse_branch_country_code(frm.doc.country_code);
	if (code === "EG") {
		return;
	}

	let tabLabel = code;
	try {
		const r = await frappe.call({
			method: "omnexa_einvoice.tax_engine.branch_country_tax.get_branch_tab_labels_for_doc",
			args: { country_code: code },
		});
		const labels = r.message || {};
		tabLabel = labels.tab_break_country_tax || labels.tab_break_zatca || code;
	} catch (e) {
		// fallback: single label lookup
		const r2 = await frappe.call({
			method: "omnexa_einvoice.tax_engine.branch_country_tax.get_branch_country_tab_label",
			args: { country_code: code },
		});
		tabLabel = r2.message || code;
	}

	if (code === "SA" && frm.fields_dict.tab_break_zatca) {
		apply_tab_label(frm, "tab_break_zatca", tabLabel);
		if (!frm.is_new() && frm.doc.zatca_enabled) {
			frm.dashboard.add_indicator(__("ZATCA enabled on branch"), "green");
		}
		return;
	}

	if (frm.fields_dict.tab_break_country_tax) {
		apply_tab_label(frm, "tab_break_country_tax", tabLabel);
		if (!frm.is_new() && frm.doc.intl_tax_enabled) {
			frm.dashboard.add_indicator(__("{0} e-invoice enabled", [code]), "green");
		}
	}
}

frappe.ui.form.on("Branch", {
	async onload(frm) {
		await refresh_branch_tax_tab_labels(frm);
	},
	async refresh(frm) {
		await refresh_branch_tax_tab_labels(frm);
	},
	async country_code(frm) {
		await refresh_branch_tax_tab_labels(frm);
	},
	intl_tax_enabled(frm) {
		refresh_branch_tax_tab_labels(frm);
	},
	zatca_enabled(frm) {
		refresh_branch_tax_tab_labels(frm);
	},
});
